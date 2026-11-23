# -*- coding: utf-8 -*-
"""A-25 ④(원천은 맞게 읽었는데 같은 마디 뒤 음에 전파 안 됨) 가설 확인 — 표본 4쪽만. 제품 코드 무변경.

제품 마디선 = `accidental_detect._find_barlines`(annotate_accidentals가 전파 경계로 쓰는 그 함수, 같은 인자).
원천(인쇄 임시표) ~ 대상(전파 안 된 음) 사이 제품 마디선을 정답 상자로 분류: 진짜 마디선(barLine ±0.5sp) / 기둥(stem 상자) / 기타.

    python tools/measure_a25_barline.py
"""
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from modules.preprocess import preprocess  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402

SAMPLE4 = ["bach_bwv846_leipzig_p1", "bach_bwv846_bravura_p1", "clara_polonaise_1_bravura_p1", "clara_polonaise_4_bravura_p1"]
PAGES = SAMPLE4
VRV = os.path.join(ROOT, "debug", "vrv")
OUT = os.path.join(ROOT, "docs", "review", "a25_barline")


def main():
    cases = [o for o in json.load(open(os.path.join(VRV, "a25_classes.json"), encoding="utf-8")) if o["cause"].startswith("④")]
    tally, rows = Counter(), []
    for stem in PAGES:
        t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
        real = [b["box"] for b in t["boxes"] if b["cls"] == "barLine"]
        stems_ = [b["box"] for b in t["boxes"] if b["cls"] == "stem"]
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))
        ns = remove_staff_lines(res.binary, res.staves)
        H = res.binary.shape[0]
        img = res.original_bgr
        tiles = []
        for o in [c for c in cases if c["stem"] == stem]:
            st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - o["y"]))
            sp = st.spacing
            bl = AD._find_barlines(ns, st, H)
            sx, tx = o["src"][0], o["x"]
            between = [x for x in bl if sx < x < tx]
            kinds = []
            for x in between:
                if any(b[0] - sp * 0.5 <= x <= b[2] + sp * 0.5 and b[1] <= st.bottom and b[3] >= st.top for b in real):
                    k = "진짜 마디선"
                elif any(b[0] - 2 <= x <= b[2] + 2 and b[1] <= st.bottom and b[3] >= st.top for b in stems_):
                    k = "기둥"
                else:
                    k = "기타"
                kinds.append((x, k))
                tally[k] += 1
            tally["사이에 제품 마디선 있음" if between else "사이에 없음"] += 1
            rows.append(dict(stem=stem, src=o["src"][:2], tgt=(tx, o["y"]), pitch=o["pitch"], between=kinds))
            # 그림: 원천 파랑 · 대상 주황 · 사이 제품 마디선 (진짜 초록 / 가짜 빨강) · 그 밖 제품 마디선 회색
            x0, x1 = int(sx - 1.5 * sp), int(tx + 1.5 * sp)
            y0, y1 = int(st.top - 3 * sp), int(st.bottom + 3 * sp)
            c = img[y0:y1, x0:x1].copy()
            for x in bl:
                if x0 <= x < x1:
                    k = dict(kinds).get(x)
                    col = (0, 160, 0) if k == "진짜 마디선" else (0, 0, 255) if k else (170, 170, 170)
                    cv2.line(c, (x - x0, 0), (x - x0, c.shape[0]), col, 2 if k else 1)
            cv2.circle(c, (int(sx - x0), int(o["src"][1] - y0)), int(sp * 0.8), (255, 0, 0), 2)
            cv2.circle(c, (int(tx - x0), int(o["y"] - y0)), int(sp * 0.8), (0, 140, 255), 2)
            z = 900 / max(c.shape[1], 1)
            c = cv2.resize(c, None, fx=min(z, 2.0), fy=min(z, 2.0), interpolation=cv2.INTER_AREA)
            head = np.full((22, c.shape[1], 3), 255, np.uint8)
            lab = " ".join("REAL" if k == "진짜 마디선" else "STEM" if k == "기둥" else "OTHER" for _x, k in kinds) or "none"
            cv2.putText(head, f"{stem[:22]} src{tuple(o['src'][:2])} -> tgt({tx},{o['y']}) {o['pitch']} | between: {lab}",
                        (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
            tiles.append(np.vstack([head, c, np.full((6, c.shape[1], 3), 128, np.uint8)]))
        W = max(t_.shape[1] for t_ in tiles)
        tiles = [cv2.copyMakeBorder(t_, 0, 0, 0, W - t_.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t_ in tiles]
        open(os.path.join(OUT, f"{stem}.png"), "wb").write(cv2.imencode(".png", np.vstack(tiles))[1].tobytes())
    json.dump(rows, open(os.path.join(VRV, "a25_barline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(dict(tally))
    for r in rows:
        print(r)


if __name__ == "__main__":
    if sys.argv[1:] == ["all"]:                     # ④가 있는 12쪽 전부(표본 4쪽 + 나머지 8쪽)
        PAGES[:] = sorted({o["stem"] for o in json.load(open(os.path.join(VRV, "a25_classes.json"), encoding="utf-8"))
                           if o["cause"].startswith("④")})
    main()
