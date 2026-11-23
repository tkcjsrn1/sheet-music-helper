# -*- coding: utf-8 -*-
"""오선 안 기타 유령 「머리 옆」 24(ERROR_CENSUS_1015 큐 4번) — 같은 음 라벨이 가로로 바로 옆에 붙은 쌍(측정만, 라벨 파일만 씀).

쌍 = 같은 보표 · 같은 음고 · 가로 DX_LO~DX_HI sp · 세로 ≤ DY_SP sp. 기각 32(세로 0.5~0.9sp 중복을 지움)와 다른 거리대 · 표시만.
쌍의 두 라벨을 정답 대응(`debug/error_census.json` 유령 목록)으로 「진짜+유령」 · 「진짜+진짜(유니즌 등)」 · 「유령+유령」으로 센다.
라벨 = `debug/sim_lp/flatc1u`(census와 같은 것) · Mutopia = `debug/inputs_score/mutopia`(정답 위치만).

    python tools/measure_side_dup.py
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DX_LO, DX_HI, DY_SP = 0.6, 1.2, 0.3


def main():
    P = json.load(open(os.path.join(ROOT, "debug", "error_census.json"), encoding="utf-8"))
    c, dx = Counter(), {}
    for p in P:
        n = p["page"]
        f = os.path.join(ROOT, "debug", "sim_lp", "flatc1u", n + ".json")
        if not os.path.exists(f):
            f = os.path.join(ROOT, "debug", "inputs_score", "mutopia", n + ".json")
        d = json.load(open(f, encoding="utf-8"))
        ghost = {(r["x"], r["y"]) for r in p["rows"] if r["kind"] == "유령"}
        sp = {s["id"]: s["spacing"] for s in d["staves"]}
        L = d["labels"]
        for i, a in enumerate(L):
            for b in L[i + 1:]:
                if a["staff"] != b["staff"] or a["pitch"] != b["pitch"]:
                    continue
                s = sp[a["staff"]]
                h, v = abs(a["x"] - b["x"]) / s, abs(a["y"] - b["y"]) / s
                if DX_LO <= h <= DX_HI and v <= DY_SP:
                    g = sum((l["x"], l["y"]) in ghost for l in (a, b))
                    k = ("유령+유령", "진짜+유령", "진짜+진짜")[2 - g]
                    c[(p["set"], k)] += 1
                    dx.setdefault(k, []).append(round(h, 2))
    for st in ("pdf", "unseen", "verovio", "mutopia"):
        print(st, {k[1]: v for k, v in c.items() if k[0] == st})
    for k, v in dx.items():
        print(k, sorted(v))


if __name__ == "__main__":
    main()
