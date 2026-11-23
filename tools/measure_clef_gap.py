# -*- coding: utf-8 -*-
"""음자리표 끝 판정(A-8)의 여유를 잰다 — 음자리표와 첫 조표 사이 **틈**이 문턱을 얼마나 넘나.

측정 전용. `modules/`는 읽기만 한다. 음자리표 클러스터 탐색(`clef_keysig._analyze_one` 1단계)은
안에서 가로챌 수 없어 **같은 식으로 다시 계산**하고, 결과 `clef_end`가 제품 값과 같은지 보표마다 대조한다.

    python tools/measure_clef_gap.py orig    [출력.tsv]   # 다섯 악보 전 쪽, 원본
    python tools/measure_clef_gap.py resample [출력.tsv]   # 각 악보 1쪽 × 재표본화 7가지
    python tools/measure_clef_gap.py sharp    [출력.tsv]   # Aoharu ♯ 두 세로획 붙음

잰 값 (보표마다):

- **틈 폭** — 오선 행(선 y ±2px)을 뺀 헤더 띠에서 잉크가 0인 열의 연속 길이. 음자리표 오른끝과
  첫 조표 글리프 왼끝 사이. 기하학적 틈이다
- **틈 잔여** — 그 틈 열들에서 제품 프로파일(`ink_cnt`, 오선 제거 뒤 헤더 띠 열 잉크)의 최댓값.
  이 값이 **0.5sp 이상**이면 그 열은 음자리표 클러스터의 일부로 본다
- **알고리즘이 보는 틈** — 틈 구간에서 `ink_cnt < 0.5sp`인 열의 최장 연속. 이것이 `max_g`보다 길어야
  클러스터가 멈춘다
- **조표 안 틈** — 첫 조표 글리프 왼끝부터 조표 오른끝(투표 key_right)까지 오선 행 제외 잉크 0 열의 연속들
"""
import csv
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.preprocess import preprocess  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402
from measure_keysig_resample import tilt_and_fix, _write, _Spy  # noqa: E402

PAGES = ([("aoharu", os.path.join(ROOT, "sample_images", f"KakaoTalk_20260731_162400402{s}.png"), 0)
          for s in ("", "_01", "_02")]
         + [("bach", os.path.join(ROOT, "test_scores", "bach_minuet_Am.pdf"), 0)]
         + [("bbm", os.path.join(ROOT, "test_scores", "chopin_nocturne_Bbm.pdf"), p) for p in range(6)]
         + [("db", os.path.join(ROOT, "test_scores", "chopin_nocturne_Db_6-8.pdf"), p) for p in range(6)]
         + [("em", os.path.join(ROOT, "test_scores", "chopin_nocturne_Em.pdf"), p) for p in range(4)])
VARIANTS = [(0.15, "linear"), (0.3, "linear"), (1.0, "linear"), (5.0, "linear"), (8.0, "linear"),
            ("shift", "linear"), ("shift", "lanczos4")]
LINE_PAD = 2                     # 오선 y ±2px 행을 뺀다(선 두께 3px 실측)


def staff_profiles(res):
    """보표마다 제품과 같은 헤더 띠 열 잉크(`ink_cnt`)와, 오선 행을 뺀 열 잉크."""
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    out = {}
    for s in res.staves:
        sp = s.spacing
        top = max(0, int(s.top - sp * 3)); bottom = min(H, int(s.bottom + sp * 3))
        band = ns[top:bottom, :]
        Hb = band.shape[0]
        ink_rows = band > 0
        any_ink = ink_rows.any(axis=0)
        first = ink_rows.argmax(axis=0)
        last = Hb - 1 - ink_rows[::-1, :].argmax(axis=0)
        tall_thin = np.where(any_ink, last - first, -1) > sp * 8.5
        r0 = max(0, int(s.top - top - sp * 1.5)); r1 = min(Hb, int(s.bottom - top + sp * 1.5) + 1)
        sub = band[r0:r1, :] > 0
        ink = sub.sum(axis=0)
        keep = np.ones(r1 - r0, bool)
        for ly in s.line_ys:
            a = max(0, ly - top - r0 - LINE_PAD); b = min(r1 - r0, ly - top - r0 + LINE_PAD + 1)
            keep[a:b] = False
        off = sub[keep].sum(axis=0)
        out[s.index] = dict(sp=sp, ink=ink, off=off, tall=tall_thin, top=s.top)
    return out


