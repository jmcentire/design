async args => {
  const start=performance.now(),end=start+args.budgetMs,origin={left:scrollX,top:scrollY};
  const left=()=>Math.max(0,end-performance.now());
  const bounded=(promise,ms)=>new Promise(resolve=>{
    const timer=setTimeout(()=>resolve(false),Math.min(ms,left()));
    Promise.resolve(promise).then(()=>{clearTimeout(timer);resolve(true);},()=>{clearTimeout(timer);resolve(false);});
  });
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,Math.min(ms,left())));
  const visible=image=>{const r=image.getBoundingClientRect(),s=getComputedStyle(image);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&(!image.checkVisibility||image.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}));};
  const nearby=image=>{const r=image.getBoundingClientRect();return visible(image)&&r.bottom>=0&&r.top<=innerHeight;};
  const eager=()=>{for(const image of document.images)image.loading='eager';};
  const signature=()=>[...document.images].filter(nearby).map(i=>(i.currentSrc||i.src)+':'+i.complete+':'+i.naturalWidth).join('|');
  async function settle(){
    eager();await pause(args.settleMs);
    let previous=signature(),stable=0;
    while(left()>0&&stable<args.quietMs){
      const images=[...document.images].filter(nearby);
      await bounded(Promise.all(images.map(i=>i.decode().catch(()=>{}))),args.decodeMs);
      await pause(args.settleMs);eager();const current=signature();
      stable=current===previous?stable+args.settleMs:0;previous=current;
    }
  }
  let steps=0,complete=false;
  try{
    window.scrollTo({left:origin.left,top:0,behavior:'instant'});
    while(left()>0&&steps<args.maxSteps){
      steps++;await settle();
      const height=Math.max(document.documentElement.scrollHeight,document.body.scrollHeight);
      const bottom=Math.max(0,height-innerHeight);
      if(scrollY>=bottom-1){complete=true;break;}
      window.scrollTo({left:origin.left,top:Math.min(bottom,scrollY+Math.max(1,innerHeight*args.stepFraction)),behavior:'instant'});
    }
    eager();await bounded(document.fonts.ready,left());
    await bounded(Promise.all([...document.images].filter(visible).map(i=>i.decode().catch(()=>{}))),left());
  }finally{
    window.scrollTo({...origin,behavior:'instant'});
    await pause(args.settleMs);
  }
  const pending=[...document.images].filter(i=>visible(i)&&(!i.complete||!i.naturalWidth));
  return {steps,complete_sweep:complete,pending_images:pending.length,elapsed_ms:Math.round(performance.now()-start)};
}
