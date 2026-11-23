# -*- coding: utf-8 -*-
"""§1-48 검증 보조 — 기준 · 새 라벨(Verovio 20쪽)에서 정답 머리마다 「맞음」(음고 + 표기)을 가르고, 맞던 머리가 틀리게 된 것(새로 틀림)을 확신도별로 센다.
머리 짝: 가로 0.7sp · 세로 0.5sp 안 가장 가까운 라벨(compare_change_impl과 같은 창). 측정만.

    python tools/judge_wide3.py <기준> <새>              # 개발 Verovio 20쪽(debug/sim_lp)
    python tools/judge_wide3.py <기준> <새> holdout      # 보류 12쪽(debug/vrv_holdout, 채점만)
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LP = os.path.join(ROOT, "debug", "sim_lp")
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
NORM = lambda a: {"natural": "", None: ""}.get(a, a)


def state(L, h):
    near = [l for l in L if abs(l["x"] - h["x"]) <= 0.7 * 18 and abs(l["y"] - h["y"]) <= 0.5 * 18]
    if not near:
        return "누락", None
    l = min(near, key=lambda l: abs(l["x"] - h["x"]) + abs(l["y"] - h["y"]))
    ok = l["pitch"] == h["note_name"] + h["octave"] and ACC(l["text"]) == NORM(h["eff"] or "")
    return ("맞음" if ok else "틀림"), l


if __name__ == "__main__":
    base, new = sys.argv[1:3]
    if sys.argv[3:4] == ["holdout"]:
        LP = os.path.join(ROOT, "debug", "vrv_holdout")
        TR = os.path.join(LP, "truth")
    else:
        TR = os.path.join(ROOT, "debug", "vrv", "truth")
    c, rows = Counter(), []
    for f in sorted(os.listdir(os.path.join(LP, new))):
        if not f.endswith(".json"):
            continue
        nm = f[:-5]
        if not os.path.exists(os.path.join(TR, f)):
            continue
        T = json.load(open(os.path.join(TR, f), encoding="utf-8"))["notes"]
        A = json.load(open(os.path.join(LP, base, f), encoding="utf-8"))["labels"]
        B = json.load(open(os.path.join(LP, new, f), encoding="utf-8"))["labels"]
        for h in T:
            (sa, la), (sb, lb) = state(A, h), state(B, h)
            if sa != sb:
                c[(sa, sb, lb["confidence"] if lb else "-")] += 1
                if sa == "맞음":
                    rows.append((nm, h["x"], h["y"], h["note_name"] + h["octave"], h["eff"], la["text"], lb and (lb["text"], lb["confidence"])))
    for k, v in sorted(c.items()):
        print(" → ".join(k[:2]), "(새 확신도", k[2] + ")", v)
    print("새로 틀림 · 누락(맞던 머리):")
    for r in rows:
        print("  ", *r)
