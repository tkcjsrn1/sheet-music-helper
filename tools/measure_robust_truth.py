# -*- coding: utf-8 -*-
"""흔들림 시험의 「확실」 흔들림을 정답 기준으로 나눈다 — 맞음→틀림 / 틀림→맞음 / 둘 다 틀림 / 확신도만 변화. 측정 전용.

    python tools/measure_robust_truth.py [변형 ...]      # 기본 scale+1 scale-1 · 결과 debug/render_robust/truth_<변형>.json + 표

정답: PDF 17쪽 = `error_census._truth_pdf`(PDF 머리 글리프 + 적힌 임시표 + 마디선 전파 + 곡 조표). 라벨이 맞다 = 정답 머리와 짝(가로 0.7 · 세로 0.5sp)이 있고
음고 · 실효 임시표가 같다. 짝 없음 = 유령. 정답 머리가 짝을 잃으면 = 누락.
흔들림 단위(`measure_render_robustness.compare_page`와 같은 짝짓기):
  기준에만(기준 확실) · 변형에만(변형 확실) · 음고 · 표기 바뀜(변형 확실) → 맞음→틀림 / 틀림→맞음 / 둘 다 틀림
  확신도만 바뀜(어느 한쪽이 확실) → 확신도만 변화
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import measure_render_robustness as R  # noqa: E402

CACHE = os.path.join(R.OUT, "truth_cache")


def truth(tag, pdf, pg):
    p = os.path.join(CACHE, tag + ".json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    import error_census as E
    heads, _boxes, sp = E._truth_pdf(tag, os.path.join("test_scores", pdf), pg)
    os.makedirs(CACHE, exist_ok=True)
    json.dump(dict(heads=heads, sp=sp), open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return dict(heads=heads, sp=sp)


def verdicts(labels, T):
    """라벨마다 (맞음 여부, 유형). 유형: 맞음 · 유령 · 음고 · 표기."""
    import error_census as E
    m = E._match(T["heads"], labels, T["sp"])
    inv = {j: i for i, j in m.items()}
    out = []
    for j, l in enumerate(labels):
        if j not in inv:
            out.append((False, "유령"))
            continue
        h = T["heads"][inv[j]]
        if l["pitch"] != h["pitch"]:
            out.append((False, "음고"))
        elif E.ACC(l["text"]) != h["eff"]:
            out.append((False, "표기"))
        else:
            out.append((True, "맞음"))
    return out


def main(variants):
    res = {}
    for v in variants:
        tab, kinds, ex = Counter(), Counter(), []
        for tag, pdf, pg in R.PAGES:
            if not all(os.path.exists(os.path.join(R.OUT, "out", x, tag + ".json")) for x in (R.BASE, v)):
                continue
            T = truth(tag, pdf, pg)
            _c, d = R.compare_page(v, tag)
            A = R._labels(os.path.join(R.OUT, "out", R.BASE, tag + ".json"))[1]
            B = R._labels(os.path.join(R.OUT, "out", v, tag + ".json"))[1]
            for b in B:
                b["x"], b["y"] = R._to_base(v, b["x"], b["y"])
            va, vb = verdicts(A, T), verdicts(B, T)
            ka = {(a["staff"], a["x"], a["y"]): va[i] for i, a in enumerate(A)}
            kb = {(b["staff"], round(b["x"], 3), round(b["y"], 3)): vb[i] for i, b in enumerate(B)}
            key_b = lambda b: (b["staff"], round(b["x"], 3), round(b["y"], 3))

            def add(cat, kind, a=None, b=None):
                tab[cat] += 1
                kinds[(cat, kind)] += 1
                ex.append(dict(tag=tag, cat=cat, kind=kind, base=a, var=b))
            for a in d["only_base"]:
                if a["conf"] != "certain":
                    continue
                ok, k = ka[(a["staff"], a["x"], a["y"])]
                add("맞음→틀림" if ok else "틀림→맞음", "누락" if ok else k, a=a)
            for b in d["only_var"]:
                if b["conf"] != "certain":
                    continue
                ok, k = kb[key_b(b)]
                add("틀림→맞음" if ok else "맞음→틀림", "되찾음" if ok else k, b=b)
            for a, b in d["changed"]:
                if b["conf"] != "certain":
                    continue
                oa, _ = ka[(a["staff"], a["x"], a["y"])]
                ob, k = kb[key_b(b)]
                cat = "맞음→틀림" if oa and not ob else "틀림→맞음" if ob and not oa else "둘 다 틀림" if not oa and not ob else "둘 다 맞음"
                add(cat, k if not ob else "고쳐짐", a, b)
            for a, b in d["conf"]:
                if "certain" in (a["conf"], b["conf"]):
                    ok, _k = ka[(a["staff"], a["x"], a["y"])]
                    add("확신도만 변화", f"{'맞는' if ok else '틀린'} 라벨 {a['conf']}→{b['conf']}", a, b)
        res[v] = dict(table=dict(tab), kinds={f"{a}|{b}": n for (a, b), n in kinds.items()}, examples=ex)
        print(v, dict(tab))
        for (cat, kind), n in sorted(kinds.items(), key=lambda x: (x[0][0], -x[1])):
            print(f"    {cat:8s} {kind:24s} {n}")
        json.dump(res[v], open(os.path.join(R.OUT, f"truth_{v}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return res


if __name__ == "__main__":
    main(sys.argv[1:] or ["scale+1", "scale-1"])
