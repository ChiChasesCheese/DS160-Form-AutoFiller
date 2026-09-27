// CEAC page snapshot -> compact TSV (id \t value \t display). Run via Claude-in-Chrome javascript_tool.
// Tool output is truncated at ~1.5k chars, so: `window.__snap = (<this>)()` then read `window.__snap.slice(i, i+1400)`.
// Radio groups collapse to one row (value = checked option's value, '' if none). Checkbox -> '1'/'0'.
() => {
  const P = 'ctl00_SiteContentPlaceHolder_FormView1_';
  const out = [], seen = {};
  for (const e of document.querySelectorAll('input,select,textarea')) {
    if (!e.offsetParent || ['hidden', 'image', 'submit', 'button'].includes(e.type) || e.id === 'ctl00_ddlLanguage') continue;
    const id = e.id.replace(P, '');
    if (e.type === 'radio') {
      const g = id.replace(/_\d+$/, '');
      if (!(g in seen)) { seen[g] = out.length; out.push([g, '', '']); }
      if (e.checked) out[seen[g]] = [g, e.value, ''];
      continue;
    }
    out.push([id, e.type === 'checkbox' ? (e.checked ? '1' : '0') : e.value,
      e.tagName === 'SELECT' ? (e.selectedOptions[0]?.text || '').trim() : '']);
  }
  const err = (document.body.innerText.match(/Please correct all areas[\s\S]*?(?=\n\s*\n|Help:)/) || [''])[0];
  return '#node=' + new URLSearchParams(location.search).get('node') + '\n#err=' + err.replace(/\n+/g, ' | ') + '\n'
    + out.map(r => r.join('\t')).join('\n');
}
