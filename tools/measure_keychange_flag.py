# -*- coding: utf-8 -*-
"""[6] 곡 중간 조바꿈 → 「확인 필요」 표시안의 헛표시. 제품 코드 무변경.

증거: `measure_midline_keysig`(간격 창 + 같은 시스템 두 보표 동의, KEY_CHANGE.md §4 — Verovio 조바꿈 6/6, 오검출 24 · 10 · 8)와 같은 계산.
표시 구간: 증거 x부터 그 시스템 보표들의 끝까지. 라벨 = 현재 main(`debug/sim_lp/cglyph`).
정답: Verovio SVG(음고 · 실효 임시표), PDF · 보지 않은 악보 = `measure_pdf_effective`(`measure_certain_errors._truth`). 오르간 2쪽 제외.

    python tools/measure_keychange_flag.py
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
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _page(job):
    import measure_midline_keysig as K
    from measure_certain_errors import _truth
    from modules.preprocess import preprocess
    kind, name, path, pg, lab = job
    K.MIN_STAVES = 2
    _k, _n, _truth_kc, found = K._page((kind, name, path, pg, lab))
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    staves = sorted(res.staves, key=lambda s: s.top)
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        sys_of = {s.index: ts["system"] for s, ts in zip(staves, t["staves"])} if len(t["staves"]) == len(staves) else {}
    else:
        sys_of = {s.index: i // 2 for i, s in enumerate(staves)}
    L = json.load(open(lab, encoding="utf-8"))["labels"]
    heads, sp = _truth("verovio" if kind == "verovio" else "pdf", name, path, pg)
    c = Counter()
    c["증거"] = len(found)
    for l in L:
        sy = sys_of.get(l["staff"])
        if not any(f[0] == sy and l["x"] >= f[1] for f in found):
            continue
        h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
        k = "유령" if not h else "음고 틀림" if l["pitch"] != h[0][2] else "표기 틀림" if ACC(l["text"]) != h[0][3] else "맞음(헛표시)"
        c[k] += 1
        c[k + " · 확실" if l["confidence"] == "certain" else k + " · 이미 주의/check"] += 1
    return kind, name, c


def main():
    import measure_sim_ledger_pair as S
    jobs = [(st, n, p, pg, os.path.join(ROOT, "debug", "sim_lp", "cglyph", n + ".json")) for st, n, p, pg in S.pages()
            if st != "aoharu" and n != "organ2"]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    tot = {}
    for kind, name, c in res:
        tot.setdefault(kind, Counter()).update(c)
    for kind, c in tot.items():
        print(f"{kind}: 증거 {c['증거']} | 표시 대상 — 표기 틀림 {c['표기 틀림']} · 음고 틀림 {c['음고 틀림']} · 유령 {c['유령']} · 맞음(헛표시) {c['맞음(헛표시)']}"
              f" | 그중 지금 확실: 표기 틀림 {c['표기 틀림 · 확실']} · 맞음 {c['맞음(헛표시) · 확실']}")


if __name__ == "__main__":
    main()
