# -*- coding: utf-8 -*-
"""수정 ① 측정 — 오선 밖 머리의 덧줄 런이 렌더에 따라 얼마나 달라지나(`verify.drop_offstaff_ghosts` · `ledger_check`).
측정 전용 — 제품 코드 무변경. 근거 docs/RENDER_ROBUSTNESS.md §①.

    python tools/measure_ledger_render.py collect   # debug/ledger_render/rows.json
    python tools/measure_ledger_render.py           # 분포 요약

입력: PyMuPDF 49쪽(PDF 17 · 아오하루 골든 3 · 보지 않은 9 · Verovio 20) + PDF 17쪽의 PDFium 렌더 3가지
(300dpi AA 켬 · 315dpi 글자·선 끔 → 300 리샘플(#504) · 360dpi AA 켬 → 300 리샘플(#512)).
정답: PyMuPDF 판정(덧줄 있음 = 진짜 · 없음 = 유령, 두 악보 전 쪽 정밀도 100% · 오삭제 0으로 채택된 조건)을
같은 보표 6px 안 머리로 PDFium 렌더에 옮긴다. 짝 없는 머리는 「모름」.
특징(머리마다, 필요한 덧줄 중 가장 약한 것): 런(sp, 지금 판정과 같은 `ledger_run_sp`) · 그 줄의 세로 두께(px) ·
머리 폭(sp) · 런 − 머리 폭.
"""
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "ledger_render")


def inputs():
    from measure_render_robustness import PAGES, _render
    out = [("mupdf", t, os.path.join("test_scores", p), g) for t, p, g in PAGES]
    A = os.path.join("sample_images", "KakaoTalk_20260731_162400402")
    out += [("mupdf", f"aoharu{i + 1}", A + s + ".png", 0) for i, s in enumerate(["", "_01", "_02"])]
    U = os.path.join("output", "unseen-scores-20260829", "sources")
    out += [("mupdf", f"moon{p + 1}", os.path.join(U, "moonlight-a4.pdf"), p) for p in (0, 1, 10, 17)]
    out += [("mupdf", f"rain{p + 1}", os.path.join(U, "Chop-28-15-a4.pdf"), p) for p in range(4)]
    out += [("mupdf", "organ2", os.path.join(U, "Ich_ruf_zu_dir2-a4.pdf"), 1)]
    V = os.path.join(ROOT, "test_scores", "verovio")
    out += [("mupdf", f[:-4], os.path.join("test_scores", "verovio", f), 0) for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    for v in ("pdfium300_t1p1i1", "pdfium315_t0p0i1", "pdfium360_t1p1i1"):
        out += [(v, t, p, g) for t, p, g in PAGES]
    return out


def _thickness(binary, x, y, sp):
    """(x 주변 ±0.6sp 열에서) y를 지나는 가로 잉크 줄의 세로 두께 — 같은 열 묶음에 잉크가 이어지는 행 수."""
    h = binary.shape[0]
    x0, x1 = max(0, int(x - sp * 0.6)), int(x + sp * 0.6) + 1
    cols = binary[:, x0:x1] > 0
    row_ink = cols.mean(axis=1)
    if row_ink[y] < 0.5:
        return 0
    a = b = y
    while a > 0 and row_ink[a - 1] >= 0.5:
        a -= 1
    while b + 1 < h and row_ink[b + 1] >= 0.5:
        b += 1
    return b - a + 1


def _stem(no_staff, x, y, sp):
    """머리 행을 지나는 가장 긴 세로 잉크(sp)와 그 열의 머리 중심 대비 가로 거리(sp) — 좌우 ±0.9sp(`notehead_detect._has_stem`과 같은 창)."""
    H, W = no_staff.shape[:2]
    xa, xb = max(0, int(x - sp * 0.9)), min(W, int(x + sp * 0.9) + 1)
    y0, y1 = max(0, int(y - sp * 5)), min(H, int(y + sp * 5))
    sub = no_staff[y0:y1, xa:xb] > 0
    r = y - y0
    best = (0.0, 0.0)
    for c in range(sub.shape[1]):
        col = sub[:, c]
        if not (0 <= r < len(col)) or not col[r]:
            continue
        up = dn = r
        while up - 1 >= 0 and col[up - 1]:
            up -= 1
        while dn + 1 < len(col) and col[dn + 1]:
            dn += 1
        L = (dn - up + 1) / sp
        if L > best[0]:
            best = (L, (xa + c - x) / sp)
    return best


def collect():
    from measure_render_robustness import _render
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    from modules import verify as V
    rows = []
    tmp = os.path.join(OUT, "tmp")
    os.makedirs(tmp, exist_ok=True)
    for kind, tag, path, pg in inputs():
        if kind == "mupdf":
            full = os.path.join(ROOT, path)
            res = preprocess(full, pdf_page=pg) if full.endswith(".pdf") else preprocess(full)
        else:
            img = os.path.join(tmp, "page.png")
            open(img, "wb").write(cv2.imencode(".png", _render(kind, os.path.basename(path), pg))[1].tobytes())
            res = preprocess(img)
        ctx = analyze_staves(res)
        heads, _ = V.drop_beam_ghosts(res, detect_noteheads(res, contexts=ctx))
        ns = V.remove_staff_lines(res.binary, res.staves)
        st = {s.index: s for s in res.staves}
        for hd in heads:
            s = st.get(hd.staff_index)
            if s is None:
                continue
            need = V.needed_ledger_ys(s, int(hd.y))
            if need is None:
                continue
            sp = s.spacing
            weakest = None
            for w in need:
                best = (0.0, int(round(w)))
                for yy in range(int(w - sp * V.LEDGER_MATCH_SP), int(w + sp * V.LEDGER_MATCH_SP) + 1):
                    r = V.ledger_run_sp(res.binary, int(hd.x), yy, sp)
                    if r > best[0]:
                        best = (r, yy)
                th = _thickness(res.binary, int(hd.x), best[1], sp)
                if weakest is None or best[0] < weakest[0]:
                    weakest = (best[0], th, len(need))
            rows.append(dict(kind=kind, tag=tag, staff=hd.staff_index, x=int(hd.x), y=int(hd.y), filled=bool(hd.filled),
                             ok=bool(V.ledger_check(res.binary, s, int(hd.x), int(hd.y))), run=round(weakest[0], 3),
                             thick=int(weakest[1]), n_need=weakest[2], sp=round(sp, 2),
                             stem=[round(v, 2) for v in _stem(ns, int(hd.x), int(hd.y), sp)]))
        print(kind, tag, len(rows), flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, "rows.json"), "w", encoding="utf-8"))


