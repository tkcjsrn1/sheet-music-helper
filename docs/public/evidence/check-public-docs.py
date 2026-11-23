import collections,json,re,subprocess
from pathlib import Path
r=Path('F:/akbo-data/tmp/public-prep-20261026'); d=r/'docs/public'; rows=[json.loads(s) for s in (d/'IMAGE_HISTORY.jsonl').read_text(encoding='utf8').splitlines()]; summary=json.loads((d/'IMAGE_HISTORY_SUMMARY.json').read_text(encoding='utf8'))
assert len(rows)==summary['blobs']==597
assert len({p for a in rows for p in a['paths']})==summary['historical_paths']==659
assert len({p for a in rows for p in a['current_main_paths']})==summary['current_main_paths']==601
assert dict(collections.Counter(a['category'] for a in rows))==summary['categories']
assert all('공개 제외' in a['decision'] for a in rows)
links=[]
for p in list(d.glob('*.md'))+list((r/'docs/review/dense_analysis_20261026').glob('*.md')):
 for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
  if link.startswith(('https://','http://','#')): continue
  assert (p.parent/link.split('#')[0]).is_file(),(str(p),link)
  links.append(link)
product=['gui.py','main.py','modules','tests','requirements.txt','악보헬퍼.spec','build.py','assets','AGENTS.md','CLAUDE.md','docs/DECISIONS.md','docs/COLLAB.md']
changes=subprocess.check_output(['git','diff','--name-only','HEAD','--',*product],cwd=r).decode().strip(); assert not changes,changes
assert not subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*product],cwd=r).strip()
result=dict(inventory_rows=len(rows),local_links_checked=len(links),all_public_decisions_held=True,product_and_protected_diff=[],base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r).decode().strip())
(d/'evidence/document-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False))
