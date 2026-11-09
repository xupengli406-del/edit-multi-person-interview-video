#!/usr/bin/env python3
"""Draw measured natural-proportion type and real PNG logos on prepared cover art.

Project JSON supplies all asset paths, copy, geometry and actual keepouts. This
helper does not generate/edit people or rearrange the underlying artwork.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math

from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def rect(value, name):
    if len(value) != 4:
        raise ValueError(f"{name} must be [x,y,width,height]")
    r = [number(v, name) for v in value]
    if r[2] <= 0 or r[3] <= 0:
        raise ValueError(f"{name} must have positive dimensions")
    return r


def inside(a, b):
    x, y, w, h = a
    bx, by, bw, bh = b
    return bx <= x and by <= y and x + w <= bx + bw and y + h <= by + bh


def intersects(a, b):
    x, y, w, h = a
    bx, by, bw, bh = b
    return x < bx + bw and bx < x + w and y < by + bh and by < y + h


def load_font(path, size, weight):
    f = ImageFont.truetype(str(path), round(number(size, "font size", 1)))
    try:
        axes = f.get_variation_axes()
    except OSError:
        return f
    values = [a["default"] for a in axes]
    for i, axis in enumerate(axes):
        name = axis["name"].decode() if isinstance(axis["name"], bytes) else axis["name"]
        if name.lower() == "weight":
            if not axis["minimum"] <= weight <= axis["maximum"]:
                raise ValueError("Requested font weight outside available axis")
            values[i] = weight
    f.set_variation_by_axes(values)
    return f


def draw_text(layer, label, spec, font_path, weight):
    for key in ("scale_x", "scale_y"):
        if number(spec.get(key, 1), key) != 1:
            raise ValueError("Text must retain natural proportions; recompose instead of stretching")
    text = spec.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{label} needs nonempty project copy")
    lines = text.split("\n")
    if any(not line.strip() for line in lines):
        raise ValueError("Empty lines are not layout spacing")
    f = load_font(font_path, spec["size"], weight)
    outline = round(number(spec.get("outline", 0), "outline", 0))
    sx, sy = spec.get("shadow", [0, 0])
    sx, sy = round(number(sx, "shadow x")), round(number(sy, "shadow y"))
    cx = number(spec["center_x"], "center_x")
    baseline = number(spec["baseline"], "baseline")
    step = number(spec.get("line_height", spec["size"] * 1.25), "line_height", 1)
    records, runs = [], []
    for i, line in enumerate(lines):
        box = f.getbbox(line, anchor="ls", stroke_width=outline)
        left, top = min(box[0], box[0] + sx), min(box[1], box[1] + sy)
        right, bottom = max(box[2], box[2] + sx), max(box[3], box[3] + sy)
        pad = 4
        glyph = Image.new("RGBA", (right - left + 2 * pad, bottom - top + 2 * pad))
        d = ImageDraw.Draw(glyph)
        pen = (pad - left, pad - top)
        if sx or sy:
            d.text((pen[0] + sx, pen[1] + sy), line, font=f, anchor="ls",
                   fill="#080808", stroke_width=outline, stroke_fill="#080808")
        d.text(pen, line, font=f, anchor="ls", fill=spec.get("color", "#FFFFFF"),
               stroke_width=outline, stroke_fill=spec.get("outline_color", "#080808"))
        ink_box = glyph.getbbox()
        if ink_box is None:
            raise ValueError("Font produced no visible glyphs")
        ink = glyph.crop(ink_box)
        x = round(cx - ink.width / 2)
        y = round(baseline + i * step + top - pad + ink_box[1])
        bounds = [x, y, ink.width, ink.height]
        if not inside(bounds, [0, 0, *layer.size]):
            raise ValueError(f"{label} exceeds canvas; change copy or natural layout")
        layer.alpha_composite(ink, (x, y))
        runs.append({"text": line, "flow": f"{label}-{i}", "line": i, "rect": bounds})
        records.append({"text": line, "font_size": spec["size"], "scale_x": 1.0,
                        "scale_y": 1.0, "stroke_width": outline,
                        "shadow_offset": [sx, sy], "rect": bounds})
    return {"id": label, "text": "".join(lines), "atomic": spec.get("atomic", []), "runs": runs}, records


def render(config_path, output, measure_path, overlay_path=None):
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    home = config_path.resolve().parent
    w, h = cfg["canvas"]
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (w, h)):
        raise ValueError("canvas requires positive integer width and height")
    safe = rect(cfg.get("safe_rect", [0, 0, w, h]), "safe_rect")
    if not inside(safe, [0, 0, w, h]):
        raise ValueError("safe_rect exceeds canvas")
    art_path = home / cfg["art"]
    font_path = home / cfg["font"]["path"]
    weight = number(cfg["font"].get("weight", 900), "font weight", 1)
    if not art_path.is_file() or not font_path.is_file():
        raise ValueError("Prepared project art and real font must exist")
    art = Image.open(art_path).convert("RGBA")
    if art.width * h != art.height * w:
        raise ValueError("Prepare native target-ratio artwork; helper never stretches or hard-crops art")
    if art.size != (w, h):
        art = art.resize((w, h), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (w, h))
    blocks, measurements = [], []
    for label in ("main", "subtitle"):
        if label == "subtitle" and not cfg.get(label, {}).get("text", "").strip():
            continue
        block, records = draw_text(layer, label, cfg[label], font_path, weight)
        blocks.append(block)
        measurements.extend(records)
    regions = [(b["id"], r["rect"]) for b in blocks for r in b["runs"]]
    logos = cfg.get("logos", [])
    ids = [v["id"] for v in logos]
    if len(ids) != len(set(ids)):
        raise ValueError("Logo identifiers must be unique")
    logo_records = []
    if logos:
        group = cfg["logo_group"]
        for key in ("scale_x", "scale_y"):
            if number(group.get(key, 1), key) != 1:
                raise ValueError("Logo geometry must retain original aspect")
        tile = round(number(group["tile_size"], "tile_size", 1))
        gap = number(group.get("gap", 0), "gap", 0)
        row_gap = number(group.get("row_gap", 0), "row_gap", 0)
        rows = group.get("rows", 1)
        if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= len(logos):
            raise ValueError("Logo rows must be between one and logo count")
        padding = round(number(group.get("padding", tile * .1), "padding", 0))
        if 2 * padding >= tile:
            raise ValueError("Logo tile has no content space")
        total_h = rows * tile + (rows - 1) * row_gap
        # Contiguous rows preserve the supplied semantic logo order.
        each, remainder = divmod(len(logos), rows)
        groups, start = [], 0
        for ri in range(rows):
            count = each + (ri < remainder)
            groups.append(logos[start:start + count]); start += count
        for ri, row in enumerate(groups):
            row_w = len(row) * tile + (len(row) - 1) * gap
            x0 = group["center_x"] - row_w / 2
            y = round(group["center_y"] - total_h / 2 + ri * (tile + row_gap))
            for ci, logo in enumerate(row):
                path = home / logo["path"]
                if not path.is_file() or path.suffix.lower() != ".png":
                    raise ValueError(f"Logo {logo['id']} requires an existing real PNG asset")
                icon = Image.open(path).convert("RGBA")
                if icon.getbbox() is None:
                    raise ValueError("Logo asset is empty")
                scale = min((tile - 2 * padding) / icon.width, (tile - 2 * padding) / icon.height)
                if scale > number(group.get("max_upscale", 1.5), "max_upscale", 1):
                    raise ValueError("Logo resolution is too small; obtain a larger original or rasterize its official vector at target resolution")
                fit = icon.resize((max(1, round(icon.width * scale)), max(1, round(icon.height * scale))), Image.Resampling.LANCZOS)
                x = round(x0 + ci * (tile + gap))
                tile_art = Image.new("RGBA", (tile, tile))
                ImageDraw.Draw(tile_art).rounded_rectangle([1, 1, tile - 2, tile - 2],
                    radius=round(tile * .16), fill=group.get("background", "#FFFFFF"), outline="#080808", width=3)
                tile_art.alpha_composite(fit, ((tile - fit.width) // 2, (tile - fit.height) // 2))
                bounds = [x, y, tile, tile]
                if not inside(bounds, [0, 0, w, h]):
                    raise ValueError("Logo group exceeds canvas; recompose or select relevant products")
                layer.alpha_composite(tile_art, (x, y)); regions.append(("logo:" + logo["id"], bounds))
                logo_records.append({"id": logo["id"], "path": logo["path"], "sha256": sha(path),
                                     "rect": bounds, "fit": "uniform_contain", "source_size": list(icon.size)})
    keepouts = [{"id": k["id"], "rect": rect(k["rect"], "keepout")} for k in cfg.get("keepouts", [])]
    people_present = cfg.get("people_present", True)
    if not isinstance(people_present, bool):
        raise ValueError("people_present must be an explicit boolean")
    if people_present and not keepouts:
        raise ValueError("Person cover requires keepouts derived from this artwork")
    for i, (name, bounds) in enumerate(regions):
        if not inside(bounds, safe):
            raise ValueError(f"{name} exceeds safe area")
        for k in keepouts:
            if intersects(bounds, k["rect"]):
                raise ValueError(f"{name} overlaps protected region {k['id']}")
        for other, other_bounds in regions[:i]:
            if intersects(bounds, other_bounds):
                raise ValueError(f"{name} overlaps {other}")
    targets = [output, measure_path] + ([overlay_path] if overlay_path else [])
    if len({p.resolve() for p in targets}) != len(targets) or any(p.exists() for p in targets):
        raise ValueError("Use distinct unused candidate output paths; preserve existing results")
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
    final = art.copy(); final.alpha_composite(layer); final.convert("RGB").save(output)
    if overlay_path:
        layer.save(overlay_path)
    record = {"canvas": [w, h], "image_sha256": sha(output), "safe_rect": safe,
              "keepouts": keepouts, "blocks": blocks, "measured_ink": measurements,
              "official_logos": logo_records, "font": {"path": cfg["font"]["path"], "sha256": sha(font_path), "weight": weight},
              "art": {"path": cfg["art"], "sha256": sha(art_path)},
              "contract": "natural_proportions_measured_bounds_uniform_logo_contain",
              "visual_review": "not_performed_by_this_helper"}
    measure_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measure", type=Path, required=True)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    record = render(args.config, args.output, args.measure, args.overlay)
    print(json.dumps({"output": str(args.output), "sha256": record["image_sha256"]}))


if __name__ == "__main__":
    main()
