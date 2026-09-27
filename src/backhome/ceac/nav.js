// CEAC left-sidebar links with click coordinates (CSS px). Screenshot frames may be scaled:
// multiply by (screenshot_width / window.innerWidth) before clicking with computer.left_click.
() => {
  window.scrollTo(0, 0);
  return [...document.querySelectorAll('a[href*="node="]')].filter(a => a.offsetParent).map(a => {
    const r = a.getBoundingClientRect();
    return new URLSearchParams(a.href.split('?')[1]).get('node') + '@' + Math.round(r.x + r.width / 2) + ',' + Math.round(r.y + r.height / 2);
  }).join(' ') + ' | innerWidth=' + innerWidth;
}
