# -*- coding: utf-8 -*-
"""A-17 결합안의 새 유령 6 원인 · 빈 머리 ♭ 오인 · 과적합 점검 · 「결합 + 유령 보정」 (2026-09-30, 제품 코드 무변경).

1. trace: 기준 `run_page`에서 `remove_accidental_ghosts`(main이 이름으로 가져온 것)를 가로채, 새 유령 6 자리를 지운 호출과
   방아쇠 음표(임시표가 붙은 오른쪽 음표 j: 0.5 ≤ xj − xi ≤ 1.6sp · |dy| ≤ 1.25sp — 제품 조건 그대로)를 기록.
   방아쇠 임시표가 원시 판정인지 전파인지는 같은 호출 직전 `annotate_accidentals`의 입력으로 원시 판정을 다시 내 가른다.
   가로챈 필터의 삭제 집합을 원본 반환값과 대조해 재계산이 제품과 같은지 확인한다(측정 함정 A-1).
2. 「결합 + 보정」 사본(c12fix) = 결합안(c12) + 아래 넷. 전부 가로채기 — 제품 파일은 안 바꾼다.
   G1 기울어진 빔: `verify.beam_mask`에 ±7.5~45° 선 커널 열림을 합친다(가로 2.5sp 직선만으로는 가파른 셋잇단 빔이 0).
      `drop_beam_ghosts`의 넓은 마스크(빔 위 · 빔 사이)에만 쓰인다 — 좁은 마스크(빔에 닿음)는 그대로
   G2 자기 글리프 유령: 속 빈 후보 자리(±0.8sp × ±2sp)에서 `_find_glyphs`가 ♯/♮ 쌍을 중심 0.5sp 안에 찾으면 지운다
      (`remove_accidental_ghosts` 뒤, 속 빈 후보만 — 채워진 후보는 제품처럼 건드리지 않는다)
   H1 ♭ 고리가 검출된 빈 머리(filled=False) 중심 0.5sp 안이면 ♭이 아니다(빈 머리 링 속)
   H2 ♭ 고리 양옆 0.95sp 안에 막대가 있고 그 막대들이 고리 중심 행을 덮으면 ♭이 아니다(♯/♮ 안쪽 칸)
   ♭ 판정은 제품 `_find_glyphs`의 ♭ 부분을 옮겨 쓰고, 보정을 끈 결과가 제품 ♭ 목록과 같은지 매 호출 대조한다(다르면 멈춤).
실행: python tools/measure_a17_ghost6.py trace | run <base|c12|c12fix> <pdf20|unseen|photo>
"""
import dataclasses
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import measure_a17_cand1 as T1  # noqa: E402
import measure_a17 as A  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402

GHOSTS = {"db3": [(1239, 1622), (1266, 1614), (1278, 1632), (1390, 1580), (636, 2858)], "em3": [(2059, 260)]}
ORIG_RAG = AD.remove_accidental_ghosts


