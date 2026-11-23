# -*- coding: utf-8 -*-
"""`measure_wide3.py` 기록 중 창(폭 ≤ 2.65 · 높이 2.3~2.8sp) 안 덩어리 + 창 둘레 잡음을 격자로 (2026-10-19 · 측정만).
초록 테두리 = 창 안, 빨강 = 창 둘레 잡음(머리 < 3). 칸 아래 숫자 = 정답 머리 수. → debug/wide3_grid.png"""
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

if __name__ == "__main__":
    import measure_sim_ledger_pair as S
    from modules.preprocess import preprocess
    rows = json.load(open(os.path.join(ROOT, "debug", "wide3_log.json"), encoding="utf-8"))
    win = lambda r: r["w"] <= 2.65 * r["sp"] and 2.3 * r["sp"] <= r["h"] <= 2.8 * r["sp"]
    near = lambda r: r["n"] < 3 and r["w"] <= 2.9 * r["sp"] and 2.0 * r["sp"] <= r["h"] <= 3.2 * r["sp"]
    sel = [r for r in rows if win(r) or near(r)]
    pages = {p[1]: p for p in S.pages()}
    C = 120
    tiles = []
    for nm in sorted({r["page"] for r in sel}):
        st, _n, path, pg = pages[nm]
        b = preprocess(os.path.join(ROOT, path), pdf_page=pg).binary
        for r in [r for r in sel if r["page"] == nm]:
            cx, cy = r["x"] + r["w"] // 2, r["y"] + r["h"] // 2
            pad = np.pad(b, C)
            t = 255 - pad[cy:cy + 2 * C, cx:cx + 2 * C]
            t = cv2.cvtColor(t.astype(np.uint8), cv2.COLOR_GRAY2BGR)
            col = (0, 160, 0) if win(r) else (0, 0, 220)
            cv2.rectangle(t, (C - r["w"] // 2, C - r["h"] // 2), (C + r["w"] - r["w"] // 2, C + r["h"] - r["h"] // 2), col, 1)
            cv2.putText(t, f"{r['n']} {r['h'] / r['sp']:.2f}", (3, 2 * C - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            cv2.putText(t, nm[:14], (3, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (90, 90, 90), 1)
            tiles.append(t)
    k = 10
    tiles += [np.full_like(tiles[0], 255)] * (-len(tiles) % k)
    grid = np.vstack([np.hstack(tiles[i:i + k]) for i in range(0, len(tiles), k)])
    open(os.path.join(ROOT, "debug", "wide3_grid.png"), "wb").write(cv2.imencode(".png", grid)[1].tobytes())
    print("칸", len(sel))
