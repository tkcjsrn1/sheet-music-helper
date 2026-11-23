# -*- coding: utf-8 -*-
"""큐 3 — 화음 아닌 창 밖 임시표 22 중 「머리 없음」 11: 머리 누락이 임시표보다 먼저인가 (2026-10-19 · 측정만, 제품 코드 무변경).

창 밖 22 = `measure_acc_columns.py` ①의 「단독」(정답 인쇄 임시표 상자 왼끝이 머리 − 2.0sp 밖 · 같은 x 화음에 다른 임시표 없음).
라벨 = `debug/sim_lp/chordcol4`(§1-49 병합 뒤 main). 라벨 없는 머리는 `detect_noteheads`(첫 검출) 머리가 있었는지로
「검출 단계 누락」 · 「검출 뒤 필터에서 사라짐」을 가르고, 정답 2도 짝(세로 0.4 ~ 0.6sp · 가로 0.6 ~ 1.4sp)과 짝 머리 라벨 유무를 적는다.

    python tools/measure_far22_heads.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SP = 18.0


def main():
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    near = lambda a, x, y: abs(a["x"] - x) <= 0.7 * SP and abs(a["y"] - y) <= 0.5 * SP
    heads_cache = {}
    for f in sorted(os.listdir(D)):
        if not f.endswith("_p1.json"):
            continue
        nm = f[:-5]
        T = [n for n in json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"] if not (n["grace"] or n["cue"])]
        acc = [n for n in T if n["accidental"] and n["acc_box"]]
        L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "chordcol4", nm + ".json"), encoding="utf-8"))["labels"]
        for n in acc:
            if (n["x"] - n["acc_box"][0]) / SP <= 2.0:
                continue
            if any(m is not n and m["staff"] == n["staff"] and abs(m["x"] - n["x"]) <= 0.3 * SP for m in acc):
                continue
            lab = [l for l in L if near(l, n["x"], n["y"])]
            pair = [m for m in T if m is not n and m["staff"] == n["staff"]
                    and 0.4 * SP <= abs(m["y"] - n["y"]) <= 0.6 * SP and 0.6 * SP <= abs(m["x"] - n["x"]) <= 1.4 * SP]
            pdesc = ";".join(f"{'왼' if m['x'] < n['x'] else '오'}{m['note_name']}{m['octave']}"
                             f"(라벨{'있음' if any(near(l, m['x'], m['y']) for l in L) else '없음'})" for m in pair)
            stage = "라벨 있음"
            if not lab:
                if nm not in heads_cache:
                    res = preprocess(os.path.join(ROOT, "test_scores", "verovio", nm + ".png"))
                    heads_cache[nm] = detect_noteheads(res, contexts=analyze_staves(res))
                hs = [h for h in heads_cache[nm] if abs(h.x - n["x"]) <= 0.7 * SP and abs(h.y - n["y"]) <= 0.5 * SP]
                stage = "검출 뒤 사라짐" if hs else "검출 단계 누락"
            text = lab[0]["text"] if lab else "-"
            print(f"{nm}\t({n['x']:.0f},{n['y']:.0f})\t{n['note_name']}{n['octave']}{n['accidental']}\t"
                  f"창밖 {(n['x'] - n['acc_box'][0]) / SP:.2f}sp\t{stage}\t{text}\t2도짝 {pdesc or '없음'}", flush=True)


if __name__ == "__main__":
    main()
