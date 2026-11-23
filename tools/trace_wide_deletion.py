# -*- coding: utf-8 -*-
"""[2] 2도 머리 쌍 분할 사본의 오삭제 경로 — 표적 주변 머리를 단계마다(기본 검출 · 버림 기록 · 빔 · 보표 밖 · 임시표 유령 뒤, 구제 경로도) 출력.
지금 작업 트리의 notehead_detect로 돈다(main판 · 사본판을 각각 실행해 비교).

    python tools/trace_wide_deletion.py moon11 540 1569
"""
import os
import sys
import tempfile

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

if __name__ == "__main__":
    import measure_a17_ghost6 as G
    import measure_faded_stages as F
    from modules.preprocess import load_image
    name, tx, ty = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    path, pg = {n: (p, g) for n, p, g in G.UNSEEN}[name]
    f = os.path.join(tempfile.mkdtemp(), "p.png")
    open(f, "wb").write(cv2.imencode(".png", load_image(os.path.join(ROOT, path), pdf_page=pg))[1].tobytes())
    S, _b = F.stages(f)
    sp = S["sp"]
    near = lambda p: abs(p[0] - tx) <= 1.5 * sp and abs(p[1] - ty) <= 1.5 * sp
    for k in ("base_det", "base_rej", "base_beam", "base_off", "base_final", "rescue_det", "rescue_final"):
        print(k, [tuple(round(v, 1) if isinstance(v, float) else v for v in p) for p in S[k] if near(p)])
