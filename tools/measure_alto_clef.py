# -*- coding: utf-8 -*-
"""판단 2 — 알토(가온) 음자리표 검출: 머리 음자리표 검출 구간(`clef_start ~ clef_end`)의 잉크 세로 범위를 오선 기준으로. 제품 코드 무변경.

기보: 높은음자리표는 오선 위아래로 약 1.5sp 넘치고, 낮은음자리표는 윗줄 근처에서 시작해 아랫줄 위에서 끝나며(점 둘 포함),
알토(C) 음자리표는 윗줄에서 아랫줄까지 오선에 꼭 맞고 위아래 대칭이다.
top = (잉크 위끝 − 윗줄) / sp, bot = (잉크 아래끝 − 아랫줄) / sp. 정답 종류: Verovio SVG 보표 첫 음자리표, PDF 글리프(clefs.G · F · C).
`product`를 붙이면 제품 `clef_keysig.is_alto`(구현 뒤)로 표시 대상 · 헛표시를 센다.

    python tools/measure_alto_clef.py
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


def extent(ns, st, c):
    sp = st.spacing
    H = ns.shape[0]
    y0, y1 = max(0, int(st.top - 3 * sp)), min(H, int(st.bottom + 3 * sp))
    win = ns[y0:y1, c.clef_start:c.clef_end] > 0
    rows = np.where(win.any(axis=1))[0]
    if not len(rows):
        return None
    return round((y0 + rows[0] - st.top) / sp, 2), round((y0 + rows[-1] - st.bottom) / sp, 2)


def vrun(ns, st, c):
    """음자리표 칸 열마다 세로로 끊김 없이 이어진 잉크 길이의 최댓값(sp) — 알토는 왼쪽 굵은 획이 오선 높이(4sp) 전체를 관통한다."""
    sp = st.spacing
    win = ns[max(0, int(st.top - 3 * sp)):int(st.bottom + 3 * sp), c.clef_start:c.clef_end] > 0
    best = 0
    for col in win.T:
        run = cur = 0
        for v in col:
            cur = cur + 1 if v else 0
            run = max(run, cur)
        best = max(best, run)
    return round(best / sp, 2)


def _page(job):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    staves = sorted(res.staves, key=lambda s: s.top)
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        truth = [s["clefs"][0]["val"] if s["clefs"] else None for s in t["staves"]] if len(t["staves"]) == len(staves) else [None] * len(staves)
    else:
        import measure_omission_rate as M
        g = [q for q in M.pdf_glyphs(path, pg, ("clefs.",)) if "_change" not in q["name"]]
        truth = []
        for st in staves:
            q = [q for q in g if st.top - 2 * st.spacing <= q["cy"] <= st.bottom + 2 * st.spacing and q["cx"] < 600]
            n = q[0]["name"].split(".")[1] if q else None
            truth.append({"G": "treble", "F": "bass", "C": "alto"}.get(n[:1]) if n else None)
    rows = []
    for st, tv in zip(staves, truth):
        c = ctx.get(st.index)
        if c is None or not c.clef_found or c.clef_end <= c.clef_start:
            continue
        e = extent(ns, st, c)
        if e:
            alto = None
            if "product" in sys.argv:
                from modules.clef_keysig import is_alto
                alto = is_alto(ns, st, c)
            rows.append(dict(set=kind, page=name, staff=st.index, truth=tv, read=c.clef, top=e[0], bot=e[1], vrun=vrun(ns, st, c), alto=alto))
    return rows


def main():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")] + [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    jobs += [("fixture", f[:-4], os.path.join("tests", "fixtures", "key_signatures", "pdf", f), 0)
             for f in sorted(os.listdir(os.path.join(ROOT, "tests", "fixtures", "key_signatures", "pdf")))]
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_page, jobs) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "alto_clef.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for tv in ("treble", "bass", "alto3", "alto", None):
        v = [r for r in rows if r["truth"] == tv]
        if not v:
            continue
        p = lambda k: " · ".join(f"{np.percentile([r[k] for r in v], q):.2f}" for q in (0, 5, 50, 95, 100))
        print(f"정답 {tv}: {len(v)} 보표 · 읽음 {dict(Counter(r['read'] for r in v))} | top 최소 · 5 · 50 · 95 · 최대 {p('top')} | bot {p('bot')} | 세로 잉크 최장 {p('vrun')}")
    if "product" in sys.argv:
        for st in ("pdf", "unseen", "verovio", "fixture"):
            v = [r for r in rows if r["set"] == st]
            print(f"{st}: 알토로 봄 {sum(bool(r['alto']) for r in v)} · 그중 정답 알토 {sum(bool(r['alto']) and str(r['truth']).startswith('alto') for r in v)}"
                  f" · 정답 알토 {sum(str(r['truth']).startswith('alto') for r in v)}")


if __name__ == "__main__":
    main()
