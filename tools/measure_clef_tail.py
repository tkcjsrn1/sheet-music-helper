# -*- coding: utf-8 -*-
"""[6] 높은음 / 낮은음 판별(「아래 꼬리 잉크 비율 > 0.06이면 높은음」, `clef_keysig._analyze_one`)이 왜 기우나 — 전 세트 분포. 제품 코드 무변경.

제품과 같은 계산: 오선 제거 영상 띠(오선 ±3sp) · 음자리표 칸(`clef_start ~ clef_end`, 최소 2.2sp — 제품이 쓰는 xe)에서
below = 아랫줄 + 0.4sp ~ + 2.5sp 행의 잉크, total = 칸 전체 잉크, ratio = below / total.
추가로 칸 잉크를 연결 성분으로 나눠 「아래 행에 걸린 성분이 음자리표 본체와 이어져 있나」(본체 = 가장 큰 성분)를 본다 — 칸 아래 다른 잉크(낮은 음표 · 덧줄 · 셈여림)가 섞이는지.
정답 종류: Verovio SVG 보표 첫 음자리표, PDF 글리프(clefs.G · F · C). `measure_alto_clef`와 같은 짝짓기.

    python tools/measure_clef_tail.py
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
    import cv2
    import measure_alto_clef as A
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves, CLEF_MIN_WIDTH_SP
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    staves = sorted(res.staves, key=lambda s: s.top)
    truth = A._page.__globals__["_truth_kinds"](kind, name, path, pg, res, staves) if "_truth_kinds" in A._page.__globals__ else None
    rows = []
    H = ns.shape[0]
    for i, st in enumerate(staves):
        c = ctx.get(st.index)
        if c is None or not c.clef_found:
            continue
        sp = st.spacing
        top = max(0, int(st.top - sp * 3))
        band = ns[top:min(H, int(st.bottom + sp * 3)), :]
        xe = max(c.clef_end, c.clef_start + int(sp * CLEF_MIN_WIDTH_SP))
        win = band[:, c.clef_start:xe] > 0
        total = int(win.sum())
        bl = st.bottom - top
        b0, b1 = int(bl + sp * 0.4), min(band.shape[0], int(bl + sp * 2.5))
        below = int(win[b0:b1, :].sum())
        n, lab, stats, _c = cv2.connectedComponentsWithStats(win.astype(np.uint8), connectivity=8)
        body = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) if n > 1 else 0
        below_body = int((win[b0:b1, :] & (lab[b0:b1, :] == body)).sum()) if body else 0
        rows.append(dict(set=kind, page=name, staff=st.index, order=i, read=c.clef, ratio=round(below / max(1, total), 3),
                         ratio_body=round(below_body / max(1, int((lab == body).sum())), 3) if body else None))
    return kind, name, path, pg, rows


def _truth_kinds(kind, name, path, pg, staves):
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [s["clefs"][0]["val"] if s["clefs"] else None for s in t["staves"]] if len(t["staves"]) == len(staves) else [None] * len(staves)
    import measure_omission_rate as M
    g = [q for q in M.pdf_glyphs(path, pg, ("clefs.",)) if "_change" not in q["name"]]
    out = []
    for st in staves:
        q = [q for q in g if st.top - 2 * st.spacing <= q["cy"] <= st.bottom + 2 * st.spacing and q["cx"] < 600]
        n = q[0]["name"].split(".")[1] if q else None
        out.append({"G": "treble", "F": "bass", "C": "alto"}.get(n[:1]) if n else None)
    return out


def _job(job):
    from modules.preprocess import preprocess
    kind, name, path, pg, rows = _page(job)
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    kinds = _truth_kinds(kind, name, path, pg, sorted(res.staves, key=lambda s: s.top))
    for r in rows:
        r["truth"] = kinds[r["order"]]
    return rows


def _notfound(job):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    st = sorted(res.staves, key=lambda s: s.top)
    kinds = _truth_kinds(kind, name, path, pg, st)
    return [(kind, name, i, kinds[i], ctx[s.index].clef, ctx[s.index].header_end) for i, s in enumerate(st) if s.index in ctx and not ctx[s.index].clef_found]


def _photo_nf(job):
    """사진 한 장 — 사진 모드 전처리에서 음자리표를 못 찾은 보표 수, 원본 쪽 같은 순번 보표의 음자리표(정답)와 기본값(높은음) 비교."""
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    name, path, src_path, src_pg = job
    try:
        res = preprocess(os.path.join(ROOT, path), photo=True)
    except Exception:
        return name, None
    ctx = analyze_staves(res)
    src = preprocess(os.path.join(ROOT, src_path), pdf_page=src_pg)
    sctx = analyze_staves(src)
    st, sst = sorted(res.staves, key=lambda s: s.top), sorted(src.staves, key=lambda s: s.top)
    out = []
    for i, s_ in enumerate(st):
        c = ctx.get(s_.index)
        if c is not None and not c.clef_found:
            truth = sctx[sst[i].index].clef if len(st) == len(sst) and sst[i].index in sctx else None
            out.append((i, truth, c.clef))
    return name, out


def photo_main():
    import measure_a17_ghost6 as G
    src = {"bach": ("test_scores/bach_minuet_Am.pdf", 0), "chopin_Db": ("test_scores/chopin_nocturne_Db_6-8.pdf", 0),
           "F_flat1": ("tests/fixtures/key_signatures/pdf/12_F_major_flat1.pdf", 0)}
    jobs = []
    for n, p, _pg in G.photo_pages():
        k = next(k for k in src if n.startswith("ph_" + k + "__"))
        jobs.append((n, p) + src[k])
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_photo_nf, jobs))
    ok = [r for r in res if r[1] is not None]
    nf = [(n, x) for n, xs in ok for x in xs]
    print(f"사진 {len(res)}장(사진 모드 통과 {len(ok)}) · 음자리표 못 찾은 보표 {len(nf)} · 그중 기본값(높은음)이 맞음 {sum(x[1] == x[2] for _n, x in nf)} · 틀림 {sum(x[1] is not None and x[1] != x[2] for _n, x in nf)}")
    for n, x in nf:
        print("   ", n, x)


def main():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")] + [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    jobs += [("fixture", f[:-4], os.path.join("tests", "fixtures", "key_signatures", "pdf", f), 0)
             for f in sorted(os.listdir(os.path.join(ROOT, "tests", "fixtures", "key_signatures", "pdf")))]
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_job, jobs) for r in part]
        nf = [r for part in ex.map(_notfound, jobs) for r in part]
    print(f"음자리표를 못 찾은 보표(기본값 높은음으로 읽힘) {len(nf)} · 정답 종류 {dict(Counter(r[3] for r in nf))}")
    for r in nf:
        print("   못 찾음", r)
    json.dump(rows, open(os.path.join(ROOT, "debug", "clef_tail.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for tv in ("treble", "bass"):
        v = [r for r in rows if r["truth"] == tv]
        a = np.array([r["ratio"] for r in v])
        b = np.array([r["ratio_body"] for r in v if r["ratio_body"] is not None])
        wrong = [r for r in v if r["read"] != tv]
        print(f"정답 {tv}: {len(v)} 보표 · 틀리게 읽음 {len(wrong)} | 비율 최소 · 5 · 50 · 95 · 최대 " + " · ".join(f"{x:.3f}" for x in np.percentile(a, [0, 5, 50, 95, 100]))
              + " | 본체만 " + " · ".join(f"{x:.3f}" for x in np.percentile(b, [0, 5, 50, 95, 100])))
        for r in wrong:
            print(f"   틀림 {r['set']} {r['page']} 보표 {r['order']} 읽음 {r['read']} 비율 {r['ratio']} 본체만 {r['ratio_body']}")


if __name__ == "__main__":
    photo_main() if sys.argv[1:] == ["photo"] else main()
