/** Parameterized selected two-line header. No logos, fonts or project IDs bundled. */
export async function createTwoLineHeader(root, content, preset, options = {}) {
  if (!(root instanceof Element)) throw new Error('root must be a DOM Element');
  const p = preset.header;
  const scale = options.scale ?? 1;
  const font = options.fontFamily ?? p?.font_family;
  const logoRequired = options.logoRequired ?? true;
  if (!p || !Number.isFinite(scale) || scale <= 0 || !font ||
      typeof content.context !== 'string' || !content.context.trim() ||
      typeof content.conclusion !== 'string' || !content.conclusion.trim() ||
      !Array.isArray(content.logos)) throw new Error('invalid header content, preset or scale');
  if (typeof logoRequired !== 'boolean') throw new Error('logoRequired must be explicit boolean');
  if (logoRequired && !content.logos.length) throw new Error('Product header requires at least one real logo; use logoRequired:false only for an intentional unbranded context header');
  const requiredNumbers = ['crop_height','x','y','width','height','padding_x','padding_y',
    'radius','text_logo_gap','line_gap','context_size','context_line_height','context_weight',
    'conclusion_size','conclusion_line_height','conclusion_weight','logo_size','wide_logo_width',
    'logo_gap','logo_radius','wide_logo_padding'];
  if (requiredNumbers.some(k => !Number.isFinite(p[k]) || p[k] < 0)) throw new Error('invalid numeric preset');
  if (p.layout !== 'two_simultaneous_lines_right_logos') throw new Error('unsupported header layout');
  const px = x => `${x * scale}px`;
  root.replaceChildren();
  Object.assign(root.style, {position:'relative', width:px(preset.reference_canvas.width),
    height:px(p.crop_height), overflow:'visible', fontFamily:font});
  const plate = document.createElement('div');
  Object.assign(plate.style, {position:'absolute', left:px(p.x), top:px(p.y), width:px(p.width),
    height:px(p.height), padding:`${px(p.padding_y)} ${px(p.padding_x)}`, boxSizing:'border-box',
    display:'flex', alignItems:'center', justifyContent:'space-between', gap:px(p.text_logo_gap),
    borderRadius:px(p.radius), background:p.background, whiteSpace:'nowrap'});
  const copy = document.createElement('div');
  Object.assign(copy.style, {display:'flex', flexDirection:'column', alignItems:'flex-start',
    justifyContent:'center', gap:px(p.line_gap), flex:'1', minWidth:'0'});
  const textLine = (text, size, lineHeight, weight, color) => {
    const el = document.createElement('span'); el.textContent = text;
    Object.assign(el.style, {display:'block', width:'max-content', flex:'none', fontSize:px(size),
      lineHeight:px(lineHeight), fontWeight:String(weight), color, letterSpacing:'0px'});
    copy.append(el); return el;
  };
  const context = textLine(content.context, p.context_size, p.context_line_height, p.context_weight, p.context_color);
  const conclusion = textLine(content.conclusion, p.conclusion_size, p.conclusion_line_height, p.conclusion_weight, p.conclusion_color);
  plate.append(copy);
  const logos = document.createElement('div');
  Object.assign(logos.style, {display:'flex', alignItems:'center', gap:px(p.logo_gap), flex:'none'});
  const images = content.logos.map(item => {
    if (!item || typeof item.src !== 'string' || !item.src || typeof item.label !== 'string' || !item.label) {
      throw new Error('each logo needs a real src and label');
    }
    const img = document.createElement('img'); img.src = item.src; img.alt = item.label;
    Object.assign(img.style, {display:'block', flex:'none', boxSizing:'border-box', objectFit:'contain',
      width:px(item.wide ? p.wide_logo_width : p.logo_size), height:px(p.logo_size),
      padding:item.wide ? px(p.wide_logo_padding) : '0px', borderRadius:px(p.logo_radius), background:p.logo_background});
    logos.append(img); return img;
  });
  if (images.length) plate.append(logos);
  root.append(plate);
  await document.fonts.ready;
  await Promise.all([document.fonts.load(`${p.context_weight} ${px(p.context_size)} ${font}`),
    document.fonts.load(`${p.conclusion_weight} ${px(p.conclusion_size)} ${font}`), ...images.map(i => i.decode())]);
  if (images.some(i => !i.naturalWidth || !i.naturalHeight)) throw new Error('logo did not decode');
  const rect = n => { const r=n.getBoundingClientRect(); return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}; };
  function measure() {
    const box=rect(plate), tolerance=.5;
    const inner={left:box.x+p.padding_x*scale, right:box.right-p.padding_x*scale,
      top:box.y+p.padding_y*scale, bottom:box.bottom-p.padding_y*scale};
    const copyRight=images.length ? rect(logos).x-p.text_logo_gap*scale : inner.right;
    const canvas=document.createElement('canvas'), ctx=canvas.getContext('2d');
    const items=[context,conclusion,...images].map(el => {
      const r=rect(el), style=getComputedStyle(el), item={kind:el===context?'context':el===conclusion?'conclusion':'logo',...r};
      if (el.tagName!=='IMG') {
        ctx.font=`${style.fontWeight} ${style.fontSize} ${font}`;
        const m=ctx.measureText(el.textContent), a=m.fontBoundingBoxAscent??m.actualBoundingBoxAscent,
          d=m.fontBoundingBoxDescent??m.actualBoundingBoxDescent;
        const baseline=r.y+(parseFloat(style.lineHeight)-a-d)/2+a;
        item.glyph={left:r.x-m.actualBoundingBoxLeft,right:r.x+m.actualBoundingBoxRight,
          top:baseline-m.actualBoundingBoxAscent,bottom:baseline+m.actualBoundingBoxDescent};
      }
      const b=item.glyph??{left:r.x,right:r.right,top:r.y,bottom:r.bottom};
      const right=el.tagName==='IMG'?inner.right:copyRight;
      item.overflow=b.left<inner.left-tolerance || b.right>right+tolerance ||
        b.top<inner.top-tolerance || b.bottom>inner.bottom+tolerance;
      return item;
    });
    return {plate:box,inner,copyRight,items,overflow:items.filter(i=>i.overflow)};
  }
  const metrics=measure();
  if (options.strict!==false && metrics.overflow.length) {
    throw new Error(`Header overflow (${metrics.overflow.map(i=>i.kind).join(', ')}); recompose without truncation or automatic shrinking`);
  }
  return {root,plate,context,conclusion,images,measure,metrics};
}