def trace():
    pages = {n: (p, g) for n, p, g in T1.C.PAGES}
    out = []
    for name, targets in GHOSTS.items():
        path, pg = pages[name]
        calls = []
        last = {}

        def ann(result, contexts, notes):
            last["res"], last["ctx"] = result, contexts
            return T1.ORIG_ANN(result, contexts, notes)

        def rag(notes, accs, staves, filled=None, flagged=None):
            kept, kaccs = ORIG_RAG(notes, accs, staves, filled=filled, flagged=flagged)
            kept_ids = {id(n) for n in kept}
            raw = A.raw_judgments(last["res"], last["ctx"], notes) if "res" in last else [None] * len(notes)
            sp_of = {s.index: s.spacing for s in staves}
            glyphs = A.truth(path, pg, last["res"], last["ctx"])[0]
            rec = []
            for i, ni in enumerate(notes):
                if not any(abs(ni.x - tx) <= 3 and abs(ni.y - ty) <= 3 for tx, ty in targets):
                    continue
                sp = sp_of[ni.staff_index]
                trig = []
                for j, nj in enumerate(notes):
                    if j != i and accs[j] and nj.staff_index == ni.staff_index and \
                            sp * 0.5 <= nj.x - ni.x <= sp * 1.6 and abs(ni.y - nj.y) <= sp * AD.ACCIDENTAL_GHOST_Y_SP:
                        g = [q for q in glyphs if abs(q["hx"] - nj.x) <= 0.7 * sp and abs(q["hy"] - nj.y) <= 0.5 * sp]
                        trig.append(dict(x=nj.x, y=nj.y, pitch=f"{nj.note_name}{nj.octave}", eff=accs[j], raw=raw[j] or "",
                                         glyph=g[0]["kind"] if g else "", dx_sp=round((nj.x - ni.x) / sp, 2), dy_sp=round((nj.y - ni.y) / sp, 2)))
                rec.append(dict(x=ni.x, y=ni.y, pitch=f"{ni.note_name}{ni.octave}", filled=None if filled is None else bool(filled[i]),
                                dropped=id(ni) not in kept_ids, spared_flagged=flagged is not None and any(f is ni for f in flagged),
                                triggers=trig))
            calls.append(dict(call=len(calls) + 1, notes=len(notes), kept=len(kept), rec=rec))
            return kept, kaccs

        T1.MAIN.annotate_accidentals = ann
        T1.MAIN.remove_accidental_ghosts = rag
        sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", T1.tempfile.gettempdir(),
                    "--save-labels", os.path.join(T1.OUT, "trace.json")]
        try:
            T1.MAIN.run_page(T1.MAIN.parse_args(), os.path.join(ROOT, path), pg, T1.tempfile.gettempdir())
        finally:
            T1.MAIN.annotate_accidentals = T1.ORIG_ANN
            T1.MAIN.remove_accidental_ghosts = ORIG_RAG
        out.append(dict(page=name, calls=calls))
        for c in calls:
            for r in c["rec"]:
                print(name, "호출", c["call"], "(1=기존 · 2=chord_rescue)", r["x"], r["y"], r["pitch"], "filled", r["filled"],
                      "지워짐" if r["dropped"] else ("check로 남김" if r["spared_flagged"] else "남음"), flush=True)
                for t in r["triggers"]:
                    print("    방아쇠", t, flush=True)
    json.dump(out, open(os.path.join(ROOT, "debug", "a17_ghost6_trace.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ 결합 + 보정
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import measure_a17_cand12 as T  # noqa: E402
from modules import verify as V  # noqa: E402
from modules import notehead_detect as ND  # noqa: E402

FIX = dict(C12=True, G1=True, G2=True, G3=False, H1=True, H2=True, H3=False)
# G2 막대 길이 하한(sp): ♯/♮ 글리프 높이 표준 ≈2.5sp(accidental_detect 주석) · 두 머리가 쌓인 빈 머리 링 옆면 ≤ 2.0sp(E단조 2쪽 실측 1.81~2.02) 사이
G2_BAR_SP = 2.2
# G2 두 막대 사이 잉크 비율 상한: ♯/♮ 칸(가로획 두 줄, 실측 0.45) · 빽빽한 화음 덩어리(1.00) 사이. 글리프 표본 1개라 근거 약함 — G2 삭제 전부 눈 판정
G2_INNER_INK = 0.7
G2_HITS = []                   # G2가 지운 자리(페이지별로 run_set이 기록)
G3_KEPT = []                   # G3가 모양은 맞았지만 주인 음표가 없어 남긴 자리
STATS = T.STATS
ORIG_BEAM, ORIG_DETECT, ORIG_MAIN_DETECT = V.beam_mask, ND.detect_noteheads, T1.MAIN.detect_noteheads
PRODUCT_GLYPHS = AD._find_glyphs
HOLLOW = []                    # 이번 쪽에서 검출된 빈 머리(페이지 좌표) — 기존 머리 검출 결과
BAND_TOP = {}                  # 밴드 배열 주소 → 밴드 top(페이지 행)
LAST = {}


def sloped_beam_mask(binary, staves):
    base = ORIG_BEAM(binary, staves)
    sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
    no_staff = V.remove_staff_lines(binary, staves)
    L = max(3, int(sp * 2.5))
    thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
    out = base.copy()
    for deg in (7.5, 15, 22.5, 30, 37.5, 45, -7.5, -15, -22.5, -30, -37.5, -45):
        t = np.deg2rad(deg)
        dx, dy = L * np.cos(t) / 2, L * np.sin(t) / 2
        size = int(2 * max(abs(dx), abs(dy))) + 3
        k = np.zeros((size, size), np.uint8)
        c = size // 2
        cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        line = cv2.morphologyEx(no_staff, cv2.MORPH_OPEN, k)
        out |= cv2.morphologyEx(line, cv2.MORPH_OPEN, thick)
    STATS["G1 빔 마스크"] += 1
    return out


def detect_record(*a, **k):
    heads = ORIG_DETECT(*a, **k)
    HOLLOW.extend((h.x, h.y) for h in heads if not h.filled)
    return heads


class _Cv2Spy:
    """annotate_accidentals 안의 cv2 — 밴드(no_staff[top:bottom]의 뷰)를 닫힘한 결과 배열의 top을 기록한다."""
    def __getattr__(self, name):
        return getattr(cv2, name)

    def morphologyEx(self, src, op, k, *a, **kw):
        out = cv2.morphologyEx(src, op, k, *a, **kw)
        if src.base is not None and src.ndim == 2 and op == cv2.MORPH_CLOSE:
            off = src.__array_interface__["data"][0] - src.base.__array_interface__["data"][0]
            BAND_TOP[out.__array_interface__["data"][0]] = off // src.base.strides[0]
        return out


PROBE = None                   # h1probe가 켜면 list — 고리마다 왼쪽 막대의 쪽 전체 기준 위 · 아래 뻗음


def _bar_extent(cx, cy, ring_top, ring_bot, ring_left, sp, cols=None, tag=""):
    """고리 왼쪽 0.35sp 안 기둥 중 고리 중심 행을 지나는 가장 긴 세로 런 — 띠(patch)에 잘리지 않게 쪽 전체 no_staff(세로 닫힘)에서 잰다.
    ♭ 막대는 글리프 설계상 고리 아래끝에서 끝나고, 아래로 뻗는 기둥은 머리에서 ~3.5sp 내려간다(H1 em4 원인)."""
    res = LAST["res"]
    key = id(res)
    if LAST.get("ns_key") != key:
        ns = AD.remove_staff_lines(res.binary, res.staves)
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        LAST["ns"], LAST["ns_key"] = cv2.morphologyEx(ns, cv2.MORPH_CLOSE, vk), key
    ns = LAST["ns"]
    cyp, best = int(cy), None
    for col in (cols if cols is not None else range(max(0, int(ring_left - 0.35 * sp)), int(ring_left) + 1)):
        c = ns[:, col] > 0
        if not c[cyp]:
            continue
        a = cyp
        while a > 0 and c[a - 1]:
            a -= 1
        b = cyp
        while b + 1 < len(c) and c[b + 1]:
            b += 1
        if best is None or b - a > best[1] - best[0]:
            best = (a, b)
    out = dict(cx=round(cx), cy=round(cy), sp=sp)
    if best:
        out.update({tag + "above": round((ring_top - best[0]) / sp, 2), tag + "below": round((best[1] - ring_bot) / sp, 2),
                    tag + "run": round((best[1] - best[0]) / sp, 2)})
    return out


def _flats(patch, sp, top, c0, r0, excl):
    """제품 `_find_glyphs`의 ♭ 부분(막대 있으면 닫힘 3×3 → 안쪽 윤곽 0.25~0.9sp) + H1 · H2 제외."""
    bars = AD._find_thin_bars(patch, sp)
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
        x, y, w, h = cv2.boundingRect(contours[idx])
        if not (sp * 0.25 <= w <= sp * 0.9 and sp * 0.25 <= h <= sp * 0.9):
            continue
        if excl and FIX["H1"] and top is not None:
            cx, cy = c0 + x + w / 2, top + r0 + y + h / 2
            # 첫 판(빈 머리 자리면 무조건 제외)은 20쪽 ♭ 정답 171 → 13으로 무너뜨렸다 — ♭ 고리 자체가 머리 검출에서 빈 머리 후보로 잡힌다.
            # 구조로 가른다: 20쪽 PDF ♭ 777개는 100% 고리 왼쪽 0.35sp 안에 고리 중심 행을 지나는 막대(1.5~3.2sp)가 있고,
            # 빈 머리 링 속은 33%(49/147)만 그렇다 → 「빈 머리 자리 + 왼쪽 막대 없음」만 뺀다(♭ 표본에서는 한 번도 안 걸림)
            cyp = int(y + h / 2)
            left_bar = False
            for col in range(max(0, x - int(0.35 * sp)), x + 1):
                r_, s_, e_ = AD._max_run_and_extent(patch[:, col] > 0)
                if sp * 1.5 <= r_ <= sp * 3.2 and s_ <= cyp <= e_:
                    left_bar = True
                    break
            if PROBE is not None:
                rgt = c0 + x + w
                PROBE.append(_bar_extent(cx, cy, top + r0 + y, top + r0 + y + h, c0 + x, sp)
                             | _bar_extent(cx, cy, top + r0 + y, top + r0 + y + h, c0 + x, sp, range(int(rgt) - 1, int(rgt + 0.35 * sp) + 1), "r_")
                             | dict(w=round(w / sp, 2), h=round(h / sp, 2),
                    left_bar=left_bar, hollow=any(abs(hx - cx) <= 0.5 * sp and abs(hy - cy) <= 0.5 * sp for hx, hy in HOLLOW)))
            if not left_bar and any(abs(hx - cx) <= 0.5 * sp and abs(hy - cy) <= 0.5 * sp for hx, hy in HOLLOW):
                STATS["H1 빈 머리 고리 제외"] += 1
                continue
        if excl and FIX.get("H3"):
            # H3: 같은 창에서 제품 규칙으로 ♯ 쌍(간격 0.3~0.95sp · ♮ 어긋남 아님)이 된 두 막대 사이 · 겹친 높이 안의 고리는 ♯ 안쪽 칸.
            # em4 (1067,894) · em2 (1736,1314)의 가짜 ♭이 이것(2026-09-30 추적 — 「빈 머리 링 속」이라던 첫 기록은 틀림).
            # H2(아무 막대든 양옆)와 달리 ♯ 쌍이 된 막대만 본다
            rx, ry = x + w / 2, y + h / 2
            if any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95
                   and not (p_[1] + sp * 0.45 < q[1] and p_[2] + sp * 0.45 < q[2])
                   and p_[0] < rx < q[0] and max(p_[1], q[1]) <= ry <= min(p_[2], q[2])
                   for p_, q in zip(bars, bars[1:])):
                STATS["H3 ♯ 쌍 안쪽 칸 제외"] += 1
                continue
        if excl and FIX["H2"]:
            cyp = y + h / 2
            left = [b for b in bars if x - 0.95 * sp <= b[0] <= x + 1 and b[1] <= cyp <= b[2]]
            right = [b for b in bars if x + w - 1 <= b[0] <= x + w + 0.95 * sp and b[1] <= cyp <= b[2]]
            if left and right:
                STATS["H2 막대 사이 칸 제외"] += 1
                continue
        out.append(("b", y + h / 2.0))
    return out


def fixed_glyphs(patch, sp):
    """cand2가 부르는 「원래」 _find_glyphs 자리 — ♯/♮은 제품 그대로, ♭만 보정."""
    res = PRODUCT_GLYPHS(patch, sp)
    band = patch.base
    off = patch.__array_interface__["data"][0] - band.__array_interface__["data"][0]
    r0, c0 = divmod(off, band.strides[0])
    c0 //= band.strides[1]
    top = BAND_TOP.get(band.__array_interface__["data"][0])
    if top is None:
        STATS["밴드 top 모름"] += 1
    prod_b = [g for g in res if g[0] == "b"]
    mine = _flats(patch, sp, top, c0, r0, excl=False)
    if [round(g[1], 3) for g in mine] != [round(g[1], 3) for g in prod_b]:
        raise RuntimeError(f"♭ 재현 불일치: 제품 {prod_b} / 사본 {mine}")      # 측정 함정 A-1
    return [g for g in res if g[0] != "b"] + _flats(patch, sp, top, c0, r0, excl=True)


def c12fix_annotate(result, contexts, notes):
    LAST["res"] = result
    if not FIX.get("C12", True):
        return T1.ORIG_ANN(result, contexts, notes)          # 단독 평가: 판정은 제품 그대로, 유령 보정(G1 · G3)만 얹는다
    real = AD.cv2
    AD.cv2 = _Cv2Spy()
    keep = T.ORIG_GLYPHS
    T.ORIG_GLYPHS = fixed_glyphs
    try:
        return T.MODES["c12"](result, contexts, notes)
    finally:
        T.ORIG_GLYPHS = keep
        AD.cv2 = real
        BAND_TOP.clear()


def c12fix_rag(notes, accs, staves, filled=None, flagged=None):
    kept, kaccs = ORIG_RAG(notes, accs, staves, filled=filled, flagged=flagged)
    if not ((FIX["G2"] or FIX.get("G3")) and filled is not None and "res" in LAST):
        return kept, kaccs
    res = LAST["res"]
    no_staff = AD.remove_staff_lines(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in staves}
    fl = {id(n): f for n, f in zip(notes, filled)}
    out_n, out_a = [], []
    for n, a in zip(kept, kaccs):
        sp = sp_of.get(n.staff_index, 12.0)
        if not fl.get(id(n), True):
            y0, x0 = max(0, int(n.y - 2 * sp)), max(0, int(n.x - 0.8 * sp))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            band = cv2.morphologyEx(no_staff[y0:int(n.y + 2 * sp), :], cv2.MORPH_CLOSE, vk)
            patch = band[:, x0:int(n.x + 0.8 * sp)]
            # ♯/♮ 쌍: 이웃 막대 간격 0.3~0.95sp(제품 쌍 조건) · 두 막대 모두 ≥ G2_BAR_SP · 쌍 중심 y가 후보 0.5sp 안 ·
            # 후보 x가 두 막대 사이. 첫 판(제품 _find_glyphs 그대로)은 E단조 2쪽 (1782,1314) 진짜 2분음표를 지웠다 —
            # 2도로 쌓인 빈 머리 링 옆면이 1.8~2.0sp 막대 여럿이 되어 ♯ 쌍으로 잡혔다
            bars = AD._find_thin_bars(patch, sp)
            cx = n.x - x0
            # 둘째 판도 빗방울 4쪽 (372,1693) 진짜 C♯4 2분음표를 지웠다 — 빽빽한 화음 덩어리의 양 가장자리가 막대가 됐다.
            # ♯/♮ 칸 안쪽은 가로획 두 줄만 잉크(D♭ 3쪽 글리프 유령 0.45) · 덩어리는 가득(1.00) → 두 막대 사이 잉크 ≤ G2_INNER_INK
            def inner_ink(p_, q):
                r0_, r1_ = max(p_[1], q[1]), min(p_[2], q[2])
                c0_, c1_ = int(p_[0] + 0.15 * sp), int(q[0] - 0.15 * sp)
                return (patch[r0_:r1_ + 1, c0_:c1_ + 1] > 0).mean() if c1_ >= c0_ and r1_ >= r0_ else 1.0
            hit = any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95
                      and min(p_[2] - p_[1], q[2] - q[1]) + 1 >= G2_BAR_SP * sp
                      and abs(y0 + (p_[1] + p_[2] + q[1] + q[2]) / 4 - n.y) <= 0.5 * sp
                      and p_[0] - 0.1 * sp <= cx <= q[0] + 0.1 * sp
                      and inner_ink(p_, q) <= G2_INNER_INK
                      for p_, q in zip(bars, bars[1:]))
            if hit and FIX.get("G3"):
                # G3: 그 ♯/♮의 주인 음표가 오른쪽에 있어야 지운다(오른쪽 0.5~2.0sp · 세로 1sp 안의 다른 음표).
                # G2는 Aoharu 2쪽 (338,1305) 골든 C5(2도로 쌓인 빈 머리 + 왼쪽 기둥)를 지웠다 — 그 자리 오른쪽엔 음표가 없다.
                # 기준 유령 필터(remove_accidental_ghosts)가 가짜 임시표를 거쳐 잡던 「임시표 글리프 칸 = 유령」을 글리프 모양 + 주인 음표로 직접 본다
                hit = any(o is not n and o.staff_index == n.staff_index and 0.5 * sp <= o.x - n.x <= 2.0 * sp
                          and abs(o.y - n.y) <= 1.0 * sp for o in kept)
                if not hit:
                    STATS["G3 모양만 맞고 주인 음표 없어 남김"] += 1      # G3 경로가 실제로 돈다는 증거(골든 run_page 대조용)
                    G3_KEPT.append((n.x, n.y))
            if hit:
                G2_HITS.append((n.x, n.y))
                STATS["G2 자기 글리프 유령 제거" if not FIX.get("G3") else "G3 ♯ 칸 유령 제거"] += 1
                continue
        out_n.append(n)
        out_a.append(a)
    return out_n, out_a


# ---- A-18 세 방향 비교 (2026-09-30, 사용자 지시 — 막대 문턱 1.5 조정 금지) ----
# 바흐 회전 사진: 오선 아랫가장자리 잔여 + 앞 음표 머리를 세로 닫힘이 이어 1.59sp 가짜 막대 → 앞 기둥과 가짜 ♯(docs/A18_BACH_PHOTO.md)
A18_GAPS = []                  # CONT 탐침: 막대마다 닫힘 전 원 이진 영상의 최대 흰 틈(행)
ORIG_CAND2 = T.cand2_find_glyphs
ORIG_BARS_T = T.ORIG_BARS
ORIG_RSL_T1 = T1.ORIG_RSL


def _band_origin(p):
    band = p.base
    if band is None or band.ndim != 2:
        return None
    off = p.__array_interface__["data"][0] - band.__array_interface__["data"][0]
    r0, c0 = divmod(off, band.strides[0])
    return band, r0, c0 // band.strides[1]


def cand2_all_heads(patch, sp):
    """(a) 후보 2 쪽: 자기 머리 덩어리만이 아니라 창 안 **모든** 두꺼운 덩어리(열림 0.4sp 뒤 남는 머리 · 빔)를
    0.5sp 이상 지나가는 막대를 뺀다 — 가짜 막대 A는 앞 음표 머리 위에 있다."""
    o = _band_origin(patch)
    if o is None:
        return ORIG_CAND2(patch, sp)
    band, r0, c0 = o
    H, W = patch.shape
    hc = int(round(W + 0.55 * sp))
    local = band[r0:r0 + H, c0:min(band.shape[1], c0 + hc + int(0.8 * sp))]
    k = max(3, int(0.4 * sp)) | 1
    ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    blobs = cv2.dilate(cv2.morphologyEx((local > 0).astype(np.uint8), cv2.MORPH_OPEN, ell), ell, iterations=1)

    def bars_wo(p, s):
        out = []
        for b in T.ORIG_BARS(p, s):
            if blobs[b[1]:b[2] + 1, int(round(b[0]))].sum() >= T.OWN_ROWS_SP * s:
                STATS["A 머리 덩어리 막대 제외"] += 1
                continue
            out.append(b)
        return out

    AD._find_thin_bars = bars_wo
    try:
        return T.ORIG_GLYPHS(patch, sp)
    finally:
        AD._find_thin_bars = T.ORIG_BARS


def cont_bars(p, sp):
    """(c) 막대 연속성: 닫힘 전 원 이진 영상(오선 제거 전)에서 막대 구간의 **가장 긴 연속 잉크**가 제품 막대 하한(1.5sp, 그대로)을
    못 채우면 — 닫힘이 짧은 조각들을 이어 붙여 막대가 된 것 — 뺀다.
    첫 판(틈이 있으면 뺌)은 버렸다: 진짜 ♮ · ♯ 막대도 닫힘이 옆 잔여와 이어 붙여 원 이진 틈이 0.31~0.38sp(바흐 (1695,915) ♮ 등) —
    A-18 가짜 막대(0.38)와 같다. 진짜 막대는 몸통(~2.4sp)이 끊김 없이 남고, 가짜 막대는 잔여 4행 + 머리 ~1.0sp로 쪼개진다."""
    out = ORIG_BARS_T(p, sp)
    o = _band_origin(p)
    if o is None or "res" not in LAST:
        return out
    band, r0, c0 = o
    top = BAND_TOP.get(band.__array_interface__["data"][0])
    if top is None:
        return out
    binary = LAST["res"].binary
    keep = []
    for b in out:
        cx = c0 + int(round(b[0]))
        rows = (binary[top + r0 + b[1]:top + r0 + b[2] + 1, max(0, cx - 1):cx + 2] > 0).any(axis=1)
        gap, run, ink, irun = 0, 0, 0, 0
        for v in rows:
            run = 0 if v else run + 1
            irun = irun + 1 if v else 0
            gap, ink = max(gap, run), max(ink, irun)
        A18_GAPS.append((cx, top + r0 + b[1], top + r0 + b[2], gap, round(sp, 2), ink))
        if FIX.get("CONT") and ink < sp * 1.5:                   # 제품 _find_thin_bars 하한 그대로(바꾸지 않음)
            STATS["C 끊긴 막대 제외"] += 1
            continue
        keep.append(b)
    return keep


def rsl_resid(binary, staves):
    """(b) 오선 잔여: 오선 제거 뒤 각 오선 y ±0.15sp(선 두께) 띠 안의 잉크 중, 띠 바로 위 · 아래 행 둘 다 비어 있는 열은
    오선이 남긴 조각으로 보고 지운다(세로로 가로지르는 기호는 띠 밖으로 이어져 남는다). 임시표 밴드에만."""
    ns = ORIG_RSL_T1(binary, staves)
    out = ns.copy()
    Hh = ns.shape[0]
    for st in staves:
        h = max(1, int(np.ceil(st.spacing * 0.15)))
        for y in st.line_ys:
            y = int(round(y))
            if y - h - 1 < 0 or y + h + 1 >= Hh:
                continue
            lone = ~(ns[y - h - 1] > 0) & ~(ns[y + h + 1] > 0)
            cleared = out[y - h:y + h + 1][:, lone]
            STATS["B 오선 잔여 화소 지움"] += int((cleared > 0).sum())
            out[y - h:y + h + 1, lone] = 0
    return out


def install_a18():
    T.cand2_find_glyphs = cand2_all_heads if FIX.get("A2ALL") else ORIG_CAND2
    bars = cont_bars if (FIX.get("CONT") or FIX.get("CONT_PROBE")) else ORIG_BARS_T
    T.ORIG_BARS = AD._find_thin_bars = bars
    T1.ORIG_RSL = rsl_resid if FIX.get("RESID") else ORIG_RSL_T1


def install(fix=True):
    """c12fix 가로채기 설치/해제 — 판정 · 유령 제거 · 빔 마스크 · 머리 검출(빈 머리 기록)."""
    install_a18()
    if fix:
        V.beam_mask = sloped_beam_mask if FIX["G1"] else ORIG_BEAM
        ND.detect_noteheads = T1.MAIN.detect_noteheads = detect_record
        T1.MAIN.annotate_accidentals = AD.annotate_accidentals = c12fix_annotate
        T1.MAIN.remove_accidental_ghosts = c12fix_rag
    else:
        V.beam_mask = ORIG_BEAM
        ND.detect_noteheads, T1.MAIN.detect_noteheads = ORIG_DETECT, ORIG_MAIN_DETECT
        T1.MAIN.annotate_accidentals = AD.annotate_accidentals = T1.ORIG_ANN
        T1.MAIN.remove_accidental_ghosts = ORIG_RAG


UNSEEN_DIR = "output/unseen-scores-20260829/sources/"
UNSEEN = ([(f"moon{p + 1}", UNSEEN_DIR + "moonlight-a4.pdf", p) for p in (0, 1, 10, 17)]
          + [(f"rain{p + 1}", UNSEEN_DIR + "Chop-28-15-a4.pdf", p) for p in range(4)]
          + [("organ2", UNSEEN_DIR + "Ich_ruf_zu_dir2-a4.pdf", 1)])


def photo_pages():
    """사진 합성 세트 전부(M1이 거부하는 것은 run_page가 SystemExit으로 알려 준다 — 통과분만 남는다)."""
    import measure_normalize_sp as N
    out = []
    for d in (N.SYN, N.EDGE):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".png", ".jpg")):
                out.append((f"ph_{os.path.splitext(f)[0]}", os.path.relpath(os.path.join(d, f), ROOT), 0))
    return out


