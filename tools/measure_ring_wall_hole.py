# -*- coding: utf-8 -*-
"""(b) 2단계 — 「구멍 위아래 경계가 오선 행과 겹치는가」로 가짜 빈 음표 구멍(머리 옆 오선 칸)을 가를 수 있나. 제품 코드 무변경.

`measure_ring_wall.install`과 같은 방식: `_detect_noteheads_in_band` 소스에 기록 한 줄만 끼운 사본(매 쪽 원본과 검출 결과 같음 확인).
확정된 구멍(`accepted_holes`, 빈 음표로 받아들인 것 전부)마다
  위 경계 거리 = 구멍 첫 흰 행 − 바로 위 오선 중심(px · sp), 아래 경계 거리 = 바로 아래 오선 중심 − 구멍 끝 행.
  (가짜 칸은 오선 두 줄이 곧 경계라 두 거리 모두 선 반두께 근처, 진짜 빈 머리는 링 두께만큼 오선에서 떨어진다는 가설)
분류: 진짜 빈 머리 = 정답 빈 머리(s1 · s0 / Verovio E0A3 · E0A2 · E0A0)가 구멍 x 0.6sp · 세로 범위 ±0.3sp 안, 그 밖 = 가짜.
세트: PDF 17쪽 · Verovio 20쪽 · 픽스처 PDF(조표 15 · 빔 1).

    python tools/measure_ring_wall_hole.py          # 경계 ↔ 오선 거리(기각, RING_WALL §4)
    python tools/measure_ring_wall_hole.py shape    # 구멍 모양(채움 비율 · 기울기 · 샘) — 위 결과 json을 다시 읽어 잰다(RING_WALL §5)
"""
import glob
import inspect
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
HOLLOW_VRV = ("E0A3", "E0A2", "E0A0")


def install():
    import modules.notehead_detect as ND
    if getattr(ND, "HOLE_HOOK", None) is not None:
        return ND
    src = inspect.getsource(ND._detect_noteheads_in_band)
    key = "    accepted_holes: List[tuple] = []\n"
    tail = "    # 빈 음표로 확정된 링의 좌/우 벽이"
    assert src.count(key) == 1 and src.count(tail) == 1
    src = src.replace(tail, "    HOLE_HOOK.append(dict(staff=staff.index, holes=list(accepted_holes), lines=list(staff.line_ys), sp=spacing))\n" + tail)
    ND.HOLE_HOOK = []
    ND.ORIG_BAND = ND._detect_noteheads_in_band
    exec(compile(src, ND.__file__, "exec"), ND.__dict__)
    return ND


def _page(job):
    ND = install()
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    ND.HOLE_HOOK.clear()
    a = [(h.x, h.y, h.filled) for h in ND.detect_noteheads(res, contexts=ctx)]
    hooks = list(ND.HOLE_HOOK)
    patched = ND._detect_noteheads_in_band
    ND._detect_noteheads_in_band = ND.ORIG_BAND
    b = [(h.x, h.y, h.filled) for h in ND.detect_noteheads(res, contexts=ctx)]
    ND._detect_noteheads_in_band = patched
    if a != b:
        raise RuntimeError(f"사본 ≠ 원본 {name}")
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        hollow = [(n["x"], n["y"]) for n in t["notes"] if n["glyph"] in HOLLOW_VRV]
        filled = [(n["x"], n["y"]) for n in t["notes"] if n["glyph"] not in HOLLOW_VRV]
    else:
        from measure_normalize_sp import truth_at
        hs = truth_at(path, pg, 1.0)[0]
        hollow = [(h["cx"], h["cy"]) for h in hs if h["name"] in ("noteheads.s1", "noteheads.s0")]
        filled = [(h["cx"], h["cy"]) for h in hs if h["name"] not in ("noteheads.s1", "noteheads.s0")]
    rows = []
    for hk in hooks:
        sp, lines = hk["sp"], sorted(hk["lines"])
        for hx, hy0, hy1 in hk["holes"]:
            above = [ly for ly in lines if ly <= hy0]
            below = [ly for ly in lines if ly >= hy1]
            real = any(abs(x - hx) <= 0.6 * sp and hy0 - 0.3 * sp <= y <= hy1 + 0.3 * sp for x, y in hollow)
            # 해로운 가짜 = 진짜 빈 머리가 아닌데 링 벽 창(가로 0.95sp · 세로 ±0.3sp, 제품과 같음) 안에 진짜 꽉 찬 머리가 있는 구멍
            harm = (not real) and any(abs(x - hx) <= 0.95 * sp and hy0 - 0.3 * sp <= y <= hy1 + 0.3 * sp for x, y in filled)
            rows.append(dict(set=kind, page=name, x=round(hx), y0=round(hy0), y1=round(hy1), sp=sp, real=real, harm=harm,
                             d_top=(hy0 - max(above)) if above else None, d_bot=(min(below) - hy1) if below else None,
                             h=(hy1 - hy0) / sp))
    return rows


