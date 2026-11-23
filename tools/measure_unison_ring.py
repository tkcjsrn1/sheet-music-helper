# -*- coding: utf-8 -*-
"""기각 28 재개 조건 — 「같은 높이 바로 옆 중복」이 지운 빈 머리가 진짜 링(사방 잉크)인가 (2026-10-19 · 측정만, 제품 코드 무변경).

49쪽(organ2 · 아오하루 제외)마다 `detect_noteheads(reject_log=[])`를 돌려 사유 「같은 높이 바로 옆의 중복으로 판정」 · 빈 머리(filled=False)인 것을 모은다.
정답(`error_census._truth_*`)에 그 자리(±0.5sp) 머리가 있으면 「진짜」(지우면 안 됐던 것), 없으면 「유령」(지워야 맞는 가짜 구멍).
특징(오선 제거 영상): 중심에서 8방향으로 뻗은 반직선이 타원(가로 0.65sp · 세로 0.5sp) 안에서 잉크를 만나는 방향 수 `dirs`(링이면 8),
중심 ±0.15sp 잉크 비율 `core`(구멍이면 0에 가까움), 짝(남은 꽉 찬 머리)과의 가로 거리 `dx`.

    python tools/measure_unison_ring.py     → debug/unison_ring.json (쪽마다 순서대로)
    python tools/measure_unison_ring.py report
"""
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "unison_ring.json")


def feats(ns, x, y, sp):
    H, W = ns.shape
    dirs = 0
    for k in range(8):
        a = k * math.pi / 4
        hit = False
        for t in range(1, 40):
            r = t / 40
            px, py = int(round(x + math.cos(a) * 0.65 * sp * r)), int(round(y + math.sin(a) * 0.5 * sp * r))
            if 0 <= px < W and 0 <= py < H and ns[py, px]:
                hit = True
                break
        dirs += hit
    c = max(1, int(0.15 * sp))
    core = ns[max(0, int(y) - c):int(y) + c + 1, max(0, int(x) - c):int(x) + c + 1]
    return dirs, round(float((core > 0).mean()) if core.size else 0.0, 2)


def main():
    import measure_sim_ledger_pair as S
    import error_census as EC
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads, remove_staff_lines
    rows = []
    for st, nm, path, pg in S.pages():
        if st == "aoharu" or nm == "organ2":
            continue
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = analyze_staves(res)
        log = []
        heads = detect_noteheads(res, contexts=ctx, reject_log=log)
        ns = remove_staff_lines(res.binary, res.staves) > 0
        truth, _b, _sp = EC._truth_vrv(nm) if st == "verovio" else EC._truth_pdf(nm, path, pg)
        sp_of = {s.index: s.spacing for s in res.staves}
        for g in log:
            if "중복" not in g["reason"] or g.get("filled"):
                continue
            sp = sp_of[g["staff"]]
            real = any(abs(h["x"] - g["x"]) <= 0.5 * sp and abs(h["y"] - g["y"]) <= 0.5 * sp for h in truth)
            mate = [h for h in heads if h.staff_index == g["staff"] and 0.6 * sp <= abs(h.x - g["x"]) <= 1.3 * sp and abs(h.y - g["y"]) <= 0.35 * sp]
            d, core = feats(ns, g["x"], g["y"], sp)
            rows.append(dict(set=st, page=nm, x=int(g["x"]), y=int(g["y"]), real=real, dirs=d, core=core,
                             dx=round(min((abs(h.x - g["x"]) for h in mate), default=0) / sp, 2),
                             mate_filled=[bool(h.filled) for h in mate]))
        print(nm, sum(1 for r in rows if r["page"] == nm), flush=True)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(rows)


def report(rows=None):
    rows = rows or json.load(open(OUT, encoding="utf-8"))
    for real in (True, False):
        R = [r for r in rows if r["real"] == real]
        print("진짜(지우면 안 됐음)" if real else "유령(지워야 맞음)", len(R))
        print("   dirs:", sorted(Counter(r["dirs"] for r in R).items()))
        print("   core:", sorted(r["core"] for r in R))
        print("   dx:", sorted(r["dx"] for r in R))


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
