# -*- coding: utf-8 -*-
"""[2] 「가로로 긴 덩어리(w > 2.2sp)」로 버려지는 꽉 찬 덩어리 — 정답 머리 수별 폭 · 높이 · 위아래 4분의 1 좌우 중심 차 분포. 측정 전용.
제품 `_detect_noteheads_in_band`에 임시 기록(_WIDE_LOG)을 넣은 사본에서만 돈다(작업 트리에서 잠시 고쳐 쓰고 되돌린다).
덩어리마다 bbox 안 정답 머리 수(PDF 글리프 · Verovio SVG): 2 = 2도 머리 쌍, 1, 0(빔 잔여물 · 글자 · 기타), 3+.

    python tools/measure_wide_blobs.py
"""
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def truth(st, name, path, pg):
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"]) for n in t["notes"]]
    if st == "aoharu":
        return None
    from measure_normalize_sp import truth_at
    return [(h["cx"], h["cy"]) for h in truth_at(path, pg, 1.0)[0]]


if __name__ == "__main__":
    import measure_sim_ledger_pair as S
    import modules.notehead_detect as ND
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    rows = []
    for st, name, path, pg in S.pages():
        if name == "organ2":
            continue
        res = preprocess(path, pdf_page=pg) if path.endswith(".pdf") else preprocess(path)
        ND._WIDE_LOG.clear()
        ND.detect_noteheads(res, contexts=analyze_staves(res))
        heads = truth(st, name, path, pg)
        for si, x, y, w, h, sp, spread in ND._WIDE_LOG:
            n = None if heads is None else sum(1 for hx, hy in heads if x <= hx <= x + w and y <= hy <= y + h)
            rows.append(dict(set=st, page=name, x=x, y=y, w=round(w / sp, 2), h=round(h / sp, 2), n=n, spread=round(spread, 2)))
    json.dump(rows, open(os.path.join(ROOT, "debug", "wide_blobs.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("버려진 넓은 덩어리", len(rows), "· 정답 머리 수:", dict(Counter(r["n"] for r in rows)))
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (0, 5, 50, 95, 100)) if a else "-"
    for k in (2, 1, 0):
        v = [r for r in rows if r["n"] == k]
        print(f"  머리 {k}: {len(v)} | 폭 최소 · 5 · 50 · 95 · 최대 {pct([r['w'] for r in v])} | 높이 {pct([r['h'] for r in v])}")
    win = [r for r in rows if 2.2 < r["w"] <= 2.65 and 1.45 <= r["h"] <= 1.8]
    for k in (2, 0, None):
        v = [r["spread"] for r in win if r["n"] == k]
        print(f"  창(폭 2.2~2.65 · 높이 1.45~1.8) 머리 {k}: {len(v)} · 위아래 4분의 1 좌우 중심 차(sp) {pct(v)}")
    for W in (2.6, 2.7, 2.8):
        for H in (1.3, 1.4, 1.5):
            c = Counter(r["n"] if r["n"] is not None else "Aoharu" for r in rows if r["w"] <= W and r["h"] >= H)
            print(f"  폭 ≤ {W} · 높이 ≥ {H}: {dict(c)}")
