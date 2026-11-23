# -*- coding: utf-8 -*-
"""[7] 같은 머리에 라벨 2개 이상 — 수 · 표기 같음/다름 · 안전하게 합칠 조건(오삭제 0). 제품 코드 무변경.

정답 머리마다 0.7 × 0.5sp 안 라벨 수(라벨 = 현재 main `debug/sim_lp/cglyph`, #217 재적용은 `debug/sim_lp/flatleft`의 D♭ 1쪽).
합치기 조건 후보는 제품이 아는 성질 — 같은 보표 라벨 쌍의 가로 · 세로 거리. 쌍마다 「같은 정답 머리 하나에 둘 다 짝(중복)」 vs 「서로 다른 정답 머리 둘(합치면 오삭제)」.
정답: Verovio SVG, PDF · 보지 않은 악보 = PDF 글리프 머리(작은 머리 포함). 오르간 2쪽 · Aoharu 제외.

    python tools/measure_duplicate_labels.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    st, name, path, pg, variant = job
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", variant, name + ".json"), encoding="utf-8"))["labels"]
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads, sp = [(n["x"], n["y"]) for n in t["notes"]], 18.0
    else:
        import measure_omission_rate as M
        from modules.preprocess import preprocess
        heads = [(q["cx"], q["cy"]) for q in M.pdf_glyphs(path, pg, ("noteheads.",))]
        sp = float(np.median([s.spacing for s in preprocess(os.path.join(ROOT, path), pdf_page=pg).staves]))
    near = lambda l, h: abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp
    owner = []
    for l in L:
        m = [(abs(h[0] - l["x"]) + abs(h[1] - l["y"]), i) for i, h in enumerate(heads) if near(l, h)]
        owner.append(min(m)[1] if m else None)
    dup = Counter(o for o in owner if o is not None)
    sites = []
    for hi, n in dup.items():
        if n >= 2:
            ls = [l for l, o in zip(L, owner) if o == hi]
            sites.append(dict(page=name, x=round(heads[hi][0]), y=round(heads[hi][1]), n=n, texts=[l["text"] for l in ls],
                              same=len({l["text"] for l in ls}) == 1, conf=[l["confidence"] for l in ls]))
    pairs = []
    for i, a in enumerate(L):
        for j in range(i + 1, len(L)):
            b = L[j]
            if a["staff"] != b["staff"]:
                continue
            dx, dy = abs(a["x"] - b["x"]) / sp, abs(a["y"] - b["y"]) / sp
            if dx > 1.0 or dy > 1.0:
                continue
            oa, ob = owner[i], owner[j]
            kind = "같은 머리(중복)" if oa is not None and oa == ob else "다른 진짜 머리 둘" if oa is not None and ob is not None else "유령 낀 쌍"
            pairs.append((round(dx, 2), round(dy, 2), kind))
    return st, sites, pairs


def main():
    import measure_sim_ledger_pair as S
    jobs = [(st, n, p, pg, "cglyph") for st, n, p, pg in S.pages() if st != "aoharu" and n != "organ2"]
    jobs += [(st, n, p, pg, "flatleft") for st, n, p, pg in S.pages() if n == "db1"]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    main_res, f217 = res[:-1], res[-1]
    for st in ("pdf", "unseen", "verovio"):
        sites = [s for k, ss, _p in main_res if k == st for s in ss]
        print(f"{st}: 라벨 2개 이상 붙은 머리 {len(sites)} · 표기 같음 {sum(s['same'] for s in sites)} · 다름 {sum(not s['same'] for s in sites)}")
    print("#217 재적용 D♭ 1쪽:", [s for s in f217[1] if abs(s["x"] - 2336) < 20])
    pairs = [p for _k, _s, ps in main_res for p in ps]
    print("같은 보표 라벨 쌍(1sp 안):", dict(Counter(p[2] for p in pairs)))
    for dxm, dym in ((0.2, 0.2), (0.3, 0.25), (0.4, 0.3), (0.5, 0.3), (0.5, 0.4)):
        c = Counter(p[2] for p in pairs if p[0] <= dxm and p[1] <= dym)
        print(f"  가로 ≤ {dxm} · 세로 ≤ {dym}sp: 중복 {c['같은 머리(중복)']} · 다른 진짜 머리 둘 {c['다른 진짜 머리 둘']}(합치면 오삭제 후보) · 유령 낀 쌍 {c['유령 낀 쌍']}")
    json.dump(dict(sites=[s for _k, ss, _p in main_res for s in ss], pairs=pairs), open(os.path.join(ROOT, "debug", "duplicate_labels.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
