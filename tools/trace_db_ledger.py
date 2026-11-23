# -*- coding: utf-8 -*-
"""쇼팽 D♭ 녹턴 — 라벨이 안 붙은 PDF 음표 머리 전수, 특히 **두 보표 사이의 높은 덧줄 음표**. 측정 전용.

PDF 음표 머리 글리프(`measure_omission_rate.pdf_glyphs`, 일반 크기만)를 정답으로 두고 제품 결과 라벨
(`check_accidental_fix.snapshot_page` — 제품 경로와 같은 순서)과 짝짓는다(가로 0.7sp · 세로 0.5sp, `measure_omission_rate.match`).
라벨 없는 머리마다 **위·아래 보표 각각을 기준으로** 음고와 덧줄 수를 낸다 — 두 보표 사이 음표는 어느 보표에
속하는지가 음고를 가르기 때문이다(`truth_pitch`는 가장 가까운 보표 하나만 본다). 음자리표는 PDF 글리프로 정한다.

    python tools/trace_db_ledger.py [쪽 번호(1부터) ...]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import measure_omission_rate as M  # noqa: E402
import check_accidental_fix as C  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402

PDF = "test_scores/chopin_nocturne_Db_6-8.pdf"
LET = "CDEFGAB"
BOTTOM = {"treble": ("E", 4), "bass": ("G", 2)}


def clef_of(staff, clefs, cx):
    """그 보표에서 cx 왼쪽 가장 가까운 PDF 음자리표."""
    mid = (staff.top + staff.bottom) / 2
    mine = [c for c in clefs if abs(c["cy"] - mid) <= staff.spacing * 3 and c["cx"] < cx]
    if not mine:
        return "treble"
    return "bass" if max(mine, key=lambda c: c["cx"])["name"].startswith("clefs.F") else "treble"


def pitch_on(staff, clef, cy):
    """보표 기준 음고와 덧줄 수(위 +, 아래 −)."""
    step = int(round((staff.line_ys[-1] - cy) / (staff.spacing / 2.0)))
    letter, octave = BOTTOM[clef]
    i = LET.index(letter) + step
    led = (step - 8) // 2 if step > 8 else (-((-step) // 2) if step < 0 else 0)
    return f"{LET[i % 7]}{octave + i // 7}", led, step


def page(pg):
    res = preprocess(os.path.join(ROOT, PDF), pdf_page=pg)
    staves = res.staves
    sp = sum(s.spacing for s in staves) / len(staves)
    g = M.pdf_glyphs(PDF, pg)
    heads = [x for x in g if x["name"].startswith("noteheads.") and x["size"] >= 15]
    clefs = [x for x in g if x["name"].startswith("clefs.")]
    labels = C.snapshot_page(PDF, pg)["labels"]
    _pairs, used_t, _used_l = M.match(heads, labels, sp)
    rows = []
    for ti, h in enumerate(heads):
        if ti in used_t:
            continue
        above = [s for s in staves if (s.top + s.bottom) / 2 <= h["cy"]]
        below = [s for s in staves if (s.top + s.bottom) / 2 > h["cy"]]
        desc = []
        for tag, s in (("위 보표", above[-1] if above else None), ("아래 보표", below[0] if below else None)):
            if s is None:
                continue
            clef = clef_of(s, clefs, h["cx"])
            p, led, _st = pitch_on(s, clef, h["cy"])
            d = (h["cy"] - (s.top + s.bottom) / 2) / s.spacing
            desc.append(f"{tag} {s.index}({clef}) {p} 덧줄 {led:+d} 중심에서 {d:+.2f}sp")
        rows.append((h, desc))
    return res, rows, heads, labels


if __name__ == "__main__":
    pages = [int(a) - 1 for a in sys.argv[1:]] or list(range(6))
    for pg in pages:
        res, rows, heads, labels = page(pg)
        print(f"== {pg + 1}쪽: 일반 머리 {len(heads)} · 라벨 {len(labels)} · 라벨 없는 머리 {len(rows)}")
        for h, desc in rows:
            print(f"  ({h['cx']:.0f},{h['cy']:.0f}) {h['name']:18s} | " + " | ".join(desc), flush=True)
