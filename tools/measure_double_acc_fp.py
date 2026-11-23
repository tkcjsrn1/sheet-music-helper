# -*- coding: utf-8 -*-
"""겹임시표 헛검출 두 패턴 분석 (2026-10-18 밤 · 측정만, 제품 코드 무변경).

대상 = `debug/double_acc_kinds.json`(#388 측정)의 「직접」 검출 59(𝄪 16 · ♭♭ 43). 쪽마다 전처리만 다시 하고
`accidental_detect._double_acc_hits`와 **같은 창**(왼쪽 DOUBLE_ACC_LEFT_SP ~ −0.55sp · 위아래 2sp)을 만들어 특징을 잰다.
  𝄪: 검출된 ✕ 자리(열림 뒤 덩어리 중심)를 지나는 **열리기 전** 영상의 연결 성분 폭 · 높이(sp),
      그 자리 ±0.3sp 안 최장 가로 런 · 세로 런(sp) — 「앞 음 덧줄 끝 + 기둥」이면 성분이 길게 이어지거나 런이 길다
  ♭♭: 짝이 된 ♭ 구멍 둘 각각의 **오른쪽 벽** 세로 런(sp, 구멍 오른쪽 끝 + 1 ~ 3px 열, 구멍 중심 행을 지나는 연속 잉크) —
      ♮은 오른쪽이 곧은 긴 획, ♭은 짧은 곡선
격자: `debug/double_acc_fp/<종류>_<진짜|헛검출|유령>.png` (원본, 머리 중심 빨간 점)

    python tools/measure_double_acc_fp.py          (쪽마다 순서대로 — 워커 없음)
    python tools/measure_double_acc_fp.py report
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "double_acc_fp")


def _vrun(img, x, y):
    H, W = img.shape
    if not (0 <= x < W and 0 <= y < H) or not img[y, x]:
        return 0
    a = b = y
    while a > 0 and img[a - 1, x]:
        a -= 1
    while b < H - 1 and img[b + 1, x]:
        b += 1
    return b - a + 1


def _hrun(img, x, y):
    H, W = img.shape
    if not (0 <= x < W and 0 <= y < H) or not img[y, x]:
        return 0
    a = b = x
    while a > 0 and img[y, a - 1]:
        a -= 1
    while b < W - 1 and img[y, b + 1]:
        b += 1
    return b - a + 1


def _page(st, nm, path, pg, rows):
    import cv2
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    from modules import accidental_detect as AD
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    by = {s.index: s for s in res.staves}
    H = res.binary.shape[0]
    out = []
    for r in rows:
        s = by.get(r["staff"])
        if s is None:
            continue
        sp = s.spacing
        top = max(0, int(int(s.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
        bottom = min(H, int(int(s.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        band = cv2.morphologyEx(ns[top:bottom, :], cv2.MORPH_CLOSE, vk)
        x, y = r["x"], r["y"]
        x1, x0 = int(x - sp * 0.55), int(x - sp * 2.0)
        xe = int(x - sp * AD.DOUBLE_ACC_LEFT_SP)
        if s.index in ctx:
            x0 = max(x0, ctx[s.index].header_end + int(sp * 0.2))
            xe = max(xe, ctx[s.index].header_end + int(sp * 0.2))
        xe = min(max(0, xe), max(0, x0))
        py0 = max(0, int(y - top - sp * 2.0))
        py1 = min(band.shape[0], int(y - top + sp * 2.0))
        ep = band[py0:py1, xe:x1]
        ehp = ns[top + py0:top + py1, xe:x1]
        ny = y - top - py0
        f = dict(r, sp=round(sp, 2))
        if r["pred"] == "##":
            k = max(3, int(0.25 * sp)) | 1
            op = cv2.morphologyEx((ehp > 0).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            n, lab, stt, cen = cv2.connectedComponentsWithStats(op, connectivity=8)
            # 머리 높이 ±0.35sp · 머리 왼쪽 0.8 ~ 3.0sp 안 가장 큰 덩어리를 ✕ 자리로(두 경로 공통 근사)
            cand = [i for i in range(1, n) if abs(cen[i][1] - ny) <= 0.6 * sp and 0.8 * sp <= (x - xe) - cen[i][0] <= 3.0 * sp]
            if cand:
                i = max(cand, key=lambda i: stt[i][4])
                cx, cy = int(cen[i][0]), int(cen[i][1])
                raw = (ehp > 0).astype(np.uint8)
                m, lab2, st2, _c2 = cv2.connectedComponentsWithStats(raw, connectivity=8)
                j = lab2[cy, cx] if raw[cy, cx] else 0
                f.update(blob_w=round(stt[i][2] / sp, 2), blob_h=round(stt[i][3] / sp, 2),
                         comp_w=round(st2[j][2] / sp, 2) if j else 0.0, comp_h=round(st2[j][3] / sp, 2) if j else 0.0,
                         hrun=round(max(_hrun(raw, xx, yy) for yy in range(max(0, cy - int(0.3 * sp)), min(raw.shape[0], cy + int(0.3 * sp) + 1)) for xx in (cx,)) / sp, 2),
                         vrun=round(max(_vrun(raw, xx, cy) for xx in range(max(0, cx - int(0.3 * sp)), min(raw.shape[1], cx + int(0.3 * sp) + 1))) / sp, 2))
        else:
            bars = AD._find_thin_bars(ep, sp)
            hs = [(hx, hy) for hx, hy in AD._flat_holes_xy(ehp, sp, bars) if abs(hy - ny) <= 0.35 * sp]
            pairs = [(a, b) for k_, a in enumerate(hs) for b in hs[k_ + 1:] if 0.35 * sp <= abs(a[0] - b[0]) <= 1.2 * sp and max(a[0], b[0]) + xe >= x0]
            if pairs:
                a, b = pairs[0]
                raw = ehp > 0
                walls = []
                for hx, hy in (a, b):
                    hx, hy = int(hx), int(hy)
                    rx = hx
                    while rx < raw.shape[1] - 1 and not raw[hy, rx]:
                        rx += 1          # 구멍 중심에서 오른쪽 첫 잉크 = 오른쪽 벽
                    walls.append(max(_vrun(raw, xx, hy) for xx in range(rx, min(raw.shape[1], rx + 3))) / sp)
                f.update(wall_max=round(max(walls), 2), wall_min=round(min(walls), 2), pair_dx=round(abs(a[0] - b[0]) / sp, 2))
        # 원본 자르기(머리 기준 왼쪽 3.2sp ~ 오른쪽 0.8sp, 위아래 2sp)
        im = res.original_bgr
        c = im[max(0, int(y - 2 * sp)):int(y + 2 * sp), max(0, int(x - 3.2 * sp)):int(x + 0.8 * sp)].copy()
        cy0, cx0 = int(y) - max(0, int(y - 2 * sp)), int(x) - max(0, int(x - 3.2 * sp))
        cv2.circle(c, (cx0, cy0), 3, (0, 0, 255), -1)
        out.append((f, cv2.resize(c, (160, 160))))
    return out


def main():
    import cv2
    import measure_sim_ledger_pair as S
    P = json.load(open(os.path.join(ROOT, "debug", "double_acc_kinds.json"), encoding="utf-8"))
    pages = {p[1]: p for p in S.pages()}
    rows = defaultdict(list)
    for p in P:
        for r in p["rows"]:
            if r["src"] == "직접":
                rows[p["page"]].append(dict(r, page=p["page"], set=p["set"],
                                            cls="진짜" if r["pred"] == r["truth"] else "유령" if r["ghost"] else "헛검출"))
    os.makedirs(OUT, exist_ok=True)
    feats, tiles = [], defaultdict(list)
    for nm, rs in sorted(rows.items()):
        st, _n, path, pg = pages[nm]
        for f, t in _page(st, nm, path, pg, rs):
            cv2.putText(t, f"{nm[:10]} {f['x']}", (2, 12), 0, 0.35, (255, 0, 0), 1)
            feats.append(f)
            tiles[(f["pred"].replace("#", "s"), f["cls"])].append(t)
        print("쪽", nm, len(rs), flush=True)
    for (k, cls), ts in tiles.items():
        rows_ = [np.hstack(ts[i:i + 8] + [np.full_like(ts[0], 255)] * (8 - len(ts[i:i + 8]))) for i in range(0, len(ts), 8)]
        open(os.path.join(OUT, f"{k}_{cls}.png"), "wb").write(cv2.imencode(".png", np.vstack(rows_))[1].tobytes())
    json.dump(feats, open(os.path.join(OUT, "features.json"), "w", encoding="utf-8"), ensure_ascii=False)
    report(feats)


def report(F=None):
    F = F or json.load(open(os.path.join(OUT, "features.json"), encoding="utf-8"))
    for kind, keys in (("##", ("blob_w", "blob_h", "comp_w", "comp_h", "hrun", "vrun")), ("bb", ("wall_max", "wall_min", "pair_dx"))):
        print("==", kind)
        for k in keys:
            for cls in ("진짜", "헛검출", "유령"):
                v = sorted(f[k] for f in F if f["pred"] == kind and f["cls"] == cls and k in f)
                print(f"  {k:8s} {cls}: {v}")
        miss = [f for f in F if f["pred"] == kind and keys[0] not in f]
        print("  특징 못 잰 행:", [(f["page"], f["x"], f["y"], f["cls"]) for f in miss])
    for f in F:
        if f["cls"] == "헛검출":
            print("  헛검출", f["page"], f["x"], f["y"], {k: f[k] for k in f if k in ("blob_w", "comp_w", "comp_h", "hrun", "vrun", "wall_max", "wall_min")})


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
