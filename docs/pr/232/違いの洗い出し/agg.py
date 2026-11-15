import json,collections,sys
d=json.load(open(sys.argv[1]))
agg=collections.defaultdict(collections.Counter)
for n,v in d.items():
  e,g=v['e'],v['d']
  for k,a in e.items():
    b=g.get(k)
    if b is None: continue
    tag=k.split('|')[0]
    for p in a:
      if a[p]==b[p]: continue
      side=p.split('-')[1] if p.startswith('border-') else None
      if side and p!=f'border-{side}-width':
        if a.get(f'border-{side}-width','0px')=='0px' and b.get(f'border-{side}-width','0px')=='0px': continue
        if a.get(f'border-{side}-style')=='none' and b.get(f'border-{side}-style')=='none': continue
      if p=='list-style-type' and a.get('display')!='list-item' and b.get('display')!='list-item': continue
      agg[(tag,p)][(a[p][:50],b[p][:50])]+=1
for (tag,p),c in sorted(agg.items()):
  for (a,b),m in c.most_common(1): print(f'{tag[:38]:38s} {p:20s} E={a!r} D={b!r} x{sum(c.values())}')
