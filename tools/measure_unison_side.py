# -*- coding: utf-8 -*-
"""D2 후보 ② — 유니즌 옆 짝 누락 63의 거절 원인 (2026-10-19 · 측정만, 제품 코드 무변경).

대상 = `ERROR_CENSUS_1015` 「2도 · 유니즌」 누락 중 지금 main 라벨(`dblconn`)에서도 빠졌고, 같은 높이(±0.5반칸) 라벨이 1.5sp 안 옆에 있는 것.
쪽마다 `detect_noteheads(reject_log=[])`(제품 첫 검출 단계)를 돌려 누락 자리 ±0.5sp 안 거절 기록의 사유를 센다.
「같은 높이 바로 옆의 중복」으로 지워졌으면 그 쌍(지워진 쪽 · 남은 쪽)의 빈/채움 · 머리 근거(`_head_evidence`와 같은 좌우 띠 잉크) 값을 남긴다.

    python tools/measure_unison_side.py        → debug/unison_side.json (쪽마다 순서대로, 워커 없음)
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "unison_side.json")


def targets():
    P = json.load(open(os.path.join(ROOT, "debug", "error_census.json"), encoding="utf-8"))
    out = defaultdict(list)
    for p in P:
        f = os.path.join(ROOT, "debug", "sim_lp", "dblconn", p["page"] + ".json")
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        L = d["labels"]
        for r in p["rows"]:
            if r["kind"] != "누락" or r["cause"] != "2도 · 유니즌 화음":
                continue
            x, y = r["x"], r["y"]
            st = min(d["staves"], key=lambda s: abs((s["top"] + s["bottom"]) / 2 - y))
            s = st["spacing"]
            if any(l["staff"] == st["id"] and abs(l["x"] - x) <= 0.7 * s and abs(l["y"] - y) <= 0.5 * s for l in L):
                continue
            mates = [l for l in L if l["staff"] == st["id"] and 0.3 * s < abs(l["x"] - x) <= 1.5 * s and abs(l["y"] - y) <= 0.25 * s]
            if mates:
                m = min(mates, key=lambda l: abs(l["x"] - x))
                out[p["page"]].append(dict(set=p["set"], x=x, y=y, staff=st["id"], sp=s, mate=(m["x"], m["y"], m["pitch"], m["confidence"])))
    return out


def main():
    import measure_sim_ledger_pair as S
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads, remove_staff_lines
    pages = {p[1]: p for p in S.pages()}
    T = targets()
    rows = []
    for nm, rs in sorted(T.items()):
        st, _n, path, pg = pages[nm]
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = analyze_staves(res)
        log = []
        heads = detect_noteheads(res, contexts=ctx, reject_log=log)
        ns = remove_staff_lines(res.binary, res.staves)
        for r in rs:
            s = r["sp"]
            near = [g for g in log if abs(g["x"] - r["x"]) <= 0.5 * s and abs(g["y"] - r["y"]) <= 0.5 * s]
            kept = [h for h in heads if abs(h.x - r["mate"][0]) <= 0.5 * s and abs(h.y - r["mate"][1]) <= 0.5 * s]

            def ev(x, y):
                dy = max(1, int(round(s * 0.25)))
                inner, outer = max(1, int(round(s * 0.20))), max(2, int(round(s * 0.55)))
                x, y = int(x), int(y)
                sides = []
                for x0, x1 in ((max(0, x - outer), max(0, x - inner + 1)), (x + inner, x + outer + 1)):
                    strip = ns[max(0, y - dy):y + dy + 1, x0:x1] > 0
                    sides.append(float(strip.mean()) if strip.size else 0.0)
                return round(min(sides), 3)
            rows.append(dict(r, page=nm, reasons=sorted({g["reason"] for g in near}),
                             removed_filled=[g.get("filled") for g in near if "중복" in g["reason"]],
                             mate_filled=[bool(h.filled) for h in kept],
                             ev_missing=ev(r["x"], r["y"]), ev_mate=ev(r["mate"][0], r["mate"][1]),
                             dx=round(abs(r["mate"][0] - r["x"]) / s, 2)))
        print(nm, len(rs), flush=True)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(rows)


def report(rows=None):
    rows = rows or json.load(open(OUT, encoding="utf-8"))
    print("대상", len(rows))
    print("거절 사유:", Counter(" + ".join(r["reasons"]) or "(거절 기록 없음)" for r in rows).most_common())
    dup = [r for r in rows if any("중복" in x for x in r["reasons"])]
    print("중복으로 지워진 것", len(dup), "· (지워진 쪽 채움, 남은 쪽 채움):",
          Counter((tuple(r["removed_filled"]), tuple(r["mate_filled"])) for r in dup).most_common())
    print("  지워진 쪽 근거:", sorted(r["ev_missing"] for r in dup))
    print("  남은 쪽 근거:", sorted(r["ev_mate"] for r in dup))
    print("  거리 dx:", sorted(r["dx"] for r in dup))


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
