from pathlib import Path
import importlib.metadata as md,json
from PyInstaller.archive.readers import CArchiveReader
root=Path('F:/akbo-data/tmp/public-prep-20261026'); p=root/'docs/public/LICENSE_EVIDENCE.json'; a=json.loads(p.read_text(encoding='utf8'))
r=CArchiveReader('F:/akbo-data/tmp/beta-features-20261023/dist/d69a025a063f-20261023-200643-946483/악보헬퍼.exe'); pyz=r.open_embedded_archive('PYZ.pyz')
modules=sorted({n.split('.')[0] for n in pyz.toc}); mapping=md.packages_distributions(); names=sorted({d for n in modules for d in mapping.get(n,[])})
rows=[]
for n in names:
 d=md.distribution(n); m=d.metadata
 rows.append(dict(name=n,version=d.version,license_expression=m.get('License-Expression'),license_header=(m.get('License') or '').splitlines()[:2],matching_modules=[x for x in modules if n in mapping.get(x,[])],license_files=[str(f) for f in d.files or [] if 'license' in str(f).lower() or 'copying' in str(f).lower()]))
a['archive_pyz_distribution_candidates']=rows; a['archive_pyz_unmapped_top_modules']=[n for n in modules if n not in mapping]
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print('PYZ 대응 배포판',len(rows)); print([(x['name'],x['version']) for x in rows]); print('추가 개발패키지 포함',set(('music21','verovio','cairosvg','pymupdf'))&{x['name'].lower() for x in rows})
