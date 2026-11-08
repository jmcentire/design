(e) => {
  if(!e.matches('button,input:not([type="hidden"]),textarea,select'))return false;
  const properties=['appearance','accent-color','color','background-color','background-image',
    'box-shadow','filter','opacity','font-family','font-size','font-weight','font-style',
    'outline-color','outline-style','outline-width','outline-offset',
    'line-height','padding-top','padding-right','padding-bottom','padding-left',
    ...['top','right','bottom','left'].flatMap(side=>['color','style','width'].map(p=>`border-${side}-${p}`)),
    ...['top-left','top-right','bottom-left','bottom-right'].map(c=>`border-${c}-radius`)];
  const computed=getComputedStyle(e);
  if(computed.appearance==='none')return false;
  const authored=properties.map(p=>computed.getPropertyValue(p));
  const original=e.getAttribute('style');
  try {
    // Revert author declarations on this element only. Its inherited context
    // and real focus state remain intact; geometry is checked separately.
    e.style.cssText='all:revert!important';
    const native=getComputedStyle(e);
    return properties.every((p,index)=>native.getPropertyValue(p)===authored[index]);
  } finally {
    if(original===null)e.removeAttribute('style');else e.setAttribute('style',original);
  }
}