def clef_cluster(p):
    """`_analyze_one` 1단계와 같은 식 — (xc, cluster_end, xe) 또는 None."""
    sp, ink, tall = p["sp"], p["ink"], p["tall"]
    W = len(ink)
    cx = 0
    while cx < W:
        if tall[cx] or ink[cx] < sp * 0.5:
            cx += 1
            continue
        c2, g = cx, 0
        max_g = max(3, int(sp * 0.5))
        while c2 < W and not tall[c2]:
            if ink[c2] >= sp * 0.5:
                g = 0
            else:
                g += 1
                if g > max_g:
                    break
            c2 += 1
        c2 -= g
        if c2 - cx >= sp * 1.4 and float(ink[cx:c2].max()) > sp * 0.8:
            xe = min(W, max(c2, cx + int(sp * 2.2)), cx + int(sp * 5))
            return cx, c2, xe
        cx = max(c2, cx + 1)
    return None


def runs(mask):
    """True 연속 구간 [(시작, 길이)]."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and mask[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def page_rows(name, path, page, label="원본", img=None):
    if img is not None:
        tmp = os.path.join(ROOT, "debug", "clef_gap"); os.makedirs(tmp, exist_ok=True)
        path = os.path.join(tmp, f"{name}{page}_{label}.png"); _write(path, img); page = 0
    res = preprocess(path, pdf_page=page)
    ctxs = CK.analyze_staves(res)
    kc, ks, key_right = CK._vote_key_signature(ctxs)
    # 첫 구조 막대 x — 투표와 같은 ±3px 클러스터
    found = [c for c in ctxs.values() if c.clef_found]
    thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    bars = sorted(x for c in found for x, _ in c.bars)
    cons, i = [], 0
    while i < len(bars):
        j = i
        while j + 1 < len(bars) and bars[j + 1] - bars[i] <= 3.0:
            j += 1
        if j - i + 1 >= thr:
            cons.append(float(np.mean(bars[i:j + 1])))
        i = j + 1
    profs = staff_profiles(res)
    rows = []
    for s in res.staves:
        p, c = profs[s.index], ctxs[s.index]
        cl = clef_cluster(p)
        row = dict(악보=name, 쪽=page if label == "원본" else label, 보표=s.index, sp=round(p["sp"], 2),
                   조표=f"{ks}{kc}" if kc else "0", 제품clef_end=c.clef_end if c.clef_found else -1,
                   재계산clef_end=cl[2] if cl else -1, top=p["top"])
        if cl:
            xc, cend, xe = cl
            row.update(xc=xc, cluster_end=cend)
        rows.append(row)
    return rows, profs, cons, key_right, (kc, ks)


def gap_stats(p, clef_right, glyph_x, key_right):
    """clef_right 뒤 ~ glyph_x(첫 조표 막대) 앞의 기하학적 틈과 그 잔여."""
    sp, ink, off = p["sp"], p["ink"], p["off"]
    gl = int(glyph_x)
    while gl > clef_right and off[gl - 1] > 0:        # 첫 조표 글리프 왼끝
        gl -= 1
    gr = gl
    while gr > clef_right and off[gr - 1] == 0:       # 그 왼쪽 잉크 0 연속 = 틈
        gr -= 1
    gap = (gr, gl)
    width = gl - gr
    resid = int(ink[gr:gl].max()) if width > 0 else None
    low = runs(ink[gr:gl] < sp * 0.5) if width > 0 else []
    alg = max((n for _a, n in low), default=0)
    inner = [n for a, n in runs(off[gl:int(key_right)] == 0)] if key_right > gl else []
    return dict(gap_x0=gr, gap_x1=gl, 틈폭=width, 틈폭sp=round(width / sp, 3),
                틈잔여=resid, 틈잔여sp=None if resid is None else round(resid / sp, 3),
                알고리즘틈=alg, max_g=max(3, int(sp * 0.5)),
                조표안틈최대sp=round(max(inner) / sp, 3) if inner else 0.0,
                조표안틈=";".join(str(n) for n in inner))


def orig(out_tsv):
    allrows = []
    for name, path, page in PAGES:
        rows, profs, cons, key_right, (kc, ks) = page_rows(name, path, page)
        if name == "aoharu":                          # 이미지 세 장이 모두 page 0이라 파일로 구분
            page = {"": 0, "01": 1, "02": 2}[os.path.basename(path)[28:-4].lstrip("_")]
        for r in rows:
            r["쪽"] = page
            if kc and cons and r.get("cluster_end") is not None and r["제품clef_end"] > 0:
                p = profs[r["보표"]]
                # 들여쓰기된 보표는 합의 x와 다른 자리에 조표가 있다 — 음자리표 끝 뒤 첫 구조 막대를 쓴다
                first = [x for x in cons if x > r["cluster_end"] - 1]
                if first and first[0] - r["cluster_end"] < p["sp"] * 4:
                    r.update(gap_stats(p, r["xc"], first[0], key_right))
            allrows.append(r)
        print(f"{name} p{page}: 보표 {len(rows)} 조표 {ks}{kc}", flush=True)
    _dump(allrows, out_tsv)


def resample(out_tsv):
    allrows = []
    seen = set()
    for name, path, page in PAGES:
        if name in seen:
            continue
        seen.add(name)
        base_rows, base_profs, cons, key_right, (kc, ks) = page_rows(name, path, page)
        img = preprocess(path, pdf_page=page).original_bgr
        gaps = {}
        for r in base_rows:
            if kc and r.get("cluster_end") is not None:
                first = [x for x in cons if x > r["cluster_end"] - 1]
                if first and first[0] - r["cluster_end"] < base_profs[r["보표"]]["sp"] * 4:
                    gaps[r["보표"]] = gap_stats(base_profs[r["보표"]], r["xc"], first[0], key_right)
        for deg, m in VARIANTS:
            lab = f"{deg}_{m}"
            rows, profs, _c, _k, (vkc, vks) = page_rows(name, path, page, lab, tilt_and_fix(img, deg, m))
            for r in rows:
                # 보표 대응: 원본과 top이 sp 안
                b = min(base_rows, key=lambda q: abs(q["top"] - r["top"]))
                g = gaps.get(b["보표"])
                if g is None or abs(b["top"] - r["top"]) > r["sp"]:
                    continue
                p = profs[r["보표"]]
                x0, x1 = g["gap_x0"], g["gap_x1"]
                seg = p["ink"][x0:x1]
                r.update(원본보표=b["보표"], 원본틈잔여=g["틈잔여"], 틈폭=g["틈폭"],
                         틈잔여=int(seg.max()) if len(seg) else None,
                         틈잔여sp=round(float(seg.max()) / p["sp"], 3) if len(seg) else None,
                         오선뺀틈잔여=int(p["off"][x0:x1].max()) if len(seg) else None,
                         알고리즘틈=max((n for _a, n in runs(seg < p["sp"] * 0.5)), default=0),
                         max_g=max(3, int(p["sp"] * 0.5)),
                         원본clef_end=b["제품clef_end"],
                         삼킴=int(r["제품clef_end"] > x1), 판정=f"{vks}{vkc}" if vkc else "0")
                allrows.append(r)
            print(f"{name} {lab}: 조표 {vks}{vkc}", flush=True)
    _dump(allrows, out_tsv)


def sharp(out_tsv):
    """♯ 조표 악보 1쪽(기본 Aoharu, 셋째 인자로 em): ♯ 글리프마다 두 세로획 사이 열의 closing 뒤 run — 오선 행을 빼면 몇인가."""
    want = sys.argv[3] if len(sys.argv) > 3 else "aoharu"
    name, path, page = next(q for q in PAGES if q[0] == want)
    img = preprocess(path, pdf_page=page).original_bgr
    allrows = []
    for deg, m in [("원본", None)] + VARIANTS:
        if m is None:
            p, pg = path, page
        else:
            pg = 0
            p = os.path.join(ROOT, "debug", "clef_gap", f"sharp_{name}_{deg}_{m}.png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _write(p, tilt_and_fix(img, deg, m))
        res = preprocess(p, pdf_page=pg)
        ns = remove_staff_lines(res.binary, res.staves)
        H = res.binary.shape[0]
        for s in res.staves:
            with _Spy() as spy:
                CK._analyze_one(ns, s, H, False)
            if not spy.calls:
                continue
            w = spy.calls[0]
            sp, x0 = w["sp"], w["x0"]
            seg_raw = w["band"][w["r0"]:w["r1"], w["x0"]:w["x1"]]
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            seg = cv2.morphologyEx(seg_raw, cv2.MORPH_CLOSE, vk)
            # 오선 행을 뺀(흰색으로 만든) 뒤 같은 closing
            top = max(0, int(s.top - sp * 3))
            raw2 = seg_raw.copy()
            for ly in s.line_ys:
                a = max(0, ly - top - w["r0"] - LINE_PAD); b = min(raw2.shape[0], ly - top - w["r0"] + LINE_PAD + 1)
                raw2[a:b] = 0
            seg2 = cv2.morphologyEx(raw2, cv2.MORPH_CLOSE, vk)

            def maxrun(col):
                best = run = 0
                for v in col:
                    run = run + 1 if v else 0
                    best = max(best, run)
                return best
            isbar = np.array([sp * 1.6 <= maxrun(seg[:, c] > 0) <= sp * 3.4 for c in range(seg.shape[1])])
            isbar2 = np.array([sp * 1.6 <= maxrun(seg2[:, c] > 0) <= sp * 3.4 for c in range(seg2.shape[1])])
            # 조표 구간(첫 2.5sp)의 막대 열 덩어리 폭
            lim = int(sp * 2.6)
            for a, n in runs(isbar[:lim]):
                allrows.append(dict(악보=name, 변형=f"{deg}_{m}" if m else "원본", 보표=s.index, sp=round(sp, 2),
                                    x=x0 + a, 폭=n, 폭sp=round(n / sp, 3), max_w_초과=int(n > sp * 0.45),
                                    오선뺀폭=";".join(str(k) for _b, k in runs(isbar2[a:a + n]))))
        print(f"sharp {deg} {m}", flush=True)
    _dump(allrows, out_tsv)


def _dump(rows, path):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, keys, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"→ {path} ({len(rows)}행)")



def prop(out_tsv):
    """성질 후보: 오선 행(±pad)을 뺀 프로파일에서 「음자리표 뒤 틈」 폭 vs 「음자리표 안·조표 안」 틈 폭.

    각 악보 1쪽(Aoharu는 세 장), 원본 + `resample`이 저장한 변형 7가지(1쪽만). 빈 열 = 오선 행 밖 잉크 ≤ e.
    **원본에서 이미 클러스터가 조표를 넘는 보표도 포함한다** — 틈 위치를 `cluster_end`가 아니라
    음자리표 시작 `xc` + 1.4sp 뒤 첫 구조 막대로 잡는다. 들여쓴 첫 시스템(각 악보 첫 쪽 보표 0·1)은 뺀다.
    조표가 없으면(바흐) 음자리표 뒤 첫 빈 열 연속 = 음자리표와 다음 기호(박자표·음표) 사이 틈.
    """
    global LINE_PAD
    out = []
    todo = [q for q in PAGES if q[0] == "aoharu"] + [next(q for q in PAGES if q[0] == n) for n in ("bach", "bbm", "db", "em")]
    for name, path, page in todo:
        base_rows, _p, cons, key_right, (kc, _ks) = page_rows(name, path, page)
        first_page = name != "aoharu" or path.endswith("402.png")
        srcs = [("원본", path, page)]
        if first_page and name != "bach":
            srcs += [(f"{d}_{m}", os.path.join(ROOT, "debug", "clef_gap", f"{name}{page}_{d}_{m}.png"), 0)
                     for d, m in VARIANTS]
        tag = path[-7:-4] if name == "aoharu" else str(page)
        for lab, p, pg in srcs:
            res = preprocess(p, pdf_page=pg)
            for pad in (2, 3):
                LINE_PAD = pad
                profs = staff_profiles(res)
                for s in res.staves:
                    b = min(base_rows, key=lambda q: abs(q["top"] - s.top))
                    if abs(b["top"] - s.top) > s.spacing or b.get("xc") is None:
                        continue
                    if first_page and b["보표"] in (0, 1):
                        continue                          # 들여쓴 첫 시스템
                    pr = profs[s.index]
                    sp, off = pr["sp"], pr["off"]
                    xc = b["xc"]
                    for e_sp in (0.0, 0.1, 0.2):
                        empty = off <= e_sp * sp
                        if kc:
                            first = [x for x in cons if x > xc + sp * 1.4]
                            if not first:
                                continue
                            gl = int(first[0])
                            while gl > xc and not empty[gl - 1]:
                                gl -= 1
                            gr = gl
                            while gr > xc and empty[gr - 1]:
                                gr -= 1
                            inkey = max((n for _x, n in runs(empty[gl:int(key_right)])), default=0)
                        else:                              # 조표 없음: 음자리표 뒤 첫 빈 연속
                            gr = int(xc + sp * 1.4)
                            while gr < len(empty) and not empty[gr]:
                                gr += 1
                            gl = gr
                            while gl < len(empty) and empty[gl]:
                                gl += 1
                            inkey = 0
                        a = max(xc, int(gr - 2.5 * sp))
                        inclef = max((n for _x, n in runs(empty[a:gr])), default=0)
                        out.append(dict(악보=name, 쪽=tag, 변형=lab, pad=pad, e_sp=e_sp, 보표=b["보표"],
                                        sp=round(sp, 2), xc=xc, 원본cluster_end=b["cluster_end"],
                                        틈x=gr, 틈sp=round((gl - gr) / sp, 3),
                                        음자리표안sp=round(inclef / sp, 3), 조표안sp=round(inkey / sp, 3)))
            print(f"prop {name} {tag} {lab}", flush=True)
    _dump(out, out_tsv)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "debug", f"clef_gap_{mode}.tsv")
    {"orig": orig, "resample": resample, "sharp": sharp, "prop": prop}.get(mode, lambda _o: print(__doc__))(out)
