# -*- coding: utf-8 -*-
"""§1-42 빔 위 채워진 머리 → check 구현 검증(2026-10-16) — 기준 · 새 라벨(49쪽, `measure_sim_ledger_pair run`)의 확신도 변화.

병합 조건(사용자 10-16): 라벨 생김 · 사라짐 0 / 헛표시(진짜 라벨의 확신도 내림) ≤ 「확실」 감소량의 절반 / 골든 711 / 스냅샷 판정.
진짜 · 유령 = `debug/error_census.json`(같은 좌표 라벨 — 그 뒤 §1-40 · §1-41은 표시만이라 좌표 같음). Aoharu는 정답 골든(전부 진짜).

    python tools/compare_fbeam_impl.py <기준> <새>       # 예: textrow fbeam
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def main(base, new):
    import measure_sim_ledger_pair as S
    P = json.load(open(os.path.join(ROOT, "debug", "error_census.json"), encoding="utf-8"))
    ghost = {p["page"]: {(r["x"], r["y"]) for r in p["rows"] if r["kind"] == "유령"} for p in P}
    c = Counter()
    for st, n, _p, _pg in S.pages():
        a = os.path.join(ROOT, "debug", "sim_lp", base, n + ".json")
        if not os.path.exists(a):
            continue
        key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
        A = {key(l): l for l in json.load(open(a, encoding="utf-8"))["labels"]}
        B = {key(l): l for l in json.load(open(os.path.join(ROOT, "debug", "sim_lp", new, n + ".json"), encoding="utf-8"))["labels"]}
        c["사라짐"] += len(A.keys() - B.keys())
        c["생김"] += len(B.keys() - A.keys())
        for k in A.keys() & B.keys():
            la, lb = A[k], B[k]
            if la["confidence"] == lb["confidence"]:
                continue
            g = (la["x"], la["y"]) in ghost.get(n, set()) and st != "aoharu"
            what = "유령" if g else "진짜(헛표시)"
            c[f"{what} {la['confidence']} → {lb['confidence']}"] += 1
            c[f"{st} 바뀜"] += 1
            if not g:
                print("  헛표시", st, n, la["x"], la["y"], la["text"], la["confidence"], "→", lb["confidence"], lb["flags"])
    for k, v in sorted(c.items()):
        print(f"{k}: {v}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
