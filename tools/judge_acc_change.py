# -*- coding: utf-8 -*-
"""표기 변경 판정(2026-10-19 · §1-49 초안 검증, 측정만) — 기준 · 새 라벨(49쪽)에서 새로 생긴 라벨을 정답(PDF 글리프 + 실효 임시표 · Verovio SVG)과
대조해 고침 · 새로 틀림 · 틀림→틀림으로 가르고, 표기는 같고 확신도만 바뀐 라벨을 센다. 오삭제는 `compare_change_impl.py`.

    python tools/judge_acc_change.py <기준> <새>
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
NORM = lambda a: {"natural": "", None: ""}.get(a, a)
KEY = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])


def main(base, new):
    import measure_sim_ledger_pair as S
    from measure_certain_errors import _truth
    c = Counter()
    for st, nm, path, pg in S.pages():
        load = lambda v: json.load(open(os.path.join(ROOT, "debug", "sim_lp", v, nm + ".json"), encoding="utf-8"))["labels"]
        A, B = load(base), load(new)
        conf = {KEY(l): l["confidence"] for l in A}
        for l in B:
            if KEY(l) in conf and conf[KEY(l)] != l["confidence"]:
                c[("확신도만", conf[KEY(l)], l["confidence"])] += 1
                print("  확신도만", nm, KEY(l), conf[KEY(l)], "→", l["confidence"])
        add = [l for l in B if KEY(l) not in conf]
        if not add or st == "aoharu":
            c["아오하루 바뀜"] += len(add) if st == "aoharu" else 0
            continue
        if st == "verovio":
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
            heads, sp = [(n["x"], n["y"], n["note_name"] + n["octave"], n["eff"] or "") for n in t["notes"]], 18.0
        else:
            heads, sp = _truth("pdf", nm, path, pg)
        for l in add:
            h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
            old = [a["text"] for a in A if a["staff"] == l["staff"] and a["x"] == l["x"] and a["y"] == l["y"]]
            ok = bool(h) and h[0][2] == l["pitch"] and ACC(l["text"]) == NORM(h[0][3])
            was = bool(h) and bool(old) and h[0][2] == l["pitch"] and ACC(old[0]) == NORM(h[0][3])
            k = "고침" if ok and not was else "새로 틀림" if was and not ok else "틀림→틀림" if not ok else "맞음→맞음"
            c[(k, l["confidence"])] += 1
            print(f"  {k:6}", nm, l["x"], l["y"], old, "→", l["text"], l["confidence"], "정답", h[0][2:] if h else "없음")
    for k, v in sorted(c.items(), key=str):
        print(k, v)


if __name__ == "__main__":
    main(*sys.argv[1:3])
