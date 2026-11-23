# -*- coding: utf-8 -*-
"""현재 상태 재측정 — PDF 글리프 정답 머리 ↔ 라벨(누락 · 음고 · 유령). `measure_verovio.pdf17`과 같은 짝짓기, 라벨은 run_page JSON.

    python tools/measure_status.py <라벨 JSON 폴더> <pdf20|unseen>     → 세트 합계 · 범주별
"""
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def eval_page(path, pg, labels):
    import measure_omission_rate as M
    from modules.preprocess import preprocess
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    g = M.pdf_glyphs(path, pg)
    clefs = [dict(c, staff=min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index)
             for c in g if c["name"].startswith("clefs.")]
    heads = []
    for x in (x for x in g if x["name"].startswith("noteheads.")):
        if any(abs(x["cx"] - h["cx"]) < 2 and abs(x["cy"] - h["cy"]) < 2 for h in heads):
            continue
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - x["cy"]))
        if x["cy"] < st.top - 6 * st.spacing or x["cy"] > st.bottom + 6 * st.spacing:
            continue
        heads.append(x)
    cat = Counter()
    if not heads:
        cat["정답 없음(벡터 글리프 없음)"] = 1
        return cat
    main_size = Counter(x["size"] for x in heads).most_common(1)[0][0]
    normal = [h for h in heads if abs(h["size"] - main_size) < 0.05]
    small = [h for h in heads if abs(h["size"] - main_size) >= 0.05]
    pairs, _used_t, used_l = M.match(normal, labels, sp)
    h2l = dict(pairs)
    for i, h in enumerate(normal):
        chord = any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp for j, q in enumerate(normal))
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - h["cy"]))
        k = int(round((h["cy"] - st.top) / (st.spacing / 2.0)))
        status = "누락" if i not in h2l else ("음고" if labels[h2l[i]]["pitch"] != M.truth_pitch(h["cx"], h["cy"], staves, clefs)[1] else "맞음")
        for c in ["전체", "화음" if chord else "단일", "빈 머리" if h["name"] in ("noteheads.s1", "noteheads.s0") else "꽉 찬 머리"] \
                + (["덧줄 구역"] if not 0 <= k <= 8 else []):
            cat[c + " · 정답"] += 1
            cat[c + " · " + status] += 1
    ghosts = [labels[i] for i in range(len(labels)) if i not in used_l]
    _p, _t, small_hit = M.match(small, ghosts, sp)
    cat["유령"] = len(ghosts) - len(small_hit)
    cat["라벨"] = len(labels)
    return cat


def run(folder, which):
    import measure_a17_ghost6 as G
    tot = Counter()
    for name, path, pg in G.SETS[which]():
        if not path.endswith(".pdf"):
            continue
        p = os.path.join(folder, name + ".json")
        if not os.path.exists(p):
            continue
        labels = [dict(x=l["x"], y=l["y"], pitch=l["pitch"], text=l["text"]) for l in json.load(open(p, encoding="utf-8"))["labels"]]
        c = eval_page(path, pg, labels)
        print(name, {k: v for k, v in c.items() if k.startswith("전체") or k in ("유령", "라벨") or k.startswith("정답 없음")}, flush=True)
        tot.update(c)
    n = tot["전체 · 정답"]
    print(f"\n== {which} 정답 머리 {n} · 라벨 {tot['라벨']}")
    for c in ("전체", "단일", "화음", "꽉 찬 머리", "빈 머리", "덧줄 구역"):
        t = tot[c + " · 정답"]
        if t:
            print(f"  {c}: 누락 {tot[c + ' · 누락']}/{t} ({tot[c + ' · 누락'] / t * 100:.1f}%) · 음고 {tot[c + ' · 음고']} ({tot[c + ' · 음고'] / t * 100:.1f}%)")
    print(f"  유령 {tot['유령']} ({tot['유령'] / max(1, n) * 100:.1f}% of 정답)")
    return tot


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])


def notation(folder, which="pdf20"):
    """PDF 표기 틀림 — 음고가 맞은 머리 중 라벨 임시표 ≠ 실효 임시표 정답(`measure_pdf_effective`, 붙임줄 · 꾸밈음 미반영)."""
    import measure_a17_ghost6 as G
    import measure_omission_rate as M
    import measure_pdf_effective as E
    acc = lambda t: "#" if t and t.endswith("#") else "b" if t and t.endswith("b") else ""
    norm = {"#": "#", "b": "b", "natural": "", "": "", "flatflat": "b", "doublesharp": "#"}
    tot = Counter()
    for name, path, pg in G.SETS[which]():
        if not path.endswith(".pdf") or name.startswith(("moon", "rain", "organ")):
            continue                                            # 실효 정답의 곡 조표는 PDF 17쪽만 알고 있다
        L = [dict(x=l["x"], y=l["y"], pitch=l["pitch"], text=l["text"]) for l in json.load(open(os.path.join(folder, name + ".json"), encoding="utf-8"))["labels"]]
        res, heads = E.effective(name, path, pg)
        sp = float(np.median([s.spacing for s in res.staves]))
        hh = [dict(cx=h["x"], cy=h["y"]) for h in heads]
        pairs, _t, _l = M.match(hh, L, sp)
        for ti, li in pairs:
            if L[li]["pitch"] != heads[ti]["pitch"]:
                continue
            tot["음고 맞음"] += 1
            tot["표기 틀림"] += acc(L[li]["text"]) != norm.get(heads[ti]["eff"], "")
    print(which, folder, dict(tot))
    return tot
