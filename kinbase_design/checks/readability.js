(all,{identity,visible,visibleLines,context,column})=>{
  const result={words:[],labelPairs:[]},groups=new Map(),widths=new Map();
  const contentWidth=e=>{const s=getComputedStyle(e);return Math.max(0,e.getBoundingClientRect().width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth));};
  const block=e=>{while(e.parentElement&&['inline','contents'].includes(getComputedStyle(e).display))e=e.parentElement;return e;};
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let order=0;
  for(let node=walker.nextNode();node;node=walker.nextNode(),order++){
    const e=node.parentElement;if(!visible(e)||e.closest('script,style'))continue;
    const owner=block(e);let group=groups.get(owner);
    if(!group){group={text:'',parts:[],last:order-1};groups.set(owner,group);}
    if(group.last!==order-1)group.text+=' ';
    group.parts.push({node,start:group.text.length,end:group.text.length+node.textContent.length});
    group.text+=node.textContent;group.last=order;
  }
  for(const [owner,group] of groups){
    const blockWidth=contentWidth(owner),availableWidth=column(owner,true).columnWidth;
    for(const match of group.text.matchAll(/[\p{L}\p{N}][\p{L}\p{N}\p{M}]*/gu)){
      const start=match.index,end=start+match[0].length,parts=group.parts.filter(p=>p.end>start&&p.start<end);
      if(!parts.length)continue;
      const range=document.createRange();range.setStart(parts[0].node,start-parts[0].start);range.setEnd(parts.at(-1).node,end-parts.at(-1).start);
      const boxes=visibleLines(owner,range),lines=[];
      for(const box of boxes)if(!lines.some(r=>Math.min(r.bottom,box.bottom)-Math.max(r.top,box.top)>Math.min(r.height,box.height)/2))lines.push(box);
      let wordWidth=0;
      for(const part of parts){
        const s=getComputedStyle(part.node.parentElement);let text=part.node.textContent.slice(Math.max(start-part.start,0),Math.min(end-part.start,part.node.textContent.length));
        if(s.textTransform==='uppercase')text=text.toLocaleUpperCase();else if(s.textTransform==='lowercase')text=text.toLocaleLowerCase();
        const font=s.font||`${s.fontStyle} ${s.fontWeight} ${s.fontSize} ${s.fontFamily}`,key=font+'|'+s.letterSpacing+'|'+text;
        if(!widths.has(key)){context.font=font;widths.set(key,context.measureText(text).width+(parseFloat(s.letterSpacing)||0)*text.length);}
        wordWidth+=widths.get(key);
      }
      result.words.push({...identity(owner),key:owner.dataset.kdCheck+':'+start,word:match[0],lines:lines.length,wordWidth,blockWidth,availableWidth});
    }
  }
  const distance=(a,b)=>{
    const overlap=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);
    return overlap>0?{axis:'horizontal',gap:Math.max(b.left-a.right,a.left-b.right)}:{axis:'vertical',gap:Math.max(b.top-a.bottom,a.top-b.bottom)};
  };
  for(const dl of all.filter(e=>e.tagName==='DL')){
    const nodes=[...dl.querySelectorAll('dt,dd')].filter(e=>e.closest('dl')===dl&&visible(e));
    for(let i=0;i<nodes.length;i++){
      const dd=nodes[i];if(dd.tagName!=='DD')continue;
      const label=nodes.slice(0,i).reverse().find(e=>e.tagName==='DT'),next=nodes.slice(i+1).find(e=>e.tagName==='DT');
      if(!label||!next)continue;
      result.labelPairs.push({...identity(dd),label:label.textContent.trim(),value:dd.textContent.trim(),nextLabel:next.textContent.trim(),
        own:distance(label.getBoundingClientRect(),dd.getBoundingClientRect()),next:distance(dd.getBoundingClientRect(),next.getBoundingClientRect())});
    }
  }
  return result;
}
