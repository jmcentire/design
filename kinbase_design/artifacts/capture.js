(args) => {
  const selector=e=>e===document.body?'body':e.parentElement?selector(e.parentElement)+' > '+e.tagName.toLowerCase()+':nth-of-type('+([...e.parentElement.children].filter(n=>n.tagName===e.tagName).indexOf(e)+1)+')':e.tagName.toLowerCase();
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
  const all=[document.body,...document.body.querySelectorAll('*')].filter(e=>!['SCRIPT','STYLE','NOSCRIPT'].includes(e.tagName)&&visible(e));
  const queries=[],faces=[],problems=[];
  const rules=list=>{for(const rule of list){if(rule.media)queries.push(rule.conditionText||rule.media.mediaText);if(rule.type===CSSRule.FONT_FACE_RULE)faces.push({family:rule.style.fontFamily,weight:rule.style.fontWeight,style:rule.style.fontStyle,src:rule.style.src});if(rule.cssRules)rules(rule.cssRules);}};
  for(const sheet of document.styleSheets){try{rules(sheet.cssRules);}catch{problems.push('Cross-origin stylesheet rules unavailable: '+(sheet.href||'inline'));}}
  for(const face of document.fonts)faces.push({family:face.family,weight:face.weight,style:face.style,src:'',status:face.status});
  if(all.some(e=>(e.textContent||'').length>args.maxText))problems.push('Some captured text exceeds the per-element text bound; the DOM original retains it');
  const nodes=all.slice(0,args.maxNodes).map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {
    selector:selector(e),parent:e.parentElement?selector(e.parentElement):null,tag:e.tagName.toLowerCase(),
    text:(e.innerText||e.textContent||'').slice(0,args.maxText),directText:[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').slice(0,args.maxText),
    attributes:Object.fromEntries(['id','class','role','alt','type','aria-label','href'].map(n=>[n,e.getAttribute(n)]).filter(p=>p[1]!==null)),
    src:e.tagName==='IMG'?e.currentSrc:e.tagName.toLowerCase()==='svg'?'inline:'+location.href+'#'+selector(e):null,box:[r.x+scrollX,r.y+scrollY,r.width,r.height],
    styles:Object.fromEntries(args.properties.map(p=>[p,s.getPropertyValue(p)]))};});
  return {title:document.title,nodes,media_queries:[...new Set(queries)],font_faces:faces,
    candidates:[...[...document.images].map(e=>({url:e.currentSrc,alt:e.alt,selector:selector(e),kind:/logo|brand/i.test(e.alt+' '+e.className+' '+e.src)?'logo':'image'})),
      ...[...document.querySelectorAll('svg')].filter(visible).map(e=>({url:'inline:'+location.href+'#'+selector(e),inline:e.outerHTML,selector:selector(e),kind:e.closest('nav')?'logo':'image'}))],
    problems:[...problems,...(all.length>args.maxNodes?['Element sampling limit reached; '+(all.length-args.maxNodes)+' elements unsampled']:[])]};
}
