(e) => {
  if(!e.matches('button,input:not([type="hidden"]),textarea,select'))return null;
  const properties=['appearance','accent-color','color','background-color','background-image',
    'box-shadow','filter','opacity','font-family','font-size','font-weight','font-style',
    'outline-color','outline-style','outline-width','outline-offset',
    'line-height','padding-top','padding-right','padding-bottom','padding-left',
    ...['top','right','bottom','left'].flatMap(side=>['color','style','width'].map(p=>`border-${side}-${p}`)),
    ...['top-left','top-right','bottom-left','bottom-right'].map(c=>`border-${c}-radius`)];
  const computed=getComputedStyle(e);
  if(computed.appearance==='none')return null;
  const snapshot=s=>Object.fromEntries(properties.map(p=>[p,s.getPropertyValue(p)]));
  const authored=snapshot(computed);
  const original=e.getAttribute('style');
  try {
    // Revert author declarations on this element only. Its inherited context
    // and real focus state remain intact; geometry is checked separately.
    e.style.cssText='all:revert!important';
    const native=getComputedStyle(e);
    return {checkable:e.matches('input[type="checkbox"],input[type="radio"]'),
      authored,native:snapshot(native)};
  } finally {
    if(original===null)e.removeAttribute('style');else e.setAttribute('style',original);
  }
}
