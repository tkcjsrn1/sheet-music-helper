# -*- coding: utf-8 -*-
"""겹임시표 ♭♭ · 𝄪 → check 표시안 측정 (2026-10-15, 사용자 결정 16시 1 · 측정만, 보류 세트 미사용).

검출(라벨마다, 제품과 같은 창 — 머리 x −2 ~ −0.55sp · y ±2sp, 헤더 끝 제외):
  ♭♭ = ♭ 구멍(``_find_glyphs``의 ♭ 조건과 같은 계산 — 닫힘 전 오선 제거 영상 구멍 + 왼쪽 세로획) 두 개가 머리 높이 0.35sp 안에서
       가로 0.35~1.2sp 떨어져 나란함
  𝄪 = 닫힌 밴드의 연결 성분 중 상자 폭 · 높이 0.55~1.15sp · 중심이 머리와 0.35sp 안 · 구멍 없음 · 세로 최장 런 < 0.9sp(막대 아님) ·
       상자 두 대각선 위 잉크 비율 둘 다 ≥ 0.6
정답: PDF · 보지 않은 = PDF 글리프(``measure_a17.truth`` — accidentals.flatflat · doublesharp가 붙는 머리), Verovio = 적힌 임시표 ``##``.
표시 시뮬레이션: 검출된 머리 + 같은 마디(``_propagation_barlines``) 뒤쪽 같은 음 → check. 라벨 정오는 ``error_census``와 같은 정답(실효 임시표)으로.
라벨 = ``debug/sim_lp/flatc1u``(지금 main과 같은 인식 코드).

    python tools/measure_double_acc.py
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
OUT = os.path.join(ROOT, "debug", "double_acc.json")
LAB = "flatc1u"
EXT_SP = 2.9         # 검출 패치 왼쪽 끝(머리 기준) — ♭♭ 상자 최대 2.57 · 𝄪 중심 최대 2.84sp + 여유


def _flat_holes_xy(patch, hole_patch, sp, bars):
    import cv2
    from modules import accidental_detect as AD
    out = []
    if not bars:
        return out
    small = cv2.morphologyEx(hole_patch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    cs, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return out
    for i, c in enumerate(cs):
        if hier[0][i][3] == -1:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if not (sp * 0.25 <= w <= sp * 0.9 and sp * 0.25 <= h <= sp * 0.9):
            continue
        if not any(AD.FLAT_BAR_LEFT_SP[0] * sp <= x + w / 2 - b[0] <= AD.FLAT_BAR_LEFT_SP[1] * sp for b in bars):
            continue
        out.append((x + w / 2, y + h / 2))
    return out


def _dsharp(patch, sp, ny, nx):
    """ny · nx = 패치 안 머리 y · x. 𝄪 = 굵은 귀퉁이 덩어리 4개가 2 × 2로 놓인 ✕(Emmentaler 상자 1.07sp, 중심이 머리 1.5~2.84sp 왼쪽).
    덧줄 · 기둥 같은 얇은 선과 붙어 한 덩어리가 되므로(월광 2쪽 덧줄 위), 타원 열림(0.25sp)으로 얇은 선을 지운 뒤 덩어리 4개를 찾는다."""
    import cv2
    k = max(3, int(0.25 * sp)) | 1
    op = cv2.morphologyEx((patch > 0).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, cen = cv2.connectedComponentsWithStats(op, connectivity=8)
    for i in range(1, n):                         # 가운데로 이어진 한 덩어리 ✕
        x, y, w, h, _a = st[i]
        if not (0.8 * sp <= w <= 1.2 * sp and 0.8 * sp <= h <= 1.2 * sp) or abs(cen[i][1] - ny) > 0.35 * sp or not (0.8 * sp <= nx - cen[i][0] <= 3.0 * sp):
            continue
        comp = lab[y:y + h, x:x + w] == i
        q = lambda r0, r1, c0, c1: comp[int(r0 * h):max(int(r0 * h) + 1, int(r1 * h)), int(c0 * w):max(int(c0 * w) + 1, int(c1 * w))].mean()
        corners = min(q(0, .3, 0, .3), q(0, .3, .7, 1), q(.7, 1, 0, .3), q(.7, 1, .7, 1))
        edges = max(q(0, .2, .4, .6), q(.8, 1, .4, .6), q(.4, .6, 0, .2), q(.4, .6, .8, 1))
        if corners >= 0.5 and q(.4, .6, .4, .6) >= 0.5 and edges <= 0.25:
            return True
    blobs = [tuple(cen[i]) for i in range(1, n) if 0.2 * sp <= st[i][2] <= 0.6 * sp and 0.2 * sp <= st[i][3] <= 0.6 * sp]
    for a in blobs:
        for b in blobs:
            if not (0.45 * sp <= b[0] - a[0] <= 0.9 * sp and abs(b[1] - a[1]) <= 0.15 * sp):
                continue
            for c in blobs:
                if not (abs(c[0] - a[0]) <= 0.15 * sp and 0.45 * sp <= c[1] - a[1] <= 0.9 * sp):
                    continue
                if any(abs(d[0] - b[0]) <= 0.15 * sp and abs(d[1] - c[1]) <= 0.15 * sp for d in blobs):
                    mx, my = (a[0] + b[0]) / 2, (a[1] + c[1]) / 2
                    if abs(my - ny) <= 0.35 * sp and 0.8 * sp <= nx - mx <= 3.0 * sp:
                        return True
    return False

def _dsharp_old(patch, sp, ny):
    import cv2
    n, lab, st, _c = cv2.connectedComponentsWithStats((patch > 0).astype(np.uint8), connectivity=8)
    for k in range(1, n):
        x, y, w, h, _a = st[k]
        if not (0.55 * sp <= w <= 1.15 * sp and 0.55 * sp <= h <= 1.15 * sp) or abs(y + h / 2 - ny) > 0.35 * sp:
            continue
        comp = (lab[y:y + h, x:x + w] == k).astype(np.uint8)
        cs, hier = cv2.findContours(comp, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hier is not None and any(hier[0][i][3] != -1 for i in range(len(cs))):
            continue
        runs = [max((len(s) for s in "".join("1" if v else "0" for v in comp[:, c]).split("0")), default=0) for c in range(w)]
        if max(runs) >= 0.9 * sp:
            continue
        t = np.linspace(0, 1, 15)
        d1 = np.mean([comp[min(h - 1, int(a * (h - 1))), min(w - 1, int(a * (w - 1)))] for a in t])
        d2 = np.mean([comp[min(h - 1, int(a * (h - 1))), min(w - 1, int((1 - a) * (w - 1)))] for a in t])
        if d1 >= 0.6 and d2 >= 0.6:
            return True
    return False


def _job(job):
    import cv2
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    from modules import accidental_detect as AD
    import error_census as EC
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    doc = json.load(open(os.path.join(ROOT, "debug", "sim_lp", LAB, name + ".json"), encoding="utf-8"))
    L = doc["labels"]
    # 정답: 적힌 겹임시표 머리 · 실효 임시표(라벨 정오)
    if st == "verovio":
        heads, _b, sp0 = EC._truth_vrv(name)
        dbl = [(h["x"], h["y"], "dsharp") for h in heads if h["own"] == "##"]
    else:
        import measure_a17 as A
        g, _sk, _h = A.truth(path, pg, res, ctx)
        dbl = [(q["hx"], q["hy"], "dflat" if q["kind"] == "flatflat" else "dsharp") for q in g if q["kind"] in ("flatflat", "doublesharp")]
        heads, _b, sp0 = EC._truth_pdf(name, path, pg)
    m = EC._match(heads, L, sp0)
    truth_of = {j: heads[i] for i, j in m.items()}
    staff_of = {s.index: s for s in res.staves}
    H = res.binary.shape[0]
    bands, pred = {}, {}
    for j, l in enumerate(L):
        s = staff_of.get(l["staff"])
        if s is None:
            continue
        sp = s.spacing
        if s.index not in bands:
            top = max(0, int(int(s.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(H, int(int(s.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[s.index] = (cv2.morphologyEx(ns[top:bottom, :], cv2.MORPH_CLOSE, vk), top)
        band, top = bands[s.index]
        x, y = l["x"], l["y"]
        x1, x0 = int(x - sp * 0.55), int(x - sp * 2.0)
        if s.index in ctx:
            x0 = max(x0, ctx[s.index].header_end + int(sp * 0.2))
        if x1 - x0 < sp * 0.6:
            continue
        py0 = max(0, int(y - top - sp * 2.0))
        patch = band[py0:min(band.shape[0], int(y - top + sp * 2.0)), max(0, x0):x1]
        if patch.size == 0:
            continue
        hp = ns[top + py0:top + py0 + patch.shape[0], max(0, x0):max(0, x0) + patch.shape[1]]
        bars = AD._bars_without_own_head(band, py0, max(0, x0), patch, sp)
        if bars is None:
            bars = AD._find_thin_bars(patch, sp)
        ny = y - top - py0
        # 검출 전용 넓은 패치(표시만 — 읽기는 안 바꿈): 왼쪽 EXT_SP까지. ♭♭은 첫 ♭이 창 왼끝(−2sp) 밖으로 나가 있다(상자 1.0~2.57sp)
        xe = int(x - sp * EXT_SP)
        if s.index in ctx:
            xe = max(xe, ctx[s.index].header_end + int(sp * 0.2))
        xe = min(xe, max(0, x0))
        ep = band[py0:py0 + patch.shape[0], xe:x1]
        ehp = ns[top + py0:top + py0 + patch.shape[0], xe:x1]
        ebars = AD._find_thin_bars(ep, sp)
        hs = [(hx + xe, hy) for hx, hy in _flat_holes_xy(ep, ehp, sp, ebars) if abs(hy - ny) <= 0.35 * sp]
        if any(0.35 * sp <= abs(a[0] - b[0]) <= 1.2 * sp and max(a[0], b[0]) >= x0 for i, a in enumerate(hs) for b in hs[i + 1:]):
            pred[j] = "dflat"
        elif _dsharp(ehp, sp, ny, x - xe):      # 세로 닫힘 전 영상 — 닫힘이 ✕의 좌우 홈을 메운다(월광 2쪽)
            pred[j] = "dsharp"
    # 정답 겹임시표가 붙는 라벨
    tl = {}
    for hx, hy, k in dbl:
        c = [(abs(l["x"] - hx) + abs(l["y"] - hy), j) for j, l in enumerate(L) if abs(l["x"] - hx) <= 0.7 * sp0 and abs(l["y"] - hy) <= 0.5 * sp0]
        if c:
            tl[min(c)[1]] = k
    # 표시: 검출 머리 + 같은 마디 뒤쪽 같은 음
    flagged = set(pred)
    for si, s in staff_of.items():
        idx = sorted((j for j, l in enumerate(L) if l["staff"] == si), key=lambda j: L[j]["x"])
        bx = AD._propagation_barlines(res.binary, ns, s, [(int(L[j]["x"]), int(L[j]["y"])) for j in idx])
        for j in idx:
            if j in pred:
                nxt = min([b for b in bx if b > L[j]["x"]] or [10 ** 9])
                flagged |= {k for k in idx if L[j]["x"] < L[k]["x"] < nxt and L[k]["pitch"] == L[j]["pitch"]}
    rows = []
    for j in sorted(flagged | set(tl)):
        l, h = L[j], truth_of.get(j)
        ok = h is not None and h["pitch"] == l["pitch"] and EC.ACC(l["text"]) == h["eff"]
        rows.append(dict(x=l["x"], y=l["y"], text=l["text"], conf=l["confidence"], pred=pred.get(j), truth=tl.get(j),
                         flagged=j in flagged, correct=ok, ghost=h is None))
    return dict(set=st, page=name, n_truth=len(dbl), n_truth_labeled=len(tl), rows=rows)


def main():
    import measure_sim_ledger_pair as S
    jobs = [(st, n, p, pg) for st, n, p, pg in S.pages() if st != "aoharu" and n != "organ2"]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        P = list(ex.map(_job, jobs))
    json.dump(P, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(P)


def report(P=None):
    P = P or json.load(open(OUT, encoding="utf-8"))
    rows = [r | dict(page=p["page"], set=p["set"]) for p in P for r in p["rows"]]
    print("정답 겹임시표 머리", sum(p["n_truth"] for p in P), "· 라벨 붙은 것", sum(p["n_truth_labeled"] for p in P))
    for k in ("dflat", "dsharp"):
        tp = sum(1 for r in rows if r["pred"] == k and r["truth"] == k)
        fp = sum(1 for r in rows if r["pred"] == k and r["truth"] != k)
        fn = sum(1 for r in rows if r["truth"] == k and r["pred"] != k)
        print(f"  {k}: 검출 {tp + fp} · 맞음 {tp} · 정밀도 {tp / max(1, tp + fp) * 100:.0f}% · 재현율 {tp / max(1, tp + fn) * 100:.0f}% · 헛검출 {fp} "
              f"({dict(Counter(r['set'] for r in rows if r['pred'] == k and r['truth'] != k))})")
    F = [r for r in rows if r["flagged"]]
    c = Counter()
    for r in F:
        if r["conf"] == "check":
            c["이미 check"] += 1
        elif r["ghost"]:
            c[f"유령 {r['conf']} → check"] += 1
        else:
            c[("틀린 라벨 " if not r["correct"] else "맞는 라벨(헛표시) ") + r["conf"] + " → check"] += 1
    print("표시 대상", len(F), dict(c))
    print("  확실 오류 감소 =", c["틀린 라벨 certain → check"] + c["유령 certain → check"], "· 맞는 라벨 헛표시(확실 → check) =", c["맞는 라벨(헛표시) certain → check"])


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
