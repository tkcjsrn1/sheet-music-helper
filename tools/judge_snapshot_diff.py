# -*- coding: utf-8 -*-
"""PDF 스냅샷 바뀐 줄(debug/snapshot_diff.tsv)을 PDF 글리프 정답(음고 + 실효 임시표)으로 판정. 측정 전용.
줄마다: 정답 머리 없음(유령) / 맞음(음고 · 표기) / 틀림. 사라짐 · 생김을 같은 자리끼리 묶어 「고쳐짐 · 망가짐 · 틀림→틀림」도 센다.

    python tools/judge_snapshot_diff.py
"""
import csv
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

if __name__ == "__main__":
    import check_accidental_fix as C
    import measure_pdf_effective as E
    import measure_pdf_text_causes as TC
    rows = list(csv.DictReader(open(os.path.join(ROOT, "debug", "snapshot_diff.tsv"), encoding="utf-8"), delimiter="\t"))
    P = {n: (p, g) for n, p, g in C.PAGES}
    c = Counter()
    by = {}
    for page in sorted({r["쪽"] for r in rows}):
        res, heads = E.effective(page, *P[page])
        sp = float(sum(s.spacing for s in res.staves) / len(res.staves))
        for r in (r for r in rows if r["쪽"] == page):
            x, y = int(r["x"]), int(r["y"])
            h = [q for q in heads if abs(q["x"] - x) <= 0.7 * sp and abs(q["y"] - y) <= 0.5 * sp]
            if not h:
                v = "유령"
            else:
                ok = r["음이름"] == h[0]["pitch"] and TC.ACC(r["표기"]) == TC.NORM.get(h[0]["eff"], "")
                v = "맞음" if ok else "틀림"
                by.setdefault((page, round(h[0]["x"]), round(h[0]["y"])), {})[r["변화"]] = v
            c[(r["변화"], v)] += 1
    for k, n in sorted(c.items()):
        print(" ", k, n)
    pair = Counter()
    for (_p, _x, _y), d in by.items():
        a, b = d.get("사라짐"), d.get("생김")
        pair["되찾음(새 머리 맞음)" if a is None and b == "맞음" else "되찾음(새 머리 틀림)" if a is None and b == "틀림"
             else "잃음(맞던 것)" if b is None and a == "맞음" else "잃음(틀리던 것)" if b is None
             else "고쳐짐" if (a, b) == ("틀림", "맞음") else "망가짐" if (a, b) == ("맞음", "틀림") else f"{a}→{b}"] += 1
    print("정답 머리별:", dict(pair))