VARIANT_FIX = {"c12fix": dict(G1=True, G2=True, H1=True, H2=True),
               # G2는 Aoharu 2쪽 (338,1305) 골든 C5를 지웠고(오삭제 — 방향 기각), H2는 ♭ 고리 오른쪽 막대 때문에 진짜 ♭을 막았다 → 둘 뺀 판
               "c12g1h1": dict(G1=True, G2=False, H1=True, H2=False),
               # H1은 목표 2건(em4 · em2) 어느 것도 못 건드리고 틀린 칸끼리만 바꿨다 → 빼고 H3(♯ 쌍 안쪽 칸)
               "c12g1h3": dict(G1=True, G2=False, H1=False, H2=False, H3=True),
               "c12g13h3": dict(G1=True, G2=False, G3=True, H1=False, H2=False, H3=True),
               # 단독 평가(사용자 지시 2026-09-30): 제품 판정 + G1 / + G3, 결합안에서 G1 뺀 판(G3 뺀 판은 c12g1h3)
               "g1": dict(C12=False, G1=True, G2=False, G3=False, H1=False, H2=False, H3=False),
               "g3": dict(C12=False, G1=False, G2=False, G3=True, H1=False, H2=False, H3=False),
               "c12g3h3": dict(C12=True, G1=False, G2=False, G3=True, H1=False, H2=False, H3=True),
               # A-18 세 방향(2026-09-30): 결합안 c12 위에 하나씩 — (a) 후보 2 모든 머리 · (b) 오선 잔여 · (c) 막대 연속성, probe = (c) 기록만
               **{v: dict(C12=True, G1=False, G2=False, G3=False, H1=False, H2=False, H3=False,
                          A2ALL=v == "a18a", RESID=v == "a18b", CONT=v == "a18c", CONT_PROBE=v == "a18probe")
                  for v in ("a18a", "a18b", "a18c", "a18probe")}}


