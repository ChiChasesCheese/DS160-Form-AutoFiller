// Extract a CEAC Review page as compact TSV: "## Section" lines and "label<TAB>value" rows, in page order.
// Usage (tool output truncates ~1 kB): window.__rev = (<this>)(); then read window.__rev.slice(i, i + 900).
() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const out = ['#node=' + new URLSearchParams(location.search).get('node'), '#title=' + clean(document.title)];
  const root = document.getElementById('aspnetForm') || document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  for (let n = walker.currentNode; n; n = walker.nextNode()) {
    if (n.tagName === 'A' && /^Edit /.test(clean(n.textContent))) out.push('## ' + clean(n.textContent).replace(/^Edit /, ''));
    if (n.tagName !== 'TR' || n.querySelector('table')) continue;
    const cells = [...n.children].filter(c => c.tagName === 'TD');
    if (cells.length < 2) continue;
    const label = clean(cells[0].innerText);
    const value = clean(cells.slice(1).map(c => c.innerText).join(' '));
    if (!label && value && !/^Edit /.test(value) && out.length && out[out.length - 1].includes('\t')) {  // continuation row (address line 2)
      out[out.length - 1] += ', ' + value;
      continue;
    }
    if (!label.endsWith(':')) continue;
    out.push(label.slice(0, -1) + '\t' + value);
  }
  return out.join('\n');
}
