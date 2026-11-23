from pathlib import Path
import hashlib,importlib.metadata as md,json,re,urllib.request
from urllib.parse import urlparse
from fontTools.ttLib import TTFont
R=Path.cwd(); OUT=R/'docs/public/notices-20261026';OUT.mkdir(parents=True,exist_ok=True)
OLD=json.loads((R/'docs/public/LICENSE_EVIDENCE.json').read_text(encoding='utf8'))
SOURCES={};TEXTS={}
def add(origin,raw):
 text=raw.decode('utf-8-sig').replace('\r\n','\n');assert text.strip() and '\0' not in text,origin
 key=hashlib.sha256(text.encode()).hexdigest()
 if key not in SOURCES:SOURCES[key]=dict(id=key,origins=[],normalized_sha256=key);TEXTS[key]=text
 SOURCES[key]['origins'].append(dict(path=origin,raw_sha256=hashlib.sha256(raw).hexdigest()))
 return key
base=add('repository:THIRD_PARTY_NOTICES.txt',(R/'THIRD_PARTY_NOTICES.txt').read_bytes())
packages=[];by_path={}
pattern=re.compile(r'^(?:licen[cs]e|copying|notice)(?:[._-].*)?$',re.I)
for row in OLD['archive_pyz_distribution_candidates']:
 d=md.distribution(row['name']);assert d.version==row['version'],row['name']
 ids=[]
 for f in sorted(d.files or [],key=str):
  if not pattern.fullmatch(Path(str(f)).name):continue
  p=Path(d.locate_file(f));key=add(str(f).replace('\\','/'),p.read_bytes());by_path[str(f).replace('\\','/')]=key;ids.append(key)
 assert ids,row['name']
 packages.append(dict(name=row['name'],version=d.version,status='원문 확인',source_ids=sorted(set(ids)),version_in_actual_binary='미확인(설치본 대응 후보)'))
# Certifi 고지는 MPL 본문 링크이므로 공식 배포자의 전문도 포함한다.
url='https://www.mozilla.org/media/MPL/2.0/index.815ca599c9df.txt'
cache=Path('F:/akbo-data/tmp/license-followup-20261026/MPL-2.0.txt')
if cache.is_file():raw=cache.read_bytes()
else:
 with urllib.request.urlopen(url,timeout=30) as response:
  assert response.status==200 and urlparse(response.url).hostname=='www.mozilla.org'
  raw=response.read(200001)
 assert len(raw)<=200000 and b'Mozilla Public License Version 2.0' in raw
 cache.write_bytes(raw)
mpl=add(url,raw)
next(p for p in packages if p['name']=='certifi')['source_ids'].append(mpl)
apache=next(k for path,k in by_path.items() if path.startswith('packaging-') and path.endswith('/LICENSE.APACHE'))
matplotlib=by_path['matplotlib-3.11.2.dist-info/LICENSE']
deja=by_path['matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU'];stix=by_path['matplotlib/mpl-data/fonts/ttf/LICENSE_STIX']
assert 'SIL OPEN FONT LICENSE Version 1.1' in TEXTS[stix]
assert "Files: matplotlib/mpl-data/fonts/ttf/cm*.ttf" in TEXTS[matplotlib]
assert "Files: matplotlib/mpl-data/fonts/ttf/LastResortHE-Regular.ttf" in TEXTS[matplotlib]
fontmeta=[]
for item in OLD['archive_font_hashes']:
 with TTFont(Path('C:/Users/정혁/Desktop/악보헬퍼/venv/Lib/site-packages')/item['entry'],lazy=True) as font:
  names={str(n):sorted({x.toUnicode() for x in font['name'].names if x.nameID==n}) for n in (0,13)}
 fontmeta.append(dict(entry=item['entry'],sha256=item['sha256'],names=names))