def summary():
    rows = json.load(open(os.path.join(OUT, "rows.json"), encoding="utf-8"))
    base = defaultdict(list)
    for r in rows:
        if r["kind"] == "mupdf":
            base[(r["tag"], r["staff"])].append(r)
    for r in rows:
        if r["kind"] == "mupdf":
            r["truth"] = "진짜" if r["ok"] else "유령"
            continue
        m = [b for b in base[(r["tag"], r["staff"])] if abs(b["x"] - r["x"]) <= 6 and abs(b["y"] - r["y"]) <= 6]
        r["truth"] = ("진짜" if m[0]["ok"] else "유령") if m else "모름"
    by = defaultdict(list)
    for r in rows:
        by[(r["kind"], r["truth"])].append(r)
    q = lambda a, p: round(float(np.percentile(a, p)), 3) if a else None
    for (k, t), rs in sorted(by.items()):
        runs = [r["run"] for r in rs]
        print(f"{k:18s} {t} {len(rs):4d}  런 최소 {q(runs, 0)} · 5% {q(runs, 5)} · 중앙 {q(runs, 50)} · 95% {q(runs, 95)} · 최대 {q(runs, 100)}"
              f"  두께 중앙 {q([r['thick'] for r in rs], 50)}  지금 판정 통과 {sum(r['ok'] for r in rs)}")
    json.dump(rows, open(os.path.join(OUT, "rows_truth.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    collect() if sys.argv[1:] == ["collect"] else summary()
