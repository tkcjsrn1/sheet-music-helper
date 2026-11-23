import hashlib, importlib.metadata as md, json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
p=Path('F:/akbo-data/tmp/public-prep-20261026/docs/public/LICENSE_EVIDENCE.json'); a=json.loads(p.read_text(encoding='utf-8'))
r=CArchiveReader('F:/akbo-data/tmp/beta-features-20261023/dist/d69a025a063f-20261023-200643-946483/악보헬퍼.exe')
base=Path('C:/Users/user/Desktop/악보헬퍼/venv/Lib/site-packages')
fonts=[]
for name in a['beta_exe_font_entries']:
 local=base/Path(name); data=r.extract(name)
 fonts.append(dict(entry=name,sha256=hashlib.sha256(data).hexdigest(),local_matches=local.is_file() and hashlib.sha256(local.read_bytes()).digest()==hashlib.sha256(data).digest()))
a['archive_font_hashes']=fonts
for name in ('matplotlib','fonttools','contourpy','cycler','kiwisolver','pyparsing','python-dateutil','six'):
 d=md.distribution(name); a['packages'].append(dict(name=name,version=d.version,license_expression=d.metadata.get('License-Expression'),license_header=(d.metadata.get('License') or '').splitlines()[:3],license_files=[str(f) for f in d.files or [] if 'license' in str(f).lower() or 'copying' in str(f).lower()]))
a['font_notice_matches']={term:term.lower() in (p.parents[2]/'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf-8').lower() for term in ('Roboto','DejaVu','STIX','matplotlib','CustomTkinter_shapes_font')}
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('폰트',len(fonts),'로컬 동일',sum(f['local_matches'] for f in fonts)); print(a['font_notice_matches'])
print([(x['name'],x['version'],x.get('license_expression'),x.get('license_header')) for x in a['packages'][-8:]])
