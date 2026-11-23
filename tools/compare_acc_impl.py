# -*- coding: utf-8 -*-
"""임시표(표기) 변경 구현 검증 — 같은 자리 · 같은 음고 라벨의 표기가 바뀐 것을 정답 실효 임시표로 가른다 (2026-10-13, TASKS M-2).

  고침 = 기준 틀림 → 새 맞음 · 새로 틀림 = 기준 맞음 → 새 틀림 · 둘 다 틀림 · 정답 짝 없음(유령) · 아오하루(골든) = 바뀐 수만
정답·짝짓기는 `compare_change_impl`과 같다(Verovio SVG eff · PDF `measure_certain_errors._truth`, 가로 0.7sp · 세로 0.5sp).
라벨 생김 · 사라짐(오삭제)은 `compare_change_impl.py`로 따로 본다.

    python tools/compare_acc_impl.py <기준> <새>      # 출력 + debug/compare_<새>_acc.json (grid_changes 형식)
"""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


def main(base, new):
    import measure_sim_ledger_pair as S
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"])
    acc = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
    norm = lambda a: {"natural": "", None: ""}.get(a, a)
    c, items = Counter(), []
    for st, nm, path, pg in S.pages():
        A = {key(l): l for l in json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]}
        B = {key(l): l for l in json.load(open(os.path.join(LP, new, nm + ".json"), encoding="utf-8"))["labels"]}
        ch = [(A[k], B[k]) for k in A.keys() & B.keys() if A[k]["text"] != B[k]["text"]]
        if not ch:
            continue
        if nm == "organ2":      # 정답 없음(compare_change_impl도 뺀다) — 바뀐 수만
            c["organ2 표기 변화(정답 없음)"] += len(ch)
            items += [("organ2", nm, b["x"], b["y"], f"{a['text']}→{b['text']}") for a, b in ch]
            continue
        if st == "aoharu":
            c["아오하루 표기 변화"] += len(ch)
            items += [("아오하루", nm, b["x"], b["y"], f"{a['text']}→{b['text']}") for a, b in ch]
            continue
        if st == "verovio":
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
            heads, sp = [(n["x"], n["y"], n["note_name"] + n["octave"], n["eff"] or "") for n in t["notes"]], 18.0
        else:
            from measure_certain_errors import _truth
            heads, sp = _truth("pdf", nm, path, pg)
        for a, b in ch:
            h = [q for q in heads if abs(q[0] - b["x"]) <= 0.7 * sp and abs(q[1] - b["y"]) <= 0.5 * sp]
            if not h:
                k = "정답 짝 없음(유령)"
            elif h[0][2] != b["pitch"]:
                k = "음고 틀림 라벨(표기 비교 안 함)"
            else:
                want = norm(h[0][3])
                ok_a, ok_b = acc(a["text"]) == want, acc(b["text"]) == want
                k = "고침" if ok_b and not ok_a else "새로 틀림" if ok_a and not ok_b else "둘 다 틀림" if not ok_b else "둘 다 맞음"
            c[k] += 1
            items.append((k, nm, b["x"], b["y"], f"{a['text']}→{b['text']}"))
    print(dict(c))
    for i in items:
        print("   ", i)
    json.dump(items, open(os.path.join(ROOT, "debug", f"compare_{new}_acc.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:3])
