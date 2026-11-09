#!/usr/bin/env python3
"""Validate original-speed, same-CFR integer-frame interview timelines; no media edits."""
from __future__ import annotations
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(obj, key, label, minimum=0):
    value = obj.get(key)
    require(type(value) is int and value >= minimum, f'{label}.{key}: integer >= {minimum} required')
    return value


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'{label}: non-empty text required')
    return value


def records(data, key):
    value = data.get(key)
    require(isinstance(value, list), f'{key}: array required')
    require(all(isinstance(x, dict) for x in value), f'{key}: objects required')
    ids = [nonempty(x.get('id'), f'{key}.id') for x in value]
    require(len(set(ids)) == len(ids), f'{key}: duplicate IDs')
    return value, {x['id']: x for x in value}


def fps(value, label):
    require(isinstance(value, dict), f'{label}: numerator/denominator object required')
    return Fraction(integer(value, 'num', label, 1), integer(value, 'den', label, 1))


def window(item, label, total):
    start = integer(item, 'start_frame', label)
    end = integer(item, 'end_frame', label, 1)
    require(start < end <= total, f'{label}: positive half-open window within frame_count required')
    return start, end


def source_ranges(start, end, edl):
    """Project an output half-open frame interval into its exact ordered EDL instances."""
    result = []
    for clip in edl:
        output_start = clip['output_start']
        output_end = output_start + clip['out_frame'] - clip['in_frame']
        a, b = max(start, output_start), min(end, output_end)
        if a < b:
            result.append({'edl_id': clip['id'], 'source_id': clip['source_id'],
                'in_frame': clip['in_frame'] + a - output_start,
                'out_frame': clip['in_frame'] + b - output_start})
    return result


def check_ranges(actual, expected, label):
    require(isinstance(actual, list) and all(isinstance(x, dict) for x in actual),
        label + ': source_ranges array required')
    for item in actual:
        for key in ('in_frame', 'out_frame'):
            integer(item, key, label + '.source_ranges')
    require(actual == expected, label + ': stale source_ranges')


def map_source_frame(data, edl_id, source_frame):
    matches = [x for x in data['edl'] if x['id'] == edl_id]
    require(len(matches) == 1, f'unknown or duplicate EDL instance: {edl_id}')
    clip = matches[0]
    require(clip['in_frame'] <= source_frame < clip['out_frame'],
        'source frame is outside this retained half-open EDL instance; no snapping across removed speech')
    output = clip['output_start'] + source_frame - clip['in_frame']
    rate = fps(data['fps'], 'fps')
    return {'edl_id': edl_id, 'source_id': clip['source_id'], 'source_frame': source_frame,
        'output_frame': output, 'output_seconds': str(Fraction(output, 1) / rate)}