def set_variant(variant):
    if variant in VARIANT_FIX:
        FIX.update(VARIANT_FIX[variant])


def run_set(variant, which):
    """variant: base · c12 · c12fix, which: pdf20 · unseen · photo. JSON → debug/a17_cand1/<variant>_<which>/"""
    pages = {"pdf20": T1.C.PAGES, "unseen": UNSEEN, "photo": photo_pages()}[which]
    out = os.path.join(T1.OUT, f"{variant}_{which}")
    os.makedirs(out, exist_ok=True)
    for name, path, pg in pages:
        HOLLOW.clear()
        LAST.clear()
        G2_HITS.clear()
        A18_GAPS.clear()
        js = os.path.join(out, f"{name}.json")
        argv = [os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", T1.tempfile.gettempdir(),
                "--save-labels", js] + (["--photo"] if which == "photo" else [])
        sys.argv = ["main.py"] + argv
        args = T1.MAIN.parse_args()
        if variant in VARIANT_FIX:
            install(True)
        elif variant == "c12":
            T1.MAIN.annotate_accidentals = AD.annotate_accidentals = T.MODES["c12"]
        try:
            T1.MAIN.run_page(args, argv[0], pg, T1.tempfile.gettempdir())
            if G2_HITS:
                json.dump(sorted(set(G2_HITS)), open(os.path.join(out, f"{name}_g2.json"), "w", encoding="utf-8"))
            if FIX.get("CONT_PROBE"):
                json.dump(A18_GAPS, open(os.path.join(out, f"{name}_gaps.json"), "w", encoding="utf-8"))
            print(variant, name, "완료", dict(STATS), flush=True)
        except SystemExit:
            print(variant, name, "거부 · 실패", flush=True)
        finally:
            install(False)


