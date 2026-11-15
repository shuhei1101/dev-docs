// 本文の全要素と疑似要素（::before・::after・::marker）の算出値を、単独の mdmark と dev-docs の画面で比べる
// 引数: 幅 明暗 [差し込む CSS のファイル] [出力の名前]
const { chromium } = require('/mnt/c/Users/shuhe/repo/mdmark/.claude/worktrees/develop/node_modules/playwright');
const fs = require('fs');
const base = '/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/mdcompare-232';
const docs = [['SCR-155-1','/dev-docs/docs/screen/SCR-155-1'],['IF-155-1','/dev-docs/docs/interface/IF-155-1'],['CLI','/dev-docs/docs/guide/files/docs/guide/CLI.md'],['TABLE','/mdmark/docs/guide/files/docs/guide/'+encodeURIComponent('記載する-表に機能を付ける.md')]];
const W = +(process.argv[2]||1440), scheme = process.argv[3]||'light', cssFile = process.argv[4], name = process.argv[5]||`sweep2-${W}-${scheme}`;
const P = ['content','tab-size','-webkit-text-size-adjust','font-feature-settings','font-variation-settings','-webkit-tap-highlight-color','font-family','font-size','line-height','font-weight','font-style','color','background-color','margin-top','margin-bottom','margin-left','margin-right','padding-top','padding-bottom','padding-left','padding-right','border-top-width','border-top-style','border-top-color','border-bottom-width','border-bottom-color','border-left-width','border-left-color','list-style-type','text-decoration-line','text-align','vertical-align','display','visibility','width','height','max-width','border-radius','box-shadow','box-sizing','white-space','gap','fill','stroke','opacity'];
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: W, height: 900 }, colorScheme: scheme });
  const p = await ctx.newPage();
  const probe = (P) => {
    const root = document.querySelector('.mdmark'); const res = {}; const cnt = {};
    const els = [root, ...root.querySelectorAll('*')];
    for (const e of els) {
      if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
      const cls = (e.getAttribute('class')||'').split(/\s+/).filter(c=>c.startsWith('mdmark')).sort().join('.');
      const key0 = e.tagName.toLowerCase() + (cls?'.'+cls:'') + (e.hasAttribute('hidden')?'[hidden]':'') + '|' + (e.textContent||'').trim().slice(0,24);
      cnt[key0] = (cnt[key0]||0)+1; const key = key0 + '#' + cnt[key0];
      for (const pseudo of [null, '::before', '::after', '::marker']) {
        const s = getComputedStyle(e, pseudo);
        if (pseudo && pseudo !== '::marker' && (s.content === 'none' || s.content === 'normal')) continue;
        if (pseudo === '::marker' && s.display !== 'list-item' && getComputedStyle(e).display !== 'list-item') continue;
        const o = {}; for (const k of P) o[k] = s.getPropertyValue(k);
        if (o.width.endsWith('px')) o.width = 'px'; if (o.height.endsWith('px')) o.height = 'px';
        res[key + (pseudo||'')] = o;
      }
    }
    return res;
  };
  const css = cssFile === 'SCOPE' ? 'SCOPE' : cssFile ? fs.readFileSync(cssFile, 'utf8') : null;
  const out = {};
  for (const [n,url] of docs) {
    await p.goto('file://'+base+'/out/'+n+'.html'); await p.waitForTimeout(1500);
    const e = await p.evaluate(probe, P);
    await p.goto((process.env.DEVDOCS_ORIGIN||'http://127.0.0.1:8781')+url,{waitUntil:'networkidle',timeout:180000});
    if (css === 'SCOPE') await p.evaluate(() => {
      // 組み上がった CSS の base の層を消し、同じ中身を @scope (html) to (.mdmark) に包んで入れ直す
      for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch { continue; }
        for (let i = 0; i < rules.length; i++) { const r = rules[i];
          if (r.constructor.name === 'CSSLayerBlockRule' && r.name === 'base') {
            const inner = [...r.cssRules].map(x => x.cssText).join('\n');
            sh.deleteRule(i); sh.insertRule('@layer base { @scope (html) to (.mdmark) { ' + inner + ' } }', i); return; } } }
    });
    else if (css) await p.addStyleTag({content: css});
    await p.waitForTimeout(2500);
    const d = await p.evaluate(probe, P);
    out[n] = {e, d};
  }
  fs.writeFileSync(`${base}/${name}.json`, JSON.stringify(out));
  await b.close();
})();
