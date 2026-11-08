(args) => {
  const properties = args.properties;
  const all = [...document.body.querySelectorAll('*')].filter(e => !['SCRIPT','STYLE'].includes(e.tagName));
  const target = e => e.closest('[data-kd-slot]')?.dataset.kdSlot || e.closest('[data-kd-construct]')?.dataset.kdConstruct || 'page';
  const rect = e => {const r=e.getBoundingClientRect(); return [r.x+scrollX,r.y+scrollY,r.width,r.height];};
  const visible = e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);if(!(r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'))return false;for(let p=e;p;p=p.parentElement)if(parseFloat(getComputedStyle(p).opacity)===0)return false;return true;};
  const interactive = e => e.matches('a[href],button,input:not([type="hidden"]),textarea,select,summary,[tabindex]') && e.tabIndex>=0;
  const background = e => {
    const result=[];
    for(let p=e;p;p=p.parentElement) {
      const s=getComputedStyle(p);
      result.push({color:s.backgroundColor,image:s.backgroundImage,uncertain:parseFloat(s.opacity)<1 || s.mixBlendMode!=='normal' || s.filter!=='none'});
    }
    return result;
  };
  const nativeControl = __NATIVE_CONTROL__;
  const nodes=all.map((e,index) => {
    e.setAttribute('data-kd-check',String(index));
    const s=getComputedStyle(e),r=e.getBoundingClientRect(),root=e.closest('[data-kd-construct]');
    const directText=[...e.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join('');
    const text=e.textContent||'';
    const disabled=e.matches(':disabled') || !!e.closest('[aria-disabled="true"]');
    let clipped=false;
    if(text.trim()) {
      clipped=((['hidden','clip'].includes(s.overflowX)||s.textOverflow==='ellipsis') && e.scrollWidth>e.clientWidth+args.tolerance)
        || ((['hidden','clip'].includes(s.overflowY)||parseInt(s.webkitLineClamp)>0) && e.scrollHeight>e.clientHeight+args.tolerance);
      if(!clipped) {
        const range=document.createRange();range.selectNodeContents(e);const tr=range.getBoundingClientRect();
        for(let p=e.parentElement;p;p=p.parentElement) {
          const ps=getComputedStyle(p),pr=p.getBoundingClientRect();
          if((['hidden','clip'].includes(ps.overflowX) && (tr.left<pr.left-args.tolerance||tr.right>pr.right+args.tolerance)) ||
             (['hidden','clip'].includes(ps.overflowY) && (tr.top<pr.top-args.tolerance||tr.bottom>pr.bottom+args.tolerance))) {clipped=true;break;}
        }
      }
    }
    const control=e.matches('button,input:not([type="hidden"]),textarea,select');
    const hasBorder=parseFloat(s.borderTopWidth)>0 && !['none','hidden'].includes(s.borderTopStyle);
    const boundary=hasBorder?s.borderTopColor:(s.backgroundColor!=='rgba(0, 0, 0, 0)'?s.backgroundColor:null);
    const boundaries=[...(hasBorder?[s.borderTopColor]:[]),s.backgroundColor].filter(value=>value!=='rgba(0, 0, 0, 0)'&&value!=='transparent');
    const inline=e.tagName==='A' && e.parentElement && e.parentElement.matches('p,li') && [...e.parentElement.childNodes].some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());
    const userAgent=e.matches('input[type="checkbox"],input[type="radio"]') && s.appearance!=='none';
    const equivalent=e.tagName==='A' && [...document.querySelectorAll('a[href]')].some(a=>a!==e&&a.href===e.href&&visible(a)&&a.getBoundingClientRect().width>=args.targetSize&&a.getBoundingClientRect().height>=args.targetSize);
    let overImage=false;
    if(directText.trim()) {
      for(let p=e.parentElement;p;p=p.parentElement) {
        if([...p.children].some(c=>c!==e&&c.matches('img,svg,video,canvas')&&getComputedStyle(c).position==='absolute'&&(()=>{const ir=c.getBoundingClientRect();return ir.left<r.right&&ir.right>r.left&&ir.top<r.bottom&&ir.bottom>r.top;})())) {overImage=true;break;}
      }
    }
    const backgroundAsset=s.backgroundImage.startsWith('url(');
    const backgroundURL=backgroundAsset?s.backgroundImage.slice(4,-1).trim().replace(/^['"]|['"]$/g,''):null;
    const backgroundDecoded=backgroundAsset?window.__kdBackgroundImages?.[backgroundURL]===true:null;
    const image=e.tagName==='IMG' && !!e.closest('[data-kd-asset]');
    const fontSize=parseFloat(s.fontSize),fontWeight=parseFloat(s.fontWeight)||400;
    const controlStyles=args.controlSlots.includes(e.dataset.kdSlot)?[...e.querySelectorAll('input,select,textarea,button')].map(control=>{
      const style=getComputedStyle(control);
      return {css:Object.fromEntries(properties.map(p=>[p,style.getPropertyValue(p)])),fontSize:parseFloat(style.fontSize)};
    }):null;
    return {index,target:target(e),slot:e.dataset.kdSlot||null,state:root?.dataset.kdState||'default',
      text,directText,visible:visible(e),box:rect(e),scroll:[e.scrollWidth,e.scrollHeight],
      css:Object.fromEntries(properties.map(p=>[p,s.getPropertyValue(p)])),fontSize,fontWeight,controlStyles,
      backgrounds:background(e),overImage,disabled,clipped,lineClamp:parseInt(s.webkitLineClamp)||0,
      backgroundAsset,backgroundDecoded,image,asset:image?e.closest('[data-kd-asset]').dataset.kdAsset:null,
      imageURL:image?e.getAttribute('src'):null,decoded:image?e.complete&&e.naturalWidth>0&&e.naturalHeight>0:null,
      meaningfulImage:image&&!!e.alt,control,nativeAppearance:control?nativeControl(e):null,boundary,boundaries,interactive:interactive(e),inline,userAgent,equivalent,
      scrollContainer:['auto','scroll'].includes(s.overflowX),
      fontReady:document.fonts.check(`${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`,text.trim()||'A')};
  });
  return {nodes,rootSize:parseFloat(getComputedStyle(document.documentElement).fontSize),
    fonts:[...document.fonts].map(f=>({family:f.family,weight:f.weight,style:f.style,status:f.status})),
    pageWidth:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth),
    text:document.body.innerText,
    links:[...document.querySelectorAll('a[href]')].map(e=>({href:e.getAttribute('href'),visible:visible(e)})),
    states:[...document.querySelectorAll('[data-kd-construct][data-kd-state]')].map(e=>[e.dataset.kdConstruct,e.dataset.kdState])};
}
