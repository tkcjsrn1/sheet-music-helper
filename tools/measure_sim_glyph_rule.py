# -*- coding: utf-8 -*-
"""판단 4 — 글리프 모양 규칙(`GLYPH_GHOST.md` ♭형 · ♮형) 사본 시뮬레이션. 표시만 하는 부분(i)과 임시표를 바꾸는 부분(ii)을 나눠 센다. 제품 코드 무변경.

(i) 표시: 모든 라벨에 LU · LD · RU · RD(`measure_glyph_ghost.runs`)를 재고 ♭형(LU ≥ 1.3 · LD ≤ 0.6 · RU ≤ 1.0) 또는 ♮형(LU ≥ 0.6 · RD ≥ 0.6 · LD ≤ 1.7 · RU ≤ 2.0)이면 check.
    걸린 라벨을 정답 대조(유령 / 진짜 머리)하고, 원래 등급별로 센다(확실 → check가 사용자에게 보이는 변화).
(ii) 주인 ♭ 회복: ♭형에 걸린 라벨 g의 오른쪽 0.5~1.6sp · 세로 ±0.5sp 라벨을 주인으로 보고 그 표기를 ♭으로 바꿨다고 할 때
    실효 정답(`measure_certain_errors._truth`) 대비 고쳐짐(틀림 → 맞음) · 망가짐(맞음 → 틀림) · 그대로. 같은 마디 뒤 음으로의 전파는 넣지 않았다(단순화).
라벨 = 현재 main 제품(`debug/vrv_clefflag/base`, `debug/a17_cand1_clefflag/base_*`). Aoharu = 정답 골든이 라벨 그대로라 걸린 라벨 수만(전부 헛표시).

    python tools/measure_sim_glyph_rule.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
FB = lambda g: g["LU"] >= 1.3 and g["LD"] <= 0.6 and g["RU"] <= 1.0
FN = lambda g: g["LU"] >= 0.6 and g["RD"] >= 0.6 and g["LD"] <= 1.7 and g["RU"] <= 2.0
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _page(job):
    from measure_glyph_ghost import runs
    from measure_certain_errors import _truth
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    st, name, path, pg, lab = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ns = remove_staff_lines(res.binary, res.staves) > 0
    sp_of = {s.index: s.spacing for s in res.staves}
    L = json.load(open(lab, encoding="utf-8"))["labels"]
    heads, sp0 = (None, None) if st == "aoharu" else _truth(st if st != "unseen" else "pdf", name, path, pg)
    c = Counter()
    for l in L:
        sp = sp_of.get(l["staff"], 18.0)
        g = runs(ns, l["x"], l["y"], sp)
        fb, fn = FB(g), FN(g)
        if not (fb or fn):
            continue
        if heads is None:
            c["걸림(Aoharu — 전부 헛표시)"] += 1
            continue
        h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp0 and abs(q[1] - l["y"]) <= 0.5 * sp0]
        c[f"(i) {'유령' if not h else '진짜 머리'} · 원래 {l['confidence']}"] += 1
        if not fb:
            continue
        own = [m for m in L if m is not l and m["staff"] == l["staff"] and 0.5 * sp <= m["x"] - l["x"] <= 1.6 * sp and abs(m["y"] - l["y"]) <= 0.5 * sp]
        if not own:
            c["(ii) 주인 없음"] += 1
            continue
        m = min(own, key=lambda m: m["x"])
        hh = [q for q in heads if abs(q[0] - m["x"]) <= 0.7 * sp0 and abs(q[1] - m["y"]) <= 0.5 * sp0]
        if not hh:
            c["(ii) 주인이 유령"] += 1
            continue
        right_now = m["pitch"] == hh[0][2] and ACC(m["text"]) == hh[0][3]
        right_after = m["pitch"] == hh[0][2] and hh[0][3] == "b"
        c["(ii) 이미 ♭" if ACC(m["text"]) == "b" else "(ii) 고쳐짐" if (not right_now and right_after) else "(ii) 망가짐" if (right_now and not right_after) else "(ii) 그대로 틀림"] += 1
    return st, dict(c)


def main():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    jobs = [("pdf" if p.endswith(".pdf") else "aoharu", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES]
    jobs += [("unseen", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_unseen", n + ".json")) for n, p, pg in G.UNSEEN if n != "organ2"]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0, os.path.join(ROOT, "debug", "vrv_clefflag", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(2) as ex:
        res = list(ex.map(_page, jobs))
    tot = {}
    for st, c in res:
        tot.setdefault(st, Counter()).update(c)
    json.dump({k: dict(v) for k, v in tot.items()}, open(os.path.join(ROOT, "debug", "sim_glyph_rule.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st, c in tot.items():
        print(st)
        for k in sorted(c):
            print(f"   {k}: {c[k]}")


if __name__ == "__main__":
    main()
