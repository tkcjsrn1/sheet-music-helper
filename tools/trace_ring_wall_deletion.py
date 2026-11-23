# -*- coding: utf-8 -*-
"""[3] 링 벽 예외(브랜치 claude/ring-wall-keep-stopped)의 오삭제 1 — Clara 3 Bravura (1662, 2516) 「솔」 경로 추적. 제품 코드 무변경.

지금 작업 트리의 notehead_detect로 `measure_faded_stages.stages`를 돌려 표적 ±R sp 안의 머리를 단계마다(기본 검출 · 버림 기록 · 빔 · 보표 밖 · 임시표 유령 뒤, 구제 경로도) 출력.
main 판과 브랜치 판을 각각 실행해 비교한다(브랜치 판은 그 파일만 잠시 꺼내 쓰고 되돌린다).

    python tools/trace_ring_wall_deletion.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
PAGE = os.path.join(ROOT, "test_scores", "verovio", "clara_polonaise_3_bravura_p1.png")
TX, TY, R = 1662, 2516, 2.0

if __name__ == "__main__":
    import measure_faded_stages as F
    S, _b = F.stages(PAGE)
    sp = S["sp"]
    near = lambda p: abs(p[0] - TX) <= R * sp and abs(p[1] - TY) <= R * sp
    for k in ("base_det", "base_rej", "base_beam", "base_off", "base_final", "rescue_det", "rescue_rej", "rescue_beam", "rescue_off", "rescue_final"):
        print(k, [tuple(round(v, 1) if isinstance(v, float) else v for v in p) for p in S[k] if near(p)])
    print("sp", round(sp, 2))
