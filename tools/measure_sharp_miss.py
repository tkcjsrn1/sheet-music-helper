# -*- coding: utf-8 -*-
"""[4] 인쇄된 ♯을 원시 판정이 못 읽는 단계 — PDF 17쪽(특히 D♭ 3 · 4쪽). 제품 코드 무변경.

정답 = `measure_a17.truth`(인쇄 임시표 글리프 → 붙는 머리 hx · hy · 글리프 중심 gx · gy). 대상 = 인쇄 ♯ 머리 전부.
제품과 같은 순서로 창(머리 x − 2sp ~ − 0.55sp, 헤더 끝 + 0.2sp 이상, y ± 2sp) · 막대(`_bars_without_own_head`) · 쌍 · ♮ 판정 · 높이 허용(0.35sp)을 따라가
처음 떨어지는 단계를 센다. 막대 단계에서 떨어지면 글리프 두 세로획 자리(gx ± 0.5sp 안 열)의 최장 런(sp) · 막대 폭(sp)을 함께 적는다.

    python tools/measure_sharp_miss.py
"""
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    import check_accidental_fix as C
    import measure_a17 as A
    import modules.accidental_detect as AD
    from modules.notehead_detect import remove_staff_lines
    name, path, pg = job
    res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = C.analyze_staves(res)
    glyphs = [g for g in A.truth(path, pg, res, ctx)[0] if g["kind"] == "#"]
    no_staff = remove_staff_lines(res.binary, res.staves)
    H = no_staff.shape[0]
    st_of = {s.index: s for s in res.staves}
    rows = []
    for g in glyphs:
        st = st_of[g["staff"]]
        sp = st.spacing
        top = max(0, int(int(st.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
        bottom = min(H, int(int(st.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        band = cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk)
        x1 = int(g["hx"] - sp * 0.55)
        x0 = int(g["hx"] - sp * 2.0)
        if g["staff"] in ctx:
            x0 = max(x0, ctx[g["staff"]].header_end + int(sp * 0.2))
        y0 = int(g["hy"] - top - sp * 2.0)
        py0 = max(0, y0)
        patch = band[py0:min(band.shape[0], int(g["hy"] - top + sp * 2.0)), max(0, x0):min(band.shape[1], x1)]
        rec = dict(page=name, hx=round(g["hx"]), hy=round(g["hy"]), gx_sp=round((g["hx"] - g["gx"]) / sp, 2))
        if not (x0 <= g["gx"] <= x1) or x1 - x0 < sp * 0.6 or patch.size == 0:
            rec["stage"] = "창 밖(글리프 중심이 머리 − 2sp ~ − 0.55sp 밖 또는 헤더)"
            rows.append(rec)
            continue
        bars = AD._bars_without_own_head(band, py0, max(0, x0), patch, sp)
        allbars = AD._find_thin_bars(patch, sp)
        if bars is None:
            bars = allbars
        allbars = AD._find_thin_bars(patch, sp)
        gxl = g["gx"] - max(0, x0)
        near = [b for b in bars if abs(b[0] - gxl) <= 0.6 * sp]
        found = AD._find_glyphs(patch, sp, bars=bars, refined=True)
        ok = [k for k, gy in found if k in ("#", "natural") and abs(top + py0 + gy - g["hy"]) <= sp * AD.ACCIDENTAL_Y_TOL_SP]
        if ok and ok[0] == "#":
            rec["stage"] = "원시는 ♯(뒤 단계에서 바뀜)"
        elif len(near) < 2:
            # 글리프 자리 열의 최장 런 · 막대 폭
            cols = [c for c in range(patch.shape[1]) if abs(c - gxl) <= 0.6 * sp]
            runs = [AD._max_run_and_extent(patch[:, c] > 0)[0] / sp for c in cols]
            rec["max_run_sp"] = round(max(runs), 2) if runs else None
            ab = [b for b in allbars if abs(b[0] - gxl) <= 0.6 * sp]
            rec["stage"] = ("막대 — 자기 머리 막대로 빠짐" if len(ab) >= 2
                            else "막대 — 런 > 3.2sp(빔 · 기둥과 이어짐)" if runs and max(runs) > 3.2
                            else "막대 — 런 < 1.5sp" if runs and max(runs) < 1.5 else "막대 — 폭 > 0.45sp(두 획이 붙음 등)")
        else:
            pair = [(a, b) for a, b in zip(near, near[1:]) if sp * 0.3 <= b[0] - a[0] <= sp * 0.95]
            if not pair:
                rec["stage"] = "쌍 간격 밖(0.3~0.95sp)"
                rec["gap_sp"] = round((near[1][0] - near[0][0]) / sp, 2)
            elif ok and ok[0] == "natural":
                rec["stage"] = "♮로 판정(어긋남 합 > 0.28sp)"
            else:
                rec["stage"] = "높이 차 > 0.35sp 또는 다른 후보"
        rows.append(rec)
    return rows


def main():
    import check_accidental_fix as C
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, C.PAGES) for r in part]
    print("인쇄 ♯", len(rows))
    for pg in (None, "db3", "db4"):
        sel = [r for r in rows if pg is None or r["page"] == pg]
        print(" ", pg or "전체", dict(Counter(r["stage"] for r in sel).most_common()))
    for r in rows:
        if r["page"] in ("db3", "db4") and not r["stage"].startswith("원시는"):
            print("   ", r)




def join():
    """표기 오판(measure_pdf_text_causes 「인쇄된 임시표 오판」) 행과 이 단계 표를 머리 좌표로 잇는다."""
    import check_accidental_fix as C
    import json
    with ProcessPoolExecutor(2) as ex:
        stages = [r for part in ex.map(_page, C.PAGES) for r in part]
    bad = [r for r in json.load(open(os.path.join(ROOT, "debug", "pdf_text_causes.json"), encoding="utf-8")) if r["cause"] == "인쇄된 임시표 오판"]
    c = Counter()
    for b in bad:
        s = [r for r in stages if r["page"] == b["page"] and abs(r["hx"] - b["x"]) <= 3 and abs(r["hy"] - b["y"]) <= 3]
        k = (f"{b['got'] or '-'} → {b['eff'] or '-'}", s[0]["stage"] if s else "인쇄 ♯ 아님(♭ · ♮)")
        c[k] += 1
    for k, n in c.most_common():
        print("  ", k, n)




def _wide(job):
    """정답 머리마다 제품 순서로 원시 임시표를 창 왼끝 −2.0sp(지금) · −3.8sp(넓힘)로 읽어 정답 인쇄 임시표와 비교. 창 밖 ♯은 멀리 찍힌 까닭도."""
    import check_accidental_fix as C
    import measure_a17 as A
    import modules.accidental_detect as AD
    from modules.notehead_detect import remove_staff_lines
    name, path, pg = job
    res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = C.analyze_staves(res)
    glyphs, _sk, heads = A.truth(path, pg, res, ctx)
    own = {(round(g["hx"]), round(g["hy"])): g for g in glyphs}
    no_staff = remove_staff_lines(res.binary, res.staves)
    H = no_staff.shape[0]
    bands = {}
    c = Counter()
    why = []
    for h in heads:
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - h["cy"]))
        sp = st.spacing
        if st.index not in bands:
            top = max(0, int(int(st.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(H, int(int(st.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[st.index] = (cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk), top)
        band, top = bands[st.index]
        got = {}
        for left in (2.0, 3.8):
            x1, x0 = int(h["cx"] - sp * 0.55), int(h["cx"] - sp * left)
            if st.index in ctx:
                x0 = max(x0, ctx[st.index].header_end + int(sp * 0.2))
            py0 = max(0, int(h["cy"] - top - sp * 2.0))
            patch = band[py0:min(band.shape[0], int(h["cy"] - top + sp * 2.0)), max(0, x0):min(band.shape[1], x1)]
            best = ""
            if x1 - x0 >= sp * 0.6 and patch.size:
                bars = AD._bars_without_own_head(band, py0, max(0, x0), patch, sp)
                gl = AD._find_glyphs(patch, sp, bars=bars, refined=True)
                for group in (("#", "natural"), ("b",)):
                    cands = [(abs(top + py0 + gy - h["cy"]), k) for k, gy in gl if k in group]
                    if cands and min(cands)[0] <= sp * AD.ACCIDENTAL_Y_TOL_SP:
                        best = min(cands)[1]
                        break
            got[left] = best
        g = own.get((round(h["cx"]), round(h["cy"])))
        truth = {"#": "#", "b": "b", "natural": "natural"}.get(g["kind"], "") if g else ""
        if got[2.0] == got[3.8]:
            continue
        k = ("고침" if got[3.8] == truth else "새로 틀림 · 없는 임시표" if not truth else "새로 틀림 · 종류") if got[2.0] != truth else "망침"
        c[k] += 1
        if g and got[2.0] != truth and truth == "#":
            # 멀리 찍힌 까닭: 머리와 글리프 사이 다른 임시표 글리프 · 같은 기둥 왼쪽으로 밀린 머리
            between = [o for o in glyphs if o is not g and g["gx"] < o["gx"] < h["cx"] and abs(o["gy"] - g["gy"]) <= 3 * sp]
            lefthead = [q for q in heads if q is not h and h["cx"] - 1.5 * sp < q["cx"] < h["cx"] - 0.5 * sp and abs(q["cy"] - h["cy"]) <= 1.5 * sp]
            why.append("사이에 다른 임시표" if between else "왼쪽에 밀린 머리(2도 화음)" if lefthead else "기타")
    return c, why


def wide():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(2) as ex:
        pdf = list(ex.map(_wide, C.PAGES))
        un = list(ex.map(_wide, [u for u in G.UNSEEN if u[0] != "organ2"]))
    for tag, rs in (("PDF 17", pdf), ("보지 않은 8", un)):
        t, w = Counter(), Counter()
        for c, why in rs:
            t.update(c)
            w.update(why)
        print(tag, "창 −3.8sp로 바뀐 머리:", dict(t), "| 고친 ♯이 멀리 찍힌 까닭:", dict(w))




def _read(band, top, ctx, st, hx, hy, left, sp):
    """제품 순서 원시 임시표 — (자기 높이 결과, 창 안 모든 글리프)."""
    import modules.accidental_detect as AD
    x1, x0 = int(hx - sp * 0.55), int(hx - sp * left)
    if st.index in ctx:
        x0 = max(x0, ctx[st.index].header_end + int(sp * 0.2))
    py0 = max(0, int(hy - top - sp * 2.0))
    patch = band[py0:min(band.shape[0], int(hy - top + sp * 2.0)), max(0, x0):min(band.shape[1], x1)]
    if x1 - x0 < sp * 0.6 or not patch.size:
        return "", []
    bars = AD._bars_without_own_head(band, py0, max(0, x0), patch, sp)
    gl = AD._find_glyphs(patch, sp, bars=bars, refined=True)
    for group in (("#", "natural"), ("b",)):
        cands = [(abs(top + py0 + gy - hy), k) for k, gy in gl if k in group]
        if cands and min(cands)[0] <= sp * AD.ACCIDENTAL_Y_TOL_SP:
            return min(cands)[1], gl
    return "", gl


def _chain(job):
    """임시표 열 탐색: −2.0sp 창에 다른 높이 글리프가 인정됐는데 자기 높이가 비면 1.2sp씩 최대 3칸 왼쪽으로 넓혀 다시 읽는다."""
    import check_accidental_fix as C
    import modules.accidental_detect as AD
    from modules.notehead_detect import remove_staff_lines
    st_, name, path, pg = job
    if st_ == "verovio":
        import json
        from modules.preprocess import preprocess
        from modules.clef_keysig import analyze_staves
        res = preprocess(os.path.join(ROOT, path))
        ctx = analyze_staves(res)
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        acc = {"s": "#", "f": "b", "n": "natural", "ss": "#", "ff": "b", "x": "#"}
        heads = [(n["x"], n["y"], acc.get(n["accid_raw"] or "", "")) for n in t["notes"] if not (n.get("grace") or n.get("cue"))]
    else:
        import measure_a17 as A
        res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = C.analyze_staves(res)
        glyphs, _sk, hs = A.truth(path, pg, res, ctx)
        own = {(round(g["hx"]), round(g["hy"])): g["kind"] for g in glyphs}
        heads = [(h["cx"], h["cy"], {"#": "#", "b": "b", "natural": "natural"}.get(own.get((round(h["cx"]), round(h["cy"]))), "")) for h in hs]
    no_staff = remove_staff_lines(res.binary, res.staves)
    H = no_staff.shape[0]
    bands = {}
    c = Counter()
    for hx, hy, truth in heads:
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - hy))
        sp = st.spacing
        if st.index not in bands:
            top = max(0, int(int(st.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(H, int(int(st.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[st.index] = (cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk), top)
        band, top = bands[st.index]
        base, gl = _read(band, top, ctx, st, hx, hy, 2.0, sp)
        new = base
        if not base and gl:
            for k in range(1, 4):
                new, gl2 = _read(band, top, ctx, st, hx, hy, 2.0 + 1.2 * k, sp)
                if new:
                    break
        if new == base:
            continue
        c["고침" if new == truth else "망침" if base == truth else "새로 틀림 · 없는 임시표" if not truth else "새로 틀림 · 종류"] += 1
    return st_, c


def chain():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        rs = list(ex.map(_chain, [p for p in S.pages() if p[0] in ("pdf", "unseen", "verovio") and p[1] != "organ2"]))
    for st in ("pdf", "unseen", "verovio"):
        t = Counter()
        for s, c in rs:
            if s == st:
                t.update(c)
        print(st, "임시표 열 탐색으로 바뀐 머리:", dict(t))




def _read_fix(band, top, ctx, st, hx, hy, sp, mode):
    """수정안 사본: ① 창 왼끝에 걸린 막대(중심 ≤ 0.25sp)를 빼고 다시 읽어 ♯ · ♮이 달라지면 「종류 미정」(""),
    ② ♭인데 그 ♭ 막대 오른쪽 0.4~1.0sp에 길이 ≥ 1.5sp 막대가 같은 높이에 또 있으면 ♭ 아님("")."""
    import modules.accidental_detect as AD
    base, gl = _read(band, top, ctx, st, hx, hy, 2.0, sp)
    x1, x0 = int(hx - sp * 0.55), int(hx - sp * 2.0)
    if st.index in ctx:
        x0 = max(x0, ctx[st.index].header_end + int(sp * 0.2))
    py0 = max(0, int(hy - top - sp * 2.0))
    patch = band[py0:min(band.shape[0], int(hy - top + sp * 2.0)), max(0, x0):min(band.shape[1], x1)]
    if not base or x1 - x0 < sp * 0.6 or not patch.size:
        return base
    bars = AD._bars_without_own_head(band, py0, max(0, x0), patch, sp)
    if bars is None:
        bars = AD._find_thin_bars(patch, sp)
    yrel = hy - top - py0
    if mode == 1 and base in ("#", "natural") and any(b[0] <= 0.25 * sp for b in bars):
        rest = [b for b in bars if b[0] > 0.25 * sp]
        gl2 = AD._find_glyphs(patch, sp, bars=rest, refined=True)
        c2 = [(abs(gy - yrel), k) for k, gy in gl2 if k in ("#", "natural")]
        if not (c2 and min(c2)[0] <= sp * AD.ACCIDENTAL_Y_TOL_SP and min(c2)[1] == base):
            return ""
    if mode == 2 and base == "b":
        own = [b for b in bars if b[1] - 0.3 * sp <= yrel <= b[2] + 0.3 * sp]
        for b in own:
            if any(0.4 * sp <= o[0] - b[0] <= 1.0 * sp and o[2] - o[1] >= 1.5 * sp and min(o[2], b[2]) - max(o[1], b[1]) > 0.5 * sp for o in bars):
                return ""
    return base


def _fix(job):
    """정답 머리마다 지금 원시 판정과 수정안 ① · ② 사본 결과 비교 — 고침 / 망침 / 새로 틀림."""
    import modules.accidental_detect as AD
    from modules.notehead_detect import remove_staff_lines
    st_, name, path, pg = job
    if st_ == "verovio":
        import json
        from modules.preprocess import preprocess
        from modules.clef_keysig import analyze_staves
        res = preprocess(os.path.join(ROOT, path))
        ctx = analyze_staves(res)
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        acc = {"s": "#", "f": "b", "n": "natural", "ss": "#", "ff": "b", "x": "#"}
        heads = [(n["x"], n["y"], acc.get(n["accid_raw"] or "", "")) for n in t["notes"] if not (n.get("grace") or n.get("cue"))]
    else:
        import check_accidental_fix as C
        import measure_a17 as A
        res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = C.analyze_staves(res)
        glyphs, _sk, hs = A.truth(path, pg, res, ctx)
        own = {(round(g["hx"]), round(g["hy"])): g["kind"] for g in glyphs}
        heads = [(h["cx"], h["cy"], {"#": "#", "b": "b", "natural": "natural"}.get(own.get((round(h["cx"]), round(h["cy"]))), "")) for h in hs]
    no_staff = remove_staff_lines(res.binary, res.staves)
    H = no_staff.shape[0]
    bands = {}
    c = Counter()
    for hx, hy, truth in heads:
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - hy))
        sp = st.spacing
        if st.index not in bands:
            top = max(0, int(int(st.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(H, int(int(st.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[st.index] = (cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk), top)
        band, top = bands[st.index]
        base = _read(band, top, ctx, st, hx, hy, 2.0, sp)[0]
        for mode in (1, 2):
            new = _read_fix(band, top, ctx, st, hx, hy, sp, mode)
            if new == base:
                continue
            c[(mode, "고침" if new == truth else "망침" if base == truth else "새로 틀림(틀림→다른 틀림)")] += 1
    return st_, c


def fix():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        rs = list(ex.map(_fix, [p for p in S.pages() if p[0] in ("pdf", "unseen", "verovio") and p[1] != "organ2"]))
    for mode in (1, 2):
        for st in ("pdf", "unseen", "verovio"):
            t = Counter()
            for s, c in rs:
                if s == st:
                    t.update({k[1]: v for k, v in c.items() if k[0] == mode})
            print(f"수정안 {'①' if mode == 1 else '②'} {st}:", dict(t))


if __name__ == "__main__":
    {"join": join, "wide": wide, "chain": chain, "fix": fix}.get(sys.argv[1] if len(sys.argv) > 1 else "", main)()
