# -*- coding: utf-8 -*-
"""(g) 「라벨이 ♯/♮ 글리프 안에 있음」 신호의 정밀도 — G3 모양 검사(빈 머리 · 주인 음표 조건 뺌)를 모든 라벨에. 제품 코드 무변경.
정답: PDF = PDF 글리프 머리(0.7 × 0.5sp), Verovio = SVG 머리. 라벨은 A-25 상태 run_page JSON.

    python tools/measure_glyph_cell_signal.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def shape_hit(no_staff, n_x, n_y, sp):
    from modules import accidental_detect as AD
    y0, x0 = max(0, int(n_y - 2 * sp)), max(0, int(n_x - 0.8 * sp))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    band = cv2.morphologyEx(no_staff[y0:int(n_y + 2 * sp), :], cv2.MORPH_CLOSE, vk)
    patch = band[:, x0:int(n_x + 0.8 * sp)]
    bars = AD._find_thin_bars(patch, sp)
    cx = n_x - x0

    def inner(p_, q):
        r0, r1 = max(p_[1], q[1]), min(p_[2], q[2])
        c0, c1 = int(p_[0] + 0.15 * sp), int(q[0] - 0.15 * sp)
        return (patch[r0:r1 + 1, c0:c1 + 1] > 0).mean() if c1 >= c0 and r1 >= r0 else 1.0
    return any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95 and min(p_[2] - p_[1], q[2] - q[1]) + 1 >= AD.GLYPH_BAR_SP * sp
               and abs(y0 + (p_[1] + p_[2] + q[1] + q[2]) / 4 - n_y) <= 0.5 * sp and p_[0] - 0.1 * sp <= cx <= q[0] + 0.1 * sp
               and inner(p_, q) <= AD.GLYPH_INNER_INK for p_, q in zip(bars, bars[1:]))


def _one(job):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg, labels_path = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ns = remove_staff_lines(res.binary, res.staves)
    if kind == "pdf":
        from measure_normalize_sp import truth_at
        heads = [(h["cx"], h["cy"]) for h in truth_at(path, pg, 1.0)[0]]
    else:
        heads = [(n["x"], n["y"]) for n in json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))["notes"]]
    sp_of = {s.index: s.spacing for s in res.staves}
    out = []
    for l in json.load(open(labels_path, encoding="utf-8"))["labels"]:
        sp = sp_of.get(l["staff"], 18.0)
        if shape_hit(ns, l["x"], l["y"], sp):
            real = any(abs(hx - l["x"]) <= 0.7 * sp and abs(hy - l["y"]) <= 0.5 * sp for hx, hy in heads)
            out.append(dict(set=kind, page=name, x=l["x"], y=l["y"], text=l["text"], conf=l["confidence"], real=real))
    return out


def main():
    import measure_a17_ghost6 as G
    jobs = [("pdf", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_pdf20", n + ".json")) for n, p, pg in G.SETS["pdf20"]() if p.endswith(".pdf")]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0, os.path.join(ROOT, "debug", "vrv_a25impl", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_one, jobs) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "glyph_cell_signal.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st in ("pdf", "verovio"):
        v = [r for r in rows if r["set"] == st]
        c = Counter(("유령" if not r["real"] else "진짜", r["conf"]) for r in v)
        g = sum(1 for r in v if not r["real"])
        print(f"{st}: 신호 {len(v)} · 유령 {g} ({g / max(1, len(v)) * 100:.0f}%) · 진짜 {len(v) - g} | 확신도별 {dict(c)}")
    print("A-19 (2059,260) 걸림:", any(r["page"] == "em3" and abs(r["x"] - 2059) < 5 and abs(r["y"] - 260) < 5 for r in rows))


if __name__ == "__main__":
    main()
