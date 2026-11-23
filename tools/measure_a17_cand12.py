# -*- coding: utf-8 -*-
"""A-17 후보 2 단독 · 후보 1+2 결합 사본 측정 (2026-09-30, 제품 코드 무변경).

후보 2 — 자기 머리와 이어진 막대 제외: `_find_glyphs`가 받는 창(patch)은 보표 밴드 배열의 **뷰**라 메모리 오프셋으로
밴드 안 창 원점을 알 수 있다. 밴드(오선 제거 + 세로 닫힘, 판정이 보는 그 영상)에서 자기 머리 **덩어리**(열림 0.4sp로 얇은 획을 지우고 남는 성분)를 찾고,
`_find_thin_bars`가 낸 막대 중 그 열의 잉크가 절반 넘게 그 덩어리인 것을 뺀다(cand2_find_glyphs 설명 참고). 나머지(쌍 짓기 · ♮/♯ 규칙 · ♭ 고리 · 고르기)는 제품 그대로.

머리 위치: 창 오른쪽 끝 = note.x − 0.55sp → 머리 중심 열 = 창 원점 열 + 창 폭 + 0.55sp. 머리 행 = 창이 위에서 잘렸으면(원점 행 0)
창 높이 − 2sp, 아니면 원점 행 + 2sp(annotate_accidentals의 창 식). 빈 머리는 중심이 희므로 ±0.3sp 안 잉크 성분의 최빈값.

후보 1(밴드 ±5.5sp)은 measure_a17_cand1.wide_annotate — 마디선 · 오선 제거는 원래 보표(지난 측정 실수 재발 방지).
실행: python tools/measure_a17_cand12.py run | compare | raw | crops
"""
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import measure_a17_cand1 as T1  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402

ORIG_GLYPHS, ORIG_BARS = AD._find_glyphs, AD._find_thin_bars
OWN_ROWS_SP = 0.5      # 막대가 자기 머리 덩어리를 이만큼 이상 지나가면 제외(비율은 안 됨 — 머리 + 자기 기둥 막대는 기둥이 얇아 머리 비율이 절반 미만)
STATS = Counter()                       # 가로채기 · 제외 통계(측정 함정 B-4)


def cand2_find_glyphs(patch, sp):
    """자기 머리 **덩어리**에 속한 막대를 뺀다.

    밴드 전체 8연결 성분은 쓸 수 없었다 — 글리프가 빔 · 덧줄 · 기둥을 거쳐 머리와 한 성분(D♭ 3쪽 (986,2900): 가로 1050px)이라
    글리프 막대까지 빠졌다. 그래서 창 + 머리 영역을 열림(타원 0.4sp)으로 얇은 획(글리프 막대 · 기둥 · 이음줄 ≤ 0.3sp)을 지우고
    남은 두꺼운 덩어리 중 머리 자리 것을 자기 머리로 본다(쌓인 화음 머리는 한 덩어리). 가장자리가 열림에 깎이므로 덩어리를 k//2 부풀려 잰다.
    """
    STATS["창"] += 1
    band = patch.base
    if band is None or band.ndim != 2:
        STATS["밴드 못 찾음"] += 1
        return ORIG_GLYPHS(patch, sp)
    off = patch.__array_interface__["data"][0] - band.__array_interface__["data"][0]
    r0, c0 = divmod(off, band.strides[0])
    c0 //= band.strides[1]
    H, W = patch.shape
    hr = int(round(H - 2 * sp)) if r0 == 0 else int(round(2 * sp))      # 창 안 행 좌표
    hc = int(round(W + 0.55 * sp))                                        # 창 원점 기준 열
    local = band[r0:r0 + H, c0:min(band.shape[1], c0 + hc + int(0.8 * sp))]
    k = max(3, int(0.4 * sp)) | 1
    ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    thick = cv2.morphologyEx((local > 0).astype(np.uint8), cv2.MORPH_OPEN, ell)
    n, lab = cv2.connectedComponents(thick, connectivity=8)
    d = max(1, int(0.3 * sp))
    box = lab[max(0, hr - d):hr + d + 1, max(0, hc - d):hc + d + 1]
    ids = box[box > 0]
    if ids.size == 0:
        STATS["머리 덩어리 없음(빈 머리 등)"] += 1
        return ORIG_GLYPHS(patch, sp)
    head = cv2.dilate((lab == np.bincount(ids).argmax()).astype(np.uint8), ell, iterations=1)

    def bars_without_head(p, s):
        out = []
        for b in ORIG_BARS(p, s):
            x, s0, e0 = b
            if head[s0:e0 + 1, int(round(x))].sum() >= OWN_ROWS_SP * s:
                STATS["제외 막대"] += 1
                continue
            out.append(b)
        return out

    AD._find_thin_bars = bars_without_head
    try:
        return ORIG_GLYPHS(patch, sp)
    finally:
        AD._find_thin_bars = ORIG_BARS


def with_cand2(ann):
    def f(result, contexts, notes):
        AD._find_glyphs = cand2_find_glyphs
        try:
            return ann(result, contexts, notes)
        finally:
            AD._find_glyphs = ORIG_GLYPHS
    return f


MODES = {"c2": with_cand2(T1.ORIG_ANN), "c12": with_cand2(T1.wide_annotate)}


def run_mode(mode):
    fn = MODES[mode]
    for name, path, pg in T1.C.PAGES:
        out = os.path.join(T1.OUT, mode)
        os.makedirs(out, exist_ok=True)
        js = os.path.join(out, f"{name}.json")
        argv = [os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", T1.tempfile.gettempdir(), "--save-labels", js]
        sys.argv = ["main.py"] + argv
        args = T1.MAIN.parse_args()
        T1.MAIN.annotate_accidentals = AD.annotate_accidentals = fn
        try:
            T1.MAIN.run_page(args, argv[0], pg, T1.tempfile.gettempdir())
        finally:
            T1.MAIN.annotate_accidentals = AD.annotate_accidentals = T1.ORIG_ANN
        print(mode, name, "완료", dict(STATS), flush=True)


def raw(mode):
    """A-17 원시 판정 행렬(measure_a17.run_all)을 이 후보로 — 103 기준 대조."""
    import measure_a17 as A
    AD.annotate_accidentals = MODES[mode]
    A.crops = lambda _w: None
    try:
        A.run_all()
    finally:
        AD.annotate_accidentals = T1.ORIG_ANN
    os.replace(os.path.join(ROOT, "debug", "a17.json"), os.path.join(ROOT, "debug", f"a17_raw_{mode}.json"))
    print("통계", dict(STATS))


def golden(mode):
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_golden_regression as G
    G.annotate_accidentals = AD.annotate_accidentals = MODES[mode]
    sys.argv = ["test_golden_regression.py"]
    try:
        G.main()
    except SystemExit as e:
        print("골든 종료 코드", e.code)
    finally:
        G.annotate_accidentals = AD.annotate_accidentals = T1.ORIG_ANN
    print("통계", dict(STATS))


if __name__ == "__main__":
    cmd, mode = sys.argv[1], sys.argv[2]
    if cmd == "run":
        run_mode(mode)
    elif cmd == "raw":
        raw(mode)
    elif cmd == "golden":
        golden(mode)
    elif cmd == "compare":
        T1.compare(cand=mode, out_json=f"diff_{mode}.json")
    elif cmd == "crops":
        T1.crops(rows_json=f"diff_{mode}.json", review=os.path.join(ROOT, "docs", "review", "a17_candidate12"), prefix=f"{mode}_")
