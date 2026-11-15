const { chromium } = require('/mnt/c/Users/shuhe/repo/mdmark/.claude/worktrees/develop/node_modules/playwright');
const base = '/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/mdcompare-232';
const docs = [['SCR-155-1','/dev-docs/docs/screen/SCR-155-1'],['IF-155-1','/dev-docs/docs/interface/IF-155-1'],['CLI','/dev-docs/docs/guide/files/docs/guide/CLI.md']];
const W = +(process.argv[2]||1440), scheme = process.argv[3]||'light';
const P = ['font-family','font-size','line-height','font-weight','font-style','color','background-color','margin-top','margin-bottom','margin-left','padding-top','padding-bottom','padding-left','padding-right','border-top-width','border-top-style','border-top-color','border-bottom-width','border-bottom-color','border-left-width','border-left-color','list-style-type','text-decoration-line','text-align','vertical-align','display','width','height','max-width','border-radius','box-shadow','white-space','gap','fill','stroke'];
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: W, height: 900 }, colorScheme: scheme });
  const p = await ctx.newPage();
  const probe = (P) => {
    const root = document.querySelector('.mdmark'); const res = {}; const cnt = {};
    for (const e of root.querySelectorAll('*')) {
      if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
      const cls = (e.getAttribute('class')||'').split(/\s+/).filter(c=>c.startsWith('mdmark')).sort().join('.');
      const key0 = e.tagName.toLowerCase() + (cls?'.'+cls:'') + '|' + (e.textContent||'').trim().slice(0,24);
      cnt[key0] = (cnt[key0]||0)+1; const key = key0 + '#' + cnt[key0];
      const s = getComputedStyle(e); const o = {}; for (const k of P) o[k] = s.getPropertyValue(k);
      if (o.width.endsWith('px')) o.width = 'px'; if (o.height.endsWith('px')) o.height='px';
      res[key] = o;
    }
    return res;
  };
  const out = {};
  for (const [n,url] of docs) {
    await p.goto('file://'+base+'/out/'+n+'.html'); await p.waitForTimeout(1500);
    const e = await p.evaluate(probe, P);
    await p.goto('http://127.0.0.1:8781'+url,{waitUntil:'networkidle',timeout:120000}); await p.waitForTimeout(2500);
    const d = await p.evaluate(probe, P);
    out[n] = {e, d};
  }
  require('fs').writeFileSync(`${base}/sweep-${W}-${scheme}.json`, JSON.stringify(out));
  await b.close();
})();
