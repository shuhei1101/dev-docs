const { chromium } = require('/mnt/c/Users/shuhe/repo/mdmark/.claude/worktrees/develop/node_modules/playwright');
const variants = {
  base_revertlayer: '@layer base { .mdmark [hidden] { display: revert-layer !important; } }',
  unlayered_revertlayer: '.mdmark [hidden] { display: revert-layer !important; }',
  newlayer_first: '@layer mdreset { .mdmark [hidden] { display: revert-layer !important; } }',
  base_unset_rule_scope: '@layer base { .mdmark [hidden]:where(:not([hidden="until-found"])) { display: revert-layer !important; } }',
};
(async()=>{const b=await chromium.launch();const p=await (await b.newContext({viewport:{width:1440,height:900}})).newPage();
await p.goto('http://127.0.0.1:8781/dev-docs/docs/interface/IF-155-1',{waitUntil:'networkidle',timeout:180000});await p.waitForTimeout(2000);
console.log('layers order:', await p.evaluate(()=>[...document.styleSheets].map(s=>{try{return [...s.cssRules].filter(r=>r.constructor.name==='CSSLayerStatementRule'||r.constructor.name==='CSSLayerBlockRule').slice(0,6).map(r=>r.nameList?('stmt:'+r.nameList.join(',')):('block:'+r.name)).join(' ')}catch(e){return 'x'}})));
for (const [k,css] of Object.entries(variants)) {
  const h = await p.addStyleTag({content: k==='newlayer_first' ? css : css});
  if (k==='newlayer_first') await p.evaluate(()=>{const s=document.head.lastElementChild; document.head.prepend(s);});
  console.log(k, await p.evaluate(()=>getComputedStyle(document.querySelector('.mdmark .mdmark-diagram-legend')).display));
  await h.evaluate(n=>n.remove());
}
await b.close();})();
