# -*- coding: utf-8 -*-
"""오류 총조사 두 기준 비교표 (2026-10-20 · 측정만) — `error_census.py` 출력 JSON 둘을 세트별로 나란히 놓는다.

「확실」 정밀도 = 1 − (확실 유령 + 확실 음고 틀림 + 확실 표기 틀림) / 확실 라벨 수. 확실 라벨 수는 라벨 파일에서 센다
(49쪽 `debug/sim_lp/<이름>`, Mutopia `debug/inputs_score/mutopia` — 이 폴더는 하나뿐이라 두 기준에 같은 라벨).

    python tools/census_compare.py <기준이름> <새이름>      # debug/error_census_<이름>.json
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS = ("pdf", "unseen", "verovio", "mutopia")


def certain_labels(variant, s, page):
    p = (os.path.join(ROOT, "debug", "inputs_score", "mutopia", page + ".json") if s == "mutopia"
         else os.path.join(ROOT, "debug", "sim_lp", variant, page + ".json"))
    return sum(l["confidence"] == "certain" for l in json.load(open(p, encoding="utf-8"))["labels"])


def table(variant):
    P = json.load(open(os.path.join(ROOT, "debug", f"error_census_{variant}.json"), encoding="utf-8"))
    t = {s: Counter() for s in SETS}
    for p in P:
        c = t[p["set"]]
        c["쪽"] += 1
        c["머리"] += p["heads"]
        c["확실 라벨"] += certain_labels(variant, p["set"], p["page"])
        for r in p["rows"]:
            c[r["kind"]] += 1
            if r["certain"]:
                c[r["kind"] + " 확실"] += 1
    return t


def main(a, b):
    A, B = table(a), table(b)
    tot = lambda T: sum(T.values(), Counter())
    print(f"| 세트 | 쪽 | 누락률 {a} → {b} | 유령(확실) | 음고 틀림(확실) | 표기 틀림(확실) | 「확실」 정밀도 {a} → {b} |")
    print("|---|---:|---|---|---|---|---|")
    for name, x, y in [(s, A[s], B[s]) for s in SETS] + [("합계", tot(A), tot(B))]:
        prec = lambda c: (c["확실 라벨"] - c["유령 확실"] - c["음고 틀림 확실"] - c["표기 틀림 확실"], c["확실 라벨"])
        pa, pb = prec(x), prec(y)
        f = lambda k: f"{x[k]} ({x[k + ' 확실']}) → **{y[k]} ({y[k + ' 확실']})**"
        print(f"| {name} | {y['쪽']} | {x['누락']}/{x['머리']} ({100 * x['누락'] / max(1, x['머리']):.2f}%) → "
              f"**{y['누락']} ({100 * y['누락'] / max(1, y['머리']):.2f}%)** | {f('유령')} | "
              + (f"{f('음고 틀림')} | {f('표기 틀림')}" if name != "mutopia" else "— | —")
              + f" | {pa[0]}/{pa[1]} ({100 * pa[0] / max(1, pa[1]):.2f}%) → **{pb[0]}/{pb[1]} ({100 * pb[0] / max(1, pb[1]):.2f}%)** |")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
