# -*- coding: utf-8 -*-
"""[1] 꾸밈음 표시(§1-24 후보, PR #241)의 분모 비교 — 「화음 아닌 음표 전부」(지금) vs 「확실 · 단독 · 꽉 찬 머리」(좁힘). 제품 코드 무변경.

라벨 = 지금 main(`debug/sim_lp/nograce`, 꾸밈음 표시 없음). 머리 크기 = `measure_grace_size.sizes`(제품 `verify.grace_size_suspects`와 같은 덩어리 계산).
꽉 참 = 라벨 자리 오선 제거 조각(±0.65 × ±0.55sp) 잉크 비율 > 0.4. 화음 = 같은 보표 0.6sp 안 다른 라벨.
걸림 = 폭 · 높이 비 둘 다 0.66~0.80 · 화음 아님. 정답: 꾸밈음 / 정상 머리(헛표시, 원래 확실이면 따로) / 유령. Aoharu는 걸림 수만.

    python tools/measure_grace_denominator.py
    python tools/measure_grace_denominator.py judge <변형>   # 제품 라벨(debug/sim_lp/<변형>) — nograce 대비 라벨 변화 · grace_size 걸림 판정
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
    import measure_grace_size as GS
    import measure_omission_rate as M
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "nograce", name + ".json"), encoding="utf-8"))["labels"]
    sz = GS.sizes(res, L)
    sp_of = {s.index: s.spacing for s in res.staves}
    ns = (remove_staff_lines(res.binary, res.staves) > 0).astype(np.float32)
    chord, filled = [], []
    for l in L:
        sp = sp_of.get(l["staff"], 18.0)
        chord.append(any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 0.6 * sp for o in L))
        hw, hh = int(0.65 * sp), int(0.55 * sp)
        c = ns[int(l["y"]) - hh:int(l["y"]) + hh + 1, int(l["x"]) - hw:int(l["x"]) + hw + 1]
        filled.append(c.size > 0 and c.mean() > 0.4)
    if st == "aoharu":
        heads = None
    elif st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads = [(n["x"], n["y"], bool(n.get("grace") or n.get("cue"))) for n in t["notes"]]
    else:
        g = M.pdf_glyphs(path, pg, ("noteheads.",))
        main = Counter(round(q["size"], 2) for q in g).most_common(1)[0][0] if g else 0
        heads = [(q["cx"], q["cy"], abs(q["size"] - main) >= 0.05) for q in g]
    sp0 = float(np.median(list(sp_of.values())))
    out = {}
    for den in ("지금(화음 아닌 전부)", "좁힘(확실 · 단독 · 꽉 참)"):
        if den.startswith("지금"):
            ref = [s for s, ch in zip(sz, chord) if s[0] is not None and not ch]
        else:
            ref = [s for s, ch, f, l in zip(sz, chord, filled, L) if s[0] is not None and not ch and f and l["confidence"] == "certain"]
        c = Counter()
        if ref:
            mw, mh = float(np.median([w for w, _h in ref])), float(np.median([h for _w, h in ref]))
            for l, (w, h), ch in zip(L, sz, chord):
                if w is None or ch or not (0.66 <= w / mw <= 0.80 and 0.66 <= h / mh <= 0.80):
                    continue
                if heads is None:
                    c["Aoharu 걸림"] += 1
                    continue
                m = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp0 and abs(q[1] - l["y"]) <= 0.5 * sp0]
                k = "유령" if not m else "꾸밈음" if m[0][2] else "정상 머리(헛표시)"
                c[k] += 1
                if k.startswith("정상") and l["confidence"] == "certain":
                    c["정상 머리 확실→check"] += 1
        out[den] = c
    return st, name, out


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        res = list(ex.map(_page, [p for p in S.pages() if p[1] != "organ2"]))
    for den in ("지금(화음 아닌 전부)", "좁힘(확실 · 단독 · 꽉 참)"):
        t = Counter()
        for _s, _n, o in res:
            t.update(o[den])
        print(den, dict(t))


def _truth(st, name, path, pg):
    import measure_omission_rate as M
    if st == "aoharu":
        return None
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"], bool(n.get("grace") or n.get("cue"))) for n in t["notes"]]
    g = M.pdf_glyphs(path, pg, ("noteheads.",))
    main_sz = Counter(round(q["size"], 2) for q in g).most_common(1)[0][0] if g else 0
    return [(q["cx"], q["cy"], abs(q["size"] - main_sz) >= 0.05) for q in g]


def _judge(job):
    v, (st, name, path, pg) = job
    rd = lambda d: json.load(open(os.path.join(ROOT, "debug", "sim_lp", d, name + ".json"), encoding="utf-8"))["labels"]
    A, B = rd("nograce"), rd(v)
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"])
    c = Counter(사라짐=len({key(l) for l in A} - {key(l) for l in B}), 생김=len({key(l) for l in B} - {key(l) for l in A}))
    heads = _truth(st, name, path, pg)
    conf0 = {(l["staff"], l["x"], l["y"]): l["confidence"] for l in A}
    sp0 = 0.0
    if heads is not None:
        from modules.preprocess import preprocess
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
        sp0 = float(np.median([s.spacing for s in res.staves]))
    for l in B:
        if "grace_size" not in (l.get("flags") or []):
            continue
        if heads is None:
            c["Aoharu 걸림"] += 1
            continue
        m = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp0 and abs(q[1] - l["y"]) <= 0.5 * sp0]
        k = "유령" if not m else "꾸밈음" if m[0][2] else "정상 머리"
        c[k] += 1
        if k == "정상 머리" and conf0.get((l["staff"], l["x"], l["y"])) == "certain":
            c["정상 머리 확실→check"] += 1
    return c


def judge(v):
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        t = sum(ex.map(_judge, [(v, p) for p in S.pages() if p[1] != "organ2"]), Counter())
    print(v, dict(t))


if __name__ == "__main__":
    judge(sys.argv[2]) if sys.argv[1:2] == ["judge"] else main()
