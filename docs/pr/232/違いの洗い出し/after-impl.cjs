// 実装した画面（引数の origin）と mdmark export の HTML を、同じ条件で箇所ごとに撮る
const { chromium } = require('/mnt/c/Users/shuhe/repo/mdmark/.claude/worktrees/develop/node_modules/playwright');
const base = '/mnt/c/Users/shuhe/repo/dev-docs/.claude/worktrees/mdcompare-232';
const [origin, outDir] = [process.argv[2], process.argv[3]];
const legendUl = () => [...document.querySelectorAll('.mdmark ul')].find(u => !u.closest('[class*=toc]') && !u.className);
const items = [
  ['list', 'IF-155-1', '/dev-docs/docs/interface/IF-155-1', legendUl],
  ['h4', 'IF-155-1', '/dev-docs/docs/interface/IF-155-1', () => document.querySelector('.mdmark h4')],
  ['pre', 'CLI', '/dev-docs/docs/guide/files/docs/guide/CLI.md', () => document.querySelector('.mdmark pre')],
  ['diagram-tools', 'IF-155-1', '/dev-docs/docs/interface/IF-155-1', () => document.querySelector('.mdmark .mdmark-diagram-tool').parentElement],
  ['top', 'SCR-155-1', '/dev-docs/docs/screen/SCR-155-1', null],
];
(async () => {
  const b = await chromium.launch();
  for (const [W, H, scheme] of [[1440, 900, 'light'], [1440, 900, 'dark'], [390, 844, 'light']]) {
    const p = await (await b.newContext({ viewport: { width: W, height: H }, colorScheme: scheme })).newPage();
    for (const [name, doc, url, fn] of items) {
      for (const [src, u] of [['export', 'file://' + base + '/out/' + doc + '.html'], ['impl', origin + url]]) {
        await p.goto(u, { waitUntil: 'networkidle', timeout: 180000 }); await p.waitForTimeout(2500);
        const file = `${outDir}/${name}-${W}-${scheme}-${src}.png`;
        if (!fn) { await p.screenshot({ path: file }); continue; }
        const el = (await p.evaluateHandle(fn)).asElement();
        await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(500);
        const box = await el.boundingBox(); const pad = 16;
        await p.screenshot({ path: file, clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: Math.min(W - Math.max(0, box.x - pad), Math.min(760, box.width + pad * 2)), height: Math.min(420, box.height + pad * 2 + (name === 'h4' ? 120 : 0)) } });
      }
    }
    await p.context().close();
  }
  await b.close();
})();
