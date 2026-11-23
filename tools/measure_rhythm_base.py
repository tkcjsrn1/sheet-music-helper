# -*- coding: utf-8 -*-
"""큐 5 — 리듬 기초가 지금 파이프라인에서 얼마나 잡히나 (2026-10-19 · 측정만, 제품 코드 무변경).

정답: Verovio 개발 20쪽 `debug/vrv/truth`(머리 글리프 E0A4 = 꽉 찬 · E0A3 = 2분 빈 · E0A2 = 온음표 빈)와
#399 리듬 정답 TSV(`debug/rhythm_truth/*.tsv` — 길이 · 점 · 쉼표 수).
제품: `detect_noteheads`(제품 첫 검출 + 뒤 단계 필터 전) 머리의 `filled`. 짝 = 가로 0.7sp · 세로 0.5sp 안 가장 가까운 머리.
기둥 · 점 · 쉼표는 제품 출력에 없다 — 정답 쪽 개수만 센다(현재 기반 0).

    python tools/measure_rhythm_base.py
"""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
HOLLOW = {"E0A3": "빈(2분)", "E0A2": "빈(온)", "E0A4": "꽉 찬"}


def main():
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    c, tsv = Counter(), Counter()
    for f in sorted(os.listdir(D)):
        if not f.endswith("_p1.json"):
            continue
        nm = f[:-5]
        T = [n for n in json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"] if not (n["grace"] or n["cue"])]
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", nm + ".png"))
        heads = detect_noteheads(res, contexts=analyze_staves(res))
        sp = 18.0
        for n in T:
            kind = HOLLOW.get(n["glyph"], "기타 " + str(n["glyph"]))
            near = [h for h in heads if abs(h.x - n["x"]) <= 0.7 * sp and abs(h.y - n["y"]) <= 0.5 * sp]
            if not near:
                c[(kind, "머리 없음")] += 1
                continue
            h = min(near, key=lambda h: abs(h.x - n["x"]) + abs(h.y - n["y"]))
            c[(kind, "꽉 찬" if h.filled else "빈")] += 1
        p = os.path.join(ROOT, "debug", "rhythm_truth", nm + ".tsv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
                if r["grace"] == "True":
                    continue
                tsv["쉼표(보이는)" if r["kind"] == "rest" and r["hidden"] != "True" else "쉼표(숨김)" if r["kind"] == "rest" else "음"] += 1
                if r["kind"] == "note":
                    tsv["점 있는 음" if r["dots"] not in ("", "0") else "점 없는 음"] += 1
                    tsv["기둥 없는 음(온음표)" if r["dur"] in ("1", "3/2") else "기둥 있는 음"] += 1
        print(nm, flush=True)
    print("머리 종류(정답 → 제품):")
    for k, v in sorted(c.items()):
        print("  ", " → ".join(k), v)
    tot = sum(v for (a, b), v in c.items() if b != "머리 없음")
    ok = sum(v for (a, b), v in c.items() if (a == "꽉 찬") == (b == "꽉 찬") and b != "머리 없음")
    print(f"머리 찾은 것 중 빈/꽉 참 일치 {ok}/{tot} ({100 * ok / max(1, tot):.1f}%)")
    print("정답 TSV(제품 출력 없음):", dict(tsv))


if __name__ == "__main__":
    main()
