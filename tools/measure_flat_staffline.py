# -*- coding: utf-8 -*-
"""TASKS M-1 Clara 4 — 오선이 ♭ 고리를 지날 때 ♭을 놓치는가 (2026-10-15 · 측정만, 보류 세트 미사용).

(a) 비보류 정답 ♭ 전부(PDF 17 · 보지 않은 9 · Verovio 20): 붙는 머리 y가 오선 위(|머리 y − 오선 y| ≤ 0.25sp — ♭ 고리 중심 = 그 음 높이라
    오선이 고리 한가운데를 지난다)인지 칸인지 · 제품 원시 판정이 ♭을 읽었는지(제품과 같은 창 · 막대 · `_find_glyphs` · 고르기).
(b) 놓친 것마다 단계: 고리 구멍(♭ 조건 — 크기 0.25~0.9sp, 왼쪽 막대)이 ① 원본 이진 ② 오선 제거만(`remove_staff_lines`) ③ 오선 제거 + 세로 닫힘(제품 밴드)
    각각에서 찾히는가. 구멍 중심은 머리와 0.35sp 안이어야 한다.
(c) 후보 C1 = ♭ 구멍만 ② 「오선 제거만」 영상에서 찾음(막대 · ♯/♮은 그대로 ③) · C2 = ♭ 구멍만 ① 원본에서 — 후보로 원시 판정을 다시 낸다.

    python tools/measure_flat_staffline.py collect     → debug/flat_staffline.json
    python tools/measure_flat_staffline.py report
"""
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "flat_staffline.json")


def flat_holes(patch, sp, bars):
    """`_find_glyphs`의 ♭ 부분과 같은 계산 — (구멍 중심 y) 목록. H3(♯ 쌍 안쪽 칸 제외)도 같게."""
    import cv2
    from modules import accidental_detect as AD
    out = []
    if not bars:
        return out
    small = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    contours, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return out
    for idx in range(len(contours)):
        if hier[0][idx][3] == -1:
            continue
        _x, _y, hw, hh = cv2.boundingRect(contours[idx])
        if not (sp * 0.25 <= hw <= sp * 0.9 and sp * 0.25 <= hh <= sp * 0.9):
            continue
        if not any(AD.FLAT_BAR_LEFT_SP[0] * sp <= _x + hw / 2 - b[0] <= AD.FLAT_BAR_LEFT_SP[1] * sp for b in bars):
            continue
        rx, ry = _x + hw / 2, _y + hh / 2
        if any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95 and not (p_[1] + sp * 0.45 < q[1] and p_[2] + sp * 0.45 < q[2])
               and p_[0] < rx < q[0] and max(p_[1], q[1]) <= ry <= min(p_[2], q[2]) for p_, q in zip(bars, bars[1:])):
            continue
        out.append(_y + hh / 2.0)
    return out


def _pick(glyphs, gy0, y, sp):
    """제품 고르기 — ♯/♮ 먼저, 그다음 ♭, 머리와 0.35sp 안 가장 가까운 것."""
    from modules import accidental_detect as AD
    for group in (("#", "natural"), ("b",)):
        c = [(abs(gy0 + gy - y), k) for k, gy in glyphs if k in group]
        if c:
            dy, k = min(c)
            if dy <= sp * AD.ACCIDENTAL_Y_TOL_SP:
                return k
    return ""