fonts=[];installed=Path('C:/Users/정혁/Desktop/악보헬퍼/venv/Lib/site-packages')
for row in fontmeta:
 entry=row['entry'].replace('\\','/');assert hashlib.sha256((installed/entry).read_bytes()).hexdigest()==row['sha256']
 if 'Roboto/' in entry:family,license,ids='Roboto','Apache-2.0',[apache]
 elif 'DejaVu' in entry:family,license,ids='DejaVu','Bitstream Vera + Arev',[deja]
 elif 'STIX' in entry:family,license,ids='STIX','OFL-1.1',[stix,matplotlib]
 elif 'LastResort' in entry:family,license,ids='LastResort','OFL-1.1',[matplotlib]
 elif Path(entry).name.startswith('cm'):family,license,ids='BaKoMa','BaKoMa Fonts Licence',[matplotlib]
 else:family,license,ids='CustomTkinter shapes','미확인',[]
 copyrights='\n'.join(t for t in row['names']['0'] if t.strip())
 copyright_source=add('font-name0:'+entry,copyrights.encode()) if copyrights else None
 fonts.append(dict(entry=entry,sha256=row['sha256'],family=family,license=license,status='원문 확인' if ids else '미확인',source_ids=ids,copyright_source=copyright_source,embedded_license=row['names']['13'] if family=='Roboto' else 'name-table 확인, 원문은 source_ids 참조'))
assert len(fonts)==43 and len(packages)==21 and sum(f['status']=='원문 확인' for f in fonts)==42
info=json.loads(Path('F:/akbo-data/tmp/beta-features-20261023/dist/d69a025a063f-20261023-200643-946483/build-info.json').read_text(encoding='utf8'))
for p in packages:
 frozen=next((v for n,v in info['versions'].items() if n.lower().replace('_','-')==p['name'].lower().replace('_','-')),None)
 if frozen==p['version']:p['version_in_actual_binary']='빌드 기록 버전 일치'
header='''악보헬퍼 THIRD_PARTY_NOTICES 초안 — 2026-10-26\n공개·재배포 승인 아님. 기존 고지와 후보21개 배포판/폰트43개의 원문을 합류했다.\n원문 확인: 후보21/21, 폰트42/43. CustomTkinter shapes의 개별 적용 범위는 미확인.\n설치본 원문과 실제 동봉 코드 전체의 라이선스 완결성은 다르다.\nMPL 소스 제공 방식·native 구성요소 전체·미확인 항목은 MATCHED_LICENSES.md 참조.\n영어 원문은 번역/재허가 없이 보존하며 이 파일은 현재 exe에 동봉하지 않았다.\n\n'''
header+='후보 구성요소/폰트 원문 대응 (전체 내용/상태는 MATCHED_LICENSES.json):\n'
for p in packages:header+=p['name']+' '+p['version']+' -> '+','.join(k[:16] for k in p['source_ids'])+'\n'
for f in fonts:header+=f['entry']+' : '+f['license']+' ['+f['status']+'] -> '+','.join(k[:16] for k in f['source_ids'])+'\n'
body=bytearray(header.encode())
ordered=[base]+[k for k in SOURCES if k!=base]
for key in ordered:
 data=TEXTS[key].encode();found=body.find(data)
 if found<0:
  body.extend(('\n\n===== SOURCE '+key+' =====\n').encode());found=len(body);body.extend(data)
 SOURCES[key].update(offset=found,length=len(data))
assert all(hashlib.sha256(body[s['offset']:s['offset']+s['length']]).hexdigest()==key for key,s in SOURCES.items())
(OUT/'THIRD_PARTY_NOTICES_DRAFT.txt').write_bytes(body)
audit=dict(schema=1,beta_commit=info['commit'],draft_sha256=hashlib.sha256(body).hexdigest(),packages=packages,fonts=fonts,sources=list(SOURCES.values()),unconfirmed=['CustomTkinter shapes 개별 적용 범위','빌드 기록에 없는 후보17개 배포판의 실제 binary 버전','MPL 소스 제공/수정 대응의 배포 절차','native DLL/시스템 구성요소 전체 완결성'],generated_from='설치본 license 원문과 #443 actual archive 목차/해시, exe 실행0')
(OUT/'MATCHED_LICENSES.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('후보',len(packages),'폰트',len(fonts),'폰트 원문확인42/미확인1','원문 block',len(SOURCES),'고지 bytes',len(body))
