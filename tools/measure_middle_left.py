# -*- coding: utf-8 -*-
"""큐 3 — §1-47 뒤에도 남은 3도 쌓기 가운데 머리 누락의 원인 (2026-10-19 · 측정만, 제품 코드 무변경).

Verovio 개발 20쪽 정답에서 같은 보표 · |dx| ≤ 0.3sp · 온음계 0 · 2 · 4 단계 세 머리(3도 쌓기)를 찾고, 라벨(<변형>)에
양 끝은 있는데 가운데가 없는 것을 모은다. 각 자리에서 `chord_rescue.chord_middle_heads`가 보는 값을 다시 잰다:
두 끝 라벨 세로 거리(sp) · 두 끝 음고 차 · 가운데 · 위아래 행 런(오선 제거 영상, `chord_rescue`와 같은 함수) · 가운데가 오선 밖(덧줄 위)인지.

    python tools/measure_middle_left.py merge3
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
STEP = lambda p: "CDEFGAB".index(p[0]) + 7 * int(p[1:])


def main(var):
    import inspect
    import modules.chord_rescue as CR
    print("chord_rescue 상수:", {k: getattr(CR, k) for k in dir(CR) if k.startswith("MIDDLE")})
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    rows = []
    for f in sorted(os.listdir(D)):
        if not f.endswith("_p1.json"):
            continue
        T = [n for n in json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"] if not (n["grace"] or n["cue"])]
        L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", var, f), encoding="utf-8"))["labels"]
        lab = lambda h: [l for l in L if abs(l["x"] - h["x"]) <= 0.7 * 18 and abs(l["y"] - h["y"]) <= 0.5 * 18]
        for a in T:
            for c in T:
                if c["staff"] != a["staff"] or abs(c["x"] - a["x"]) > 0.3 * 18:
                    continue
                if STEP(c["note_name"] + c["octave"]) - STEP(a["note_name"] + a["octave"]) != 4:
                    continue
                mids = [b for b in T if b["staff"] == a["staff"] and abs(b["x"] - a["x"]) <= 0.3 * 18
                        and STEP(b["note_name"] + b["octave"]) - STEP(a["note_name"] + a["octave"]) == 2]
                if not mids or not lab(a) or not lab(c) or lab(mids[0]):
                    continue
                la, lc = lab(a)[0], lab(c)[0]
                rows.append(dict(page=f[:-5], x=round(mids[0]["x"]), y=round(mids[0]["y"]), dy=round(abs(la["y"] - lc["y"]) / 18, 2),
                                 ends=(la["pitch"], lc["pitch"], la["confidence"], lc["confidence"]), dpx=abs(la["x"] - lc["x"])))
    for r in rows:
        print(r)
    print("남은 가운데 누락", len(rows))
    json.dump(rows, open(os.path.join(ROOT, "debug", "middle_left.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
