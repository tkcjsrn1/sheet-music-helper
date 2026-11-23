# -*- coding: utf-8 -*-
"""야간 [4] 흐린 인쇄 — 대비 여러 단계에서 구제 경로 「구멍 속 회색」 문턱 안 비교. 제품 코드 무변경.

대비 c(잉크가 종이 쪽으로 옅어진 정도): 영상 = 255 − (255 − 원본) × c. c = 1이 원본.
문턱 안(구제 경로 `hole_filled_binary`의 gray_max):
  abs   지금 제품 101
  step  잉크 ≥ 89일 때만 상대(잉크 + 0.396 × (종이 − 잉크)) — `ROBUSTNESS.md` §3
  cont  잉크 ≤ 63이면 101, 잉크 ≥ 115이면 상대, 그 사이는 101과 상대값을 선형으로 — 원본 최대 잉크 63 위에서만 움직인다(원본 판정 변화 0이 구조적)
잉크 = 오선 행 잉크 화소의 원본 회색 중앙값, 종이 = 배경 중앙값(`measure_rescue_relative_gray.ref_levels`).
단계마다 원본(c = 1) 최종 머리 대비: 되찾음(abs에서 사라졌는데 안에서 남음) · 다시 잃음 · 새 유령(원본 최종에 없던 새 머리).

    python tools/measure_faded_levels.py
"""
import os
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LEVELS = (0.9, 0.8, 0.7, 0.6, 0.55, 0.5)
T = 101 / 255.0


def thr_of(variant, ink, paper):
    rel = ink + T * (paper - ink)
    if variant == "abs":
        return 101.0
    if variant == "step":
        return rel if ink >= 89 else 101.0
    w = min(1.0, max(0.0, (ink - 63) / (115 - 63)))
    return (1 - w) * 101.0 + w * rel


def _page(job):
    import measure_faded_stages as F
    import measure_rescue_relative_gray as G
    import modules.chord_rescue as CR
    from modules.preprocess import load_image, preprocess
    name, path, pg = job
    src = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
    tmp = tempfile.mkdtemp(prefix="flv_")
    f0 = os.path.join(tmp, "o.png")
    open(f0, "wb").write(cv2.imencode(".png", src)[1].tobytes())
    A = F.stages(f0)[0]
    sp = A["sp"]
    near = lambda lst, x, y: any(abs(a - x) <= 0.5 * sp and abs(b - y) <= 0.5 * sp for a, b, *_ in lst)
    fin = lambda S: S["base_final"] + [p for p in S["rescue_final"] if not near(S["base_final"], *p)]
    a = fin(A)
    out = {}
    orig = CR.hole_filled_binary
    for c in LEVELS:
        f = os.path.join(tmp, f"{c}.png")
        open(f, "wb").write(cv2.imencode(".png", (255 - (255 - src.astype(np.float32)) * c).astype(np.uint8))[1].tobytes())
        ink, paper = G.ref_levels(preprocess(f))
        res_v = {}
        for v in ("abs", "step", "cont"):
            th = thr_of(v, ink, paper)
            if v != "abs" and abs(th - 101.0) < 1e-6:
                res_v[v] = res_v["abs"]
                continue
            CR.hole_filled_binary = lambda b, g, gray_max=th: orig(b, g, gray_max)
            try:
                res_v[v] = fin(F.stages(f)[0])
            finally:
                CR.hole_filled_binary = orig
        b = res_v["abs"]
        row = dict(ink=round(ink, 1), lost_abs=sum(1 for p in a if not near(b, *p)))
        for v in ("step", "cont"):
            cc = res_v[v]
            row[v] = dict(되찾음=sum(1 for p in a if not near(b, *p) and near(cc, *p)),
                          다시잃음=sum(1 for p in a if near(b, *p) and not near(cc, *p)),
                          새유령=sum(1 for p in cc if not near(b, *p) and not near(a, *p)),
                          문턱=round(thr_of(v, ink, paper), 1))
        out[c] = row
        os.remove(f)
    os.remove(f0)
    os.rmdir(tmp)
    return name, out


def main():
    import measure_robustness as R
    with ProcessPoolExecutor(2) as ex:   # 3이면 밤에 메모리 부족으로 중단됐다
        res = list(ex.map(_page, R.pages()))
    for c in LEVELS:
        inks = [o[c]["ink"] for _n, o in res]
        lost = sum(o[c]["lost_abs"] for _n, o in res)
        line = f"대비 {c}: 잉크 회색 {min(inks)}~{max(inks)} · 지금(101) 사라짐 {lost}"
        for v in ("step", "cont"):
            t = Counter()
            for _n, o in res:
                t.update({k: val for k, val in o[c][v].items() if k != "문턱"})
            ths = [o[c][v]["문턱"] for _n, o in res]
            line += f" | {v}: 문턱 {min(ths)}~{max(ths)} · 되찾음 {t['되찾음']} · 다시 잃음 {t['다시잃음']} · 새 유령 {t['새유령']}"
        print(line)


if __name__ == "__main__":
    main()
