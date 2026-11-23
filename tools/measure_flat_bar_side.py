# -*- coding: utf-8 -*-
"""[2] 슈베르트 오삭제 원인 — 원시 ♭ 판정의 「막대가 고리 왼쪽에 있는가」 + 2도 빈 머리 쌍 수. 제품 코드 무변경.

`_find_glyphs`의 ♭ 판정은 「창 안 막대가 하나라도 있고 + 고리(구멍) 하나」면 ♭이다 — 막대와 고리의 위치 관계를 안 본다.
기보: ♭의 세로획은 고리 **왼쪽**에 붙어 위로 뻗는다. 슈베르트 L 보표 6 (626,1513) F4의 가짜 ♭은 막대가 화음 기둥(고리 오른쪽), 고리가 왼쪽 E4 빈 머리 속이었다.
측정 사본(소스 무변경 — `_find_glyphs` 결과 ♭마다 고리 중심 x와 창 막대들의 x를 같이 남기는 래퍼)로 전 세트 원시 ♭ 판정을 모아
  left = 고리 중심보다 왼쪽(0.05 ~ 1.0sp)에 막대가 있는가
를 정답(그 음표에 인쇄된 ♭이 있는가: Verovio `accidental`, PDF `accidentals.flat` 글리프가 머리 왼쪽 3sp · 같은 높이 ±0.6sp)과 대조.
2도 빈 머리 쌍: 정답 빈 머리 둘이 같은 보표 · |dx| ≤ 1.5sp · |dy| 0.35~0.65sp.

    python tools/measure_flat_bar_side.py
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
HOLLOW_V = ("E0A3", "E0A2", "E0A0")


def _page(job):
    import cv2
    import modules.accidental_detect as AD
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    from modules.pitch_calculator import calculate_pitches
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    log = []
    orig = AD._find_glyphs

    def spy(patch, sp, bars=None, refined=False):
        g = orig(patch, sp, bars=bars, refined=refined)
        bs = bars if bars is not None else AD._find_thin_bars(patch, sp)
        holes = []
        small = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        cs, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hier is not None:
            for k in range(len(cs)):
                if hier[0][k][3] != -1:
                    x, y, w, h = cv2.boundingRect(cs[k])
                    holes.append((x + w / 2, y + h / 2))
        log.append((g, [b[0] for b in bs], holes, sp))
        return g
    AD._find_glyphs = spy
    raw = AD.annotate_accidentals.__wrapped__(res, ctx, notes) if hasattr(AD.annotate_accidentals, "__wrapped__") else None
    # annotate_accidentals는 실효를 돌려주므로 원시 판정은 log에서 다시 고른다 — 음표 순서대로 한 번씩 부른다
    log.clear()
    AD.annotate_accidentals(res, ctx, notes)
    AD._find_glyphs = orig
    if len(log) < len(notes):
        # 창이 좁아 _find_glyphs를 안 부른 음표가 있다 — 음표 ↔ 호출을 맞추려면 같은 조건을 다시 적용해야 해서, 호출 수만 기록
        pass
    # 정답
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        tn = [(n["x"], n["y"], n["accidental"] == "b", n["glyph"] in HOLLOW_V) for n in t["notes"]]
        sp0 = 18.0
    else:
        import measure_omission_rate as M
        from measure_normalize_sp import truth_at
        hs = truth_at(path, pg, 1.0)[0]
        sp0 = float(np.median([s.spacing for s in res.staves]))
        fl = [q for q in M.pdf_glyphs(path, pg, ("accidentals.",)) if q["name"].startswith("accidentals.flat") and "flatflat" not in q["name"]]
        tn = [(h["cx"], h["cy"], any(0 < h["cx"] - q["cx"] <= 3 * sp0 and abs(q["cy"] + 0.5 * sp0 - h["cy"]) <= 0.6 * sp0 for q in fl),
               h["name"] in ("noteheads.s1", "noteheads.s0")) for h in hs]
    rows = []
    # 호출과 음표를 잇기: 호출마다 ♭이 있으면 그 패치의 막대 · 고리 관계를 남기고, 음표는 같은 순서의 창 조건을 다시 계산해 짝짓는다
    staff_by = {s.index: s for s in res.staves}
    called = []
    for n in notes:
        s = staff_by.get(n.staff_index)
        if s is None:
            continue
        sp = s.spacing
        x1, x0 = int(n.x - sp * 0.55), int(n.x - sp * 2.0)
        if n.staff_index in ctx:
            x0 = max(x0, ctx[n.staff_index].header_end + int(sp * 0.2))
        if x1 - x0 < sp * 0.6:
            continue
        called.append(n)
    for n, (g, bxs, holes, sp) in zip(called, log):
        fb = [gy for k, gy in g if k == "b"]
        if not fb:
            continue
        # ♭으로 인정된 고리(높이가 음표에 가장 가까운 것)의 중심 x 기준, 왼쪽 0.05~1.0sp에 막대가 있나
        left = any(any(0.05 * sp <= hx - bx <= 1.0 * sp for bx in bxs) for hx, _hy in holes)
        ds = [(hx - bx) / sp for hx, _hy in holes for bx in bxs if hx - bx > 0]
        dl = round(min(ds), 2) if ds else None          # 고리 중심 − 가장 가까운 왼쪽 막대(sp)
        h = [q for q in tn if abs(q[0] - n.x) <= 0.7 * sp0 and abs(q[1] - n.y) <= 0.5 * sp0]
        rows.append(dict(set=st, page=name, x=int(n.x), y=int(n.y), left=left, dl=dl, truth_flat=(h[0][2] if h else None)))
    pairs = 0
    hol = [q for q in tn if q[3]]
    for i, a in enumerate(hol):
        for b in hol[i + 1:]:
            if abs(a[0] - b[0]) <= 1.5 * sp0 and 0.35 * sp0 <= abs(a[1] - b[1]) <= 0.65 * sp0:
                pairs += 1
    return rows, (st, name, pairs, len(called) == len(log))


def main():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")] + [("unseen", n, p, pg) for n, p, pg in G.UNSEEN if n != "organ2"]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    rows = [r for a, _b in res for r in a]
    meta = [b for _a, b in res]
    json.dump(dict(rows=rows, meta=meta), open(os.path.join(ROOT, "debug", "flat_bar_side.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("음표 ↔ 호출 짝 안 맞은 쪽", [m[1] for m in meta if not m[3]])
    for st in ("pdf", "unseen", "verovio"):
        v = [r for r in rows if r["set"] == st and r["truth_flat"] is not None]
        c = Counter((r["truth_flat"], r["left"]) for r in v)
        print(f"{st}: 원시 ♭ 판정 {len(v)} | 진짜 ♭ — 왼쪽 막대 있음 {c[(True, True)]} · 없음 {c[(True, False)]} | 가짜 ♭ — 있음 {c[(False, True)]} · 없음 {c[(False, False)]}")
    print("2도 빈 머리 쌍(정답):", {st: sum(m[2] for m in meta if m[0] == st) for st in ("pdf", "unseen", "verovio")})
    for r in rows:
        if r["page"].startswith("schubert_lindenbaum_piano_leipzig") and 600 < r["x"] < 650:
            print("  슈베르트", r)
    t = [r["dl"] for r in rows if r["truth_flat"]]
    f = [r["dl"] for r in rows if r["truth_flat"] is False]
    tv = np.array([d for d in t if d is not None])
    print(f"진짜 ♭ {len(t)} · 왼쪽 막대 없음 {sum(d is None for d in t)} · 거리 sp 최소 · 1 · 5 · 50 · 95 · 99 · 최대 " + " · ".join(f"{x:.2f}" for x in np.percentile(tv, [0, 1, 5, 50, 95, 99, 100])))
    print("Joplin 겹친 ♭", [r["dl"] for r in rows if r["page"] == "joplin_maple_leaf_bravura_p1" and r["x"] == 1524])
    for hi in (1.0, 1.2, 1.4, 1.6, 2.0):
        lo = 0.05
        print(f"  범위 {lo}~{hi}: 진짜 ♭ 잃음 {sum(d is None or not (lo <= d <= hi) for d in t)} · 가짜 ♭ 남음 {sum(d is not None and lo <= d <= hi for d in f)} / {len(f)}")


if __name__ == "__main__":
    main()
