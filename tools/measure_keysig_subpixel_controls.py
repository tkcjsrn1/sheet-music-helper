# -*- coding: utf-8 -*-
"""C-11: 원본이 정한 조표 대조군과 막대 열의 재표본화 변화를 기록한다.

제품 판정은 바꾸지 않는다. 측정 완료와 인식 성공은 다른 결과다.
--require-preservation은 조표 변화가 한 건이라도 있으면 종료 코드 1을 낸다.
"""
import argparse
from dataclasses import asdict
import hashlib
import gzip
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import tempfile
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules import clef_keysig
from modules.preprocess import load_image, preprocess

PHASES = (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)
SYMBOLS = {'': '', 'sharp': '♯', 'flat': '♭'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def max_run(column):
    """제품과 같은 연속 길이를 시작·끝 좌표와 함께 잰다."""
    # 길이가 같으면 첫 구간을 고른다. 구간의 오른쪽 끝은 포함하지 않는다.
    padded = np.r_[False, np.asarray(column, dtype=bool), False].astype(np.int8)
    starts = np.flatnonzero(np.diff(padded) == 1)
    ends = np.flatnonzero(np.diff(padded) == -1)
    if not len(starts):
        return [0, None, None]
    i = int(np.argmax(ends - starts))
    return [int(ends[i] - starts[i]), int(starts[i]), int(ends[i])]


def inspect_window(band, sp, x0, x1, r0, r1, result):
    """실제 _find_bars 호출의 창을 받는다. 헤더 창을 따로 추정하지 않는다."""
    row = dict(window=[x0, x1, r0, r1], spacing=sp,
               bars=[[float(x), float(y)] for x, y in result[0]], holes=result[1])
    if x1 - x0 < sp * 0.5:
        row['columns'] = []
        return row
    raw = band[r0:r1, x0:x1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    closed = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, kernel)
    row['height_limits_px'] = [sp * 1.6, sp * 3.4]
    row['columns'] = []
    for i in range(raw.shape[1]):
        before, after = max_run(raw[:, i]), max_run(closed[:, i])
        # 창 전체를 기록해 통과한 가장자리 열 옆의 긴 기둥도 숨기지 않는다.
        row['columns'].append(dict(x=x0+i, raw=before, closed=after,
                                   eligible=bool(sp * 1.6 <= after[0] <= sp * 3.4)))
    return row


def trace_headers(result):
    """읽기 전용 래퍼. 원래 반환값을 그대로 돌려주고 비계측 실행과 전수 대조한다."""
    plain = clef_keysig.analyze_staves(result)
    original_one, original_bars = clef_keysig._analyze_one, clef_keysig._find_bars
    calls, current = {}, []

    def one(no_staff, staff, img_h, single_system=False):
        current.append(staff.index)
        calls[staff.index] = []
        try:
            return original_one(no_staff, staff, img_h, single_system)
        finally:
            current.pop()

    def bars(band, sp, x0, x1, r0, r1):
        value = original_bars(band, sp, x0, x1, r0, r1)
        if not current:
            raise AssertionError('보표에 속하지 않은 막대 호출')
        calls[current[-1]].append(inspect_window(band, sp, x0, x1, r0, r1, value))
        return value

    with patch.object(clef_keysig, '_analyze_one', one), patch.object(clef_keysig, '_find_bars', bars):
        traced = clef_keysig.analyze_staves(result)
    if traced != plain:
        raise AssertionError('계측이 제품 출력을 바꿈')
    staves = []
    for staff in result.staves:
        ctx = traced[staff.index]
        records = calls[staff.index]
        # _keysig_scan_end의 예비 호출과 마지막 실제 수집 호출을 분리한다.
        if ctx.bars and not records:
            raise AssertionError('막대 출처 누락')
        if records:
            assert [x for x, _ in ctx.bars] == [x for x, _ in records[-1]['bars']]
            records[-1]['role'] = 'final_collection'
            for r in records[:-1]:
                r['role'] = 'scan_probe'
        staves.append(dict(staff=asdict(staff), context=asdict(ctx), calls=records))

    # 기존 투표의 정확한 집계 단위는 보표 수가 아니라 막대 수다.
    # 두 값을 같이 기록하되 여기서 중복 제거하거나 제품 투표를 바꾸지 않는다.
    found = [(i, c) for i, c in traced.items() if c.clef_found]
    threshold = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    items = sorted((float(x), i, float(y)) for i, c in found for x, y in c.bars)
    clusters, i = [], 0
    while i < len(items):
        j = i + 1
        while j < len(items) and items[j][0] - items[i][0] <= 3.0:
            j += 1
        members = items[i:j]
        clusters.append(dict(x=float(np.mean([v[0] for v in members])),
                             bar_votes=len(members), distinct_staves=len({v[1] for v in members}),
                             accepted=len(members) >= threshold, members=members))
        i = j
    return dict(staves=staves, vote_threshold=threshold, clusters=clusters,
                signature=sorted({(c.key_symbol, c.key_count, tuple(c.key_letters)) for c in traced.values()}))


def cases():
    fixture = ROOT / 'tests/fixtures/key_signatures'
    manifest = json.loads((fixture / 'manifest.json').read_text(encoding='utf-8'))
    output = []
    for key in manifest['keys']:
        source = fixture / key['source'].replace('\\', '/')
        pdf = fixture / key['pdf']
        # 선언된 조성의 출처를 .ly에서도 확인한다. OMR 출력으로 정답을 만들지 않는다.
        text = source.read_text(encoding='utf-8')
        if f"\\key {key['lily']} \\major" not in text:
            raise ValueError(f'조성 선언과 명세 불일치: {source.name}')
        output.append(dict(id=key['slug'], path=pdf, source=source,
                           expected=(SYMBOLS[key['symbol']], key['count'], key['letters'])))
    output.append(dict(id='bach_minuet_Am', path=ROOT / 'test_scores/bach_minuet_Am.pdf',
                       source=None, expected=('', 0, [])))
    output.append(dict(id='beam_melody', path=ROOT / 'tests/fixtures/beams/pdf/beam_melody.pdf',
                       source=ROOT / 'tests/fixtures/beams/sources/beam_melody.ly', expected=('', 0, [])))
    return output


def measure(selected=None, phases=PHASES):
    report = dict(schema=1, purpose='C-11 읽기 전용 대조 측정; 제품 수정·정확성 완료 아님',
                  environment=dict(python=platform.python_version(), platform=platform.system(),
                                   packages={n: importlib.metadata.version(n) for n in
                                             ('opencv-python', 'numpy', 'scipy', 'PyMuPDF')}),
                  tool_sha256=sha256(__file__),
                  manifest_sha256=sha256(ROOT / 'tests/fixtures/key_signatures/manifest.json'),
                  transform=dict(dpi=300, axis='x', interpolation='INTER_LINEAR', border='white',
                                 identity_warp_executed=True),
                  module_sha256={p.name: sha256(p) for p in sorted((ROOT / 'modules').glob('*.py'))},
                  phases=list(phases), cases=[], mismatches=[])
    for case in cases():
        if selected and case['id'] not in selected:
            continue
        bgr = load_image(str(case['path']), pdf_dpi=300)
        base = preprocess(str(case['path']), pdf_dpi=300)
        original = trace_headers(base)
        signature = [case['expected'][0], case['expected'][1], list(case['expected'][2])]
        row = dict(id=case['id'], pdf=case['path'].relative_to(ROOT).as_posix(),
                   pdf_sha256=sha256(case['path']),
                   source_sha256=sha256(case['source']) if case['source'] else None,
                   expected=signature, original=original, runs=[])
        def normalized(value):
            return json.loads(json.dumps(value, ensure_ascii=False))
        if normalized(original['signature']) != [signature]:
            raise AssertionError(f"원본부터 조표 대조 실패: {case['id']}")
        with tempfile.TemporaryDirectory(prefix='keysig-controls-') as tmp:
            path = Path(tmp) / 'shift.png'
            for dx in phases:
                shifted = cv2.warpAffine(bgr, np.float64([[1, 0, dx], [0, 1, 0]]),
                                         (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
                ok, buf = cv2.imencode('.png', shifted)
                if not ok:
                    raise ValueError('PNG 인코딩 실패')
                buf.tofile(path)
                run = trace_headers(preprocess(str(path)))
                same = normalized(run['signature']) == [signature]
                if dx == 0:
                    if not np.array_equal(bgr, shifted) or run != original:
                        raise AssertionError('실제 0px 변환 대조가 원본과 다름')
                row['runs'].append(dict(dx=dx, matches_source_signature=same, trace=run))
                if not same:
                    report['mismatches'].append(dict(case=case['id'], dx=dx, expected=signature,
                                                      actual=run['signature']))
                print(case['id'], dx, run['signature'], '일치' if same else '불일치', flush=True)
        report['cases'].append(row)
    if not report['cases']:
        raise ValueError('측정 대상 없음')
    report['summary'] = dict(cases=len(report['cases']), runs=sum(len(c['runs']) for c in report['cases']),
                             mismatches=len(report['mismatches']), product_changed=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', dest='selected', choices=[c['id'] for c in cases()])
    parser.add_argument('--output', type=Path, default=ROOT / 'output/keysig-controls/measurement.json')
    parser.add_argument('--require-preservation', action='store_true')
    args = parser.parse_args()
    report = measure(args.selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(report, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    args.output.write_bytes(gzip.compress(encoded, mtime=0) if args.output.suffix == '.gz' else encoded)
    print(json.dumps(report['summary'], ensure_ascii=False), flush=True)
    if args.require_preservation and report['mismatches']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
