# -*- coding: utf-8 -*-
"""A-8 2단계 — 음자리표 클러스터 **시작**을 가를 성질을 찾는다. 측정 전용.

헤더 띠(보표 ±1.5sp)에서 **오선 행(±2px)을 뺀 열 잉크 > 0**인 열의 연속 = 「조각」. 보표마다
음자리표 앞 조각(괄호·시스템 세로줄 등)과 음자리표 몸통 조각의 폭(sp)을 모은다.

- 음자리표 몸통 = 음자리표-조표 틈(`measure_clef_gap` 정의, 조표 없는 악보는 제품 `clef_end` 뒤 첫 빈 연속) 바로 앞
  3sp 안에서 **가장 넓은 조각**
- 앞 조각 = 몸통보다 왼쪽의 모든 조각. `tall_thin`(세로 범위 > 8.5sp) 열은 제품처럼 조각을 끊는다

    python tools/measure_clef_start.py        # 20쪽 원본
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import measure_clef_gap as G  # noqa: E402
import check_accidental_fix as C  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402


def segments(off, tall, x1):
    """[0, x1) 의 조각 (시작, 폭)."""
    m = (off[:x1] > 0) & ~tall[:x1]
    return G.runs(m)


def edge_touch(res, s):
    """열마다 보표 띠(±3sp) 맨 위·맨 아래 2행에 잉크가 있나 — 옆 보표로 이어지는 괄호·세로줄."""
    from modules.notehead_detect import remove_staff_lines
    ns = remove_staff_lines(res.binary, res.staves)
    sp = s.spacing
    top = max(0, int(s.top - sp * 3)); bottom = min(ns.shape[0], int(s.bottom + sp * 3))
    band = ns[top:bottom] > 0
    return band[:2].any(axis=0) | band[-2:].any(axis=0)


def mode_touch():
    """조각마다 (폭 sp, 띠 가장자리 닿음 T)를 음자리표 끝 앞 8sp부터 뒤 3sp까지 전부 나열한다."""
    G.LINE_PAD = 2

    lines = []
    for page, path, pg in C.PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = CK.analyze_staves(res)
        profs = G.staff_profiles(res)
        for s in res.staves:
            c = ctx[s.index]
            if not c.clef_found:
                continue
            p = profs[s.index]
            sp = p["sp"]
            touch = edge_touch(res, s)
            x_end = min(len(p["off"]), c.clef_end + int(sp * 3))
            segs = segments(p["off"], p["tall"], x_end)
            segs = [(a, n) for a, n in segs if a > c.clef_end - 8 * sp]
            desc = []
            for a, n in segs:
                t = bool(touch[a:a + n].any())
                desc.append(f"x{a}:{n / sp:.2f}{'T' if t else ''}")
            lines.append(f"{page:8s} 보표{s.index:2d} {c.clef:6s} clef_end {c.clef_end:4d} | " + " ".join(desc))
    print("\n".join(lines))


def main():
    G.LINE_PAD = 2
    body, before, rows = [], [], []
    for page, path, pg in C.PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = CK.analyze_staves(res)
        profs = G.staff_profiles(res)
        for s in res.staves:
            c = ctx[s.index]
            if not c.clef_found:
                continue
            p = profs[s.index]
            sp = p["sp"]
            empty = p["off"] == 0
            # 음자리표 뒤 틈 시작 gr: 제품 clef_end 근처에서 왼쪽으로 가장 가까운 빈 연속(≥0.54sp)의 시작
            x = min(c.clef_end + int(sp), len(empty) - 1)
            gr = None
            for a, n in reversed(G.runs(empty[:x + 1])):
                if n >= sp * 0.54 and a > sp:
                    gr = a
                    break
            if gr is None:
                continue
            segs = segments(p["off"], p["tall"], gr)
            near = [(a, n) for a, n in segs if a + n > gr - 3 * sp]
            if not near:
                continue
            b = max(near, key=lambda t: t[1])
            body.append(b[1] / sp)
            pre = [(a, n) for a, n in segs if a + n <= b[0]]
            # 몸통 바로 앞 5sp 안의 조각만 (페이지 여백의 잡티 제외)
            pre = [(a, n) for a, n in pre if a + n > b[0] - 5 * sp]
            before += [n / sp for _a, n in pre]
            rows.append(f"{page:8s} 보표{s.index:2d} {c.clef:6s} 몸통 x{b[0]} {b[1] / sp:.2f}sp | 앞 조각 "
                        + " ".join(f"x{a}:{n / sp:.2f}" for a, n in pre))
    print("\n".join(rows))
    body, before = np.array(body), np.array(before)
    print(f"\n음자리표 몸통 {len(body)}개: 최소 {body.min():.2f} · 중앙 {np.median(body):.2f} · 최대 {body.max():.2f}sp")
    if len(before):
        print(f"앞 조각 {len(before)}개: 최소 {before.min():.2f} · 중앙 {np.median(before):.2f} · 최대 {before.max():.2f}sp")
        print("앞 조각 상위 10:", np.round(np.sort(before)[-10:], 2))
    print("몸통 하위 10:", np.round(np.sort(body)[:10], 2))


if __name__ == "__main__":
    mode_touch() if sys.argv[1:] == ["touch"] else main()
