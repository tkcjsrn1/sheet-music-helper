# -*- coding: utf-8 -*-
"""「추가만」 구현 검증 — 기준 라벨과 새 라벨(49쪽)을 비교: 사라짐 · 바뀜(확신도 · 표기 포함), 새 라벨의 정답 짝 · 음고(Verovio). 2026-10-13.

    python tools/compare_add_impl.py <기준> <새>
"""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def main(base, new):
    import measure_sim_ledger_pair as S
    import measure_verovio as V
    LP = os.path.join(ROOT, "debug", "sim_lp")
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"], l["confidence"])
    c, bad = Counter(), []
    for st, nm, path, pg in S.pages():
        A = {key(l): l for l in json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]}
        B = {key(l): l for l in json.load(open(os.path.join(LP, new, nm + ".json"), encoding="utf-8"))["labels"]}
        gone, add = [A[k] for k in A.keys() - B.keys()], [B[k] for k in B.keys() - A.keys()]
        c["사라짐 · 바뀜"] += len(gone)
        bad += [("사라짐/바뀜", nm, l["x"], l["y"], l["text"], l["confidence"]) for l in gone]
        if st == "aoharu":
            c["아오하루 새 라벨"] += len(add)
            continue
        heads, sp = S._truth(st, nm, path, pg)
        vt = json.load(open(os.path.join(V.OUT, "truth", nm + ".json"), encoding="utf-8"))["notes"] if st == "verovio" else None
        for l in add:
            h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
            if not h:
                c["새 유령"] += 1; bad.append(("새 유령", nm, l["x"], l["y"], l["text"])); continue
            if any(abs(m["x"] - h[0][0]) <= 0.7 * sp and abs(m["y"] - h[0][1]) <= 0.5 * sp for m in A.values()):
                c["이미 라벨 있던 머리"] += 1; bad.append(("중복", nm, l["x"], l["y"], l["text"])); continue
            if vt is not None:
                t = [n for n in vt if abs(n["x"] - l["x"]) <= 0.5 * sp and abs(n["y"] - l["y"]) <= 0.5 * sp]
                ok = any(n["note_name"] + n["octave"] == l["pitch"] for n in t)
                c["되찾음 · 음고 맞음" if ok else "되찾음 · 음고 틀림"] += 1
                if not ok: bad.append(("음고 틀림", nm, l["x"], l["y"], l["pitch"], [n["note_name"] + n["octave"] for n in t]))
            else:
                c["되찾음(PDF · 음고 대조 안 함)"] += 1
            c["확신도 " + l["confidence"]] += 1
    print(dict(c)); print("문제 목록", bad)


if __name__ == "__main__":
    main(*sys.argv[1:3])
