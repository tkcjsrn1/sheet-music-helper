# -*- coding: utf-8 -*-
"""[5] 보지 않은 악보 「이음매/링 조각」으로 지워진 진짜 머리 22 — 그 머리를 지운 구멍 후보의 정체. 측정 전용.
제품 `_detect_noteheads_in_band`에 임시 기록(_ART_LOG)을 넣은 사본에서만 돈다(작업 트리에서 잠시 고쳐 쓰고 되돌린다).
지운 머리마다: seam(위아래 구멍 2개) / ring(구멍이 bbox 0.75sp 밖) · 그 구멍들의 중심 · 세로 범위, 구멍 자리 원본 회색 평균, 확대 그림.

    python tools/trace_seam_holes.py
"""
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "seam_holes")

if __name__ == "__main__":
    import measure_a17_ghost6 as G
    import measure_unseen_header_seam as U
    import modules.notehead_detect as ND
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for job in [u for u in G.UNSEEN if u[0] != "organ2"]:
        miss = [r for r in U._page(job) if r["kind"] == "이음매"]
        if not miss:
            continue
        name, path, pg = job
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ND._ART_LOG.clear()
        ND.detect_noteheads(res, contexts=analyze_staves(res))
        sp = float(np.median([s.spacing for s in res.staves]))
        for m in miss:
            a = [e for e in ND._ART_LOG if abs(e["x"] - m["x"]) <= 0.5 * sp and abs(e["y"] - m["y"]) <= 0.5 * sp]
            if not a:
                rows.append(dict(page=name, x=m["x"], y=m["y"], kind="기록 없음(구제 경로에서만 지워짐 등)"))
                continue
            e = a[0]
            hg = []
            for cx, cy, h0, h1 in e["holes"]:
                win = res.gray[h0:h1 + 1, int(cx - 0.25 * sp):int(cx + 0.25 * sp) + 1]
                hg.append(dict(dy_sp=round((cy - m["y"]) / sp, 2), h_sp=round((h1 - h0) / sp, 2), gray=round(float(win.mean()), 1) if win.size else None))
            rows.append(dict(page=name, x=m["x"], y=m["y"], kind=e["kind"], holes=hg))
            x, y = int(m["x"]), int(m["y"])
            crop = res.gray[max(0, y - int(3 * sp)):y + int(3 * sp), max(0, x - int(2 * sp)):x + int(2 * sp)]
            crop = cv2.cvtColor(cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
            open(os.path.join(OUT, f"{name}_{x}_{y}.png"), "wb").write(cv2.imencode(".png", crop)[1].tobytes())
    json.dump(rows, open(os.path.join(OUT, "rows.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for r in rows:
        print(r)
