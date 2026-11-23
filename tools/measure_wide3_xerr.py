# -*- coding: utf-8 -*-
"""§1-48 분할 머리 x 오차 분포 (2026-10-20 · 기존 라벨만 읽음, 영상 처리 없음).

라벨 = `debug/sim_lp/<이름>`(기본 main1019, Verovio 개발 20쪽) · 정답 = `debug/vrv/truth`.
라벨마다 가장 가까운 정답 머리(가로 0.7sp · 세로 0.5sp 안)와의 dx = 라벨 x − 정답 x(sp)를 `wide_triple`(3음 덩어리 분할) 라벨과 그 밖 라벨로 나눠 센다.
판정 창 오른끝 = 머리 − 0.55sp라, dx가 크면 창에 화음 기둥(머리 가장자리 ≈ 정답 x ± 0.6sp)이 들어온다(Schumann L (1122,668) dx +0.28).

    python tools/measure_wide3_xerr.py [이름]
"""
import json, os, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = 18.0


def main(v):
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    dx = {True: [], False: []}
    rows = []
    for f in sorted(os.listdir(D)):
        nm = f[:-5]
        T = json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"]
        for l in json.load(open(os.path.join(ROOT, "debug", "sim_lp", v, nm + ".json"), encoding="utf-8"))["labels"]:
            near = [n for n in T if abs(n["x"] - l["x"]) <= 0.7 * SP and abs(n["y"] - l["y"]) <= 0.5 * SP]
            if not near:
                continue
            n = min(near, key=lambda n: abs(n["x"] - l["x"]) + abs(n["y"] - l["y"]))
            w = "wide_triple" in l["flags"]
            d = (l["x"] - n["x"]) / SP
            dx[w].append(d)
            if w:
                rows.append((nm, l["x"], l["y"], round(d, 2), l["text"], n["note_name"] + n["octave"], n["eff"] or ""))
    for w in (True, False):
        s = sorted(dx[w])
        if not s:
            continue
        q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
        a = sorted(abs(x) for x in s)
        print(f"{'분할(wide_triple)' if w else '그 밖'} {len(s)}: dx 중앙 {q(0.5):+.2f} · 10% {q(0.1):+.2f} · 90% {q(0.9):+.2f} · "
              f"|dx| ≥ 0.2sp {sum(x >= 0.2 for x in a)} · ≥ 0.25sp {sum(x >= 0.25 for x in a)} · 최대 {a[-1]:.2f}")
    print("분할 라벨 |dx| ≥ 0.2sp:")
    for r in rows:
        if abs(r[3]) >= 0.2:
            print("  ", r)
    print("분할 라벨 쪽별:", Counter(r[0] for r in rows).most_common())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "main1019")
