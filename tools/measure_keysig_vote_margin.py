# -*- coding: utf-8 -*-
"""조표 교차 투표의 **여유**를 잰다 — 몇 표 차이로 지금 판정이 나왔나.

측정 전용. `clef_keysig._vote_key_signature`와 **같은 순서**로 중간값을 드러낸다.

- 클러스터 지지 수 − 문턱: 인정된 구조 막대 중 가장 약한 것(**+여유**)과
  탈락한 것 중 가장 강한 것(**−여유**, −1이면 한 표만 더 있으면 들어온다)
- ♯이면 사슬 길이, ♭이면 `min(singles, 구멍 중앙값)`과 두 값의 차

    python tools/measure_keysig_vote_margin.py <이미지 또는 PDF> [...]
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.preprocess import preprocess  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402


def vote_detail(path, page=0):
    res = preprocess(path, pdf_page=page)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    single = len(res.staves) <= 2
    ctxs = {s.index: CK._analyze_one(ns, s, H, single) for s in res.staves}
    found = [c for c in ctxs.values() if c.clef_found]
    thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    bars = sorted(x for c in found for x, _ in c.bars)
    clusters = []
    i = 0
    while i < len(bars):                              # _vote_key_signature와 같은 ±3px 클러스터
        j = i
        while j + 1 < len(bars) and bars[j + 1] - bars[i] <= 3.0:
            j += 1
        clusters.append((float(np.mean(bars[i:j + 1])), j - i + 1))
        i = j + 1
    result = CK._vote_key_signature(ctxs)
    inc = [s - thr for _x, s in clusters if s >= thr]
    exc = [s - thr for _x, s in clusters if s < thr]
    holes = int(np.median([c.holes for c in found])) if found else 0
    return dict(staves=len(res.staves), found=len(found), thr=thr, result=result,
                clusters=clusters, weakest_in=min(inc) if inc else None,
                strongest_out=max(exc) if exc else None,
                near_miss=[(round(x), s) for x, s in clusters if s == thr - 1],
                weak_in=[(round(x), s) for x, s in clusters if s == thr],
                holes_median=holes)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        d = vote_detail(p)
        kc, ks, _ = d["result"]
        print(f"{os.path.basename(p):28s} 판정 {ks or '-'}{kc}  보표 {d['found']}/{d['staves']} 문턱 {d['thr']}  "
              f"인정 최약 +{d['weakest_in']}  탈락 최강 {d['strongest_out']}  "
              f"문턱 딱={d['weak_in']}  한표모자람={d['near_miss']}  구멍중앙 {d['holes_median']}")