def shape(ns, hx, hy0, hy1, sp):
    """구멍 중심에서 오선 제거 영상의 흰 영역을 채운다(상자 ±1.2sp 안). 채움 비율(면적 / 외접 상자) · 기울기(°, 2차 모멘트 주축) · 상자 밖으로 샘."""
    import cv2
    H, W = ns.shape
    cx, cy = int(round(hx)), int(round((hy0 + hy1) / 2))
    r = int(1.2 * sp)
    x0, y0 = max(0, cx - r), max(0, cy - r)
    win = (ns[y0:min(H, cy + r + 1), x0:min(W, cx + r + 1)] == 0).astype(np.uint8)
    if not (0 <= cy - y0 < win.shape[0] and 0 <= cx - x0 < win.shape[1]) or not win[cy - y0, cx - x0]:
        return dict(fill=None, tilt=None, leak=None)
    n, lab = cv2.connectedComponents(win, connectivity=4)
    comp = lab == lab[cy - y0, cx - x0]
    ys, xs = np.nonzero(comp)
    leak = bool(ys.min() == 0 or xs.min() == 0 or ys.max() == win.shape[0] - 1 or xs.max() == win.shape[1] - 1)
    fill = len(xs) / float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
    m = cv2.moments(comp.astype(np.uint8), binaryImage=True)
    tilt = 0.5 * np.degrees(np.arctan2(2 * m["mu11"], m["mu20"] - m["mu02"])) if m["m00"] else 0.0
    return dict(fill=round(fill, 3), tilt=round(abs(tilt), 1), leak=leak)


def main_shape():
    rows = json.load(open(os.path.join(ROOT, "debug", "ring_wall_hole.json"), encoding="utf-8"))
    from collections import defaultdict
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[(r["set"], r["page"])].append(i)
    with ProcessPoolExecutor(3) as ex:
        for part in ex.map(_shape_page, [(k, [rows[i] for i in v]) for k, v in by.items()]):
            for r in part:
                rows[r["_i"]] = r
    json.dump(rows, open(os.path.join(ROOT, "debug", "ring_wall_hole_shape.json"), "w", encoding="utf-8"), ensure_ascii=False)
    pct = lambda a, q: f"{np.percentile(a, q):.2f}" if len(a) else "-"
    for st in ("pdf", "verovio", "fixture"):
        for grp, f in (("진짜 빈 머리", lambda r: r["real"]), ("해로운 가짜", lambda r: r["harm"])):
            v = [r for r in rows if r["set"] == st and f(r) and r.get("fill") is not None]
            fl = [r["fill"] for r in v if not r["leak"]]
            tl = [r["tilt"] for r in v if not r["leak"]]
            print(f"{st:8s} {grp:7s} {len(v):4d} | 샘 {sum(r['leak'] for r in v)} | 채움 최소 {pct(fl, 0)} 5% {pct(fl, 5)} 중앙 {pct(fl, 50)} 95% {pct(fl, 95)} 최대 {pct(fl, 100)}"
                  f" | 기울기° 5% {pct(tl, 5)} 중앙 {pct(tl, 50)} 95% {pct(tl, 95)}")


def _shape_page(job):
    (kind, name), rs = job
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    import check_accidental_fix as C
    path = {"pdf": None}.get(kind)
    if kind == "verovio":
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", name + ".png"))
    elif kind == "pdf":
        p, pg = {n: (p, pg) for n, p, pg in C.PAGES}[name]
        res = preprocess(os.path.join(ROOT, p), pdf_page=pg)
    else:
        res = preprocess(os.path.join(ROOT, "tests", "fixtures", "key_signatures" if "_" in name and name[:2].isdigit() else "beams", "pdf", name + ".pdf"), pdf_page=0)
    ns = remove_staff_lines(res.binary, res.staves)
    out = []
    for r in rs:
        r = dict(r, **shape(ns, r["x"], r["y0"], r["y1"], r["sp"]))
        out.append(r)
    return out


def main():
    import check_accidental_fix as C
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0) for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    fx = sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "key_signatures", "pdf", "*.pdf"))) + \
        sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "beams", "pdf", "*.pdf")))
    jobs += [("fixture", os.path.basename(p)[:-4], os.path.relpath(p, ROOT), 0) for p in fx]
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_page, jobs) for r in part]
    for i, r in enumerate(rows):
        r["_i"] = i
    json.dump(rows, open(os.path.join(ROOT, "debug", "ring_wall_hole.json"), "w", encoding="utf-8"), ensure_ascii=False)
    pct = lambda a, q: f"{np.percentile(a, q):.2f}" if len(a) else "-"
    for st in ("pdf", "verovio", "fixture"):
        for grp, f in (("진짜 빈 머리", lambda r: r["real"]), ("해로운 가짜", lambda r: r["harm"])):
            v = [r for r in rows if r["set"] == st and f(r)]
            both = [r for r in v if r["d_top"] is not None and r["d_bot"] is not None]
            mx = np.array([max(r["d_top"], r["d_bot"]) / r["sp"] for r in both])
            mn = np.array([min(r["d_top"], r["d_bot"]) / r["sp"] for r in both])
            print(f"{st:8s} {grp:7s} {len(v):4d} | 오선 사이 {len(both)} · 먼 쪽 거리 sp 최소 {pct(mx, 0)} 5% {pct(mx, 5)} 중앙 {pct(mx, 50)} 95% {pct(mx, 95)} 최대 {pct(mx, 100)}"
                  f" · 가까운 쪽 중앙 {pct(mn, 50)} | 높이 sp 5% {pct([r['h'] for r in v], 5)} 중앙 {pct([r['h'] for r in v], 50)} 95% {pct([r['h'] for r in v], 95)}")


if __name__ == "__main__":
    main_shape() if sys.argv[1:] == ["shape"] else main()
