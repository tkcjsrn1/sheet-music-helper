# -*- coding: utf-8 -*-
"""[5] 붙은 화음 구제 「구멍 속 회색」 문턱(HOLE_FILL_GRAY 101)을 쪽 잉크 회색 상대값으로 — 원본 판정 변화 · 흐린 인쇄 되찾음. 제품 코드 무변경.

상대 문턱 = 잉크 + T × (종이 − 잉크). 잉크 = 오선 행 중 이진화 잉크 화소의 원본 회색 중앙값, 종이 = 이진화 배경 화소 회색 중앙값.
T = 101 / 255 ≈ 0.396 — PDF 렌더(잉크 0 · 종이 255)에서 지금 문턱과 같아지는 값(측정 근거: 뚫린 꽉 찬 머리 0.0 · 빈 머리 최소 202.6의 가운데).
① 원본(PDF 17 · Aoharu 3 · Verovio 20 · 보지 않은 8): 닫힌 구멍마다 절대(101) · 상대 판정이 뒤집히는 수 — 0이어야 한다.
② 흐린 인쇄(`measure_robustness` faded): 제품 단계(`measure_faded_stages.stages`)를 절대 · 상대로 돌려, 원본 최종 머리 중
   흐린-절대에서 사라졌는데 흐린-상대에서 남는 것(되찾음) · 흐린-상대에서 새로 생긴 머리 중 정답 없는 것(새 유령).

    python tools/measure_rescue_relative_gray.py
"""
import json
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
T = 101 / 255.0


def ref_levels(res):
    b, g = res.binary, res.gray
    rows = sorted({int(round(y)) for s in res.staves for y in s.line_ys})
    ink = [g[r][b[r] > 0] for r in rows if 0 <= r < g.shape[0]]
    ink = np.concatenate(ink) if ink else np.array([0])
    return float(np.median(ink)), float(np.median(g[b == 0]))


def rel_thr(res):
    ink, paper = ref_levels(res)
    return ink + T * (paper - ink), ink, paper


def flips(res):
    import modules.chord_rescue as CR
    thr, ink, paper = rel_thr(res)
    a = CR.hole_filled_binary(res.binary, res.gray, CR.HOLE_FILL_GRAY)
    b = CR.hole_filled_binary(res.binary, res.gray, thr)
    diff = (a != b).astype(np.uint8)
    n, _l = cv2.connectedComponents(diff, connectivity=4)
    return n - 1, thr, ink, paper


def _orig(job):
    from modules.preprocess import preprocess
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    f, thr, ink, paper = flips(res)
    return st, name, f, round(thr, 1), round(ink, 1), round(paper, 1)


def _faded(job):
    import measure_robustness as R
    import measure_faded_stages as F
    import modules.chord_rescue as CR
    from modules.preprocess import load_image, preprocess
    name, path, pg = job
    src = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
    tmp = tempfile.mkdtemp(prefix="relg_")
    out = {}
    for v in ("base", "faded"):
        f = os.path.join(tmp, v + ".png")
        open(f, "wb").write(cv2.imencode(".png", R.VARIANTS[v](src))[1].tobytes())
        out[v] = F.stages(f)[0]
        if v == "faded":
            res = preprocess(f)
            thr, _i, _p = rel_thr(res)
            orig = CR.hole_filled_binary
            CR.hole_filled_binary = lambda b, g, gray_max=thr: orig(b, g, gray_max)
            try:
                out["faded_rel"] = F.stages(f)[0]
            finally:
                CR.hole_filled_binary = orig
        os.remove(f)
    os.rmdir(tmp)
    A, B, C = out["base"], out["faded"], out["faded_rel"]
    sp = A["sp"]
    near = lambda lst, x, y: any(abs(a - x) <= 0.5 * sp and abs(b - y) <= 0.5 * sp for a, b, *_ in lst)
    fin = lambda S: S["base_final"] + [p for p in S["rescue_final"] if not near(S["base_final"], *p)]
    a, b, c = fin(A), fin(B), fin(C)
    rec = sum(1 for x, y in a if not near(b, x, y) and near(c, x, y))
    lost = sum(1 for x, y in a if near(b, x, y) and not near(c, x, y))
    new = [(x, y) for x, y in c if not near(b, x, y)]
    # 새로 생긴 것 중 원본 최종에도 없는 것 = 유령 후보(원본에 있던 머리면 되찾음 쪽)
    ghost = sum(1 for x, y in new if not near(a, x, y))
    return name, dict(되찾음=rec, 다시잃음=lost, 새유령=ghost, 흐린절대=len(b), 흐린상대=len(c), 원본=len(a))


def main():
    import measure_sim_ledger_pair as S
    import measure_robustness as R
    with ProcessPoolExecutor(3) as ex:
        o = list(ex.map(_orig, [p for p in S.pages() if p[1] != "organ2"]))
        fz = list(ex.map(_faded, R.pages()))
    by = Counter()
    for st, name, f, thr, ink, paper in o:
        by[st] += f
        if f:
            print("  뒤집힘", st, name, f, "문턱", thr, "잉크", ink, "종이", paper)
    print("① 원본 구멍 판정 뒤집힘:", dict(by), "· 잉크 · 종이 범위", min(x[4] for x in o), "~", max(x[4] for x in o), "/", min(x[5] for x in o), "~", max(x[5] for x in o))
    t = Counter()
    for name, c in fz:
        t["verovio" if name.endswith("_p1") else "pdf"] += 0
        for k, v in c.items():
            t[("verovio " if name.endswith("_p1") else "pdf ") + k] += v
    print("② 흐린 인쇄:", dict(t))
    json.dump(dict(orig=o, faded=fz), open(os.path.join(ROOT, "debug", "rescue_relative_gray.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
