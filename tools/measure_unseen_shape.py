# -*- coding: utf-8 -*-
"""[3] 보지 않은 악보 누락 중 「머리 후보 없음 · 모양 판정」 — 어떤 모양에서 떨어지나. 제품 코드 무변경.

누락 행 = `measure_unseen_causes._page`(라벨 = 지금 main). 정답 머리마다(PDF 글리프):
  머리 종류(s2 꽉 참 · s1/s0 빈), 같은 덩어리(오선 제거 영상 8연결 성분)에 붙은 정답 머리 수,
  기둥 방향(정답 기둥 `pdf_verticals` stem이 머리 오른쪽 위로 → 위, 왼쪽 아래로 → 아래, 없음),
  덩어리 폭(sp — 빔으로 이어지면 넓다), 머리 자리 열림 뒤 남는 잉크 비율(제품 꽉 찬 머리 검출은 타원 열림 뒤 덩어리).

    python tools/measure_unseen_shape.py
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
    from measure_barline_stem import pdf_verticals
    from measure_normalize_sp import truth_at
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    name, path, pg = job
    rows = [r for r in U._page(job)[2] if r["stage"] == "머리 후보 없음 · 모양 판정"]
    if not rows:
        return []
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    heads = truth_at(path, pg, 1.0)[0]
    stems = [(x, a, b) for x, a, b, k in pdf_verticals(os.path.join(ROOT, path), pg) if k == "stem"]
    ns = (remove_staff_lines(res.binary, res.staves) > 0).astype(np.uint8)
    sp0 = float(np.median([s.spacing for s in res.staves]))
    # 제품처럼 오선 제거 구멍을 세로로 메운 뒤(`_detect_noteheads_in_band` patched)
    ns = cv2.morphologyEx(ns, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp0 * 0.4)) | 1)))
    n, lab, stats, _c = cv2.connectedComponentsWithStats(ns, connectivity=8)

    ekp = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, int(sp0 * 0.65)) | 1, max(3, int(sp0 * 0.5)) | 1))
    op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, ekp)
    on, olab, ostats, _oc = cv2.connectedComponentsWithStats(op, connectivity=8)

    def ocomp_at(cx, cy):
        w = olab[max(0, int(cy) - 2):int(cy) + 3, max(0, int(cx) - 2):int(cx) + 3]
        v = w[w > 0]
        return int(np.bincount(v).argmax()) if v.size else 0

    def comp_at(cx, cy):
        w = lab[max(0, int(cy) - 2):int(cy) + 3, max(0, int(cx) - 2):int(cx) + 3]
        v = w[w > 0]
        return int(np.bincount(v).argmax()) if v.size else 0
    out = []
    for r in rows:
        sp = r["sp"]
        x, y = int(r["x"]), int(r["y"])
        comp = comp_at(x, y)
        same = sum(1 for h in heads if comp and comp_at(h["cx"], h["cy"]) == comp)
        st = [s for s in stems if abs(s[0] - x) <= 0.8 * sp and s[1] - 0.6 * sp <= y <= s[2] + 0.6 * sp]
        stem = "없음" if not st else ("위" if st[0][0] > x and st[0][1] < y - 0.5 * sp else "아래" if st[0][2] > y + 0.5 * sp else "기둥 끝")
        hw, hh = int(0.65 * sp), int(0.55 * sp)
        crop = ns[max(0, y - hh):y + hh + 1, max(0, x - hw):x + hw + 1]
        big = ns[max(0, y - 3 * hh):y + 3 * hh + 1, max(0, x - 3 * hw):x + 3 * hw + 1]
        ek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, int(sp * 0.65)) | 1, max(3, int(sp * 0.5)) | 1))   # 제품 꽉 찬 머리 열림 커널
        ob = cv2.morphologyEx(big, cv2.MORPH_OPEN, ek)
        cy0, cx0 = y - max(0, y - 3 * hh), x - max(0, x - 3 * hw)
        opened = ob[max(0, cy0 - hh):cy0 + hh + 1, max(0, cx0 - hw):cx0 + hw + 1]
        oc = ocomp_at(x, y)
        o_heads = sum(1 for h in heads if oc and ocomp_at(h["cx"], h["cy"]) == oc)
        out.append(dict(page=name, x=x, y=y, head=r["name"].split(".")[-1], same=same, stem=stem, o_heads=o_heads,
                        o_w=round(ostats[oc, cv2.CC_STAT_WIDTH] / sp, 2) if oc else 0, o_h=round(ostats[oc, cv2.CC_STAT_HEIGHT] / sp, 2) if oc else 0,
                        comp_w=round(stats[comp, cv2.CC_STAT_WIDTH] / sp, 1) if comp else 0,
                        ink=round(float(crop.mean()), 2) if crop.size else 0, opened=round(float(opened.mean()), 2) if opened.size else 0))
    return out


def main():
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, [u for u in G.UNSEEN if u[0] != "organ2"]) for r in part]
    print(f"모양 판정 누락 {len(rows)}: 머리 {dict(Counter(r['head'] for r in rows))} · 쪽 {dict(Counter(r['page'] for r in rows))}")
    print("  같은 덩어리 정답 머리 수(자기 포함):", dict(sorted(Counter(min(r["same"], 6) for r in rows).items())))
    print("  열림 뒤 덩어리에 든 정답 머리 수:", dict(sorted(Counter(min(r["o_heads"], 5) for r in rows).items())))
    s2 = [r for r in rows if r["head"] == "s2" and r["o_heads"] >= 1]
    print("  꽉 찬 머리 · 열림 뒤 덩어리 폭 · 높이(sp) 중앙:", np.median([r["o_w"] for r in s2]) if s2 else "-", np.median([r["o_h"] for r in s2]) if s2 else "-")
    print("  기둥 방향:", dict(Counter(r["stem"] for r in rows)))
    print("  덩어리 폭(sp) ≥ 4(빔 · 여러 음 연결):", sum(r["comp_w"] >= 4 for r in rows), "/", len(rows))
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (5, 25, 50, 75, 95))
    print("  머리 자리 잉크 비율 5 · 25 · 50 · 75 · 95%:", pct([r["ink"] for r in rows]))
    print("  제품 타원 열림 뒤 남는 비율:", pct([r["opened"] for r in rows]), "| 0.1 미만(열림이 머리를 지움):", sum(r["opened"] < 0.1 for r in rows))
    for r in rows:
        print("   ", r)




def pairs():
    """열림 뒤 정답 머리 2개 덩어리(누락)의 폭 · 높이 분포 — 제품 `w > 2.2sp` 버림과 대조."""
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, [u for u in G.UNSEEN if u[0] != "organ2"]) for r in part]
    p = [r for r in rows if r["o_heads"] == 2]
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (0, 5, 50, 95, 100))
    print(f"머리 2개 덩어리 {len(p)}: 폭(sp) 최소 · 5 · 50 · 95 · 최대 {pct([r['o_w'] for r in p])} | 높이 {pct([r['o_h'] for r in p])}")
    print("  폭 > 2.2sp(제품이 「가로로 긴 덩어리」로 버림):", sum(r["o_w"] > 2.2 for r in p), "· 머리:", dict(Counter(r["head"] for r in p)), "· 기둥:", dict(Counter(r["stem"] for r in p)))


if __name__ == "__main__":
    pairs() if sys.argv[1:] == ["pairs"] else main()
