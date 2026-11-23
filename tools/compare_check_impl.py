# -*- coding: utf-8 -*-
"""check 표시 신호 구현 검증 — 기준 · 새 라벨(49쪽, `measure_sim_ledger_pair run`) 대조 (2026-10-18, §1-44 머리 옆 쌍).

  생김 · 사라짐 = (보표, x, y, 음고, 표기) 집합 차 — 표시 신호는 0이어야 한다
  확신도 바뀜 = 같은 라벨의 confidence 변화. 「확실 → check」를 정답(`error_census._truth_*` 대응)으로
      유령(대응 머리 없음) = 감소 · 진짜(대응 머리 있음) = 헛표시로 가른다. 아오하루는 정답 골든이라 바뀐 수만(0이어야 함)

    python tools/compare_check_impl.py <기준> <새> [신호 이름]
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


def _job(job):
    import error_census as EC
    base, new, flag, (st, nm, path, pg) = job
    load = lambda v: json.load(open(os.path.join(LP, v, nm + ".json"), encoding="utf-8"))["labels"]
    A, B = load(base), load(new)
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
    ka, kb = Counter(map(key, A)), Counter(map(key, B))
    c = Counter(생김=sum((kb - ka).values()), 사라짐=sum((ka - kb).values()))
    old = {key(l): l["confidence"] for l in A}
    moved = [l for l in B if key(l) in old and old[key(l)] != l["confidence"]]
    c["확신도 바뀜"] = len(moved)
    rows = []
    if moved and st != "aoharu":
        heads, _b, sp = EC._truth_vrv(nm) if st == "verovio" else EC._truth_pdf(nm, path, pg)
        m = {j: heads[i] for i, j in EC._match(heads, B, sp).items()}
        idx = {id(l): j for j, l in enumerate(B)}
        for l in moved:
            h = m.get(idx[id(l)])
            k = f"{old[key(l)]}→{l['confidence']} · " + ("유령" if h is None else "진짜")
            c[k] += 1
            rows.append((k, nm, l["staff"], l["x"], l["y"], l["pitch"], l["text"], flag in l["flags"]))
    return st, nm, c, rows


def main(base, new, flag="side_pair"):
    import measure_sim_ledger_pair as S
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        R = list(ex.map(_job, [(base, new, flag, p) for p in S.pages()]))
    tot = Counter()
    for st, nm, c, rows in R:
        tot.update(c)
        if c["확신도 바뀜"] or c["생김"] or c["사라짐"]:
            print(f"  {st} {nm}: {dict(c)}")
        for r in rows:
            if r[0].endswith("진짜") or not r[-1]:
                print("    ", r)
    print("합계", dict(tot))
    down, false = tot["certain→check · 유령"], tot["certain→check · 진짜"]
    print(f"「확실」 유령 감소 {down} · 「확실」 진짜 헛표시 {false} · 기준(헛표시 ≤ 감소/2) {'충족' if false <= down / 2 else '미충족'}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
