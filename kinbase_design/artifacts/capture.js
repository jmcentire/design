(args) => {
  const selector=e=>e===document.body?'body':e.parentElement?selector(e.parentElement)+' > '+e.tagName.toLowerCase()+':nth-of-type('+([...e.parentElement.children].filter(n=>n.tagName===e.tagName).indexOf(e)+1)+')':e.tagName.toLowerCase();
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&(!e.checkVisibility||e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}));};
  const all=[document.body,...document.body.querySelectorAll('*')].filter(e=>!['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName)&&visible(e));
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
  const painter=canvas.getContext('2d',{willReadFrequently:true}),colors=new Map();
  const srgb=value=>{if(!CSS.supports("color",value))return value;if(!colors.has(value)){painter.clearRect(0,0,1,1);painter.fillStyle=value;painter.fillRect(0,0,1,1);const c=painter.getImageData(0,0,1,1).data;colors.set(value,'#'+[...c].map(v=>v.toString(16).padStart(2,'0')).join(''));}return colors.get(value);};
  const styles=new Map(all.map(e=>[e,getComputedStyle(e)]));
  const selected=new Set(),take=e=>{if(e&&selected.size<args.maxNodes)selected.add(e);};
  const spread=(items,count)=>{for(let i=0;i<Math.min(count,items.length);i++)take(items[Math.floor(i*(items.length-1)/Math.max(1,Math.min(count,items.length)-1))]);};
  take(document.body);
  spread(all.filter(e=>e.matches('nav,header,footer,main,section,article,form,[role="navigation"],[role="main"]')),Math.floor(args.maxNodes/4));
  // Preserve distinct painted colors before spending the remaining budget on
  // repeated content; finish with a sample distributed over the whole document.
  const seen=new Set();
  for(const e of all){const s=styles.get(e),keys=[];
    if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))keys.push('text:'+srgb(s.color),'type:'+e.tagName+':'+s.fontFamily+':'+s.fontSize+':'+s.fontWeight);
    if(e.matches('img,svg,input,select,textarea,button'))keys.push('media-control:'+e.tagName);
    if(srgb(s.backgroundColor).slice(-2)!=='00')keys.push('surface:'+srgb(s.backgroundColor));
    if(parseFloat(s.borderTopWidth)>0&&s.borderTopStyle!=='none')keys.push('border:'+srgb(s.borderTopColor));
    if(keys.some(k=>!seen.has(k))&&selected.size<Math.floor(args.maxNodes*3/4)){take(e);keys.forEach(k=>seen.add(k));}
  }
  spread(all.filter(e=>!selected.has(e)),args.maxNodes-selected.size);
  const sampled=all.filter(e=>selected.has(e));
  const queries=[],faces=[],problems=[],notes=[];
  const rules=list=>{for(const rule of list){if(rule.media)queries.push(rule.conditionText||rule.media.mediaText);if(rule.type===CSSRule.FONT_FACE_RULE)faces.push({family:rule.style.fontFamily,weight:rule.style.fontWeight,style:rule.style.fontStyle,src:rule.style.src});if(rule.cssRules)rules(rule.cssRules);}};
  for(const sheet of document.styleSheets){try{rules(sheet.cssRules);}catch{problems.push('Cross-origin stylesheet rules unavailable: '+(sheet.href||'inline'));}}
  for(const face of document.fonts)faces.push({family:face.family,weight:face.weight,style:face.style,src:'',status:face.status});
  if(all.some(e=>(e.textContent||'').length>args.maxText))notes.push('Some captured text exceeds the per-element text bound; the DOM original retains it');
  const nodes=sampled.map(e=>{const s=styles.get(e),r=e.getBoundingClientRect(),backgrounds=[];
    for(let parent=e;parent;parent=parent.parentElement){const style=getComputedStyle(parent);backgrounds.push({color:srgb(style.backgroundColor),image:style.backgroundImage});}
    return {
    selector:selector(e),parent:e.parentElement?selector(e.parentElement):null,tag:e.tagName.toLowerCase(),
    text:(e.innerText||e.textContent||'').slice(0,args.maxText),directText:[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').slice(0,args.maxText),
    attributes:Object.fromEntries(['id','class','role','alt','type','aria-label','href'].map(n=>[n,e.getAttribute(n)]).filter(p=>p[1]!==null)),
    src:e.tagName==='IMG'?e.currentSrc:e.tagName.toLowerCase()==='svg'?'inline:'+location.href+'#'+selector(e):null,box:[r.x+scrollX,r.y+scrollY,r.width,r.height],
    styles:Object.fromEntries(args.properties.map(p=>[p,s.getPropertyValue(p)])),backgrounds,
    normalized_colors:Object.fromEntries(['color','background-color','border-color','border-top-color'].map(p=>[p,srgb(s.getPropertyValue(p))]))};});
  return {title:document.title,nodes,media_queries:[...new Set(queries)],font_faces:faces,
    candidates:[...[...document.images].filter(visible).map(e=>({url:e.currentSrc,alt:e.alt,selector:selector(e),kind:/logo|brand/i.test(e.alt+' '+e.className+' '+e.src)?'logo':'image'})),
      ...all.flatMap(e=>[...styles.get(e).backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(m=>({url:new URL(m[1],document.baseURI).href,selector:selector(e),kind:'image'}))),
      ...[...document.querySelectorAll('svg')].filter(visible).map(e=>({url:'inline:'+location.href+'#'+selector(e),inline:e.outerHTML,selector:selector(e),kind:e.closest('nav')?'logo':'image'}))],
    problems,notes:[...notes,...(all.length>args.maxNodes?['Element sampling limit reached; '+(all.length-sampled.length)+' elements unsampled']:[])],
    stats:{elements_visible:all.length,elements_sampled:sampled.length,elements_unsampled:all.length-sampled.length}};
}
