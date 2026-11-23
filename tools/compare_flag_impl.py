# -*- coding: utf-8 -*-
"""표시(check) 구현 검증 — 기준 라벨과 새 라벨(49쪽, `measure_sim_ledger_pair run`)을 비교한다(2026-10-12).

병합 조건(사용자): 라벨 사라짐 · 생김 0 / 새 신호가 진짜 머리를 표시한 수(헛표시) / 바뀐 것은 확신도뿐.
진짜 · 유령은 `debug/beamgap_dynamic.json`(정답 대응 끝난 기준 라벨 행)으로, 시뮬레이션 일치는 그 행에 측정 규칙을 다시 걸어 본다.

    python tools/compare_flag_impl.py <기준> <새> <신호> <규칙>     # 예: main1012 narrow1012 narrow_hole narrow
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


def main(base, new, flag, rule):
    import measure_beamgap_dynamic as B
    rows = {(r["page"], r["x"], r["y"]): r for r in json.load(open(B.OUT, encoding="utf-8"))}
    sim = {k for k, r in rows.items() if B.RULES[rule](r)}
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
    c = Counter()
    flagged, changed, other = set(), [], []
    for f in sorted(os.listdir(os.path.join(LP, base))):
        page = f[:-5]
        A = {key(l): l for l in json.load(open(os.path.join(LP, base, f), encoding="utf-8"))["labels"]}
        p = os.path.join(LP, new, f)
        if not os.path.exists(p):
            c["새 라벨 없는 쪽"] += 1
            continue
        Bn = {key(l): l for l in json.load(open(p, encoding="utf-8"))["labels"]}
        c["사라짐"] += len(A.keys() - Bn.keys())
        c["생김"] += len(Bn.keys() - A.keys())
        for k in A.keys() & Bn.keys():
            a, b = A[k], Bn[k]
            if flag in b["flags"]:
                flagged.add((page, b["x"], b["y"]))
            if set(a["flags"]) - set(b["flags"]) or set(b["flags"]) - set(a["flags"]) - {flag}:
                other.append((page, b["x"], b["y"], a["flags"], b["flags"]))
            if a["confidence"] != b["confidence"]:
                r = rows.get((page, b["x"], b["y"]))
                changed.append((page, b["x"], b["y"], a["confidence"], b["confidence"], r["err"] if r else "?"))
    print(f"쪽 {len(os.listdir(os.path.join(LP, base)))} · 라벨 사라짐 {c['사라짐']} · 생김 {c['생김']} · 새 라벨 없는 쪽 {c['새 라벨 없는 쪽']}")
    print(f"「{flag}」 걸림 {len(flagged)} · 시뮬레이션 걸림 {len(sim)} · 일치 {len(flagged & sim)} · 구현만 {sorted(flagged - sim)} · 시뮬레이션만 {sorted(sim - flagged)}")
    tf = [k for k in flagged if rows.get(k) and rows[k]["err"] != "유령"]
    print(f"신호가 걸린 진짜 머리 {len(tf)}: {sorted(tf)}")
    print(f"확신도 바뀜 {len(changed)}: {dict(Counter((a, b, e or '진짜') for _p, _x, _y, a, b, e in changed))}")
    for ch in changed:
        if ch[5] != "유령":
            print("  진짜 머리 헛표시:", ch)
    print(f"다른 신호가 바뀐 라벨 {len(other)}", other[:5])


if __name__ == "__main__":
    main(*sys.argv[1:5])
