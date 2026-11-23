# -*- coding: utf-8 -*-
"""(c) 안 2 구현 판정 — 지금 제품(clef_changed 표시)으로 Verovio 20 · PDF 17 · 보지 않은 8쪽을 다시 돌려 기준 결과와 라벨 대조.
조건: 사라지는 라벨 0 · 위치 · 글자 · 음고 무변경, 확신도는 check로만 바뀐다. 기준 = A-25 병합 결과(`debug/vrv_a25impl/base` · `debug/a17_cand1_a25impl/base_*`).

    python tools/check_clef_flag_labels.py run     # 다시 돌리기(debug/vrv_clefflag · debug/a17_cand1_clefflag)
    python tools/check_clef_flag_labels.py         # 대조
"""
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
PAIRS = [("verovio", "debug/vrv_a25impl/base", "debug/vrv_clefflag/base"),
         ("pdf", "debug/a17_cand1_a25impl/base_pdf20", "debug/a17_cand1_clefflag/base_pdf20"),
         ("unseen", "debug/a17_cand1_a25impl/base_unseen", "debug/a17_cand1_clefflag/base_unseen"),
         ("photo", "debug/a17_cand1_g1flag/base_photo", "debug/a17_cand1_clefflag/base_photo")]      # 사진 모드는 꺼서 변화 0이어야 한다


def run():
    import measure_a17_ghost6 as G
    import measure_verovio as V
    V.OUT = os.path.join(ROOT, "debug", "vrv_clefflag")
    V.run("base")
    G.T1.OUT = os.path.join(ROOT, "debug", "a17_cand1_clefflag")
    G.set_variant("base")
    for which in ("pdf20", "unseen", "photo"):
        G.run_set("base", which)


def compare():
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"], l["pitch"])
    for st, a, b in PAIRS:
        c = Counter()
        for fa in sorted(glob.glob(os.path.join(ROOT, a, "*.json"))):
            fb = os.path.join(ROOT, b, os.path.basename(fa))
            if fa.endswith(("_g2.json", "_gaps.json")):
                continue
            if not os.path.exists(fb):
                c["새 결과 없음"] += 1
                continue
            A = {key(l): l for l in json.load(open(fa, encoding="utf-8"))["labels"]}
            B = {key(l): l for l in json.load(open(fb, encoding="utf-8"))["labels"]}
            c["쪽"] += 1
            c["라벨"] += len(A)
            c["사라짐"] += len(A.keys() - B.keys())
            c["생김"] += len(B.keys() - A.keys())
            for k in A.keys() & B.keys():
                ca, cb = A[k]["confidence"], B[k]["confidence"]
                if ca != cb:
                    c[f"확신도 {ca} → {cb}" + (" (clef_changed)" if "clef_changed" in B[k]["flags"] else " (다른 원인)")] += 1
                c["check 전"] += ca == "check"
                c["check 후"] += cb == "check"
        print(st, dict(c))


if __name__ == "__main__":
    run() if sys.argv[1:] == ["run"] else compare()
