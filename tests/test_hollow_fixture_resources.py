"""온음표 리소스는 소스/PDF 링크와 저장 정답만 검사한다. OMR 미사용."""
from collections import Counter
import importlib.util
import json
from pathlib import Path

FIXTURE=Path(__file__).parent/'fixtures/hollow_notes'


def main():
    spec=importlib.util.spec_from_file_location('hollow_resources',FIXTURE/'build_fixture.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    for size in builder.SIZES:
        actual=builder.expected(size)
        saved=json.loads((FIXTURE/f'expected_{size}.json').read_text(encoding='utf-8'))
        assert actual==saved, f'{size}: 소스/PDF 해시 또는 링크 정답 불일치'
        notes=actual['notes']
        assert Counter(n['duration_denominator'] for n in notes)=={1:12,2:24}
        assert len({n['id'] for n in notes})==36 and actual['beams']==[]
        assert {n['staff_index'] for n in notes}==set(range(6))
        assert actual['key_signature']==dict(symbol='',count=0,letters=[])
        assert all(n['stem'] is None for n in notes if n['duration_denominator']==1)
        assert all(len(n['center_300dpi'])==2 and len(n['bbox_pt'])==4 for n in notes)
        assert (FIXTURE/'pdf'/f'hollow_{size}.mid').read_bytes().startswith(b'MThd')
        print(f'{size}: 소스/PDF 링크 정답36개·MIDI 리소스 확인')
    print('Emmentaler 세 크기 리소스 무결성 통과 (인식 성능 측정 아님)')

if __name__=='__main__':main()
