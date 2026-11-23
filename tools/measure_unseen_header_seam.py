# -*- coding: utf-8 -*-
"""[8] 보지 않은 악보 누락 중 「헤더 안 27」 · 「이음매/링 조각 22」 — 제품 코드 무변경.

누락 행 = `measure_unseen_causes._page`(라벨 = 지금 main).
헤더 안: 머리 x와 헤더 끝 · 머리 음자리표 끝 · 조표 끝(막대 최우측 + 0.5sp)의 거리(sp). 헤더 끝이 무엇 때문에 그 자리인지(조표 끝보다 얼마나 뒤인가).
  비교로 같은 보표의 「헤더 뒤 첫 정답 머리」(검출된 것)의 헤더 끝 거리 분포 — 헤더 끝을 당기면 그 사이 무엇이 들어오는가.
이음매/링 조각: 지워진 진짜 머리(정답 꽉 찬 머리인가) 주변(±0.8sp, ±2.5sp)의 막힌 구멍(오선 제거 영상의 배경 성분, 창 테두리에 안 닿음,
  넓이 0.1~1.5sp²)이 머리 위 · 아래 · 양쪽 중 어디에 있는가, 그 구멍 자리에 정답 빈 머리(s0 · s1)가 있는가.

    python tools/measure_unseen_header_seam.py
"""
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


def _page(job):
    import measure_unseen_causes as U
    from measure_normalize_sp import truth_at
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    name, path, pg = job
    _n, _c, rows = U._page(job)
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    heads = truth_at(path, pg, 1.0)[0]
    ns = remove_staff_lines(res.binary, res.staves) > 0
    out = []
    for r in rows:
        sp, c = r["sp"], ctx.get(r["staff"])
        if r["stage"] == "헤더 안" and c is not None:
            key_end = max(b for b, _y in c.bars) + 0.5 * sp if c.key_count and c.bars else c.clef_end
            out.append(dict(kind="헤더", page=name, x=round(r["x"]), d_hdr=round((c.header_end - r["x"]) / sp, 2),
                            d_clef=round((r["x"] - c.clef_end) / sp, 2), d_key=round((r["x"] - key_end) / sp, 2),
                            hdr_after_key=round((c.header_end - key_end) / sp, 2), keys=c.key_count))
        elif r["stage"].startswith("검출 내부 필터(이음매"):
            x, y = int(r["x"]), int(r["y"])
            x0, y0 = max(0, int(x - 0.8 * sp)), max(0, int(y - 2.5 * sp))
            win = ~ns[y0:int(y + 2.5 * sp), x0:int(x + 0.8 * sp)]
            n, lab, st, cen = cv2.connectedComponentsWithStats(win.astype(np.uint8), connectivity=4)
            holes = []
            for i in range(1, n):
                bx, by, bw, bh, a = st[i]
                if bx == 0 or by == 0 or bx + bw >= win.shape[1] or by + bh >= win.shape[0] or not (0.1 * sp * sp <= a <= 1.5 * sp * sp):
                    continue
                hy = y0 + cen[i][1]
                real = any(h["name"] in ("noteheads.s0", "noteheads.s1") and abs(h["cx"] - (x0 + cen[i][0])) <= 0.6 * sp and abs(h["cy"] - hy) <= 0.4 * sp for h in heads)
                holes.append(("위" if hy < y else "아래", real))
            sides = {s for s, _r in holes}
            out.append(dict(kind="이음매", page=name, x=x, y=y, head=r["name"].split(".")[-1],
                            sides="양쪽" if sides == {"위", "아래"} else (next(iter(sides)) if sides else "구멍 없음"),
                            real_holes=sum(1 for _s, rr in holes if rr), fake_holes=sum(1 for _s, rr in holes if not rr)))
    return out


def main():
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, [u for u in G.UNSEEN if u[0] != "organ2"]) for r in part]
    hd = [r for r in rows if r["kind"] == "헤더"]
    print(f"헤더 안 {len(hd)}: 쪽 {dict(Counter(r['page'] for r in hd))}")
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (0, 25, 50, 75, 100)) if a else "-"
    print("  헤더 끝 − 머리(sp) 최소 · 25 · 50 · 75 · 최대:", pct([r["d_hdr"] for r in hd]))
    print("  머리 − 조표 끝(sp):", pct([r["d_key"] for r in hd]), "| 조표 끝 뒤에 있음", sum(r["d_key"] > 0 for r in hd))
    print("  헤더 끝 − 조표 끝(sp):", pct([r["hdr_after_key"] for r in hd]))
    sm = [r for r in rows if r["kind"] == "이음매"]
    print(f"이음매/링 조각 {len(sm)}: 머리 {dict(Counter(r['head'] for r in sm))} · 구멍 자리 {dict(Counter(r['sides'] for r in sm))}"
          f" · 진짜 빈 머리 구멍 있음 {sum(r['real_holes'] > 0 for r in sm)} · 가짜 구멍만 {sum(r['real_holes'] == 0 and r['fake_holes'] > 0 for r in sm)}")
    for r in rows:
        print("   ", r)


if __name__ == "__main__":
    main()
