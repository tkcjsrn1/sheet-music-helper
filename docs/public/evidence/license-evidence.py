import hashlib, importlib.metadata as md, json, sys
from pathlib import Path
root=Path('F:/akbo-data/tmp/public-prep-20261026'); out=root/'docs/public'
names=['opencv-python','numpy','Pillow','scipy','customtkinter','pyinstaller','darkdetect','packaging','altgraph','pefile','pywin32-ctypes','pyinstaller-hooks-contrib','PyMuPDF','verovio','music21','CairoSVG']
rows=[]
for name in names:
 try:
  d=md.distribution(name)
  rows.append(dict(name=name,version=d.version,license=d.metadata.get('License'),license_expression=d.metadata.get('License-Expression'),homepage=d.metadata.get_all('Project-URL') or [],license_files=[str(p) for p in d.files or [] if 'license' in str(p).lower() or 'copying' in str(p).lower()]))
 except md.PackageNotFoundError: rows.append(dict(name=name,installed=False))
fonts=[]
d=md.distribution('customtkinter'); fontroot=Path(d.locate_file('customtkinter/assets/fonts'))
from fontTools.ttLib import TTFont
for p in sorted(fontroot.rglob('*')):
 if p.suffix.lower() not in ('.ttf','.otf'): continue
 with TTFont(p,lazy=True) as font:
  texts={str(n):sorted(set(r.toUnicode() for r in font['name'].names if r.nameID==n)) for n in (0,1,2,5,13,14)}
 fonts.append(dict(path=str(p.relative_to(fontroot.parent.parent)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),name_records=texts))
from PyInstaller.archive.readers import CArchiveReader
exe=Path('F:/akbo-data/tmp/beta-features-20261023/dist/d69a025a063f-20261023-200643-946483/악보헬퍼.exe')
archive=CArchiveReader(str(exe))
entries=sorted(archive.toc)
result=dict(python=sys.version,packages=rows,customtkinter_fonts=fonts,beta_exe_font_entries=[p for p in entries if p.lower().endswith(('.ttf','.otf'))],excluded_pdf_entries=[p for p in entries if 'pymupdf' in p.lower() or p.lower().startswith('fitz')],notices_sha256=hashlib.sha256((root/'THIRD_PARTY_NOTICES.txt').read_bytes()).hexdigest())
(out/'LICENSE_EVIDENCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(fonts=fonts,beta_fonts=result['beta_exe_font_entries'],pdf_entries=result['excluded_pdf_entries'],packages=[(p['name'],p.get('version'),p.get('license_expression') or p.get('license')) for p in rows]),ensure_ascii=False,indent=2))
