# -*- coding: utf-8 -*-
"""A-25 마디 안 전파 놓침 원인 분류 — 기존 결과만(파이프라인 새로 안 돌림). 제품 코드 무변경.

입력: `debug/vrv/eval_base.json`(measure_verovio eval — 정답 머리마다 짝 라벨 · 상태) + `debug/vrv/truth/*.json`(SVG 정답 —
머리 · 인쇄 임시표 · 실효 임시표 · 마디선 barLine 상자 · 붙임줄 tie 상자).
대상: 평가기 원인 「마디 안 전파 놓침」(인쇄 임시표 없음 · 라벨 임시표 없음 · 실효 ≠ 조표).

원천 = 같은 보표에서 왼쪽, 같은 음이름, 인쇄 임시표가 실효와 같은 가장 가까운 머리.
마디는 **정답** 마디선으로 센다. 제품 마디선은 라벨 JSON에 없어 「읽었는데 전파 안 됨」은 제품 마디선 오검출로 **추정**한다.

    python tools/classify_a25_propagation.py
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VRV = os.path.join(ROOT, "debug", "vrv")
NORM = {"#": "#", "s": "#", "b": "b", "f": "b", "n": "natural", "natural": "natural", "": "", None: ""}


def norm(a):
    return NORM.get(a, a)


def main():
    evs = json.load(open(os.path.join(VRV, "eval_base.json"), encoding="utf-8"))
    out, by = [], Counter()
    for e in evs:
        t = json.load(open(os.path.join(VRV, "truth", e["stem"] + ".json"), encoding="utf-8"))
        sp = e["sp"]
        rows = e["rows"]
        staves = t["staves"]
        bars = [b["box"] for b in t["boxes"] if b["cls"] == "barLine"]
        ties = [b["box"] for b in t["boxes"] if b["cls"] == "tie"]

        def staff_bars(si):
            ys = staves[si]["line_ys"]
            return sorted((b[0] + b[2]) / 2 for b in bars if b[1] <= ys[2] <= b[3])

        def measure(si, x):
            return sum(1 for bx in staff_bars(si) if bx < x)

        def row_at(n):
            return next((r for r in rows if abs(r["x"] - n["x"]) < 0.5 and abs(r["y"] - n["y"]) < 0.5), None)

        for r in rows:
            if not (r["status"] == "표기" and not r["printed"] and r["label"] and not norm(r["label"]["acc"])
                    and r["eff"] != r["key_alter"]):
                continue
            h = next(n for n in t["notes"] if abs(n["x"] - r["x"]) < 0.5 and abs(n["y"] - r["y"]) < 0.5)
            si, letter, octv, eff = h["staff"], h["note_name"], h["octave"], norm(h["eff"])
            left = [n for n in t["notes"] if n["staff"] == si and n["x"] < h["x"] - 1 and n["note_name"] == letter
                    and not n["grace"] and norm(n["accidental"]) == eff]
            same_m = [n for n in left if measure(si, n["x"]) == measure(si, h["x"])]
            src = max((n for n in same_m if n["octave"] == octv), key=lambda n: n["x"], default=None)
            if src is not None:
                sr = row_at(src)
                if sr is None or sr["status"] == "누락" or not sr["label"]:
                    cause = "① 앞 임시표 음표 누락(라벨 없음)"
                elif norm(sr["label"]["acc"]) != eff:
                    cause = "② 앞 임시표를 못 읽음(원천 라벨 임시표 틀림)"
                elif sr["label"]["staff"] != r["label"]["staff"]:
                    cause = "③ 원천과 대상이 다른 보표로 귀속"
                else:
                    cause = "④ 읽었는데 전파 안 됨 — 제품 마디선 오검출 추정"
            elif any(n["octave"] != octv for n in same_m):
                src = max((n for n in same_m), key=lambda n: n["x"])
                cause = "⑤ 같은 마디 다른 옥타브에만 임시표(정답은 전파로 봄)"
            else:
                prev = [n for n in left if measure(si, n["x"]) == measure(si, h["x"]) - 1 and n["octave"] == octv]
                src = max(prev, key=lambda n: n["x"], default=None)
                tied = src is not None and any(b[0] <= h["x"] and b[2] >= src["x"] - sp and abs((b[1] + b[3]) / 2 - h["y"]) < 2 * sp
                                                for b in ties)
                if tied:
                    cause = "⑥ 붙임줄로 마디를 넘어온 음"
                else:
                    # 원천이 인쇄 임시표 없는 앞 음표(정답 전파 사슬) · 다른 보표 · 조바꿈 경계 등
                    same_m_any = [n for n in t["notes"] if n["staff"] == si and n["x"] < h["x"] - 1 and n["note_name"] == letter
                                  and n["octave"] == octv and measure(si, n["x"]) == measure(si, h["x"])]
                    cause = "⑦ 기타(같은 마디 원천 없음" + (" · 앞 같은 음 있음" if same_m_any else "") + ")"
            by[cause] += 1
            out.append(dict(stem=e["stem"], x=round(r["x"]), y=round(r["y"]), pitch=f"{letter}{octv}", eff=eff, cause=cause,
                            src=(round(src["x"]), round(src["y"]), src["note_name"] + src["octave"], norm(src["accidental"])) if src else None,
                            label=r["label"]["text"]))
    json.dump(out, open(os.path.join(VRV, "a25_classes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("합계", len(out))
    for k, v in sorted(by.items()):
        f = Counter("bravura" if "bravura" in o["stem"] else "leipzig" for o in out if o["cause"] == k)
        print(f"  {k}: {v} (Bravura {f['bravura']} · Leipzig {f['leipzig']})")
    for o in out:
        if o["stem"].startswith("bach"):
            print("  바흐", o)


if __name__ == "__main__":
    main()