SETS = {"pdf20": lambda: list(T1.C.PAGES), "unseen": lambda: list(UNSEEN), "photo": photo_pages}


def _hook_module(mod, variant):
    """골든 · 원시 행렬 도구가 이름으로 가져온 함수까지 같은 사본으로(측정 함정 B-4)."""
    saved = {k: getattr(mod, k) for k in ("annotate_accidentals", "remove_accidental_ghosts", "detect_noteheads") if hasattr(mod, k)}
    if variant in VARIANT_FIX:
        new = dict(annotate_accidentals=c12fix_annotate, remove_accidental_ghosts=c12fix_rag, detect_noteheads=detect_record)
    elif variant == "c12":
        new = dict(annotate_accidentals=T.MODES["c12"])
    else:
        new = {}
    for k, v in new.items():
        if k in saved:
            setattr(mod, k, v)
    return saved


def golden(variant):
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_golden_regression as GR
    if variant in VARIANT_FIX:
        install(True)
    saved = _hook_module(GR, variant)
    sys.argv = ["test_golden_regression.py"]
    try:
        GR.main()
    except SystemExit as e:
        print("골든 종료 코드", e.code)
    finally:
        for k, v in saved.items():
            setattr(GR, k, v)
        install(False)
    print("통계", dict(STATS))


