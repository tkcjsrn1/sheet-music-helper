# -*- coding: utf-8 -*-
"""(d) 곡 중간 조바꿈 — 보표(시스템)마다 조표를 따로 읽는 안의 정답률. 제품 코드 무변경.

입력: `debug/keysig_fix/bars.json` · `bars_extra.json`(제품 `_analyze_one` 보표별 막대, `measure_keysig_vote_fix.py collect`).
투표는 제품 사본 `vote_max(flat_pos=True)`(DECISIONS §1-10). 정답: Verovio = SVG 보표별 머리 조표, 그 밖 = 쪽 조표.
시스템: Verovio = SVG system 번호, 그 밖 = 보표 두 개씩(피아노 큰보표).

  쪽     지금 제품(쪽 전체 한 번)
  시스템 시스템마다 따로
  혼합   첫 시스템(가장 위)은 쪽 투표, 그 뒤 시스템은 자기 시스템 투표

    python tools/measure_key_change.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import measure_keysig_vote_fix as M  # noqa: E402


def key(v):
    return ("", 0) if v in ("0", None) else ({"s": "♯", "f": "♭"}[v[-1]], int(v[:-1]))


def main():
    c = Counter()
    for f in ("bars.json", "bars_extra.json"):
        for r in json.load(open(os.path.join(ROOT, "debug", "keysig_fix", f), encoding="utf-8")):
            ps = sorted(r["staves"], key=lambda s: s["i"])
            if r["set"] == "verovio":
                t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", r["name"] + ".json"), encoding="utf-8"))
                if len(t["staves"]) != len(ps):
                    continue
                sys_of = [ts["system"] for ts in t["staves"]]
                want = [key(ts["keysigs"][0]["val"] if ts["keysigs"] else "0") for ts in t["staves"]]
            else:
                sys_of = [i // 2 for i in range(len(ps))]
                want = [tuple(r["truth"])] * len(ps)
            groups = defaultdict(list)
            for s, g in zip(ps, sys_of):
                groups[g].append(s)
            page = tuple(M.vote_max(r["staves"], flat_pos=True))
            first = min(sys_of)
            for s, g, w in zip(ps, sys_of, want):
                sv = tuple(M.vote_max(groups[g], flat_pos=True))
                mix = page if g == first else sv
                st = r["set"]
                c[(st, "보표")] += 1
                c[(st, "쪽")] += page == w
                c[(st, "시스템")] += sv == w
                c[(st, "혼합")] += mix == w
                if w != want[0]:
                    c[(st, "조바뀐 보표")] += 1
                    c[(st, "조바뀐 · 혼합 맞음")] += mix == w
    for st in ("verovio", "pdf", "aoharu", "fixture", "photo", "sweep"):
        if c[(st, "보표")]:
            print(f"{st:8s} 보표 {c[(st, '보표')]:5d} | 쪽 {c[(st, '쪽')]:5d} · 시스템 {c[(st, '시스템')]:5d} · 혼합 {c[(st, '혼합')]:5d}"
                  + (f" | 머리 조표가 첫 보표와 다른 보표 {c[(st, '조바뀐 보표')]} 중 혼합 맞음 {c[(st, '조바뀐 · 혼합 맞음')]}" if c[(st, "조바뀐 보표")] else ""))


if __name__ == "__main__":
    main()
