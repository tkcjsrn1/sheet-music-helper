# -*- coding: utf-8 -*-
"""`measure_filled_beam_check` 걸린 「확실」 라벨(진짜 23 = Verovio 대각 2도 화음 · 유령 27 = 머리 없는 빔 막대, 격자 확인)을
(그다음 신호에 걸린 라벨 전부 — 확신도 무관) 라벨 자리 세로 잉크 두께로 가를 수 있나. 두께 = 오선 지운 이진 영상에서 x ± 0.4sp 각 열의, y를 지나는 세로 연속 잉크 길이(sp)의 중앙값
(중앙값 — 기둥 한 열이 값을 끌지 않게). 빔은 두께 ~0.5sp, 머리는 ~1sp.

    python tools/measure_filled_beam_thick.py
"""
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def thick(ns, x, y, sp):
    runs = []
    for cx in range(int(x - 0.4 * sp), int(x + 0.4 * sp) + 1):
        if not (0 <= cx < ns.shape[1]) or not ns[y, cx]:
            runs.append(0)
            continue
        a = b = y
        while a > 0 and ns[a - 1, cx]:
            a -= 1
        while b < ns.shape[0] - 1 and ns[b + 1, cx]:
            b += 1
        runs.append(b - a + 1)
    return round(float(np.median(runs)) / sp, 2)


def _page(job):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    path, pg, items = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ns = remove_staff_lines(res.binary, res.staves)
    sp = float(np.median([s.spacing for s in res.staves]))
    return [(k, n, x, y, thick(ns, y=y, x=x, sp=sp)) for k, n, x, y in items]


def main():
    import measure_sim_ledger_pair as S
    P = {n: (p, pg) for _s, n, p, pg in S.pages()}
    by = defaultdict(list)
    for st, n, x, y, _t, conf, _w, kind in json.load(open(os.path.join(ROOT, "debug", "filled_beam_check.json"), encoding="utf-8")):
        k = ("진짜" if kind.startswith("진짜") else "유령") + (" · 확실" if conf == "certain" else " · 그 밖")
        if n not in P:
            f, p = n.rsplit("_p", 1)
            P[n] = (os.path.join("inputs", "mutopia", f + ".pdf"), int(p) - 1)
        by[P[n]].append((k, n, x, y))
    with ProcessPoolExecutor(3) as ex:
        rows = [r for page in ex.map(_page, [(p, pg, it) for (p, pg), it in by.items()]) for r in page]
    for k in ("진짜 · 확실", "진짜 · 그 밖", "유령 · 확실", "유령 · 그 밖"):
        v = sorted(r[4] for r in rows if r[0] == k)
        print(f"{k}: {len(v)} · 두께 < 0.7sp {sum(t < 0.7 for t in v)} |", v)
    for r in rows:
        if r[0].startswith("진짜") and r[4] < 0.7:
            print("  헛표시 후보", r)


if __name__ == "__main__":
    main()