def raw(variant, which):
    """A-17 원시 판정 행렬(measure_a17.run_all)을 이 사본 · 이 입력으로. c12fix는 음표 목록(유령 보정)도 사본으로 만든다."""
    pages = SETS[which]()
    keep_pages = list(T1.C.PAGES)
    T1.C.PAGES[:] = pages
    if variant in VARIANT_FIX:
        install(True)
    saved = _hook_module(T1.C, variant)
    AD.annotate_accidentals = c12fix_annotate if variant in VARIANT_FIX else {"c12": T.MODES["c12"]}.get(variant, T1.ORIG_ANN)
    orig_final = A.final_notes

    def final_notes(path, pg):
        HOLLOW.clear()
        LAST.clear()
        return orig_final(path, pg)

    A.final_notes = final_notes
    A.crops = lambda _w: None
    try:
        A.run_all()
    finally:
        A.final_notes = orig_final
        for k, v in saved.items():
            setattr(T1.C, k, v)
        install(False)
        T1.C.PAGES[:] = keep_pages
    os.replace(os.path.join(ROOT, "debug", "a17.json"), os.path.join(ROOT, "debug", f"a17_raw_{variant}_{which}.json"))
    print("통계", dict(STATS))


def compare(variant, which):
    keep = list(T1.C.PAGES)
    T1.C.PAGES[:] = SETS[which]()
    try:
        return T1.compare(cand=f"{variant}_{which}", out_json=f"diff_{variant}_{which}.json", base=f"base_{which}")
    finally:
        T1.C.PAGES[:] = keep


