# -*- coding: utf-8 -*-
"""TASKS [2](b) 짧은 마지막 시스템 누락 — 오선 문턱 `max(0.6 × ref, 0.25 × 폭)` 측정. 제품 코드 무변경.

세트: PDF 17쪽 · Aoharu 3 · Verovio 20 · 조표 픽스처 15 · 사진 합성 70(M1 통과분).
보표 수 정답: PDF · 픽스처는 **PDF 벡터 오선**(5줄 등간격 묶음), Verovio는 SVG, Aoharu는 정답 골든 문맥, 사진은 원본 쪽의 정답.

후보(사본): 제품 보표는 그대로 두고, **보표가 없는 y 구간**에서만 낮은 문턱으로 5줄 묶음을 더 찾는다 —
기존 보표의 선 · 라벨은 바뀔 수 없다. 더한 묶음마다 정답 보표와 겹치는지(오검출인지)를 센다.

    python tools/measure_short_system.py collect   → debug/short_system/rows.json
    python tools/measure_short_system.py eval
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "debug", "short_system")


# ------------------------------------------------------------------ 정답
def pdf_staves(path, page, dpi=300):
    """PDF 벡터 가로선에서 오선 5줄 묶음 — (맨윗줄 y, 맨아랫줄 y, x0, x1) px."""
    import fitz
    p = fitz.open(path)[page]
    lines = []
    for dr in p.get_drawings():
        for it in dr["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.01 and abs(it[2].x - it[1].x) > 20:
                lines.append((it[1].y, min(it[1].x, it[2].x), max(it[1].x, it[2].x)))
            elif it[0] == "re" and it[1].height < 1.5 and it[1].width > 20:
                lines.append(((it[1].y0 + it[1].y1) / 2, it[1].x0, it[1].x1))
    lines.sort()
    out, used = [], set()
    for i in range(len(lines)):
        if i in used:
            continue
        # 같은 x 범위 · 등간격 다섯 줄
        same = [j for j in range(i, len(lines)) if j not in used
                and abs(lines[j][1] - lines[i][1]) < 1 and abs(lines[j][2] - lines[i][2]) < 1]
        if len(same) < 5:
            continue
        g = same[:5]
        d = np.diff([lines[j][0] for j in g])
        if d.min() > 2 and d.max() - d.min() < 0.2 and d.max() < 12:
            used.update(g)
            k = dpi / 72.0
            out.append((lines[g[0]][0] * k, lines[g[4]][0] * k, lines[g[0]][1] * k, lines[g[0]][2] * k))
    return out


def pages():
    """(세트, 이름, 경로, pdf 쪽, 사진 경로?, 정답 보표 [(top, bottom, x0, x1)] 또는 개수)"""
    P = []
    T = os.path.join(ROOT, "test_scores")
    srcs = [("bach", "bach_minuet_Am.pdf", [0])] + [(f"bbm", "chopin_nocturne_Bbm.pdf", range(6)),
                                                    ("db", "chopin_nocturne_Db_6-8.pdf", range(6)), ("em", "chopin_nocturne_Em.pdf", range(4))]
    for tag, f, pgs in srcs:
        for i in pgs:
            P.append(("pdf", f"{tag}{i + 1}" if tag != "bach" else "bach", os.path.join(T, f), i, False, pdf_staves(os.path.join(T, f), i)))
    for tag, f in (("p1", ""), ("p2", "_01"), ("p3", "_02")):
        ctx = [l for l in open(os.path.join(ROOT, "tests", "golden", f"aoharu_{tag}_context.tsv"), encoding="utf-8") if not l.startswith("#")]
        P.append(("aoharu", tag, os.path.join(ROOT, "sample_images", f"KakaoTalk_20260731_162400402{f}.png"), 0, False, len(ctx)))
    V = os.path.join(T, "verovio")
    for f in sorted(os.listdir(V)):
        if f.endswith("_p1.png"):
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", f[:-4] + ".json"), encoding="utf-8"))
            P.append(("verovio", f[:-4], os.path.join(V, f), 0, False,
                      [(s["line_ys"][0], s["line_ys"][-1], s["x0"], s["x1"]) for s in t["staves"]]))
    FX = os.path.join(ROOT, "tests", "fixtures", "key_signatures")
    for k in json.load(open(os.path.join(FX, "manifest.json"), encoding="utf-8"))["keys"]:
        p = os.path.join(FX, k["pdf"].replace("\\", "/"))
        P.append(("fixture", k["slug"], p, 0, False, pdf_staves(p, 0)))
    man = json.load(open(os.path.join(ROOT, "output", "synthetic_photos", "manifest.json"), encoding="utf-8"))
    src_n = {s: len(pdf_staves(os.path.join(ROOT, v[0]), v[1])) for s, v in man["sources"].items()}
    for d in ("synthetic_photos", "m1_edge"):
        for f in sorted(os.listdir(os.path.join(ROOT, "output", d))):
            if f.lower().endswith((".png", ".jpg")):
                P.append(("photo", os.path.splitext(f)[0], os.path.join(ROOT, "output", d, f), 0, True, src_n[f.split("__")[0]]))
    # 오검출 압박용 — 보지 않은 악보 9쪽 · 미지원 악보 5 · 기울였다 되돌리기 255 · M1이 거부한 사진을 기본 경로(--photo 없이)로
    U = os.path.join(ROOT, "output", "unseen-scores-20260829", "sources")
    for tag, f, pgs in (("moon", "moonlight-a4.pdf", (0, 1, 10, 17)), ("rain", "Chop-28-15-a4.pdf", range(4)),
                        ("organ", "Ich_ruf_zu_dir2-a4.pdf", (1,))):
        for i in pgs:
            P.append(("unseen", f"{tag}{i + 1}", os.path.join(U, f), i, False, pdf_staves(os.path.join(U, f), i)))
    US = os.path.join(ROOT, "tests", "fixtures", "unsupported_scores")
    for f, n in (("satie_ogive3_scan_60pct.jpg", 8), ("bach_bwv639_three_staff.png", 3), ("chopin_raindrop_key_change.png", 4),
                 ("beethoven_midscore_symbols.png", 4), ("schubert_triplet_beam_stem.png", 4)):
        P.append(("unsupported", f, os.path.join(US, f), 0, False, n))
    SW = os.path.join(OUT, "..", "keysig_fix", "sweep")
    n_src = {"bach": 8, "bbm": len(pdf_staves(os.path.join(T, "chopin_nocturne_Bbm.pdf"), 0)), "aoharu": P[[x[1] for x in P].index("p1")][5]}
    for f in sorted(os.listdir(SW)):
        P.append(("sweep", f[:-4], os.path.join(SW, f), 0, False, n_src[f.split("_")[0]]))
    for d in ("synthetic_photos", "m1_edge"):
        for f in sorted(os.listdir(os.path.join(ROOT, "output", d))):
            if f.lower().endswith((".png", ".jpg")):
                P.append(("photo_plain", os.path.splitext(f)[0], os.path.join(ROOT, "output", d, f), 0, False, src_n[f.split("__")[0]]))
    return P


# ------------------------------------------------------------------ 수집
def _collect_one(p):
    import cv2
    from modules.preprocess import preprocess, staff_line_profile, PhotoRejectedError
    st, name, path, pg, photo, truth = p
    try:
        res = preprocess(path, pdf_page=pg, photo=photo) if path.endswith(".pdf") else preprocess(path, photo=photo)
    except PhotoRejectedError as e:
        return dict(set=st, name=name, rejected=str(e)[:80], truth=truth)
    except Exception as e:                                  # 기본 경로 실패(오선 못 찾음 등) — 기록만
        return dict(set=st, name=name, rejected=f"{type(e).__name__}: {str(e)[:60]}", truth=truth)
    b = res.binary
    W = b.shape[1]
    row = staff_line_profile(b)
    k = max(15, W // 30)
    staff_only = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))

    def extent(y):
        cols = np.where(staff_only[y] > 0)[0]
        return (int(cols.min()), int(cols.max())) if len(cols) else (0, 0)
    staves = [dict(lines=list(map(int, s.line_ys)), sp=float(s.spacing),
                   rows=[float(row[y]) for y in s.line_ys], ext=[extent(y) for y in s.line_ys]) for s in res.staves]
    # 낮은 문턱 후보: 열림 커널 길이(=「가로선」의 제품 정의) 이상인 모든 봉우리
    from scipy.signal import find_peaks
    pk, _ = find_peaks(row, height=k, distance=2)
    peaks = [dict(y=int(y), v=float(row[y]), ext=extent(int(y))) for y in pk]
    return dict(set=st, name=name, truth=truth, W=W, H=b.shape[0], ref=float(row.max()), kernel=k,
                staves=staves, peaks=peaks, scale=1.0)


def collect():
    os.makedirs(OUT, exist_ok=True)
    with ProcessPoolExecutor(4) as ex:
        rows = list(ex.map(_collect_one, pages()))
    json.dump(rows, open(os.path.join(OUT, "rows.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for r in rows:
        if "rejected" in r:
            continue
        n_t = r["truth"] if isinstance(r["truth"], int) else len(r["truth"])
        if len(r["staves"]) != n_t:
            print(r["set"], r["name"], "보표", len(r["staves"]), "/", n_t, flush=True)
    print("입력", len(rows), "거부", sum("rejected" in r for r in rows))


# ------------------------------------------------------------------ 평가
def line_stats(ys_ext_v):
    """5줄의 길이비(최소 행합 / 최대 행합)와 x 겹침(공통 구간 / 전체 구간)."""
    v = [p[2] for p in ys_ext_v]
    ext = [p[1] for p in ys_ext_v]
    span = max(e[1] for e in ext) - min(e[0] for e in ext)
    common = min(e[1] for e in ext) - max(e[0] for e in ext)
    return min(v) / max(v), common / max(1, span)


def extra_staves(r, len_min=None, ovl_min=None):
    """제품 보표 밖(위아래 1sp 띠 바깥)의 낮은 문턱 봉우리에서 연속 5줄 — 간격은 제품 `group_into_staves` 검증 조건 그대로."""
    sp = float(np.median([s["sp"] for s in r["staves"]])) if r["staves"] else None
    if sp is None:
        return []
    occ = [(s["lines"][0] - sp, s["lines"][-1] + sp) for s in r["staves"]]
    free = [p for p in r["peaks"] if not any(a <= p["y"] <= b for a, b in occ)]
    out, i = [], 0
    while i + 5 <= len(free):
        g = free[i:i + 5]
        ys = [p["y"] for p in g]
        d = np.diff(ys)
        m = float(np.mean(d))
        if np.std(d) <= m * 0.25 and sp * 0.6 <= m <= sp * 1.6:
            lr, ov = line_stats([(p["y"], p["ext"], p["v"]) for p in g])
            if (len_min is None or lr >= len_min) and (ovl_min is None or ov >= ovl_min):
                out.append(dict(top=ys[0], bottom=ys[-1], len_ratio=round(lr, 3), overlap=round(ov, 3),
                                x0=min(p["ext"][0] for p in g), x1=max(p["ext"][1] for p in g)))
                i += 5
                continue
        i += 1
    return out


def truth_n(r):
    t = r["truth"]
    return t if isinstance(t, int) else (len(t) or None)


def is_real(r, e):
    """더한 보표가 정답 보표인가 — 좌표 정답이 있으면 맨윗줄 y 0.6sp 안, 없으면 None(그림 판정)."""
    t = r["truth"]
    if isinstance(t, list) and t:
        sp = float(np.median([s["sp"] for s in r["staves"]]))
        return any(abs(a[0] - e["top"]) < sp * 0.6 for a in t)
    return None


def evaluate():
    rows = json.load(open(os.path.join(OUT, "rows.json"), encoding="utf-8"))
    ok = [r for r in rows if "rejected" not in r]
    # 진짜 보표 분포 — 제품이 이미 찾은 보표 전부(사진 · 압박 입력 포함)
    real = [line_stats(list(zip(s["lines"], s["ext"], s["rows"]))) for r in ok for s in r["staves"]]
    lr = np.array([a for a, _ in real]); ov = np.array([b for _, b in real])
    print(f"제품 보표 {len(real)}: 길이비 최소 {lr.min():.2f} 1% {np.percentile(lr, 1):.2f} · x겹침 최소 {ov.min():.2f} 1% {np.percentile(ov, 1):.2f}")
    for nm, kw in (("조건 없음(간격만)", {}), (f"x 겹침 ≥ {OVL_MIN}", dict(len_min=LEN_MIN, ovl_min=OVL_MIN))):
        by, false_, unk, added = {}, [], [], 0
        for r in rows:
            b = by.setdefault(r["set"], [0, 0, 0])
            n_t = truth_n(r)
            if "rejected" in r:
                b[2] += 1
                continue
            ex = extra_staves(r, **kw)
            added += len(ex)
            for e in ex:
                k = is_real(r, e)
                (false_ if k is False else unk if k is None else []).append((r["set"], r["name"], e))
            if n_t is not None:
                b[0] += (len(r["staves"]) + len([e for e in ex if is_real(r, e) is not False])) == n_t
                b[1] += 1
        print(f"\n[{nm}] 더한 보표 {added} · 오검출(정답에 없음) {len(false_)} · 좌표 정답 없어 그림 판정 {len(unk)}")
        print("  보표 수 정답:", " · ".join(f"{k} {a}/{n}" + (f"(거부 {g})" if g else "") for k, (a, n, g) in by.items()))
        for s_, n_, e in (false_ + unk)[:12]:
            print("   ", "오검출" if (s_, n_, e) in false_ else "판정 필요", s_, n_, e)


# 길이비는 안 쓴다 — 보정 안 된 회전 사진의 오선 조각 묶음이 0.99까지 나와 가르지 못한다.
LEN_MIN = None
# x 겹침 = 「보표 5줄은 같은 x 범위를 덮는다」(기보 규칙). 진짜: 제품 보표 3,662의 1백분위 0.84(짧은 시스템 4개 1.00) ·
# 가짜: D♭ 6쪽 −0.72 · 회전 0.5° 기본 경로 조각 최대 0.33 → 기하평균 √(0.84 × 0.33) = 0.53
OVL_MIN = 0.53


if __name__ == "__main__":
    {"collect": collect, "eval": evaluate}[sys.argv[1]]()
