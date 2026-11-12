() => {
  // Every construct on the page with the slots that belong to it, in document order.
  const describe = e => e.tagName.toLowerCase();
  const controls = e => [...e.querySelectorAll('input,textarea,select,button,img,[role="img"]')].map(describe);
  const roots=[...document.querySelectorAll('[data-kd-construct]')];
  const constructs=roots.map(root => ({
    construct:root.dataset.kdConstruct, state:root.dataset.kdState||null, tag:describe(root),
    slots:[...root.querySelectorAll('[data-kd-slot]')].filter(e => e.closest('[data-kd-construct]')===root)
      .map(e => ({slot:e.dataset.kdSlot, tag:describe(e), contains:controls(e)}))}));
  const orphans=[...document.querySelectorAll('[data-kd-slot]')].filter(e => !e.closest('[data-kd-construct]')).map(e => e.dataset.kdSlot);
  return {constructs, orphans};
}
