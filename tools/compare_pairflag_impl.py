# -*- coding: utf-8 -*-
"""§1-38 초안 구현 검증 — 표기 변화(`compare_acc_impl`)에 `pair_rejected` 표시를 겹쳐 「확실로 남는 새로 틀림」 · 맞는 라벨 헛표시를 센다 (2026-10-14).

먼저 `python tools/compare_acc_impl.py <기준> <새>`(debug/compare_<새>_acc.json)를 돌린다.
헛표시 = `pair_rejected`가 붙은 라벨 중 음고 · 표기가 정답과 맞고 기준에서 check가 아니던 것. 아오하루(골든)는 새로 check 수만.

    python tools/compare_pairflag_impl.py <기준> <새> [신호]     # 예: combo1013 bundlec pair_rejected · main1014 flatc1p flat_propagated
"""
import json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


FLAG = "pair_rejected"


def main(base, new):
    import measure_sim_ledger_pair as S
    from measure_certain_errors import _truth
    items = json.load(open(os.path.join(ROOT, "debug", f"compare_{new}_acc.json"), encoding="utf-8"))
    kind = {(nm, x, y): k for k, nm, x, y, _t in items}
    acc = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
    norm = lambda a: {"natural": "", None: ""}.get(a, a)
    c, left = Counter(), []
    for st, nm, path, pg in S.pages():
        A = {(l["staff"], l["x"], l["y"]): l for l in json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]}
        B = json.load(open(os.path.join(LP, new, nm + ".json"), encoding="utf-8"))["labels"]
        for l in B:
            if kind.get((nm, l["x"], l["y"])) == "새로 틀림":
                c["새로 틀림 · " + l["confidence"]] += 1
                if l["confidence"] == "certain":
                    left.append((nm, l["x"], l["y"], l["text"]))
        fl = [l for l in B if FLAG in l["flags"]]
        if not fl:
            continue
        was_check = lambda l: A.get((l["staff"], l["x"], l["y"]), {}).get("confidence") == "check"
        if st == "aoharu":
            c["아오하루 새로 check"] += sum(1 for l in fl if not was_check(l))
            continue
        if nm == "organ2":
            c["organ2(정답 없음) 표시"] += len(fl)
            continue
        if st == "verovio":
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
            heads, sp = [(n["x"], n["y"], n["note_name"] + n["octave"], n["eff"] or "") for n in t["notes"]], 18.0
        else:
            heads, sp = _truth("pdf", nm, path, pg)
        for l in fl:
            h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
            ok = bool(h) and h[0][2] == l["pitch"] and acc(l["text"]) == norm(h[0][3])
            c[("맞음 · 헛표시" if ok else "틀림/유령 → check") + (" (기준에서 이미 check)" if was_check(l) else "")] += 1
    print(dict(c))
    print("확실로 남는 새로 틀림", len(left), left)


if __name__ == "__main__":
    if len(sys.argv) > 3:
        FLAG = sys.argv[3]
    main(*sys.argv[1:3])
