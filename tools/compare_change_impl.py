# -*- coding: utf-8 -*-
"""구현 변경의 라벨 단위 판정(2026-10-13) — 기준 대비 사라짐 · 새로 생김 · 같은 자리 표기 바뀜을 정답(위치 + 음고 · 실효 임시표)으로 가른다.

  사라짐: 정답 짝이 있던 라벨이고 그 머리에 새 라벨이 없으면 **오삭제**, 다른 라벨이 남았으면 「자리 바뀜」, 짝 없던 라벨이면 「유령 사라짐」
  새 라벨: 정답 머리와 짝 · 기준에 그 머리 라벨이 없었으면 「되찾음」(음고 맞음/틀림), 짝 없으면 「새 유령」, 이미 라벨 있던 머리면 「중복 · 자리 바뀜」
  정답 = Verovio SVG(음고 · eff) · PDF · 보지 않은 악보 `measure_certain_errors._truth`(글리프 + 실효 임시표). 아오하루는 골든 — 바뀐 라벨 수만.

    python tools/compare_change_impl.py <기준> <새>       # 출력 + debug/compare_<새>.json(바뀐 라벨 목록, 격자용)
"""
import json, os, sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


def _job(job):
    base, new, (st, nm, path, pg) = job
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
    A = json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]
    B = json.load(open(os.path.join(LP, new, nm + ".json"), encoding="utf-8"))["labels"]
    KA, KB = {key(l): l for l in A}, {key(l): l for l in B}
    gone, add = [KA[k] for k in KA.keys() - KB.keys()], [KB[k] for k in KB.keys() - KA.keys()]
    c, items = Counter(), []
    if st == "aoharu":
        c["아오하루 바뀐 라벨"] = len(gone) + len(add)
        return st, c, [("아오하루", nm, l["x"], l["y"], l["text"]) for l in gone + add]
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
        heads = [(n["x"], n["y"], n["note_name"] + n["octave"], n["eff"] or "") for n in t["notes"]]
        sp = 18.0
    else:
        from measure_certain_errors import _truth
        heads, sp = _truth("pdf", nm, path, pg)
    near = lambda l, h: abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp
    acc = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
    norm = lambda a: {"natural": "", None: ""}.get(a, a)
    for l in gone:
        h = [q for q in heads if near(l, q)]
        k = "유령 사라짐" if not h else ("자리 바뀜(같은 머리 다른 라벨)" if any(near(m, h[0]) for m in B) else "오삭제")
        c[k] += 1
        items.append((k, nm, l["x"], l["y"], l["text"]))
    for l in add:
        h = [q for q in heads if near(l, q)]
        if not h:
            k = "새 유령"
        elif any(near(m, h[0]) for m in A):
            k = "중복 · 자리 바뀜"
        else:
            k = "되찾음 · 음고 " + ("맞음" if l["pitch"] == h[0][2] else "틀림")
            if l["pitch"] == h[0][2]:
                c["되찾음 중 표기 " + ("맞음" if acc(l["text"]) == norm(h[0][3]) else "틀림")] += 1
        c[k] += 1
        items.append((k, nm, l["x"], l["y"], l["text"]))
    return st, c, items


def main(base, new):
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_job, [(base, new, p) for p in S.pages() if p[1] != "organ2"]))
    tot = {}
    for st, c, _i in R:
        tot.setdefault(st, Counter()).update(c)
    for st, c in tot.items():
        print(f"{st:8s}", dict(c))
    allc = sum(tot.values(), Counter())
    print("합계", dict(allc))
    items = [i for _s, _c, it in R for i in it]
    print("오삭제", [i for i in items if i[0] == "오삭제"])
    json.dump(items, open(os.path.join(ROOT, "debug", f"compare_{new}.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:3])
