# -*- coding: utf-8 -*-
"""(c) 빔 마스크 후보 덩어리의 가로 길이 분포 — 진짜 빔 vs 오검출 (2026-10-13 · 측정만, 제품 코드 무변경, 보류 세트 미사용).

`verify.beam_mask`와 같은 계산(오선 제거 → 가로 열림 → 세로 두께 열림 0.35sp)을 가로 열림만 1.0sp로 짧게 해서 덩어리를 모두 꺼낸 뒤
덩어리마다 가로 폭(sp)을 잰다. 제품은 폭 ≥ 2.5sp만 남긴다 — 2.0~2.5sp 구간이 「낮추면 새로 잡히는 것」이다.
종류: Verovio = SVG 상자 — 빔 상자와 겹치면 「빔」, 정답 머리 중심을 품으면 「머리」, 그 밖 「기타」(어느 상자와 겹치는지 기록).
PDF · 보지 않은 악보는 빔이 벡터라 정답 상자가 없다 — 정답 머리를 품으면 「머리」, 아니면 「빔 · 기타(구분 없음)」.

    python tools/measure_beam_lengths.py     # debug/beam_lengths.json + 표
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    import cv2
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    import measure_chord_miss as C
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    sp = float(np.median([s.spacing for s in res.staves]))
    ns = remove_staff_lines(res.binary, res.staves)
    horiz = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * 1.0)), 1)))
    m = cv2.morphologyEx(horiz, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35)))))
    n, lab, stats, _c = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), connectivity=8)
    heads = [(x, y) for x, y, _h in C.truth(st, name, path, pg)]
    boxes = []
    if st == "verovio":
        import measure_verovio as V
        boxes = json.load(open(os.path.join(V.OUT, "truth", name + ".json"), encoding="utf-8"))["boxes"]
    out = []
    for i in range(1, n):
        x, y, w, h, _a = stats[i]
        has_head = any(x <= hx <= x + w and y <= hy <= y + h for hx, hy in heads)
        hit = sorted({b["cls"] for b in boxes if b["box"][0] <= x + w and x <= b["box"][2] and b["box"][1] <= y + h and y <= b["box"][3]})
        if has_head:
            kind = "머리"
        elif st != "verovio":
            kind = "빔 · 기타"
        elif "beam" in hit:
            kind = "빔"
        else:
            kind = "기타:" + ("+".join(hit[:2]) or "상자 없음")
        out.append(dict(set=st, page=name, w=round(w / sp, 2), h=round(h / sp, 2), kind=kind))
    return out


def main():
    import measure_chord_miss as C
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        R = [r for part in ex.map(_page, C.pages()) for r in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "beam_lengths.json"), "w", encoding="utf-8"), ensure_ascii=False)
    bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 2.1), (2.1, 2.5), (2.5, 99)]
    for st in ("verovio", "pdf", "unseen"):
        v = [r for r in R if r["set"] == st]
        kinds = [k for k, _ in Counter(r["kind"] for r in v).most_common()]
        print(f"[{st}] 덩어리 {len(v)}")
        for k in kinds:
            w = [r["w"] for r in v if r["kind"] == k]
            print(f"  {k:24s} {len(w):5d} · " + " · ".join(f"{a}~{b if b < 99 else ''}: {sum(a <= x < b for x in w)}" for a, b in bins))


if __name__ == "__main__":
    main()