def validate(data, base=Path('.'), check_files=False, require_lock=False):
    require(isinstance(data, dict), 'timeline must be an object')
    require(data.get('schema_version') == '1.0', 'unsupported schema_version')
    rate = fps(data.get('fps'), 'fps')
    total = integer(data, 'frame_count', 'timeline', 1)
    sources, source_by_id = records(data, 'sources')
    require(bool(sources), 'sources cannot be empty')
    for s in sources:
        integer(s, 'frame_count', s['id'], 1)
        require(fps(s.get('fps'), s['id'] + '.fps') == rate,
            f'{s["id"]}: mixed frame rates need an explicit resampling/time-base workflow')
        source_path = Path(nonempty(s.get('path'), s['id'] + '.path'))
        if check_files:
            require((base / source_path).is_file(), f'{s["id"]}: source file missing: {source_path}')
    participants, participant_by_id = records(data, 'participants')
    require(bool(participants), 'participants cannot be empty')
    for p in participants:
        nonempty(p.get('display_name'), p['id'] + '.display_name')
        nonempty(p.get('bio'), p['id'] + '.bio')
        nonempty(p.get('confirmation_source'), p['id'] + '.confirmation_source')
    edl, edl_by_id = records(data, 'edl')
    require(bool(edl), 'edl cannot be empty')
    cursor = 0
    for clip in edl:
        label = clip['id']
        require(clip.get('source_id') in source_by_id, label + ': unknown source')
        a, b = integer(clip, 'in_frame', label), integer(clip, 'out_frame', label, 1)
        require(a < b <= source_by_id[clip['source_id']]['frame_count'], label + ': invalid source bounds')
        require(clip.get('speed') == 1 and not isinstance(clip.get('speed'), bool),
            label + ': this helper supports original speed only')
        require(integer(clip, 'output_start', label) == cursor,
            label + ': output gap, overlap or unsorted EDL')
        cursor += b - a
    require(cursor == total, f'EDL covers {cursor} frames, expected {total}')
    audio = data.get('audio')
    require(isinstance(audio, dict), 'audio object required')
    sample_rate = integer(audio, 'sample_rate', 'audio', 1)
    sample_count = integer(audio, 'sample_count', 'audio', 1)
    require(abs(Fraction(sample_count, 1) - Fraction(total * sample_rate, 1) / rate) <= 1,
        'audio sample_count does not match output duration within one sample')
    audio_path = Path(nonempty(audio.get('path'), 'audio.path'))
    if check_files:
        require((base / audio_path).is_file(), f'audio file missing: {audio_path}')
    if require_lock:
        require(audio.get('status') == 'locked', 'production audio must be explicitly locked')
        require(not data.get('example_only'), 'example_only timeline cannot be treated as production')
    captions, caption_by_id = records(data, 'captions')
    require(bool(captions), 'captions cannot be empty')
    previous_end = 0
    emphasis_count = 0
    warnings = []
    for c in captions:
        label = c['id']
        start, end = window(c, label, total)
        require(start >= previous_end, label + ': captions overlap or are unsorted')
        previous_end = end
        require(c.get('speaker_id') in participant_by_id, label + ': unknown participant')
        nonempty(c.get('text'), label + '.text')
        check_ranges(c.get('source_ranges'), source_ranges(start, end, edl), label)
        words = c.get('words')
        require(isinstance(words, list) and bool(words) and all(isinstance(w, dict) for w in words),
            label + ': non-empty words array required')
        word_end = start
        for index, word in enumerate(words):
            wl = f'{label}.words[{index}]'
            a, b = window(word, wl, total)
            require(start <= a < b <= end and a >= word_end, wl + ': outside caption, overlapping or unsorted')
            word_end = b
            nonempty(word.get('text'), wl + '.text')
            mapped = source_ranges(a, b, edl)
            check_ranges(word.get('source_ranges'), mapped, wl)
            if len(mapped) > 1:
                warnings.append(wl + ': token crosses an edit; review actual syllable and action continuity')
        require(''.join(w['text'] for w in words) == c['text'], label + ': words must reconstruct complete caption text')
        e = c.get('emphasis')
        if e is None:
            continue
        require(isinstance(e, dict), label + ': emphasis object required')
        indices = e.get('word_indices')
        require(isinstance(indices, list) and bool(indices) and
            all(type(i) is int and 0 <= i < len(words) for i in indices), label + ': invalid emphasis word_indices')
        require(indices == list(range(indices[0], indices[-1] + 1)), label + ': emphasized words must be contiguous')
        require(e.get('text') == ''.join(words[i]['text'] for i in indices), label + ': emphasis text differs from real word tokens')
        anchor = integer(e, 'anchor_frame', label + '.emphasis')
        duration = integer(e, 'duration_frames', label + '.emphasis', 1)
        require(words[indices[0]]['start_frame'] <= anchor < words[indices[0]]['end_frame'],
            label + ': emphasis anchor outside spoken first keyword')
        require(anchor + duration < end, label + ': emphasis needs completed hold before caption exit')
        require(type(e.get('scale')) in (int, float) and math.isfinite(e['scale']) and e['scale'] > 1,
            label + ': finite scale must exceed one')
        emphasis_count += 1
    events, _ = records(data, 'visual_events')
    groups = {}
    for event in events:
        label = event['id']
        a, b = window(event, label, total)
        nonempty(event.get('kind'), label + '.kind')
        refs = event.get('source_caption_ids')
        require(isinstance(refs, list) and all(x in caption_by_id for x in refs), label + ': unknown source captions')
        semantic = event.get('semantic')
        require(isinstance(semantic, dict), label + ': semantic lifecycle object required')
        for phase in ('enter', 'hold', 'change', 'exit'):
            nonempty(semantic.get(phase), label + '.semantic.' + phase)
        group = event.get('exclusive_group')
        if event['kind'] in ('identity', 'header', 'summary', 'teaser'):
            require(group in (None, 'primary_information'),
                label + ': core information layers must share primary_information exclusion group')
            group = 'primary_information'
        if group is not None:
            nonempty(group, label + '.exclusive_group')
            groups.setdefault(group, []).append((a, b, label))
    for group, items in groups.items():
        ordered = sorted(items)
        for before, after in zip(ordered, ordered[1:]):
            require(after[0] >= before[1], f'{group}: mutually exclusive {before[2]} and {after[2]} overlap')
    if data.get('example_only'):
        warnings.append('Synthetic schema example only: no original speech, identity or media has been verified')
    if not check_files:
        warnings.append('Metadata checked only; source/audio files were not opened or verified')
    return {'ok': True, 'scope': 'structural metadata and optional file existence only; media content not inspected',
        'file_existence_checked': check_files, 'frames': total, 'duration_seconds': str(Fraction(total, 1) / rate),
        'edl_instances': len(edl), 'captions': len(captions), 'emphasis': emphasis_count,
        'visual_events': len(events), 'warnings': warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('validate')
    check.add_argument('timeline', type=Path)
    check.add_argument('--check-files', action='store_true')
    check.add_argument('--require-lock', action='store_true')
    mapping = commands.add_parser('map')
    mapping.add_argument('timeline', type=Path)
    mapping.add_argument('--edl-id', required=True)
    mapping.add_argument('--source-frame', type=int, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.timeline.read_text())
        report = validate(data, args.timeline.parent, getattr(args, 'check_files', False), getattr(args, 'require_lock', False))
        if args.command == 'map':
            report = map_source_frame(data, args.edl_id, args.source_frame)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