def golden_full(variant):
    """골든 711을 전체 파이프라인(run_page 라벨 JSON)으로 대조. 골든 테스트는 remove_accidental_ghosts에 filled를
    안 넘겨 G2처럼 filled에 기대는 보정을 한 번도 안 거친다(2026-09-30 발견 — c12fix가 골든 C5를 지웠는데 골든 통과)."""
    miss, wrong, n = [], [], 0
    for i in (1, 2, 3):
        labs = json.load(open(os.path.join(ROOT, "debug", "a17_cand1", f"{variant}_pdf20", f"aoharu{i}.json"), encoding="utf-8"))["labels"]
        for line in open(os.path.join(ROOT, "tests", "golden", f"aoharu_p{i}.tsv"), encoding="utf-8"):
            st, x, y, pitch, _acc, fixed, _mov = line.rstrip("\n").split("\t")
            n += 1
            hit = [l for l in labs if l["staff"] == int(st) and abs(l["x"] - int(x)) <= 2 and abs(l["y"] - int(y)) <= 2]
            if not hit:
                miss.append((f"aoharu{i}", x, y, pitch, fixed))
            elif not any(l["pitch"] == pitch and l["text"] == fixed for l in hit):
                wrong.append((f"aoharu{i}", x, y, pitch, fixed, [(l["pitch"], l["text"]) for l in hit]))
    print(variant, f"골든 {n} · 일치 {n - len(miss) - len(wrong)} · 라벨 없음 {len(miss)} · 다름 {len(wrong)}")
    for r in miss + wrong:
        print("  ", r)


