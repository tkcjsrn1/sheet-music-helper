import collections, datetime, hashlib, json, re, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1]); out=root/'docs/public'; out.mkdir(parents=True,exist_ok=True)
def git(*args, data=None):
 return subprocess.run(['git',*args],cwd=root,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
exts=('png','jpg','jpeg','bmp','tif','tiff','webp','gif','svg','ico','pdf','mxl','musicxml','mei')
def parse(raw):
 toks=raw.split(b'\0'); items=[]; i=0
 while i<len(toks):
  token=toks[i].lstrip(b'\r\n'); i+=1
  if not token: continue
  m=re.fullmatch(rb':\d{6} \d{6} ([0-9a-f]{40}) ([0-9a-f]{40}) ([A-Z])',token)
  assert m,repr(token[:150])
  assert i<len(toks) and toks[i]
  path=toks[i].decode('utf-8'); i+=1
  for oid in m.group(1,2):
   if oid!=b'0'*40: items.append((oid.decode(),path))
 return items
# NUL 구분 경로는 공백·한글·개행이 있어도 쪼개지지 않아야 한다.
a='a'*40; b='b'*40
assert parse(f':100644 100644 {a} {b} M\0한 글\n.png\0'.encode())==[(a,'한 글\n.png'),(b,'한 글\n.png')]
paths=collections.defaultdict(set)
raw=git('log','--all','--root','--full-history','-m','--no-renames','--no-ext-diff','--format=','--raw','--no-abbrev','-z','--',*[f':(icase)*.{e}' for e in exts])
for oid,path in parse(raw): paths[oid].add(path)
current=collections.defaultdict(set)
for record in git('ls-tree','-r','-z','origin/main').split(b'\0'):
 if not record: continue
 meta,path=record.split(b'\t',1); mode,kind,oid=meta.split()
 if kind==b'blob': current[oid.decode()].add(path.decode())
sizes={}
for line in git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',data=('\n'.join(sorted(paths))+'\n').encode()).splitlines():
 oid,kind,size=line.split(); assert kind==b'blob'; sizes[oid.decode()]=int(size)
def classify(names):
 joined=' '.join(names).lower()
 if all(p in ('docs/review/practice_controls_20261026/01_selected_double_flat.png','docs/review/practice_controls_20261026/02_chord_and_keys.png','docs/review/practice_controls_20261026/03_double_sharp_playback.png') for p in names):
  return '자체 합성 GUI 캡처·공개 승인 대기','draft #442 tests/test_gui_piano_widget.py 생성, 악보 원본 사용0','승인 전 공개 제외'
 if any(s in joined for s in ('aoharu','아오하루','kakaotalk','카카오')):
  return '저작권·허락 확인 필요','현대곡/개인 입력 이름; 파생 그림도 원본 권리를 잇는다','공개 제외'
 if any(p.startswith('test_scores/verovio/') for p in names):
  return '공개 악곡 기반 렌더·인코딩 권리 미확인','test_scores/verovio/README.md: music21 개별 인코딩 권리 별도','공개 제외'
 if any('synthetic' in p.lower() for p in names):
  return '합성 후보·원본/생성기 확인 필요','경로 단서뿐; 사진 열화/라벨 합성은 원본 권리를 잇을 수 있다','판정 보류·공개 제외'
 if any(s in joined for s in ('bach','chopin','clara','schubert','schumann','beethoven','mozart','바흐','쇼팽')):
  return '공개 악곡 주장·판본 권리 미확인','파일명 단서; 작곡 저작권 만료와 스캔/편집/인코딩 권리는 별개','판정 보류·공개 제외'
 if any(p.startswith('assets/') for p in names):
  return '아이콘 등 출처 확인 필요','직접 제작/제공 라이선스 증빙 미수집','판정 보류·공개 제외'
 return '미확인(그림/화면 포함)','경로만으로 원본 권리/개인정보를 확정할 수 없음','판정 보류·공개 제외'
rows=[]
for oid,names in sorted(paths.items()):
 names=sorted(names); category,evidence,decision=classify(names)
 rows.append(dict(blob=oid,bytes=sizes[oid],paths=names,current_main_paths=sorted(current[oid]),category=category,evidence=evidence,decision=decision))
assert len(rows)==len(paths)==len(sizes)
all_paths=set(p for row in rows for p in row['paths'])
summary=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),main=git('rev-parse','origin/main').decode().strip(),head=git('rev-parse','HEAD').decode().strip(),scope='로컬 도달 가능 refs 전체',extensions=exts,blobs=len(rows),historical_paths=len(all_paths),current_main_blobs=sum(bool(r['current_main_paths']) for r in rows),current_main_paths=len(set(p for r in rows for p in r['current_main_paths'])),total_blob_bytes=sum(sizes.values()),categories=dict(collections.Counter(r['category'] for r in rows)),non_image_blobs=sum(any(Path(p).suffix.lower() in ('.pdf','.mxl','.musicxml','.mei') for p in r['paths']) for r in rows))
summary['scope']='로컬에서 도달 가능한 모든 refs; reflog·도달 불가능 object·원격 삭제 refs는 제외'
(out/'IMAGE_HISTORY.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
(out/'IMAGE_HISTORY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'INVENTORY_REFS.txt').write_bytes(git('show-ref'))
print(json.dumps(summary,ensure_ascii=False,indent=2))
