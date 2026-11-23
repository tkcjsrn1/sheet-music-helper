# -*- coding: utf-8 -*-
"""라벨을 더하는 구현의 판정 — `debug/sim_lp/<기준>` ↔ `debug/sim_lp/<구현>`(기본 nograce ↔ ctadd). 제품 코드 무변경.
    python tools/check_label_additions.py <기준> <구현>
새 라벨 = 되찾음(음고 맞음 · 틀림) / 중복(이미 라벨 있는 정답 머리) / 새 유령, 사라진 라벨, Aoharu 변화. 정답은 `measure_chord_template._truth`."""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


DIRS = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("nograce", "ctadd")


def _one(job):
    import numpy as np
    import measure_chord_template as T
    from modules.preprocess import preprocess
    st, name, path, pg = job
    A = json.load(open(os.path.join(ROOT, "debug", "sim_lp", DIRS[0], name + ".json"), encoding="utf-8"))["labels"]
    B = json.load(open(os.path.join(ROOT, "debug", "sim_lp", DIRS[1], name + ".json"), encoding="utf-8"))["labels"]
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"], l["pitch"])
    ka, kb = {key(l) for l in A}, {key(l) for l in B}
    c = Counter(사라짐=len(ka - kb))
    new = [l for l in B if key(l) not in ka]
    if not new:
        return st, c
    if st == "aoharu" or name == "organ2":
        c[f"{st} 새 라벨(정답 없음)"] += len(new)
        return st, c
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    heads = T._truth(st, name, path, pg, res)
    sp = float(np.median([s.spacing for s in res.staves]))
    for l in new:
        h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
        if h and any(abs(o["x"] - h[0][0]) <= 0.7 * sp and abs(o["y"] - h[0][1]) <= 0.5 * sp for o in A):
            c["중복"] += 1
        elif not h:
            c["새 유령"] += 1
        else:
            c["되찾음 · 음고 맞음" if h[0][2] == l["pitch"] else "되찾음 · 음고 틀림"] += 1
        c["새 라벨 확신도 " + l["confidence"]] += 1
    return st, c


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        res = list(ex.map(_one, S.pages()))
    for st in ("verovio", "pdf", "unseen", "aoharu"):
        t = Counter()
        for s, c in res:
            if s == st:
                t.update(c)
        print(st, dict(t))


if __name__ == "__main__":
    main()
