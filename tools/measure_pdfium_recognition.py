"""C-12 측정 전용: PDFium 17쪽을 같은 제품 CLI 경로에 넣어 대조한다."""
import argparse
from collections import Counter
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import test_golden_regression as G


def worker(args):
    sys.path.insert(0,str(args.package.resolve()))
    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    import main as pipeline

    def load_pdf(path,pdf_page=0,pdf_dpi=300):
        with pdfium.PdfDocument(path) as document:
            with closing(document[pdf_page]) as page:
                bitmap=page.render(scale=pdf_dpi/72)
                try:
                    rgb=np.array(bitmap.to_pil().convert('RGB'))
                finally:
                    bitmap.close()
        return cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)

    sys.argv=['main.py',str(ROOT/'test_scores'/args.pdf),'--page',str(args.page),
              '--no-debug','--output-dir',str(args.output.parent),'--save-labels',str(args.output)]
    # 파일은 수정하지 않는다. 별도 프로세스에서 입력 로드만 PDFium으로 대체한다.
    with patch('modules.preprocess.load_image',side_effect=load_pdf):
        pipeline.main()


def measure(case,package,folder):
    tag,pdf,page=case
    original=G.run_product(pdf,page,str(folder/'fitz'))
    first,context=G.pdf_lines(original)
    expected=Path(G.snapshot_path(tag)).read_text(encoding='utf-8').splitlines()
    expected=[x for x in expected if not x.startswith('#')]
    assert first==expected, f'{tag}: PyMuPDF 대조가 기존 제품 스냅샷과 다르다'
    dest=folder/'pdfium'/f'{tag}.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    proc=subprocess.run([sys.executable,__file__,'--worker','--package',str(package),
        '--pdf',pdf,'--page',str(page),'--output',str(dest)],cwd=ROOT,
        env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,
        encoding='utf-8',errors='replace',timeout=300)
    row=dict(page=tag,pdf=pdf,page_index=page,pymupdf_count=len(first),control_snapshot_equal=True,
             pymupdf_staves=len(original['staves']),pymupdf_key=original['music'])
    if proc.returncode or not dest.is_file():
        row.update(status='실패',error=(proc.stdout+proc.stderr)[-2000:].replace(str(ROOT),'<저장소>'))
    else:
        second_doc=json.loads(dest.read_text(encoding='utf-8'))
        second,context2=G.pdf_lines(second_doc)
        a,b=Counter(first),Counter(second)
        row.update(status='성공',pdfium_count=len(second),
            only_pymupdf=sorted((a-b).elements()),only_pdfium=sorted((b-a).elements()),
            context_equal=context==context2,pymupdf_context=context,pdfium_context=context2,
            pdfium_staves=len(second_doc['staves']),pdfium_key=second_doc['music'],
            pymupdf_size=[original['source']['width'],original['source']['height']],
            pdfium_size=[second_doc['source']['width'],second_doc['source']['height']])
    print(tag,row['status'],row['pymupdf_count'],row.get('pdfium_count'),flush=True)
    return row


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--pdf');parser.add_argument('--page',type=int,default=0)
    args=parser.parse_args()
    args.package=args.package.resolve();args.output=args.output.resolve()
    if args.worker:
        return worker(args)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pdfium-17-',dir=ROOT/'output') as tmp:
        folder=Path(tmp);(folder/'fitz').mkdir()
        with ThreadPoolExecutor(2) as pool:
            rows=list(pool.map(lambda case:measure(case,args.package,folder),G.PDF_PAGES))
    assert len(rows)==17 and all(r['control_snapshot_equal'] for r in rows)
    report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        dpi=300,pypdfium2='5.13.0',pdfium=json.loads((args.package/'pypdfium2_raw/version.json').read_text()),
        columns=['staff','x','y','pitch','accidental','text','confidence'],pages=rows)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PyMuPDF 기존 스냅샷 17/17 완전 일치. 비교 자료:',args.output.name,flush=True)

if __name__=='__main__':
    main()
