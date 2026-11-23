# -*- coding: utf-8 -*-
"""리듬 단계 3 탐색 — 쉼표 「버리는 판정」이 정답 쉼표 자리를 얼마나 덮나 (2026-10-20 · 분석만, 제품 코드 무변경).

머리 검출의 4분쉼표 · 온/2분쉼표 제거(`notehead_detect` 「4분쉼표 제거」 · 「온쉼표/2분쉼표 제거」의 `continue`)는 기록 없이 버린다.
검출기 사본에 기록 줄만 넣어(원본과 머리 결과가 같은지 매 쪽 대조) 버린 덩어리 중심을 모으고, Verovio 정답 쉼표 상자(boxes cls=rest)와 대조한다.
- 쉼표 상자마다: 4분쉼표 판정이 버림 / 온·2분쉼표 판정이 버림 / 지금 라벨(유령)이 앉음(`debug/sim_lp/main1019`) / 아무것도 없음
- 버린 덩어리마다: 정답 쉼표 상자 안 / 밖(밖이면 무엇을 버렸나 — 정답 머리 0.7 · 0.5sp 안이면 「머리를 쉼표로 버림」)

    python tools/explore_rest_sites.py        # 개발 20쪽만
"""
import json
import os
import sys
import types
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def _instrumented():
    import modules.notehead_detect as ORIG
    src = open(ORIG.__file__, encoding="utf-8").read()
    q = "            # 4분쉼표 제거.\n"
    w = "            # 온쉼표/2분쉼표 제거: 오선에 얹히거나 매달린 '완전히 채워진 가로 직사각형'.\n"
    assert src.count(q) == 1 and src.count(w) == 1
    rec = "            _RL.append(({k!r}, staff.index, float(cents[i][0]), float(cents[i][1]) + top))\n"
    src = src.replace(q, rec.format(k="quarter") + q).replace(w, rec.format(k="whole_half") + w)
    m = types.ModuleType("modules.notehead_detect")
    m.__file__ = ORIG.__file__
    m._RL = []
    exec(compile(src, "nd_rest", "exec"), m.__dict__)
    return ORIG, m


def main():
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    ORIG, M = _instrumented()
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    c, out_kind = Counter(), Counter()
    for f in sorted(os.listdir(D)):
        nm = f[:-5]
        t = json.load(open(os.path.join(D, f), encoding="utf-8"))
        rests = [b["box"] for b in t["boxes"] if b["cls"] == "rest"]
        heads = [n for n in t["notes"]]
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", nm + ".png"))
        ctx = analyze_staves(res)
        a = ORIG.detect_noteheads(res, contexts=ctx)
        M._RL.clear()
        b = M.detect_noteheads(res, contexts=ctx)
        assert [(h.x, h.y, h.filled) for h in a] == [(h.x, h.y, h.filled) for h in b], "사본이 원본과 다르다"
        L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "main1019", nm + ".json"), encoding="utf-8"))["labels"]
        sp = 18.0
        inside = lambda x, y, bx, pad=0.3 * sp: bx[0] - pad <= x <= bx[2] + pad and bx[1] - pad <= y <= bx[3] + pad
        for bx in rests:
            q = any(k == "quarter" and inside(x, y, bx) for k, _s, x, y in M._RL)
            wh = any(k == "whole_half" and inside(x, y, bx) for k, _s, x, y in M._RL)
            g = any(inside(l["x"], l["y"], bx, 0) for l in L)
            h_sp = (bx[3] - bx[1]) / sp
            kind = "4분쉼표형(높이 ≥ 2sp)" if h_sp >= 2.0 else "8분 이하형(높이 1 ~ 2sp)" if h_sp >= 1.0 else "온·2분형(높이 < 1sp)"
            c[(kind, "4분쉼표 판정이 버림" if q else "온·2분 판정이 버림" if wh else "라벨(유령)이 앉음" if g else "기록 없음")] += 1
        for k, _s, x, y in M._RL:
            if any(inside(x, y, bx) for bx in rests):
                out_kind[(k, "정답 쉼표 상자 안")] += 1
            elif any(abs(n["x"] - x) <= 0.7 * sp and abs(n["y"] - y) <= 0.5 * sp for n in heads):
                out_kind[(k, "정답 머리 자리(머리를 쉼표로 버림?)")] += 1
            else:
                out_kind[(k, "그 밖")] += 1
        print(nm, len(rests), len(M._RL), flush=True)
    print("== 정답 쉼표 상자(높이로 나눈 꼴) → 지금 제품")
    for k in sorted(c):
        print("  ", k[0], "·", k[1], c[k])
    print("== 쉼표 판정이 버린 덩어리 → 어디였나")
    for k in sorted(out_kind):
        print("  ", k[0], "·", k[1], out_kind[k])


if __name__ == "__main__":
    main()
