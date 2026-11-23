# -*- coding: utf-8 -*-
"""(e) 사진 모드에서 정밀 판정 전체(A-25 전파 경계 §1-14 + ♮ · ♯ 수정 §1-12 · G3 · H3)를 켠 효과. 제품 코드 무변경.

정밀 판정은 `accidental_detect._refined(result)`(사진 모드면 끔) 하나로 켜지므로 그 함수만 「항상 켬」으로 가로챈 사본으로 사진 51장을 돌린다.
가로채기 호출 수를 출력한다(0이면 측정 무효 — 측정 함정 B-4). 판정은 `measure_photo_truth`(원본 PDF 실효 정답, 정렬 51/51)에 변형 all로.

    python tools/measure_photo_refined.py run     # → debug/a17_cand1_photo_all/base_photo
    python tools/measure_photo_truth.py           # off · nat · bl · all 비교
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
CALLS = {"n": 0, "photo": 0}


def install():
    import modules.accidental_detect as AD

    def always(result):
        CALLS["n"] += 1
        CALLS["photo"] += getattr(result, "photo_correction", None) is not None
        return True
    AD._refined = always


if __name__ == "__main__" and sys.argv[1:] == ["run"]:
    install()
    import measure_a17_ghost6 as G
    G.T1.OUT = os.path.join(ROOT, "debug", "a17_cand1_photo_all")
    G.set_variant("base")
    G.run_set("base", "photo")
    print("가로채기 호출", CALLS["n"], "· 그중 사진 결과", CALLS["photo"])
