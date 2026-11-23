"""측정용 spec 사본 두 개로 PDFium 동봉 시 exe 크기를 비교한다. 제품 도입 아님."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    package=args.package.resolve();output=args.output.resolve()
    assert output.is_relative_to(ROOT/'output'), '실험 빌드는 저장소 output 아래만 허용한다'
    licenses=next(package.glob('pypdfium2-*.dist-info'))/'licenses'
    assert len([p for p in licenses.rglob('*') if p.is_file()])==19
    output.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'악보헬퍼.spec').read_text(encoding='utf-8')
    source=source.replace("['gui.py']",repr([str(ROOT/'gui.py')]))
    source=source.replace("[('assets/icon.ico', 'assets')]",repr([(str(ROOT/'assets/icon.ico'),'assets')]))
    source=source.replace('pathex=[]','pathex='+repr([str(ROOT),str(package)]))
    source=source.replace(r"icon=['assets\\icon.ico']",'icon='+repr([str(ROOT/'assets/icon.ico')]))
    source=source.replace(r"version='assets\\version_info.txt'",'version='+repr(str(ROOT/'assets/version_info.txt')))
    rows=[]
    for kind in ('base','pdfium'):
        text=source
        if kind=='pdfium':
            payload="tmp_pdf = collect_all('pypdfium2')\ndatas += tmp_pdf[0]; binaries += tmp_pdf[1]; hiddenimports += tmp_pdf[2]\ndatas.append(("+repr(str(licenses))+", 'pdfium-licenses'))\n"
            text=text.replace('a = Analysis(',payload+'\na = Analysis(',1)
        spec=output/f'{kind}.spec';spec.write_text(text,encoding='utf-8')
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONPATH=str(package))
        with (output/f'{kind}-build.log').open('w',encoding='utf-8') as log:
            proc=subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm',
                '--workpath',str(output/f'{kind}-work'),'--distpath',str(output/kind),str(spec)],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        assert proc.returncode==0,f'{kind} 빌드 실패: {output/kind}'
        exe=output/kind/'악보헬퍼.exe';blob=exe.read_bytes()
        reader=CArchiveReader(str(exe))
        toc=[p.replace('\\','/') for p in reader.toc]
        pdf_dll=[p for p in toc if p.endswith('pdfium.dll')]
        notice=[p for p in toc if p.startswith('pdfium-licenses/')]
        assert bool(pdf_dll)==(kind=='pdfium')
        assert len(notice)==(19 if kind=='pdfium' else 0)
        rows.append(dict(kind=kind,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),
                         pdfium_dll=pdf_dll,license_files=len(notice)))
        print(kind,len(blob),'고지',len(notice),flush=True)
    report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                variants=rows,delta_bytes=rows[1]['bytes']-rows[0]['bytes'])
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    main()
