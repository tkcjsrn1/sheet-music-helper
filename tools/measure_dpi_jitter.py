# -*- coding: utf-8 -*-
"""야간 [9] A-15 해상도 출렁임 — 짝 없는 라벨이 190 · 240dpi에서 늘어나는 단계. 제품 코드 무변경.

같은 쪽을 dpi d(튀는 쪽)와 이웃 dpi로 렌더해 제품 단계(`measure_faded_stages.stages`)를 돌린다. 단계마다 머리 수와, 최종 머리 중 정답(PDF 글리프 머리, dpi 배율로 옮김)과 짝 없는 것(유령)의 수.
유령이 어느 단계에서 「생겨」 끝까지 살아남는지: 최종 유령마다 그것이 처음 나타난 단계(기본 검출 · 구제 검출)와 원시 검출에서의 빈/꽉 참.
또 sp에 비례하는 커널(int(sp × k) | 1)과 이진화 블록(25px 고정)의 값을 dpi별로 적는다.

    python tools/measure_dpi_jitter.py db1 190 200
"""
import os
import sys
import tempfile
from collections import Counter

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
KS = (0.2, 0.25, 0.3, 0.4, 0.5, 0.55, 0.6, 0.8)


def one(name, dpi):
    import check_accidental_fix as C
    import measure_faded_stages as F
    from measure_normalize_sp import truth_at
    from modules.preprocess import load_image
    path, pg = {n: (p, g) for n, p, g in C.PAGES}[name]
    tmp = tempfile.mkdtemp(prefix="dpi_")
    f = os.path.join(tmp, "p.png")
    open(f, "wb").write(cv2.imencode(".png", load_image(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi))[1].tobytes())
    S, _b = F.stages(f)
    os.remove(f)
    os.rmdir(tmp)
    heads = [(h["cx"], h["cy"]) for h in truth_at(path, pg, dpi / 300.0)[0]]
    sp = S["sp"]
    near = lambda lst, x, y, r=0.5: [t for t in lst if abs(t[0] - x) <= r * sp and abs(t[1] - y) <= r * sp]
    final = S["base_final"] + [p for p in S["rescue_final"] if not near(S["base_final"], *p)]
    ghosts = [p for p in final if not any(abs(h[0] - p[0]) <= 0.7 * sp and abs(h[1] - p[1]) <= 0.5 * sp for h in heads)]
    c = Counter()
    for x, y in ghosts:
        b = near(S["base_det"], x, y)
        r = near(S["rescue_det"], x, y)
        src = "기본 검출" if b else "구제 검출에서만"
        filled = (b or r)[0][2] if (b or r) else None
        c[(src, "꽉 찬" if filled else "빈" if filled is not None else "?")] += 1
    kern = {k: int(sp * k) | 1 for k in KS}
    return dict(sp=round(sp, 2), det=len(S["base_det"]), rescue=len(S["rescue_det"]), final=len(final), ghosts=len(ghosts), by=c, kern=kern)


def main():
    name = sys.argv[1]
    for d in map(int, sys.argv[2:]):
        r = one(name, d)
        print(f"{name} @{d}dpi sp {r['sp']} | 기본 검출 {r['det']} · 구제 검출 {r['rescue']} · 최종 {r['final']} · 유령 {r['ghosts']} | 유령 출처 "
              + " · ".join(f"{a}/{b} {n}" for (a, b), n in r["by"].most_common()))
        print("    커널 int(sp·k)|1: " + " · ".join(f"{k}→{v}" for k, v in r["kern"].items()))


if __name__ == "__main__":
    main()
