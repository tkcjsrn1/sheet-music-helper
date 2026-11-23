# -*- coding: utf-8 -*-
"""PDF 머리마다 **실효 임시표 정답** — PDF 글리프(임시표 · 머리) + 벡터 마디선 + 곡 조표로 만든다. 제품 코드 무변경.

규칙(기보): 머리 자신의 임시표 글리프 > 같은 보표 · 같은 마디 · 같은 음이름+옥타브의 앞 임시표 > 조표.
한계: 붙임줄로 마디를 넘는 음 · 꾸밈음 · 다른 보표로 건너간 성부는 반영 안 함(그 경우 「정답 불확실」로 센다).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

KEYS = {"bach": "", "bbm": "BEADG", "db": "BEADG", "em": "F"}       # 곡 조표(음이름) — ♭5 / ♯1
KEY_SIGN = {"bach": "", "bbm": "b", "db": "b", "em": "#"}


def effective(name, path, pg):
    import check_accidental_fix as C
    import measure_a17 as A
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    from measure_barline_stem import pdf_verticals
    tag = "".join(ch for ch in name if not ch.isdigit())
    res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = C.analyze_staves(res)
    heads, clefs = truth_at(path, pg, 1.0)
    for q in clefs:
        q["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["cy"])).index
    glyphs = A.truth(path, pg, res, ctx)[0]
    bars = [(x, a, b) for x, a, b, k in pdf_verticals(os.path.join(ROOT, path), pg) if k == "barline"]
    out = []
    for h in heads:
        st, pitch, _step, _kind = M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)
        if pitch is None:
            continue
        out.append(dict(x=h["cx"], y=h["cy"], staff=st, pitch=pitch))
    for g in glyphs:                                         # 글리프가 붙는 머리
        hs = [o for o in out if abs(o["x"] - g["hx"]) < 1 and abs(o["y"] - g["hy"]) < 1]
        for o in hs:
            o["own"] = g["kind"]
    staff_of = {s.index: s for s in res.staves}
    for o in sorted(out, key=lambda o: o["x"]):
        if "own" in o:
            o["eff"] = o["own"]
            continue
        s = staff_of.get(o["staff"])
        sb = [x for x, a, b in bars if s is not None and a <= s.bottom and b >= s.top]
        prev = [p for p in out if p["staff"] == o["staff"] and p["x"] < o["x"] - 1 and p["pitch"] == o["pitch"] and "own" in p
                and not any(p["x"] < bx < o["x"] for bx in sb)]
        if prev:
            o["eff"] = max(prev, key=lambda p: p["x"])["own"]
        else:
            o["eff"] = KEY_SIGN[tag] if o["pitch"][0] in KEYS[tag] else ""
    return res, out


def judge(diff_rows):
    """바뀐 라벨 줄마다 기준 · 후보 표기를 실효 정답과 대조 — 고쳐짐 / 새로 틀림 / 틀린 채 / 맞음 그대로 / 정답 머리 없음."""
    import check_accidental_fix as C
    from collections import Counter, defaultdict
    by = defaultdict(list)
    for r in diff_rows:
        by[(r["page"], r["path"], r["pg"])].append(r)
    acc = lambda t: "#" if t and t.endswith("#") else "b" if t and t.endswith("b") else ""
    norm = {"#": "#", "b": "b", "natural": "", "": "", "flatflat": "b", "doublesharp": "#"}
    tally, out = Counter(), []
    for (name, path, pg), rows in by.items():
        if name.startswith("aoharu"):
            continue
        res, heads = effective(name, path, pg)
        sp = float(np.median([s.spacing for s in res.staves]))
        for r in rows:
            h = [o for o in heads if abs(o["x"] - r["x"]) <= 0.7 * sp and abs(o["y"] - r["y"]) <= 0.5 * sp]
            if not h:
                k = "정답 머리 없음(유령 자리)"
            else:
                e = norm.get(min(h, key=lambda o: abs(o["x"] - r["x"]) + abs(o["y"] - r["y"]))["eff"], "")
                b, a = (acc(r["before"]) if r["before"] != "(없음)" else None), (acc(r["after"]) if r["after"] != "(없음)" else None)
                if a is None:
                    k = "사라짐(정답 머리)"
                elif b == e and a != e:
                    k = "새로 틀림"
                elif b != e and a == e:
                    k = "고쳐짐"
                elif b == e and a == e:
                    k = "맞음 그대로"
                else:
                    k = "틀린 채 바뀜"
            tally[k] += 1
            out.append(dict(r, verdict=k))
    return tally, out
