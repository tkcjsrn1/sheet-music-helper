# -*- coding: utf-8 -*-
"""[3](f) Verovio 덧줄 구역 누락 · 빈 머리 누락의 단계별 원인 — `debug/vrv/missing_trace.json`(단계 추적, A-25 병합 상태 = 라벨 위치는 지금 main과 같음) 위에서 한 단계 더. 제품 코드 무변경.

① 빈 머리 「같은 높이 바로 옆 중복」: 지워진 정답 빈 머리마다 가장 가까운 다른 정답 머리까지 dx · dy(sp), 같은 음(음이름+옥타브)인지.
② 덧줄 구역(오선 밖) 정답 머리: 머리 중심 행 ±0.15sp의 가로 잉크 연속 폭(오선 제거 영상, sp) · 덧줄이 머리 중심을 지나는가(중심 행 가로 런 ≥ 1.4sp, 머리 폭보다 넓음) ·
   빈/꽉 참 — 놓친 것(단계 「모양 판정」) vs 잡힌 것(라벨 있음, `debug/vrv_clefflag/base`).

    python tools/measure_ledger_hollow_miss.py
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
VRV = os.path.join(ROOT, "debug", "vrv")
HOLLOW = ("E0A3", "E0A2", "E0A0")


def _page(job):
    stem, miss = job
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    res = preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))
    ns = remove_staff_lines(res.binary, res.staves) > 0
    H, W = ns.shape
    t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
    L = json.load(open(os.path.join(ROOT, "debug", "vrv_clefflag", "base", stem + ".json"), encoding="utf-8"))["labels"]
    sp = 18.0
    notes = [n for n in t["notes"] if not n.get("grace") and not n.get("cue")]
    staves = sorted(res.staves, key=lambda s: s.top)
    out_dup, out_led = [], []
    for m in miss:
        if not m["stage"].endswith("(같은 높이 바로 옆의 중복으로 판정)") or m["cat"] != "빈 머리":
            continue
        me = min(notes, key=lambda n: abs(n["x"] - m["x"]) + abs(n["y"] - m["y"]))
        others = [n for n in notes if n is not me]
        o = min(others, key=lambda n: abs(n["x"] - me["x"]) + 2 * abs(n["y"] - me["y"]))
        out_dup.append(dict(page=stem, dx=round(abs(o["x"] - me["x"]) / sp, 2), dy=round(abs(o["y"] - me["y"]) / sp, 2),
                            same=(o["note_name"] + o["octave"]) == (me["note_name"] + me["octave"]), other_hollow=o["glyph"] in HOLLOW))
    missed = {(round(m["x"]), round(m["y"])): m["stage"] for m in miss}

    def run_w(x, y):
        best = 0
        for yy in range(int(y - 0.15 * sp), int(y + 0.15 * sp) + 1):
            if not (0 <= yy < H) or not ns[yy, min(W - 1, int(x))]:
                continue
            a = b = int(x)
            while a > 0 and ns[yy, a - 1]:
                a -= 1
            while b < W - 1 and ns[yy, b + 1]:
                b += 1
            best = max(best, b - a + 1)
        return best / sp

    for n in notes:
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - n["y"]))
        if st.top - 0.6 * sp <= n["y"] <= st.bottom + 0.6 * sp:
            continue          # 오선 안
        on_line = abs(((n["y"] - st.top) / (sp / 2.0)) - round((n["y"] - st.top) / (sp / 2.0))) < 0.25 and round((n["y"] - st.top) / (sp / 2.0)) % 2 == 0
        got = any(abs(l["x"] - n["x"]) <= 0.7 * sp and abs(l["y"] - n["y"]) <= 0.5 * sp for l in L)
        stage = missed.get((round(n["x"]), round(n["y"])))
        out_led.append(dict(page=stem, got=got, stage=stage, hollow=n["glyph"] in HOLLOW, on_line=bool(on_line), w=round(run_w(n["x"], n["y"]), 2)))
    return out_dup, out_led


def main():
    miss = json.load(open(os.path.join(VRV, "missing_trace.json"), encoding="utf-8"))
    by = defaultdict(list)
    for m in miss:
        by[m["stem"]].append(m)
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "test_scores", "verovio")) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(2) as ex:
        res = list(ex.map(_page, [(s, by[s]) for s in stems]))
    dup = [r for a, _b in res for r in a]
    led = [r for _a, b in res for r in b]
    json.dump(dict(dup=dup, led=led), open(os.path.join(ROOT, "debug", "ledger_hollow_miss.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"① 빈 머리 옆 중복 {len(dup)} | 이웃이 같은 음 {sum(r['same'] for r in dup)} · 이웃도 빈 머리 {sum(r['other_hollow'] for r in dup)} | "
          f"dx sp 중앙 {np.median([r['dx'] for r in dup]):.2f} · dy sp 중앙 {np.median([r['dy'] for r in dup]):.2f} · dy 분포 {Counter(round(r['dy'] * 2) / 2 for r in dup)}")
    got = [r for r in led if r["got"]]
    lost = [r for r in led if not r["got"] and r["stage"] == "머리 후보 없음 · 모양 판정"]
    print(f"② 덧줄 구역 정답 머리 {len(led)} · 잡힘 {len(got)} · 모양 판정으로 놓침 {len(lost)} · 그 밖 놓침 {len(led) - len(got) - len(lost)}")
    for name, v in (("잡힘", got), ("모양 놓침", lost)):
        print(f"   {name:6s} {len(v):5d} | 빈 머리 {sum(r['hollow'] for r in v)} · 덧줄이 중심 통과 {sum(r['on_line'] for r in v)} | "
              f"중심 행 가로 잉크 폭 sp 5 · 50 · 95% {np.percentile([r['w'] for r in v], 5):.2f} · {np.percentile([r['w'] for r in v], 50):.2f} · {np.percentile([r['w'] for r in v], 95):.2f}")
    for on in (True, False):
        g = sum(r["on_line"] == on for r in got)
        l_ = sum(r["on_line"] == on for r in lost)
        print(f"   덧줄 {'위(중심 통과)' if on else '사이'}: 잡힘 {g} · 모양 놓침 {l_} → 놓침률 {l_ / max(1, g + l_) * 100:.1f}%")


if __name__ == "__main__":
    main()
