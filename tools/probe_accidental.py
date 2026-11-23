# -*- coding: utf-8 -*-
"""(측정만, 2026-10-13 · TASKS M-1 · M-2) 한 쪽에서 지정 (x,y) 머리들의 임시표 원시 판정 과정을 찍는다. CROP=<폴더>면 확대 그림.
python tools/probe_accidental.py <악보> <pdf_page> x,y [x,y ...]"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from types import SimpleNamespace
from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
import modules.accidental_detect as A
from modules.notehead_detect import remove_staff_lines

path, pg = sys.argv[1], int(sys.argv[2])
pts = [tuple(float(v) for v in a.split(",")) for a in sys.argv[3:]]
res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
ctx = analyze_staves(res)
ns = remove_staff_lines(res.binary, res.staves)
refined = A._refined(res)
import cv2, numpy as np
H = res.binary.shape[0]
for x, y in pts:
    st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))
    sp = st.spacing
    top = max(0, int(int(st.top - A.WIDE_BAND_SP * sp) - sp * 3.5))
    bottom = min(H, int(int(st.bottom + A.WIDE_BAND_SP * sp) + sp * 3.5))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    band = cv2.morphologyEx(ns[top:bottom, :], cv2.MORPH_CLOSE, vk)
    x1, x0 = int(x - sp * 0.55), int(x - sp * 2.0)
    he = ctx[st.index].header_end + int(sp * 0.2) if st.index in ctx else None
    if he is not None:
        x0 = max(x0, he)
    y0, y1 = int(y - top - sp * 2.0), int(y - top + sp * 2.0)
    py0 = max(0, y0)
    patch = band[py0:min(band.shape[0], y1), max(0, x0):min(band.shape[1], x1)]
    allb = A._find_thin_bars(patch, sp)
    bars = A._bars_without_own_head(band, py0, max(0, x0), patch, sp) if refined else None
    g = A._find_glyphs(patch, sp, bars=bars, refined=refined)
    print(f"== 머리 ({x:.0f},{y:.0f}) 보표 {st.index} sp {sp:.2f} 창 x {max(0,x0)}~{x1} y {top+py0}~{top+py0+patch.shape[0]}")
    to_abs = lambda b: (round(max(0, x0) + b[0], 1), top + py0 + b[1], top + py0 + b[2], round((b[2]-b[1]+1)/sp, 2))
    print("   막대 전부 (x, 위끝, 아래끝, 길이sp):", [to_abs(b) for b in allb])
    print("   자기 머리 뺀 막대:", None if bars is None else [to_abs(b) for b in bars])
    for b1, b2 in zip(bars or allb, (bars or allb)[1:]):
        print(f"     쌍 간격 {(b2[0]-b1[0])/sp:.2f}sp · 위끝 차 {(b2[1]-b1[1])/sp:+.2f} · 아래끝 차 {(b2[2]-b1[2])/sp:+.2f} · 합 {((b2[1]-b1[1])+(b2[2]-b1[2]))/sp:+.2f} (♮ 문턱 {A.NATURAL_OFFSET_SUM_SP})")
    print("   글리프 (종류, 중심 y, |dy| sp):", [(k, top + py0 + gy, round(abs(top + py0 + gy - y) / sp, 2)) for k, gy in g])
    # 판정 재현
    best = ""
    for group in (("#", "natural"), ("b",)):
        c = [(abs(top + py0 + gy - y), k) for k, gy in g if k in group]
        if c:
            dy, k = min(c)
            if dy <= sp * A.ACCIDENTAL_Y_TOL_SP:
                best = k; break
    print("   → 원시 판정:", repr(best))
    if len(sys.argv) and os.environ.get("CROP"):
        img = cv2.cvtColor(res.binary, cv2.COLOR_GRAY2BGR) if res.binary.ndim == 2 else res.binary.copy()
        c = img[int(y - 3 * sp):int(y + 3 * sp), int(x - 3 * sp):int(x + 1.5 * sp)]
        c = cv2.resize(255 - c if c.mean() < 128 else c, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        out = os.path.join(os.environ["CROP"], f"crop_{int(x)}_{int(y)}.png")
        open(out, "wb").write(cv2.imencode(".png", c)[1].tobytes())
