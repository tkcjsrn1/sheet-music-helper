# -*- coding: utf-8 -*-
"""판단 5 구현 판정 — 글리프 모양 check(§1-20) 전후 라벨 대조. 전 = `debug/sim_lp/impl`(직전 main), 후 = `debug/sim_lp/gshape`(구현 뒤 제품).
조건: 라벨 사라짐 · 생김 0, 걸린(glyph_shape) 라벨 중 진짜 머리 ≤ 7 · 그중 원래 확실 ≤ 4. 제품 코드 무변경.

    python tools/measure_sim_ledger_pair.py run gshape && python tools/check_glyph_shape_labels.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _one(job):
    import measure_sim_ledger_pair as S
    st, name, path, pg = job
    A = json.load(open(os.path.join(S.OUT, "impl", name + ".json"), encoding="utf-8"))["labels"]
    B = json.load(open(os.path.join(S.OUT, "gshape", name + ".json"), encoding="utf-8"))["labels"]
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"], l["pitch"])
    c = Counter()
    c["사라짐"] = len({key(l) for l in A} - {key(l) for l in B})
    c["생김"] = len({key(l) for l in B} - {key(l) for l in A})
    before = {key(l): l["confidence"] for l in A}
    hit = [l for l in B if "glyph_shape" in l["flags"]]
    c["걸림"] = len(hit)
    c["확신도 바뀜"] = sum(before.get(key(l)) != l["confidence"] for l in B)
    if st == "aoharu":
        c["Aoharu 걸림(전부 헛표시)"] = len(hit)
        return st, c
    heads, sp = S._truth(st, name, path, pg)
    for l in hit:
        real = any(abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp for h in heads)
        c["걸린 진짜 머리" if real else "걸린 유령"] += 1
        if real:
            print(f"   진짜 머리 {st} {name} 보표 {l['staff']} ({l['x']}, {l['y']}) {l['text']} 원래 {before.get(key(l))}", flush=True)
        if real and before.get(key(l)) == "certain":
            c["진짜 머리 확실 → check"] += 1
    return st, c


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one, S.pages()))
    tot = Counter()
    for st, c in res:
        tot.update({f"{st} {k}": v for k, v in c.items()})
        tot.update({f"합 {k}": v for k, v in c.items()})
    for k in sorted(tot):
        print(k, tot[k])


if __name__ == "__main__":
    main()
