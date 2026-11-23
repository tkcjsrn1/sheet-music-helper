# -*- coding: utf-8 -*-
"""[3](c) Verovio 빽빽한 화음 누락 — 덩어리 높이로 머리 수를 추정해 「추가만」 하는 안의 정밀도. 제품 코드 무변경.

덩어리: 오선 제거 영상을 타원 0.5sp로 열어(기둥 · 얇은 획 제거) 남은 8연결 성분 중 **지금 라벨이 1개 이상 걸린 것**(정답 머리 없는 것 포함 — 화음 구제처럼 이미 잡힌 덩어리만 넓힌다).
추정 머리 수 n = round((덩어리 높이 − HEAD_SP) / STEP_SP) + 1 — 변형 「3도」(STEP 1.0sp)와 「2도」(STEP 0.5sp).
덩어리 안: 정답 머리 T · 그중 라벨이 붙은 수 D(Verovio `debug/vrv_clefflag/base`, 0.7 × 0.5sp). 「추가만」: n > D면 n − D개를 더한다고 보고
진짜로 늘어난 수 = max(0, min(n, T) − D). 정밀도 = 진짜 늘어남 / 더한 수(나머지는 유령). 위치(어느 높이에 더할지)는 따로 — 여기서는 수만.

    python tools/measure_dense_chord.py
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
HOLLOW = ("E0A3", "E0A2", "E0A0")
HEAD_SP = 1.0


def _page(stem):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    res = preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))
    sp = float(np.median([s.spacing for s in res.staves]))
    ns = remove_staff_lines(res.binary, res.staves)
    k = max(3, int(0.5 * sp)) | 1
    op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, stats, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
    t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", stem + ".json"), encoding="utf-8"))
    heads = [(n_["x"], n_["y"]) for n_ in t["notes"] if n_["glyph"] not in HOLLOW and not n_.get("grace") and not n_.get("cue")]
    L = json.load(open(os.path.join(ROOT, "debug", "vrv_clefflag", "base", stem + ".json"), encoding="utf-8"))["labels"]
    H, W = lab.shape
    comp_of = lambda x, y: lab[min(H - 1, max(0, int(round(y)))), min(W - 1, max(0, int(round(x))))]
    T, D = Counter(), Counter()
    for x, y in heads:
        c = comp_of(x, y)
        if c:
            T[c] += 1
    # D = 라벨이 붙은 정답 머리 수(라벨 좌표는 열린 덩어리 밖에 찍히기도 해 덩어리 소속으로 세면 모자란다)
    for x, y in heads:
        c = comp_of(x, y)
        if c and any(abs(l["x"] - x) <= 0.7 * sp and abs(l["y"] - y) <= 0.5 * sp for l in L):
            D[c] += 1
    # 대상 = 라벨이 하나 이상 걸린 덩어리(라벨 좌표가 덩어리 안 · 또는 라벨 붙은 정답 머리가 덩어리 안) — 정답 머리 없는 덩어리(유령 라벨)도 넣는다
    Lc = Counter()
    for l in L:
        c = comp_of(l["x"], l["y"])
        if c:
            Lc[c] += 1
    rows = []
    for c in set(Lc) | set(D):
        h = stats[c, cv2.CC_STAT_HEIGHT] / sp
        w = stats[c, cv2.CC_STAT_WIDTH] / sp
        rows.append(dict(page=stem, T=T[c], D=D[c], Dl=max(Lc[c], D[c]), h=round(h, 2), w=round(w, 2)))
    return rows


def main():
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "test_scores", "verovio")) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_page, stems) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "dense_chord.json"), "w", encoding="utf-8"), ensure_ascii=False)
    multi = [r for r in rows if r["T"] >= 2]
    print(f"라벨 걸린 덩어리 {len(rows)} · 정답 머리 없는 것 {sum(r['T'] == 0 for r in rows)} · 머리 2개 이상 {len(multi)} · 그 안 정답 머리 {sum(r['T'] for r in multi)} · 라벨 {sum(r['D'] for r in multi)} · 누락(T − D > 0) {sum(max(0, r['T'] - r['D']) for r in multi)}")
    for name, step in (("3도", 1.0), ("2도", 0.5)):
        c = Counter()
        for r in rows:
            nest = max(1, int(round((r["h"] - HEAD_SP) / step)) + 1)
            c["정확"] += nest == r["T"]
            c["과다"] += nest > r["T"]
            c["과소"] += nest < r["T"]
            add = max(0, nest - r["Dl"])     # 이미 걸린 라벨 수(유령 라벨 포함)만큼은 더하지 않는다
            c["더함"] += add
            c["진짜 늘어남"] += max(0, min(nest, r["T"]) - r["D"])
        print(f"{name}: 머리 수 정확 {c['정확']}/{len(rows)} · 과다 {c['과다']} · 과소 {c['과소']} | 추가만: 더함 {c['더함']} · 진짜 {c['진짜 늘어남']} "
              f"(정밀도 {c['진짜 늘어남'] / max(1, c['더함']) * 100:.0f}%) · 유령 {c['더함'] - c['진짜 늘어남']}")
    # 머리 수별 덩어리 높이 분포 — 3도 · 2도 쌓기가 섞이면 같은 T에서 높이가 퍼진다
    for tn in (1, 2, 3, 4):
        v = [r["h"] for r in rows if r["T"] == tn]
        if v:
            print(f"  정답 머리 {tn}: 덩어리 {len(v)} · 높이 sp 5 · 50 · 95% {np.percentile(v, 5):.2f} · {np.percentile(v, 50):.2f} · {np.percentile(v, 95):.2f}")


if __name__ == "__main__":
    main()
