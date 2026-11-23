import gzip,json
from pathlib import Path
root=Path.cwd();rows=json.loads(gzip.decompress((root/'docs/releases/pending-329-333/approved-strict.json.gz').read_bytes()))
for row in rows:
 p=next((root/'output/release-1cbc0d8'/(row['case']+'_exe')).glob('*_라벨.json'))
 assert json.loads(p.read_text(encoding='utf-8'))==row['actual'],row['case']
 print(row['case'],'실제 exe 전체JSON 승인 strict 일치',flush=True)
