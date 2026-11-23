# -*- coding: utf-8 -*-
"""A-25 사본 — 임시표 전파 경계를 `verify.barline_positions`(이미 라벨 배치가 쓰는 함수, 음표 x 0.9sp 안 세로선 제외)로. 제품 코드 무변경.

`annotate_accidentals`가 부르는 `_find_barlines(no_staff, staff, img_h)`를 가로채, 같은 쪽의 원 이진 영상(오선 있음 — 라벨 배치와 같은 입력)과
그 보표의 음표 x로 `barline_positions`를 부른다.

    python tools/measure_a25_sim.py run <pdf20|unseen|photo|verovio>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from modules import accidental_detect as AD  # noqa: E402
from modules.verify import barline_positions  # noqa: E402

CUR = {}
ORIG_ANN = AD.annotate_accidentals
MODE = {"m": "bp"}          # bp = (가) barline_positions만 · gap = (나) + 흰 틈 보조 규칙
GAP_SP = 0.10               # √(기둥 99% 0.09(Verovio · Aoharu) × 진짜 마디선 최소 0.11) — PDF 기둥 꼬리 99% 0.25와는 겹침(A25_BARLINE.md §7)


def gap_barline_positions(binary, no_staff, staff, notes):
    """`verify.barline_positions` 사본 + 흰 틈 규칙: 0.9sp 안 음표가 있어도 **그 음표들 모두와** 흰 틈(그 음표 y ±0.25sp 행,
    선 ~ 머리 x 사이 빈 열) ≥ GAP_SP면 마디선으로 남긴다. 기둥은 자기 머리와 잉크가 이어져 틈 0."""
    import numpy as np
    top, bottom = int(staff.top), int(staff.bottom)
    band = binary[top:bottom + 1] > 0
    need = (bottom - top) * 0.95
    columns = np.where(band.sum(axis=0) >= need)[0]
    sp = staff.spacing
    near = sp * 0.9
    xs = [x for x, _y in notes]

    def gap(x, nx, ny):
        a, b = sorted((int(x), int(nx)))
        y0, y1 = int(ny - 0.25 * sp), int(ny + 0.25 * sp) + 1
        return int((~(no_staff[y0:y1, a:b + 1] > 0).any(axis=0)).sum()) / sp
    groups = []
    for x in columns:
        close = [(nx, ny) for nx, ny in notes if abs(int(x) - nx) <= near]
        if close and any(gap(x, nx, ny) < GAP_SP for nx, ny in close):
            continue
        if not groups or x - groups[-1][-1] > 3:
            groups.append([int(x)])
        else:
            groups[-1].append(int(x))
    bars = [int(np.mean(g)) for g in groups]
    if xs:
        lo, hi = min(xs), max(xs)
        bars = [b for b in bars if lo < b < hi]
    return bars


def sim_annotate(result, contexts, pitched_notes):
    CUR["binary"] = result.binary
    CUR["xs"], CUR["pts"] = {}, {}
    for n in pitched_notes:
        CUR["xs"].setdefault(n.staff_index, []).append(int(n.x))
        CUR["pts"].setdefault(n.staff_index, []).append((int(n.x), int(n.y)))
    if MODE["m"] == "gap":
        from modules.notehead_detect import remove_staff_lines
        CUR["ns"] = remove_staff_lines(result.binary, result.staves)
    CUR["calls"] = CUR.get("calls", 0) + 1
    return ORIG_ANN(result, contexts, pitched_notes)


def sim_barlines(no_staff, staff, img_h):
    CUR["bar_calls"] = CUR.get("bar_calls", 0) + 1
    if MODE["m"] == "gap":
        return gap_barline_positions(CUR["binary"], CUR["ns"], staff, CUR["pts"].get(staff.index, []))
    return barline_positions(CUR["binary"], staff, CUR["xs"].get(staff.index, ()))


def install():
    """다른 도구를 불러오기 전에 — main.py가 이름으로 가져간 annotate_accidentals까지(측정 함정 B-4)."""
    AD.annotate_accidentals = sim_annotate
    AD._find_barlines = sim_barlines


def run(which, mode="bp"):
    MODE["m"] = mode
    install()
    import measure_a17_ghost6 as G
    G.T1.MAIN.annotate_accidentals = sim_annotate
    if which == "verovio":
        import measure_verovio as V
        V.OUT = os.path.join(ROOT, "debug", "vrv_bl" + ("" if mode == "bp" else "_gap"))
        V.run("base")
    else:
        G.T1.OUT = os.path.join(ROOT, "debug", "a17_cand1_bl" + ("" if mode == "bp" else "_gap"))
        G.set_variant("base")
        G.run_set("base", which)
    print("가로채기 호출", CUR.get("calls"), "마디선", CUR.get("bar_calls"))      # 0이면 측정 무효(측정 함정 B-4)


if __name__ == "__main__":
    run(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "bp")