def h1probe(which):
    """H1 후보 고리 전수: 쪽 전체 기준 왼쪽 막대 위 · 아래 뻗음을 PDF 정답(♭ 글리프 · 정답 빈 머리)으로 나눈다."""
    global PROBE
    import measure_omission_rate as M
    set_variant("c12g1h1")
    install(True)
    saved = _hook_module(T1.C, "c12g1h1")
    rows = []
    try:
        for name, path, pg in SETS[which]():
            if not path.endswith(".pdf"):
                continue
            HOLLOW.clear()
            LAST.clear()
            res, ctx, sp, notes, _src = A.final_notes(path, pg)
            PROBE = []
            A.raw_judgments(res, ctx, notes)
            g = M.pdf_glyphs(path, pg, ("accidentals.", "noteheads."))
            accs = [q for q in g if q["name"].startswith("accidentals.")]
            hollow = [q for q in g if q["name"].startswith("noteheads.s1") or q["name"].startswith("noteheads.s0")]
            for p_ in {(r["cx"], r["cy"]): r for r in PROBE}.values():
                s_ = p_["sp"]
                # 고리 중심이 글리프 상자(가로 ±0.8sp · 세로 ±1.5sp) 안이면 그 글리프 — 가장 가까운 것
                near = [q for q in accs if abs(q["cx"] - p_["cx"]) <= 0.8 * s_ and abs(q["cy"] - p_["cy"]) <= 1.5 * s_]
                ish = any(abs(q["cx"] - p_["cx"]) <= 0.5 * s_ and abs(q["cy"] - p_["cy"]) <= 0.5 * s_ for q in hollow)
                t = min(near, key=lambda q: abs(q["cx"] - p_["cx"]))["name"].split(".", 1)[1] if near else "hollow" if ish else "other"
                rows.append(dict(p_, page=name, truth=t))
            print(name, len(PROBE), flush=True)
    finally:
        PROBE = None
        for k, v in saved.items():
            setattr(T1.C, k, v)
        install(False)
    json.dump(rows, open(os.path.join(ROOT, "debug", f"h1probe_{which}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for t in sorted({r["truth"] for r in rows}):
        for key in ("below", "above", "r_below", "r_above"):
            v = sorted(r[key] for r in rows if r["truth"] == t and key in r)
            if v:
                q = lambda f: v[min(len(v) - 1, int(f * len(v)))]
                print(t, key, f"n={len(v)} min {v[0]} p5 {q(.05)} 중앙 {q(.5)} p95 {q(.95)} max {v[-1]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if len(sys.argv) > 2:
        set_variant(sys.argv[2])
    if cmd == "trace":
        trace()
    elif cmd == "run":
        run_set(sys.argv[2], sys.argv[3])
    elif cmd == "golden":
        golden(sys.argv[2])
    elif cmd == "raw":
        raw(sys.argv[2], sys.argv[3])
    elif cmd == "h1probe":
        h1probe(sys.argv[2])
    elif cmd == "goldenfull":
        golden_full(sys.argv[2])
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
