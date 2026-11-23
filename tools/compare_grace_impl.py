# -*- coding: utf-8 -*-
"""꾸밈음 기준 대체(§1-35) 구현 검증 — 기준 라벨과 새 라벨(49쪽, `measure_sim_ledger_pair run`) 비교 (2026-10-13).

조건: 라벨 사라짐 · 생김 0 · 음고 · 표기 변화 0 / 바뀐 것은 `grace_size` 표시와 확신도뿐.
새로 걸린(또는 풀린) 라벨을 정답으로 가른다 — `measure_grace_fallback._job`과 같은 규칙:
  Verovio = 정답 json의 grace · cue 머리, PDF · 보지 않은 = 쪽 주 크기와 0.05 넘게 다른 머리 글리프(작은 머리), Aoharu = 꾸밈음 없음(정상).
  라벨 ± 0.5sp 안에 작은 머리면 「꾸밈음」, 정상 머리면 「정상 진짜 머리(헛표시)」, 둘 다 없으면 「유령 · 기타」.
시뮬레이션 기대(`docs/GRACE_SIZE.md`): 49쪽 새로 13 전부 꾸밈음 · 헛표시 0 · 표시 사라짐 6(그중 check → 확실 1).

    python tools/compare_grace_impl.py <기준> <새>     # 예: combo1013 gracefb
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")


def _truth(st, name, path, pg):
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))["notes"]
        return ([(n["x"], n["y"]) for n in t if n["grace"] or n["cue"]], [(n["x"], n["y"]) for n in t if not n["grace"] and not n["cue"]])
    if st in ("pdf", "unseen"):
        import measure_omission_rate as M
        g = [q for q in M.pdf_glyphs(path, pg) if q["name"].startswith("noteheads.")]
        main = Counter(q["size"] for q in g).most_common(1)[0][0]
        return ([(q["cx"], q["cy"]) for q in g if abs(q["size"] - main) >= 0.05], [(q["cx"], q["cy"]) for q in g if abs(q["size"] - main) < 0.05])
    return None


def main(base, new):
    import measure_sim_ledger_pair as S
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
    c, rows = Counter(), []
    for st, name, path, pg in S.pages():
        A = json.load(open(os.path.join(LP, base, name + ".json"), encoding="utf-8"))
        B = json.load(open(os.path.join(LP, new, name + ".json"), encoding="utf-8"))
        a, b = {key(l): l for l in A["labels"]}, {key(l): l for l in B["labels"]}
        c["라벨 사라짐"] += len(a.keys() - b.keys())
        c["라벨 생김"] += len(b.keys() - a.keys())
        sp_of = {s["id"]: s["spacing"] for s in B["staves"]}
        tr = None
        for k in a.keys() & b.keys():
            la, lb = a[k], b[k]
            ga, gb = "grace_size" in la["flags"], "grace_size" in lb["flags"]
            other = sorted((set(la["flags"]) ^ set(lb["flags"])) - {"grace_size"})
            if other:
                c["다른 표시 변화"] += 1
            if ga == gb:
                if la["confidence"] != lb["confidence"]:
                    c["표시 같은데 확신도 변화"] += 1
                continue
            if tr is None:
                tr = _truth(st, name, path, pg) or ([], None)
            small, normal = tr
            sp = sp_of.get(lb["staff"], 18.0)
            near = lambda pts: any(abs(px - lb["x"]) <= 0.5 * sp and abs(py - lb["y"]) <= 0.5 * sp for px, py in pts)
            kind = "꾸밈음" if near(small) else "정상 진짜 머리(헛표시)" if (normal is None or near(normal)) else "유령 · 기타"
            what = "새로 걸림" if gb else "표시 사라짐"
            c[f"{what} · {kind} · {la['confidence']}→{lb['confidence']}"] += 1
            rows.append(dict(page=name, x=lb["x"], y=lb["y"], pitch=lb["pitch"], what=what, kind=kind, conf=f"{la['confidence']}→{lb['confidence']}"))
    for k in sorted(c):
        print(f"  {k}: {c[k]}")
    json.dump(rows, open(os.path.join(ROOT, "debug", f"compare_grace_{base}_{new}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows:
        print("   ", r)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
