# -*- coding: utf-8 -*-
"""§1-47 초안(가운데 머리 끝 쌍 창 1.8~2.4sp + 음고 차 5도) 검증 — 기준 · 새 라벨(49쪽) 대조 (2026-10-19 · 측정만).

쪽마다 debug/compare_middle_pair/<새>/<쪽>.json에 바로 쓰고 이미 있으면 건너뛴다(이어 돌리기).
  생김 = 새 라벨 → 정답 대응(`error_census._truth_*`)으로 되찾음(음고 맞음) · 음고 틀림 · 유령, 두 끝 거리(sp) 함께
  사라짐 = 0이어야 한다(오삭제)
  표기 바뀜 = 기존 라벨 text 변화 → 고침 · 새로 틀림(확실 따로)
  쌍 분포 = 기준 라벨의 「같은 보표 · |dx| ≤ 0.3sp · 음고 차 5도 · 가운데 0.5sp 안 라벨 없음」 쌍마다 세로 거리와 정답 가운데 머리 유무

    python tools/compare_middle_pair.py <기준> <새>
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
STEP = lambda p: "CDEFGAB".index(p[0]) + 7 * int(p[1])


def _job(job):
    base, new, (st, nm, path, pg) = job
    out = os.path.join(ROOT, "debug", "compare_middle_pair", new, nm + ".json")
    if os.path.exists(out):
        return json.load(open(out, encoding="utf-8"))
    r = _judge(base, new, st, nm, path, pg)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(r, open(out + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(out + ".tmp", out)
    return r


def _judge(base, new, st, nm, path, pg):
    import error_census as EC
    load = lambda v: json.load(open(os.path.join(LP, v, nm + ".json"), encoding="utf-8"))
    DA, DB = load(base), load(new)
    sp = {s["id"]: s["spacing"] for s in DB["staves"]}
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"])
    A = {key(l): l for l in DA["labels"]}
    B = {key(l): l for l in DB["labels"]}
    res = dict(set=st, page=nm, added=[], removed=len(A.keys() - B.keys()), text=[], pairs=[])
    if st == "aoharu":
        res["added"] = [dict(x=l["x"], y=l["y"], verdict="아오하루(골든)") for k, l in B.items() if k not in A]
        return res
    heads, _b, s0 = EC._truth_vrv(nm) if st == "verovio" else EC._truth_pdf(nm, path, pg)
    L = DB["labels"]
    m = {j: heads[i] for i, j in EC._match(heads, L, s0).items()}
    idx = {key(l): j for j, l in enumerate(L)}
    for k, l in B.items():
        if k in A:
            continue
        h = m.get(idx[k])
        s = sp[l["staff"]]
        ends = [e for e in L if e is not l and e["staff"] == l["staff"] and abs(e["x"] - l["x"]) <= 0.5 * s and 0.7 * s <= abs(e["y"] - l["y"]) <= 1.4 * s]
        dy = round((max(e["y"] for e in ends) - min(e["y"] for e in ends)) / s, 2) if len(ends) >= 2 else None
        v = "유령" if h is None else ("되찾음" if h["pitch"] == l["pitch"] else "음고 틀림")
        res["added"].append(dict(x=l["x"], y=l["y"], staff=l["staff"], pitch=l["pitch"], text=l["text"], conf=l["confidence"],
                                 verdict=v, dy=dy, ok_text=(h is not None and h["pitch"] == l["pitch"] and ACC(l["text"]) == h["eff"])))
    for k in A.keys() & B.keys():
        a, b = A[k], B[k]
        if a["text"] == b["text"]:
            continue
        h = m.get(idx[k])
        if h is None or h["pitch"] != b["pitch"]:
            v = "유령 · 음고 틀림 라벨"
        else:
            oa, ob = ACC(a["text"]) == h["eff"], ACC(b["text"]) == h["eff"]
            v = "고침" if ob and not oa else ("새로 틀림 · 확실" if b["confidence"] == "certain" else "새로 틀림") if oa and not ob else "둘 다 틀림" if not ob else "둘 다 맞음"
        res["text"].append(dict(x=b["x"], y=b["y"], before=a["text"], after=b["text"], conf=b["confidence"], verdict=v))
    # 쌍 분포(기준 라벨)
    LA = DA["labels"]
    for i, a in enumerate(LA):
        for b in LA[i + 1:]:
            if a["staff"] != b["staff"]:
                continue
            s = sp.get(a["staff"])
            if s is None or abs(a["x"] - b["x"]) > 0.3 * s or abs(STEP(a["pitch"]) - STEP(b["pitch"])) != 4:
                continue
            mx, my = (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2
            if any(abs(l["x"] - mx) <= 0.5 * s and abs(l["y"] - my) <= 0.5 * s for l in LA):
                continue
            has = any(abs(h["x"] - mx) <= 0.7 * s and abs(h["y"] - my) <= 0.5 * s for h in heads)
            res["pairs"].append(dict(dy=round(abs(a["y"] - b["y"]) / s, 2), middle=has))
    return res


def main(base, new):
    import measure_sim_ledger_pair as S
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_job, [(base, new, p) for p in S.pages() if p[1] != "organ2"]))   # organ2는 정답 좌표 불일치(다른 측정과 같음)
    c = Counter()
    for r in R:
        c["사라짐"] += r["removed"]
        for a in r["added"]:
            c["생김 · " + a["verdict"] + (" · " + a["conf"] if "conf" in a else "")] += 1
            if a["verdict"] == "되찾음" and not a["ok_text"]:
                c["되찾음 중 표기 틀림"] += 1
        for t in r["text"]:
            c["기존 라벨 표기 · " + t["verdict"]] += 1
    print("합계", {k: v for k, v in c.items() if v})
    for r in R:
        for a in r["added"]:
            if a["verdict"] != "되찾음":
                print("  ", a["verdict"], r["set"], r["page"], a)
        for t in r["text"]:
            if t["verdict"].startswith("새로") or t["verdict"].startswith("유령"):
                print("  표기", t["verdict"], r["page"], t)
    print("새 머리 두 끝 거리(sp):", sorted(a["dy"] for r in R for a in r["added"] if a.get("dy") is not None))
    dist = defaultdict(lambda: defaultdict(list))
    for r in R:
        for p in r["pairs"]:
            dist[r["set"]]["진짜 가운데 있음" if p["middle"] else "가운데 없음"].append(p["dy"])
    for st, d in dist.items():
        for k, v in d.items():
            v = sorted(v)
            print(f"  쌍 분포 {st:8s} {k}: {len(v)} · 최소 {v[0]} · 최대 {v[-1]} · 2.2 초과 {sum(x > 2.2 for x in v)} · 2.2~2.4 {sum(2.2 < x <= 2.4 for x in v)}")
    json.dump(R, open(os.path.join(ROOT, "debug", f"compare_middle_pair_{new}.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:3])