def _job(job):
    import cv2
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    from modules import accidental_detect as AD
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        flats = [(h["x"], h["y"]) for h in t["notes"] if h["accidental"] == "b" and not h["grace"] and not h["cue"]]
    else:
        import measure_a17 as A
        g, _sk, _h = A.truth(path, pg, res, ctx)
        flats = [(q["hx"], q["hy"]) for q in g if q["kind"] == "b"]
    rows, bands = [], {}
    for hx, hy in flats:
        staff = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - hy))
        sp = staff.spacing
        if staff.index not in bands:
            top = max(0, int(int(staff.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(H, int(int(staff.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[staff.index] = (cv2.morphologyEx(ns[top:bottom, :], cv2.MORPH_CLOSE, vk), top, bottom)
        band, top, bottom = bands[staff.index]
        x1, x0 = int(hx - sp * 0.55), int(hx - sp * 2.0)
        if staff.index in ctx:
            x0 = max(x0, ctx[staff.index].header_end + int(sp * 0.2))
        if x1 - x0 < sp * 0.6:
            continue
        py0 = max(0, int(hy - top - sp * 2.0))
        py1 = min(band.shape[0], int(hy - top + sp * 2.0))
        c0 = max(0, x0)
        patch = band[py0:py1, c0:x1]
        if patch.size == 0:
            continue
        bars = AD._bars_without_own_head(band, py0, c0, patch, sp)
        if bars is None:
            bars = AD._find_thin_bars(patch, sp)
        glyphs = AD._find_glyphs(patch, sp, bars=bars, refined=True)
        gy0 = top + py0
        raw = _pick(glyphs, gy0, hy, sp)
        on_line = min(abs(hy - ly) for ly in staff.line_ys) <= 0.25 * sp
        p_ns = ns[top + py0:top + py1, c0:x1]
        p_bin = res.binary[top + py0:top + py1, c0:x1]
        near = lambda ys: any(abs(gy0 + y - hy) <= sp * AD.ACCIDENTAL_Y_TOL_SP for y in ys)
        hole = dict(binary=near(flat_holes(p_bin, sp, bars)), ns=near(flat_holes(p_ns, sp, bars)), band=near(flat_holes(patch, sp, bars)))
        nonflat = [(k, gy) for k, gy in glyphs if k != "b"]
        c1 = _pick(nonflat + [("b", y) for y in flat_holes(p_ns, sp, bars)], gy0, hy, sp)
        c2 = _pick(nonflat + [("b", y) for y in flat_holes(p_bin, sp, bars)], gy0, hy, sp)
        rows.append(dict(set=st, page=name, head=(round(hx), round(hy)), sp=sp, on_line=on_line, raw=raw, hole=hole, c1=c1, c2=c2))
    return rows


def collect():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    pages = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")] + [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    pages += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        rows = [r for part in ex.map(_job, pages) for r in part]
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("정답 ♭", len(rows))


def report():
    rows = json.load(open(OUT, encoding="utf-8"))
    for where in (True, False):
        R = [r for r in rows if r["on_line"] == where]
        miss = [r for r in R if r["raw"] != "b"]
        print(f"== {'오선 위(고리를 오선이 지남)' if where else '칸'}: ♭ {len(R)} · 지금 놓침 {len(miss)} ({len(miss) / max(1, len(R)) * 100:.1f}%) · 놓친 것의 원시 {dict(Counter(r['raw'] or '없음' for r in miss))}")
        print("   놓친 것의 구멍 단계(원본 · 오선 제거만 · + 세로 닫힘):", dict(Counter((r['hole']['binary'], r['hole']['ns'], r['hole']['band']) for r in miss)))
        for c in ("c1", "c2"):
            fix = sum(1 for r in R if r["raw"] != "b" and r[c] == "b")
            broke = sum(1 for r in R if r["raw"] == "b" and r[c] != "b")
            other = Counter((r["raw"] or "없음", r[c] or "없음") for r in R if r["raw"] != r[c] and "b" not in (r["raw"], r[c]))
            print(f"   후보 {c}: 놓침 → ♭ {fix} · ♭ → 다른 것 {broke} · 그 밖 바뀜 {dict(other)}")
    print("세트별 오선 위 놓침:", dict(Counter((r["set"], r["page"]) for r in rows if r["on_line"] and r["raw"] != "b")))


if __name__ == "__main__":
    {"collect": collect, "report": report}[sys.argv[1]]()
