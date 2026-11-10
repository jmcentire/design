(all,{identity,visible,painted})=>{
  const result={headingBindings:[],gutters:[]};
  const box=e=>e.getBoundingClientRect();
  const block=e=>visible(e)&&getComputedStyle(e).display!=='inline'&&
    !!(e.textContent.trim()||e.matches('img,input,textarea,select,video,canvas')||e.querySelector('img,input,textarea,select,video,canvas'));
  for(const h of all.filter(e=>(/^H[1-6]$/.test(e.tagName)||e.getAttribute('role')==='heading')&&block(e))){
    const owner=h.closest('[data-kd-construct]');let current=h,previous=null,next=null;
    while(current.parentElement){
      const parent=current.parentElement,siblings=[...parent.children].filter(block),index=siblings.indexOf(current);
      if(index>=0){previous??=siblings[index-1]||null;next??=siblings[index+1]||null;}
      if(previous&&next||parent===owner)break;
      current=parent;
    }
    if(!previous||!next)continue;
    const a=box(previous),b=box(h),c=box(next);
    if(Math.min(a.right,b.right)<=Math.max(a.left,b.left)||Math.min(b.right,c.right)<=Math.max(b.left,c.left))continue;
    if(a.bottom>b.top+1||b.bottom>c.top+1)continue;
    result.headingBindings.push({...identity(h),before:b.top-a.bottom,after:c.top-b.bottom,previous:identity(previous).target,next:identity(next).target});
  }
  const role=e=>{
    // Action rows and navigation targets have control-separation, not gutters.
    if(e.closest('[data-kd-part="actions"],[data-kd-slot$=".actions"],[data-kd-slot$=".links"]'))return null;
    // A whole-card link remains a repeated item; its interactive tag alone
    // must not erase the card's declared identity.
    return e.dataset.kdConstruct||(['listitem','article'].includes(e.getAttribute('role'))?e.getAttribute('role'):null)||
      (['LI','ARTICLE'].includes(e.tagName)?e.tagName:null);
  };
  for(const parent of all){
    const groups=new Map();
    for(const child of parent.children){const key=role(child);if(!key||!block(child))continue;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(child);}
    for(const children of groups.values())for(let i=0;i<children.length;i++)for(let j=i+1;j<children.length;j++){
      const a=children[i],b=children[j];if(!painted(a)&&!painted(b))continue;
      const x=box(a),y=box(b),horizontal=Math.max(y.left-x.right,x.left-y.right),vertical=Math.max(y.top-x.bottom,x.top-y.bottom);
      if(Math.min(x.bottom,y.bottom)>Math.max(x.top,y.top))result.gutters.push({...identity(a),other:identity(b).target,axis:'horizontal',gap:horizontal});
      else if(Math.min(x.right,y.right)>Math.max(x.left,y.left))result.gutters.push({...identity(a),other:identity(b).target,axis:'vertical',gap:vertical});
    }
  }
  return result;
}
