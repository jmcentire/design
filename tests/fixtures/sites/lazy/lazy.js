const observer = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    const image = entry.target;
    image.src = image.dataset.src;
    observer.unobserve(image);
  }
}, {rootMargin: '0px'});
document.querySelectorAll('img[data-src]').forEach(image => observer.observe(image));
