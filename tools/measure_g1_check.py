# -*- coding: utf-8 -*-
"""G1(기울어진 빔 마스크)을 「삭제」 대신 「확인 필요(check) 표시」로만 쓰는 안 — 표시 대상 측정. 제품 코드 무변경.

표시 대상 = 현재 제품(정밀 판정 포함)에 G1만 켜서 **지워지는 라벨**. check 표시안에서는 이 라벨들이 지워지지 않고 check로 남는다.
G1 사본은 `measure_a17_ghost6.sloped_beam_mask`(A-17 §7, `verify.beam_mask`에 ±7.5~45° 선 열림을 합침) 그대로.

    python tools/measure_g1_check.py run <pdf20|unseen|verovio>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def run(which):
    import measure_a17_ghost6 as G
    # drop_beam_ghosts가 모듈 전역 beam_mask를 부른다. run_set은 쪽마다 install(False)로 되돌리므로
    # (첫 판은 그래서 첫 쪽에만 걸렸다 — 호출 6) install을 「G1 마스크 걸기」로 바꾼다. 다른 가로채기는 없다(제품 판정 그대로)
    G.install = lambda fix=True: setattr(G.V, "beam_mask", G.sloped_beam_mask)
    G.install()
    if which == "verovio":
        import measure_verovio as V
        V.OUT = os.path.join(ROOT, "debug", "vrv_g1")
        V.run("base")
    else:
        G.T1.OUT = os.path.join(ROOT, "debug", "a17_cand1_g1")
        G.set_variant("base")
        G.run_set("base", which)
    print("G1 마스크 호출", G.STATS.get("G1 빔 마스크"))         # 0이면 측정 무효(측정 함정 B-4)


if __name__ == "__main__":
    run(sys.argv[2])
