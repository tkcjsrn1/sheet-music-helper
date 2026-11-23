# -*- coding: utf-8 -*-
"""빈 머리 픽스처의 소스·PDF 링크 정답. OMR 결과를 정답으로 쓰지 않는다."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('beam_source_builder',ROOT.parent/'beams/build_fixture.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
SIZES=(16,20,24)

def expected(size):
    base.SOURCE=ROOT/'sources'/f'hollow_{size}.ly'
    base.PDF=ROOT/'pdf'/f'hollow_{size}.pdf'
    base.NOTE=re.compile(r"([a-g])([,']*)(1|2)(\[|\])?")
    result=base.expected_from_pdf()
    result['source']=f'sources/hollow_{size}.ly'
    result['pdf']=f'pdf/hollow_{size}.pdf'
    result['staff_size']=size
    assert base.SOURCE.read_text(encoding='utf-8').count(r'\key c \major')==2
    result['key_signature']={'symbol':'','count':0,'letters':[]}
    for note in result['notes']:
        if note['duration_denominator']==1:note['stem']=None
    result['engraving_family']='LilyPond 2.26.0 / Emmentaler; 서로 다른 폰트 계열 아님'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lilypond');p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check and a.lilypond:p.error('check와 조판을 함께 실행하지 않는다')
    if a.lilypond:
        version=subprocess.check_output([a.lilypond,'--version']).decode('utf-8',errors='replace')
        if 'GNU LilyPond 2.26.0' not in version:raise ValueError('LilyPond 버전 불일치')
    for size in SIZES:
        if a.lilypond:subprocess.run([a.lilypond,'-o',str(ROOT/'pdf'/f'hollow_{size}'),str(ROOT/'sources'/f'hollow_{size}.ly')],check=True)
        data=expected(size);path=ROOT/f'expected_{size}.json'
        if a.check:
            assert data==json.loads(path.read_text(encoding='utf-8'))
        else:path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(size,len(data['notes']), '소스/PDF 대응')
if __name__=='__main__':main()
