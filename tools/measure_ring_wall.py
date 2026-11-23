# -*- coding: utf-8 -*-
"""(b) 「빈 음표 링의 좌우 벽」 필터 — 어느 구멍이 어느 꽉 찬 머리를 지웠나. 제품 코드 무변경.

`notehead_detect._detect_noteheads_in_band` 소스에 **기록 한 줄**(확정 구멍 · 지운 머리)만 끼운 사본을 같은 모듈 이름공간에서 실행한다.
매 쪽 사본과 원본의 검출 결과가 같은지 대조(다르면 멈춤 — 측정 함정 A-1).
정답: Verovio = SVG 머리(꽉 찬 · 빈), PDF = PDF 글리프 머리(noteheads.s2 꽉 찬 · s1/s0 빈).

    python tools/measure_ring_wall.py
"""
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


def install():
    import modules.notehead_detect as ND
    if getattr(ND, "RING_HOOK", None) is not None:
        return ND
    src = inspect.getsource(ND._detect_noteheads_in_band)
    key = '_log_drop(_before, raw, "빈 음표 링의 좌우 벽으로 판정되어 제거")'
    assert src.count(key) == 1
    src = src.replace(key, key + "\n        RING_HOOK.append(dict(staff=staff.index, top=top, holes=list(accepted_holes), "
                                 "dropped=[(it[0], it[1]) for it in _before if it not in raw]))")
    ND.RING_HOOK = []
    ND.ORIG_BAND = ND._detect_noteheads_in_band
    exec(compile(src, ND.__file__, "exec"), ND.__dict__)
    return ND


def _relation(ns, hx, hy0, hy1, cx, cy, sp):
    """구멍(빈 음표 후보)과 지워지는 꽉 찬 후보의 관계 — RING_WALL §4 · §5에서 기각된 구멍 단독 성질(경계 · 모양 · 폭)이 아니라 둘 사이.
    same = 오선 제거 영상에서 후보 중심(±2px 안 잉크)과 구멍 둘레 잉크가 한 8연결 덩어리인가(창 = 둘을 품는 상자 + 0.5sp)
    cross = 구멍 중심 행에서 구멍 중심 → 후보 중심 x로 갈 때 흰색 → 잉크 경계를 넘는 횟수(링 벽이면 1, 옆 머리면 기둥 · 틈을 지나 2 이상일 것)"""
    import cv2
    H, W = ns.shape
    x0, x1 = int(max(0, min(hx, cx) - 0.5 * sp)), int(min(W, max(hx, cx) + 0.5 * sp + 1))
    y0, y1 = int(max(0, min(hy0, cy) - 0.5 * sp)), int(min(H, max(hy1, cy) + 0.5 * sp + 1))
    win = ns[y0:y1, x0:x1].astype(np.uint8)
    n, lab = cv2.connectedComponents(win, connectivity=8)
    yy, xx = int(cy) - y0, int(cx) - x0
    cand = set(lab[max(0, yy - 2):yy + 3, max(0, xx - 2):xx + 3].ravel()) - {0}
    ring = set()
    hy = int((hy0 + hy1) / 2) - y0
    hxx = int(hx) - x0
    for dx in range(0, int(sp)):
        for sgn in (-1, 1):
            c = hxx + sgn * dx
            if 0 <= c < win.shape[1] and 0 <= hy < win.shape[0] and win[hy, c]:
                ring.add(lab[hy, c])
                break
    same = bool(cand & ring)
    row = ns[min(H - 1, max(0, int((hy0 + hy1) / 2))), :]
    a, b = sorted((int(hx), int(cx)))
    seg = row[a:b + 1].astype(np.int8)
    cross = int(((seg[1:] - seg[:-1]) == (1 if cx > hx else -1)).sum()) if len(seg) > 1 else 0
    return dict(same=same, cross=cross)


def _page(job):
    ND = install()
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    ND.RING_HOOK.clear()
    a = [(h.x, h.y, h.filled) for h in ND.detect_noteheads(res, contexts=ctx)]
    hooks = list(ND.RING_HOOK)
    patched = ND._detect_noteheads_in_band
    ND._detect_noteheads_in_band = ND.ORIG_BAND
    b = [(h.x, h.y, h.filled) for h in ND.detect_noteheads(res, contexts=ctx)]
    ND._detect_noteheads_in_band = patched
    if a != b:
        raise RuntimeError(f"사본 ≠ 원본 {name}")
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads = [(n["x"], n["y"], n["glyph"] not in ("E0A3", "E0A2", "E0A0")) for n in t["notes"]]
    else:
        from measure_normalize_sp import truth_at
        heads = [(h["cx"], h["cy"], h["name"] not in ("noteheads.s1", "noteheads.s0")) for h in truth_at(path, pg, 1.0)[0]]
    sp_of = {s.index: s.spacing for s in res.staves}
    from modules.notehead_detect import remove_staff_lines
    ns_bin = remove_staff_lines(res.binary, res.staves) > 0
    rows = []
    for hk in hooks:
        sp = sp_of[hk["staff"]]
        for dx_, dy_ in hk["dropped"]:
            dyabs = dy_ + hk["top"] if dy_ < hk["top"] else dy_            # raw 항목의 y는 이미 절대좌표
            near = [h for h in heads if abs(h[0] - dx_) <= 0.7 * sp and abs(h[1] - dyabs) <= 0.5 * sp]
            what = "꽉 찬 진짜 머리" if near and near[0][2] else "빈 머리 링 벽(맞게 지움)" if near else "머리 없음(유령 · 맞게 지움)"
            hole = min(hk["holes"], key=lambda h: abs(h[0] - dx_))
            hx, hy0, hy1 = hole
            hole_head = [h for h in heads if abs(h[0] - hx) <= 0.6 * sp and hy0 - 0.3 * sp <= h[1] <= hy1 + 0.3 * sp]
            rel = _relation(ns_bin, hx, hy0, hy1, dx_, dyabs, sp)
            rows.append(dict(set=kind, page=name, x=dx_, y=dyabs, what=what, sp=sp, **rel,
                             hole_dx=round((hx - dx_) / sp, 2), hole_h=round((hy1 - hy0) / sp, 2),
                             hole_is=("빈 머리" if hole_head and not hole_head[0][2] else "꽉 찬 머리 자리" if hole_head else "머리 없음")))
    return rows


def main():
    import check_accidental_fix as C
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0) for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_page, jobs) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "ring_wall.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st in ("pdf", "verovio"):
        v = [r for r in rows if r["set"] == st]
        for what in sorted({r["what"] for r in v}):
            w = [r for r in v if r["what"] == what]
            print(f"   [관계] {what}: 같은 덩어리 {sum(r['same'] for r in w)}/{len(w)} · 경계 넘기 수 {dict(Counter(min(r['cross'], 3) for r in w))}")
        print(st, "지운 꽉 찬 후보", len(v), dict(Counter(r["what"] for r in v)))
        for what in sorted({r["what"] for r in v}):
            w = [r for r in v if r["what"] == what]
            print(f"   {what}: 원인 구멍 = " + " · ".join(f"{k} {n}" for k, n in Counter(r["hole_is"] for r in w).most_common())
                  + f" | 구멍 가로 거리 sp 중앙 {np.median([abs(r['hole_dx']) for r in w]):.2f} · 구멍 높이 중앙 {np.median([r['hole_h'] for r in w]):.2f}")


if __name__ == "__main__":
    main()
