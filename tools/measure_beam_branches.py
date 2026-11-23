# -*- coding: utf-8 -*-
"""빔 픽스처에서 `drop_beam_ghosts`의 조건들이 **실제로 무슨 값을 내는지** 잰다.

측정 전용. `modules/`는 읽기만 한다.

`drop_beam_ghosts`는 **채워진 머리를 조건 계산 전에 통과**시킨다(`verify.py` 「head.filled」).
그래서 빔 악보가 있어도 세 조건(빔 위·빔 사이·빔에 닿음)은 **빈 후보에서만** 돈다.
여기서는 후보마다 판정 불리언이 아니라 **비율 원값**을 남겨, 문턱(0.05·0.30)까지의
여유를 본다. 채워진 머리에도 같은 값을 계산해 「돌았다면」을 따로 적는다.

    python tools/measure_beam_branches.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads, remove_staff_lines
from modules import verify as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "beams")
BEAM_T = 0.05          # verify.drop_beam_ghosts 안의 빔 마스크 문턱


def branch_values(res, heads):
    """`drop_beam_ghosts`와 **같은 식**으로 비율 원값을 낸다(불리언 전)."""
    no_staff = remove_staff_lines(res.binary, res.staves)
    mask = V.beam_mask(res.binary, res.staves)
    narrow = V.beam_mask_strict(res.binary, res.staves)
    by = {s.index: s for s in res.staves}
    rows = []
    for h in heads:
        sp = by[h.staff_index].spacing
        x, y = int(h.x), int(h.y)
        half = max(1, int(sp * 0.5))
        rows.append(dict(
            x=x, y=y, staff=h.staff_index, filled=bool(h.filled), sp=sp,
            on=V._band_ink(mask, x, y - int(sp * 0.2), y + int(sp * 0.2) + 1, half),
            above=V._band_ink(mask, x, y - int(sp * 1.3), y - int(sp * 0.2), half),
            below=V._band_ink(mask, x, y + int(sp * 0.2), y + int(sp * 1.3), half),
            n_above=V._band_ink(narrow, x, y - int(sp * 1.3), y - int(sp * 0.2), half),
            n_below=V._band_ink(narrow, x, y + int(sp * 0.2), y + int(sp * 1.3), half),
            weak=V._side_ink(no_staff, x, y, sp)[0]))
    return rows


def reason(r):
    """`drop_beam_ghosts`의 사유 순서 그대로."""
    if r["on"] > BEAM_T:
        return "빔 위"
    if r["above"] > BEAM_T and r["below"] > BEAM_T:
        return "빔 사이"
    if r["n_above"] > BEAM_T or r["n_below"] > BEAM_T:
        return "빔에 닿음"
    if r["weak"] < V.GHOST_SIDE_THRESHOLD:
        return "좌우에 잉크 없음"
    return ""


def main():
    exp = json.load(open(os.path.join(FIX, "expected.json"), encoding="utf-8"))
    res = preprocess(os.path.join(FIX, "pdf", "beam_melody.pdf"), pdf_dpi=300)
    heads = detect_noteheads(res, contexts=analyze_staves(res))
    rows = branch_values(res, heads)

    # 소스 정답 대응 — PDF 머리 상자 안(Codex의 match_source와 같은 규칙)
    for r in rows:
        r["src"] = None
    for n in exp["notes"]:
        x0, y0, x1, y1 = [v * 300 / 72 for v in n["bbox_pt"]]
        for r in rows:
            if r["staff"] == n["staff_index"] and x0 <= r["x"] <= x1 and y0 <= r["y"] <= y1:
                r["src"] = n
    kept, dropped = V.drop_beam_ghosts(res, heads)
    dropped_xy = {(d["x"], d["y"]): d["reason"] for d in dropped}

    sp = sum(s.spacing for s in res.staves) / len(res.staves)
    print(f"sp={sp:.2f}  검출 {len(rows)}  소스 대응 {sum(1 for r in rows if r['src'])}/104  "
          f"drop_beam_ghosts 삭제 {len(dropped)}")

    def kind(r):
        if r["src"] is None:
            return "소스밖"
        return {8: "8분", 16: "16분", 2: "2분"}[r["src"]["duration_denominator"]]

    print("\n== 무리별: 조건이 실제로 도는가 (filled면 계산 전에 통과)")
    grp = collections.defaultdict(list)
    for r in rows:
        grp[(kind(r), "채움" if r["filled"] else "빈")].append(r)
    for k in sorted(grp):
        rs = grp[k]
        fire = collections.Counter(reason(r) or "-" for r in rs)
        tag = "실제 판정" if k[1] == "빈" else "가상(돌았다면)"
        print(f"  {k[0]:5s} {k[1]:2s} {len(rs):3d}개  {tag:12s} 사유 {dict(fire)}")

    print("\n== 빈 후보 전부 — 원값과 문턱까지 여유")
    for r in sorted((r for r in rows if not r["filled"]), key=lambda r: (r["staff"], r["x"])):
        beam_max = max(r["on"], r["above"] if r["below"] > BEAM_T else 0,
                       r["below"] if r["above"] > BEAM_T else 0, r["n_above"], r["n_below"])
        print(f"  st{r['staff']} ({r['x']:4d},{r['y']:4d}) {kind(r):5s} "
              f"on={r['on']:.3f} ab={r['above']:.3f} be={r['below']:.3f} "
              f"n_ab={r['n_above']:.3f} n_be={r['n_below']:.3f}  weak={r['weak']:.3f} "
              f"(0.30까지 {r['weak'] - V.GHOST_SIDE_THRESHOLD:+.3f})  "
              f"실제삭제={dropped_xy.get((r['x'], r['y']), '-')}")

    print("\n== weak 분포 (문턱 0.30)")
    for k in ("2분", "8분", "16분", "소스밖"):
        ws = sorted(r["weak"] for r in rows if kind(r) == k)
        if ws:
            print(f"  {k:5s} {len(ws):3d}개  최소 {ws[0]:.3f}  하위5 {[round(w, 3) for w in ws[:5]]}  "
                  f"중앙 {ws[len(ws) // 2]:.3f}  0.30~0.40 {sum(1 for w in ws if 0.30 <= w < 0.40)}")


if __name__ == "__main__":
    main()
