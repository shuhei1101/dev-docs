// 本文（.mdmark）の外の要素の算出値を、2 つの画面（develop と作業用のビルド）で比べる
const { chromium } = require('/mnt/c/Users/shuhe/repo/mdmark/.claude/worktrees/develop/node_modules/playwright');
const [A, B] = [process.argv[2], process.argv[3]];
const paths = ['/dev-docs/docs/screen/SCR-155-1', '/dev-docs/docs/interface/IF-155-1', '/settings'];
const P = ['font-family','font-size','line-height','font-weight','color','background-color','margin-top','margin-bottom','margin-left','margin-right','padding-top','padding-bottom','padding-left','padding-right','border-top-width','border-top-style','border-top-color','border-bottom-width','border-bottom-color','border-left-width','border-right-width','list-style-type','display','box-sizing','width','height','outline-color','vertical-align','text-decoration-line'];
(async () => {
  const b = await chromium.launch();
  let total = 0;
  for (const scheme of ['light', 'dark']) for (const W of [1440, 390]) {
    const p = await (await b.newContext({ viewport: { width: W, height: 900 }, colorScheme: scheme })).newPage();
    for (const path of paths) {
      const res = [];
      for (const origin of [A, B]) {
        await p.goto(origin + path, { waitUntil: 'networkidle', timeout: 180000 }); await p.waitForTimeout(2500);
        res.push(await p.evaluate((P) => { const o = {}; let n = 0;
          for (const e of document.querySelectorAll('body *')) { if (e.closest('.mdmark')) continue;
            for (const pseudo of [null, '::before', '::after']) { const s = getComputedStyle(e, pseudo);
              if (pseudo && (s.content === 'none' || s.content === 'normal')) continue;
              const v = {}; for (const k of P) v[k] = s.getPropertyValue(k);
              o[e.tagName + '#' + (n++) + (pseudo || '')] = v; } }
          return o; }, P));
      }
      const [x, y] = res; let diff = 0;
      const keys = Object.keys(x); if (keys.length !== Object.keys(y).length) console.log(scheme, W, path, 'element count', keys.length, Object.keys(y).length);
      for (const k of keys) { if (!y[k]) continue; for (const q of P) if (x[k][q] !== y[k][q]) { diff++; if (diff <= 5) console.log(scheme, W, path, k, q, x[k][q], '->', y[k][q]); } }
      console.log(scheme, W, path, 'elements', keys.length, 'diffs', diff); total += diff;
    }
  }
  console.log('total diffs', total);
  await b.close();
})();
