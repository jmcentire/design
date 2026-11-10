(all,{target,rect,visible,interactive,background,rules=[],measureMinimumEm=0})=>{
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
  const context=canvas.getContext('2d',{willReadFrequently:true}),colors=new Map(),surfaces=new Map();
  const rgba=value=>{if(!colors.has(value)){context.clearRect(0,0,1,1);context.fillStyle=value;context.fillRect(0,0,1,1);colors.set(value,[...context.getImageData(0,0,1,1).data].map(n=>n/255));}return colors.get(value);};
  const effective=e=>{let result=[1,1,1];for(const layer of background(e).reverse()){const c=rgba(layer.color);result=result.map((v,i)=>c[i]*c[3]+v*(1-c[3]));}return result;};
  const painted=e=>{
    if(!surfaces.has(e)){
      const s=getComputedStyle(e),own=effective(e),outer=e.parentElement?effective(e.parentElement):[1,1,1];
      const border=['Top','Right','Bottom','Left'].some(side=>parseFloat(s['border'+side+'Width'])>0&&!['none','hidden'].includes(s['border'+side+'Style'])&&rgba(s['border'+side+'Color'])[3]>0);
      surfaces.set(e,border||s.backgroundImage!=='none'||own.some((v,i)=>Math.abs(v-outer[i])>1/510));
    }
    return surfaces.get(e);
  };
  const identity=e=>({target:target(e),state:e.closest('[data-kd-state]')?.dataset.kdState||'default'});
  const contentWidth=e=>{const s=getComputedStyle(e);return Math.max(0,e.getBoundingClientRect().width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth));};
  const layoutChildren=e=>[...e.children].flatMap(child=>getComputedStyle(child).display==='contents'?layoutChildren(child):[child]);
  const inFlow=e=>visible(e)&&!['absolute','fixed'].includes(getComputedStyle(e).position);
  const beside=(a,b)=>{
    const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();
    return Math.min(x.bottom,y.bottom)>Math.max(x.top,y.top)&&
      (x.right<=y.left+1e-6||y.right<=x.left+1e-6);
  };
  const column=(e,content=false)=>{
    for(let item=e.parentElement;item;item=item.parentElement){
      const s=getComputedStyle(item);if(s.display==='contents'||!inFlow(item))continue;
      let parent=item.parentElement;
      while(parent&&getComputedStyle(parent).display==='contents')parent=parent.parentElement;
      if(!parent)continue;
      const layout=getComputedStyle(parent);
      const columns=['grid','inline-grid'].includes(layout.display)||
        ['flex','inline-flex'].includes(layout.display)&&['row','row-reverse'].includes(layout.flexDirection);
      if(columns&&layoutChildren(parent).some(peer=>peer!==item&&inFlow(peer)&&beside(item,peer)))
        return {columnWidth:content?contentWidth(item):item.getBoundingClientRect().width,column:target(item),columnKind:'item-border-box'};
    }
    const main=e.closest('main,[role="main"]')||document.querySelector('main,[role="main"]')||document.body;
    return {columnWidth:contentWidth(main),column:target(main),columnKind:'main-content-box'};
  };
  const visibleLines=(e,range)=>{
    let lines=[...range.getClientRects()].filter(r=>r.width>0&&r.height>0).map(({left,right,top,bottom})=>({left,right,top,bottom}));
    for(let p=e;p;p=p.parentElement){
      const s=getComputedStyle(p),box=p.getBoundingClientRect();
      const x=['hidden','clip','auto','scroll'].includes(s.overflowX),y=['hidden','clip','auto','scroll'].includes(s.overflowY);
      if(x||y)lines=lines.map(r=>({left:x?Math.max(r.left,box.left+parseFloat(s.borderLeftWidth)):r.left,right:x?Math.min(r.right,box.right-parseFloat(s.borderRightWidth)):r.right,
        top:y?Math.max(r.top,box.top+parseFloat(s.borderTopWidth)):r.top,bottom:y?Math.min(r.bottom,box.bottom-parseFloat(s.borderBottomWidth)):r.bottom})).filter(r=>r.right>r.left&&r.bottom>r.top);
    }
    return lines.map(r=>({...r,width:r.right-r.left,height:r.bottom-r.top}));
  };
  const result={headings:[],paragraphText:[],paragraphs:[],insets:[],targets:[]},insets=new Map();
  for(const e of all){
    if(!visible(e))continue;
    const size=parseFloat(getComputedStyle(e).fontSize),text=e.textContent.trim();
    const level=/^H[1-6]$/.test(e.tagName)?Number(e.tagName[1]):e.getAttribute('role')==='heading'?Number(e.getAttribute('aria-level')||2):null;
    if(level&&text)result.headings.push({...identity(e),level,size});
    if(e.tagName==='P'&&text)result.paragraphs.push({...identity(e),size,characters:text.length,width:contentWidth(e),...(measureMinimumEm?column(e):{})});
    if(interactive(e)){
      const ancestors=[];for(let parent=e.parentElement;parent;parent=parent.parentElement)if(interactive(parent))ancestors.push(all.indexOf(parent));
      result.targets.push({...identity(e),key:all.indexOf(e),ancestors,box:rect(e),painted:painted(e)||rgba(getComputedStyle(e).backgroundColor)[3]>0});
    }
  }
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  for(let text=walker.nextNode();text;text=walker.nextNode()){
    const e=text.parentElement,copy=text.textContent;
    if(!copy.trim()||!visible(e)||e.closest('script,style'))continue;
    if(e.closest('p'))result.paragraphText.push({size:parseFloat(getComputedStyle(e).fontSize),characters:copy.trim().length});
    if(e.closest('a[href],button'))continue;
    const range=document.createRange();range.setStart(text,copy.length-copy.trimStart().length);range.setEnd(text,copy.trimEnd().length);
    // Declared truncation is checked separately. Only the visible portion of a
    // line can touch a surface edge; clipped glyphs are not painted there.
    const lines=visibleLines(e,range);
    if(!lines.length)continue;
    for(let surface=e;surface;surface=surface.parentElement){
      if(!painted(surface))continue;
      const box=surface.getBoundingClientRect(),left=Math.min(...lines.map(r=>r.left-box.left)),right=Math.min(...lines.map(r=>box.right-r.right));
      const key=e.dataset.kdCheck+':'+(surface.dataset.kdCheck||'body');
      const prior=insets.get(key);
      insets.set(key,{...identity(e),surface:target(surface),left:Math.min(left,prior?.left??Infinity),right:Math.min(right,prior?.right??Infinity)});
    }
  }
  result.insets=[...insets.values()];
  if(rules.includes('word-break'))Object.assign(result,(__READABILITY__)(all,{identity,visible,visibleLines,context,column}));
  if(rules.includes('heading-binding')||rules.includes('gutter'))Object.assign(result,(__BINDING__)(all,{identity,visible,painted}));
  return result;
}
