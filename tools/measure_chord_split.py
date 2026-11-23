# -*- coding: utf-8 -*-
"""[B] 1단계 — 붙은 화음 누락의 원인 분류와 「세로 프로파일 봉우리 2개 · 간격 ≈1sp」가 대조군과 겹치는지. 측정 전용.

`notehead_detect`의 `opened` 연결 성분을 **픽셀 마스크까지** 가로채(제품 결과는 안 바꿈) PDF 글리프 정답과 맞춘다.

대상 쪽: 검증 PDF 17쪽(바흐 · B♭m 6 · D♭ 6 · Em 4) + 빈 음표 픽스처 3종(PR #51 브랜치의 PDF를 `debug/hollow_fixture/`로 꺼냄 — 커밋 안 함).

정답(PDF 글리프): 일반 크기 음표 머리 · 임시표 · 쉼표(`rests.*`). **붙은 화음** = 같은 기둥(가로 0.6sp)에서 위아래 1.05sp 이하로 이어진 머리 묶음.
**누락** = 제품 라벨과 짝(가로 0.7sp · 세로 0.5sp)이 안 된 머리.

누락 머리 분류(그 머리 중심을 품은 성분 기준, 코드 순서):
- 성분 없음 — 어느 `opened` 성분도 중심을 품지 않음(opening에서 이미 사라짐)
- 임시표와 한 덩어리 — 그 성분 bbox 안에 PDF 임시표 글리프 중심이 있음
- 분할 경로 진입 실패(높이) — h ≤ `CHORD_SPLIT_SP`(1.40sp)
- 진입했지만 밀도 띠 뭉침 — h > 1.40sp, 행 밀도 > 0.55 띠가 2개 미만이고 대체 분할(h≥1.5 · 면적≥1.7E · (좌우 1/4 중심차≥0.15 또는 h≥1.75 · w≤1.6)) 미충족
- 기타 — 위에 안 걸리는데 누락(분할은 됐는데 뒤 단계 등)

**밀도 띠는 성분 마스크로 다시 계산한 근사값이다** — 제품은 `patched`(오선 메운 영상)의 bbox로 잰다. 봉우리 = 성분 마스크 행 합을 0.15sp 창으로
다듬은 뒤 `find_peaks`(돌출 ≥ 최댓값 0.15배, 간격 ≥ 0.5sp).

    python tools/measure_chord_split.py
"""
import io
import math
import os
import sys
from collections import Counter, defaultdict

import cv2
import fitz
import numpy as np
from fontTools.cffLib import CFFFontSet
from scipy.signal import find_peaks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
import measure_omission_rate as M  # noqa: E402
import modules.notehead_detect as ND  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "review", "chord_split")
HOLLOW = [("hollow16", "debug/hollow_fixture/hollow_16.pdf", 0), ("hollow20", "debug/hollow_fixture/hollow_20.pdf", 0),
          ("hollow24", "debug/hollow_fixture/hollow_24.pdf", 0)]

# ---------------------------------------------------------------- 가로채기 (성분 마스크까지)
_rec, _cur = [], {}


class _CV:
    def __getattr__(self, k):
        return getattr(cv2, k)

    def connectedComponentsWithStats(self, img, *a, **kw):
        out = cv2.connectedComponentsWithStats(img, *a, **kw)
        if not a and not kw and _cur:
            n, labels, stats, cents = out
            _rec.append(dict(staff=_cur["staff"], top=_cur["top"], header_end=_cur["header_end"],
                             labels=labels.copy(), stats=stats.copy(), cents=cents.copy()))
        return out


_orig_band = ND._detect_noteheads_in_band


def _band(no_staff_img, staff, img_height, header_end=0, margins=None, reject_log=None):
    up = margins[0] if margins else staff.spacing * ND.BASE_MARGIN_SP
    _cur.update(staff=staff, top=max(0, staff.top - int(round(up))), header_end=header_end)
    try:
        return _orig_band(no_staff_img, staff, img_height, header_end=header_end, margins=margins, reject_log=reject_log)
    finally:
        _cur.clear()


ND.cv2 = _CV()
ND._detect_noteheads_in_band = _band


# ---------------------------------------------------------------- PDF 글리프
def glyphs(path, page):
    doc = fitz.open(os.path.join(ROOT, path))
    pg = doc[page]
    fonts = {}
    for f in pg.get_fonts():
        if f[1] != "cff":
            continue
        _n, _e, _t, data = doc.extract_font(f[0])
        cff = CFFFontSet()
        cff.decompile(io.BytesIO(data), None)
        fonts[f[3].split("+")[-1]] = cff[cff.fontNames[0]]
    out, k = [], 300 / 72.0
    for span in pg.get_texttrace():
        top = fonts.get(span["font"])
        if top is None:
            continue
        sc = span["size"] * top.FontMatrix[0]
        for _u, gid, o, _b in span["chars"]:
            n = top.charset[gid]
            if not n.startswith(("noteheads.", "accidentals.", "rests.", "clefs.")):
                continue
            b = M._outline_bbox(top.CharStrings, n)
            if b is None:
                continue
            out.append(dict(name=n, cx=(o[0] + (b[0] + b[2]) / 2 * sc) * k,
                            cy=(o[1] - (b[1] + b[3]) / 2 * sc) * k, size=round(span["size"], 2)))
    doc.close()
    return out


# ---------------------------------------------------------------- 성분 특징
def features(rec, i):
    st = rec["staff"]
    sp = float(st.spacing)
    x, y, w, h, area = (int(v) for v in rec["stats"][i])
    mask = (rec["labels"][y:y + h, x:x + w] == i)
    rows = mask.sum(axis=1).astype(float)
    density = rows / max(1, w)
    bands, r = 0, 0
    while r < h:
        if density[r] <= 0.55:
            r += 1
            continue
        r2 = r
        while r2 < h and density[r2] > 0.55:
            r2 += 1
        if (r2 - r) >= sp * 0.3:
            bands += 1
        r = r2
    win = max(1, int(round(sp * 0.15)))
    prof = np.convolve(rows, np.ones(win) / win, mode="same")
    pk, _ = find_peaks(np.r_[0, prof, 0], prominence=max(1e-6, prof.max() * 0.15), distance=max(1, int(sp * 0.5)))
    pk = pk - 1
    gap = (pk[1] - pk[0]) / sp if len(pk) >= 2 else None
    xs = np.arange(w)

    def xc(a, b):
        col = mask[a:b].sum(axis=0)
        return float((xs * col).sum() / col.sum()) if col.sum() else w / 2.0
    q = max(1, h // 4)
    E = math.pi * (sp * 0.6) * (sp * 0.42)
    return dict(x=x, y=y + rec["top"], w=w, h=h, area=area, sp=sp, w_sp=w / sp, h_sp=h / sp, bands=bands,
                peaks=len(pk), gap=gap, qspread=abs(xc(0, q) - xc(h - q, h)) / sp, area_E=area / E,
                cx=float(rec["cents"][i][0]), cy=float(rec["cents"][i][1]) + rec["top"])


def comp_at(recs, px, py):
    """(px, py)를 품은 성분 (기록, 번호). 같은 보표 띠가 여럿이면 bbox 안에서 그 화소가 그 성분인 것."""
    for rec in recs:
        top = rec["top"]
        yy, xx = int(round(py - top)), int(round(px))
        L = rec["labels"]
        if 0 <= yy < L.shape[0] and 0 <= xx < L.shape[1]:
            win = L[max(0, yy - 2):yy + 3, max(0, xx - 2):xx + 3]
            ids = win[win > 0]
            if ids.size:
                i = int(np.bincount(ids).argmax())
                if rec["cents"][i][0] >= rec["header_end"]:
                    return rec, i
    return None, None


def gate_fail(f):
    """제품 코드 순서대로 분할 앞의 게이트(`_detect_noteheads_in_band`) — 걸리면 그 이름, 통과면 None."""
    if f["area_E"] < 0.5:
        return "면적<0.5E"
    if f["w_sp"] < 0.7:
        return "폭<0.70sp"
    if f["w_sp"] > 2.2:
        return "폭>2.2sp"
    if f["h_sp"] < 0.68:
        return "높이<0.68sp"
    if f["w"] > f["h"] * 2.1:
        return "납작(w>2.1h)"
    return None


def classify(f, has_acc):
    """코드 순서: 분할 전 게이트 → 임시표와 한 덩어리 → 분할 진입(높이) → 밀도 띠 · 대체 분할 → 기타."""
    g = gate_fail(f)
    if g:
        return f"분할 전 게이트 탈락({g}) — 머리가 조각남"
    if has_acc:
        return "임시표와 한 덩어리"
    if f["h_sp"] <= ND.CHORD_SPLIT_SP:
        return "분할 진입 실패(높이 ≤1.40sp)"
    fallback = (f["h_sp"] >= 1.5 and f["area_E"] >= 1.7
                and (f["qspread"] >= 0.15 or (f["h_sp"] >= 1.75 and f["w_sp"] <= 1.6)))
    if f["bands"] < 2 and not fallback:
        return "진입했지만 밀도 띠 뭉침"
    return "기타"


def page(name, path, pg):
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    _rec.clear()
    ctx = analyze_staves(res)
    rej = []
    ND.detect_noteheads(res, contexts=ctx, reject_log=rej)
    recs = list(_rec)
    g = glyphs(path, pg)
    heads = []
    for q in (q for q in g if q["name"].startswith("noteheads.")):
        if any(abs(q["cx"] - h["cx"]) < 2 and abs(q["cy"] - h["cy"]) < 2 for h in heads):
            continue
        heads.append(q)
    main = Counter(h["size"] for h in heads).most_common(1)[0][0]
    heads = [h for h in heads if abs(h["size"] - main) < 0.05]
    accs = [q for q in g if q["name"].startswith("accidentals.")]
    rests = [q for q in g if q["name"].startswith("rests.")]
    # 붙은 화음 묶음
    order = sorted(range(len(heads)), key=lambda i: (heads[i]["cx"], heads[i]["cy"]))
    grp_of, groups = {}, []
    for i in order:
        if i in grp_of:
            continue
        grp, frontier = [i], [i]
        while frontier:
            k = frontier.pop()
            for j, q in enumerate(heads):
                if j not in grp and abs(q["cx"] - heads[k]["cx"]) <= 0.6 * sp and abs(q["cy"] - heads[k]["cy"]) <= 1.05 * sp:
                    grp.append(j)
                    frontier.append(j)
        for k in grp:
            grp_of[k] = len(groups)
        groups.append(grp)
    chord_acc = {gi: any(0.3 * sp < heads[k]["cx"] - a["cx"] < 3.5 * sp and abs(heads[k]["cy"] - a["cy"]) <= 0.35 * sp
                         for k in grp for a in accs) for gi, grp in enumerate(groups)}
    labels = C.snapshot_page(path, pg)["labels"] if not name.startswith("hollow") else _labels_from_main(path, pg)
    pairs, used_t, _ul = M.match(heads, labels, sp)
    matched = set(used_t)

    miss_rows, comp_rows = [], []
    seen = {}
    for hi, h in enumerate(heads):
        rec, i = comp_at(recs, h["cx"], h["cy"])
        key = (id(rec), i) if rec is not None else None
        if key is not None and key not in seen:
            seen[key] = dict(rec=rec, i=i, heads=[], f=features(rec, i))
        if key is not None:
            seen[key]["heads"].append(hi)
        gi = grp_of[hi]
        in_chord = len(groups[gi]) >= 2
        if in_chord and hi not in matched:
            if rec is None:
                cat, f = "성분 없음", None
            else:
                f = seen[key]["f"]
                has_acc = any(f["x"] <= a["cx"] <= f["x"] + f["w"] and f["y"] <= a["cy"] <= f["y"] + f["h"] for a in accs)
                cat = classify(f, has_acc)
                if cat == "기타":                  # 분할은 됐는데 뒤 단계에서 지워짐 — 기각 기록의 사유
                    why = [q.get("reason") for q in rej if abs(q["x"] - h["cx"]) <= 0.7 * sp and abs(q["y"] - h["cy"]) <= 0.5 * sp]
                    cat = f"분할 뒤 제거 — {why[0] if why else '기각 기록 없음(뒤 필터)'}"
            miss_rows.append(dict(page=name, x=round(h["cx"]), y=round(h["cy"]), acc=chord_acc[gi], cat=cat, f=f))
    # 대조군: 성분 단위
    for key, s in seen.items():
        f = s["f"]
        hs = s["heads"]
        gis = {grp_of[k] for k in hs}
        chordish = any(len(groups[g]) >= 2 for g in gis) and len(hs) >= 2
        if chordish:
            grp = "붙은 화음 · 제대로 분할" if all(k in matched for k in hs) else "붙은 화음 · 누락 있음"
        elif len(hs) == 1 and hs[0] in matched and len(groups[grp_of[hs[0]]]) == 1:
            grp = "빈 음표(픽스처)" if name.startswith("hollow") and heads[hs[0]]["name"] in ("noteheads.s1", "noteheads.s0") else (
                "단일 머리" if not name.startswith("hollow") else None)
        else:
            grp = None
        if grp:
            comp_rows.append(dict(page=name, grp=grp, f=f))
    for rec in recs:
        for i in range(1, rec["stats"].shape[0]):
            key = (id(rec), i)
            if key in seen or rec["cents"][i][0] < rec["header_end"]:
                continue
            x, y, w, h, area = (int(v) for v in rec["stats"][i])
            sp_ = float(rec["staff"].spacing)
            if h < sp_ * 0.68 or w < sp_ * 0.7:
                continue                                       # 머리 게이트 앞에서 떨어지는 작은 조각은 대상 밖
            f = features(rec, i)
            is_rest = any(f["x"] <= r["cx"] <= f["x"] + f["w"] and f["y"] <= r["cy"] <= f["y"] + f["h"] for r in rests)
            is_acc = any(f["x"] <= a["cx"] <= f["x"] + f["w"] and f["y"] <= a["cy"] <= f["y"] + f["h"] for a in accs)
            comp_rows.append(dict(page=name, grp="쉼표" if is_rest else ("임시표 글리프" if is_acc else "음표 아닌 덩어리(빔 조각 등)"), f=f))
    chord_stats = Counter()
    for gi, grp in enumerate(groups):
        if len(grp) < 2:
            continue
        kind = "임시표 있음" if chord_acc[gi] else "임시표 없음"
        chord_stats[f"{kind} · 자리"] += 1
        chord_stats[f"{kind} · 머리"] += len(grp)
        chord_stats[f"{kind} · 누락"] += sum(1 for k in grp if k not in matched)
    return miss_rows, comp_rows, chord_stats, res


def _labels_from_main(path, pg):
    """픽스처는 check_accidental_fix.PAGES 밖이라 같은 함수로 라벨만 만든다."""
    return C.snapshot_page(path, pg)["labels"]


def describe(vals):
    if not vals:
        return "—"
    v = sorted(vals)
    return f"{v[0]:.2f} ~ {v[len(v) // 2]:.2f} ~ {v[-1]:.2f}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pages = [p for p in C.PAGES if not p[0].startswith("aoharu")] + HOLLOW
    misses, comps, chords = [], [], Counter()
    crops = []
    for name, path, pg in pages:
        m, c, s, res = page(name, path, pg)
        misses += m
        comps += c
        if not name.startswith("hollow"):
            chords.update(s)
        for r in m:
            if r["f"] is not None and len(crops) < 72:
                sp_ = r["f"]["sp"]
                x0, y0 = max(0, int(r["x"] - 3 * sp_)), max(0, int(r["y"] - 3 * sp_))
                img = res.original_bgr[y0:int(r["y"] + 3 * sp_), x0:int(r["x"] + 3 * sp_)].copy()
                cv2.circle(img, (int(r["x"] - x0), int(r["y"] - y0)), int(sp_ * 0.8), (0, 140, 255), 2)   # 누락 머리(정답 좌표)
                crops.append((r, img))
        print(f"{name}: 누락 {len(m)} · 성분 {len(c)}", flush=True)

    print("\n## 1. 붙은 화음 전수 (PDF 17쪽)\n")
    print("| | 자리 | 머리 | 누락 |\n|---|---:|---:|---:|")
    for kind in ("임시표 있음", "임시표 없음"):
        print(f"| {kind} | {chords[kind + ' · 자리']} | {chords[kind + ' · 머리']} | {chords[kind + ' · 누락']} |")

    print("\n## 2. 누락 머리 원인 분류 (임시표 있음 / 없음)\n")
    cats = sorted({r["cat"] for r in misses}, key=lambda c: (not c.startswith("성분"), not c.startswith("분할 전"), c))
    tab = defaultdict(Counter)
    for r in misses:
        tab[r["cat"]]["있음" if r["acc"] else "없음"] += 1
    print("| 원인 | 임시표 있는 화음 | 임시표 없는 화음 | 합 |\n|---|---:|---:|---:|")
    for c in cats:
        print(f"| {c} | {tab[c]['있음']} | {tab[c]['없음']} | {tab[c]['있음'] + tab[c]['없음']} |")
    for c in cats:
        fs = [r["f"] for r in misses if r["cat"] == c and r["f"] is not None]
        if fs:
            print(f"  {c}: h {describe([f['h_sp'] for f in fs])} · w {describe([f['w_sp'] for f in fs])} · 띠 {Counter(f['bands'] for f in fs)} · "
                  f"봉우리 {Counter(f['peaks'] for f in fs)} · 간격 {describe([f['gap'] for f in fs if f['gap']])}")

    print("\n## 3. 봉우리 분포 — 「봉우리 2개 · 간격 0.8~1.2sp」가 겹치나\n")
    print("**3-1. 분할 단계에 실제로 오는 성분만**(분할 전 게이트 통과 + 높이 > 1.40sp):\n")
    print("| 무리 | 성분 | 봉우리 수 분포 | 봉우리 2개 간격 (최소~중앙~최대 sp) | **2개 · 0.8~1.2sp** |\n|---|---:|---|---|---:|")
    reach = defaultdict(list)
    for r in comps:
        f = r["f"]
        if gate_fail(f) is None and f["h_sp"] > ND.CHORD_SPLIT_SP:
            reach[r["grp"]].append(f)
    for grp, fs in sorted(reach.items()):
        two = [f["gap"] for f in fs if f["peaks"] == 2 and f["gap"]]
        hit = sum(1 for g in two if 0.8 <= g <= 1.2)
        pk = Counter(min(f["peaks"], 4) for f in fs)
        print(f"| {grp} | {len(fs)} | {dict(sorted(pk.items()))} | {describe(two)} | {hit} ({hit / max(1, len(fs)) * 100:.0f}%) |")
    print("\n**3-2. 전체 성분(게이트 전)**:\n")
    print("| 무리 | 성분 | 봉우리 수 분포 | 봉우리 2개 간격 (최소~중앙~최대 sp) | **2개 · 0.8~1.2sp** |\n|---|---:|---|---|---:|")
    by = defaultdict(list)
    for r in comps:
        by[r["grp"]].append(r["f"])
    gaps = {}
    for grp in ("붙은 화음 · 제대로 분할", "붙은 화음 · 누락 있음", "단일 머리", "빈 음표(픽스처)", "쉼표", "임시표 글리프", "음표 아닌 덩어리(빔 조각 등)"):
        fs = by.get(grp, [])
        two = [f["gap"] for f in fs if f["peaks"] == 2 and f["gap"]]
        hit = sum(1 for g in two if 0.8 <= g <= 1.2)
        gaps[grp] = two
        pk = Counter(min(f["peaks"], 4) for f in fs)
        print(f"| {grp} | {len(fs)} | {dict(sorted(pk.items()))} | {describe(two)} | {hit} ({hit / max(1, len(fs)) * 100:.0f}%) |")
    _chart(gaps)
    _crops(crops)


def _chart(gaps):
    """무리별 「봉우리 2개」 간격 분포(0~3sp, 0.05sp 칸) — PIL로 그린다."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 14)
    names = [k for k, v in gaps.items()]
    W, rowh, left = 1200, 110, 260
    img = Image.new("RGB", (W, rowh * len(names) + 60), "white")
    d = ImageDraw.Draw(img)
    x0, x1 = left, W - 30

    def X(v):
        return x0 + (x1 - x0) * v / 3.0
    for t in [0, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]:
        d.line([(X(t), 20), (X(t), rowh * len(names) + 30)], fill=(235, 235, 235) if t not in (0.8, 1.2) else (255, 190, 120))
        d.text((X(t) - 10, rowh * len(names) + 34), f"{t:g}", font=font, fill=(90, 90, 90))
    for r, n in enumerate(names):
        base = 20 + r * rowh + rowh - 15
        d.text((6, base - 40), f"{n} (n={len(gaps[n])})", font=font, fill=(0, 0, 0))
        bins = Counter(int(g / 0.05) for g in gaps[n] if g < 3)
        mx = max(bins.values()) if bins else 1
        for b, c in bins.items():
            hgt = (rowh - 30) * c / mx
            d.rectangle([X(b * 0.05), base - hgt, X((b + 1) * 0.05) - 1, base], fill=(60, 110, 200))
        d.line([(x0, base), (x1, base)], fill=(150, 150, 150))
    d.text((x0, 2), "세로 프로파일 봉우리 2개인 성분의 봉우리 간격(sp) — 주황 선 0.8 · 1.2sp", font=font, fill=(0, 0, 0))
    img.save(os.path.join(OUT_DIR, "peak_gap_distribution.png"))


def _crops(crops):
    """누락 머리의 성분 확대(원인별 제목) — 한 장 12칸, 긴 변 1600px 이하."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    tiles = []
    for r, img in crops:
        f = r["f"]
        k = 150 / max(img.shape[:2])
        t = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        tile = Image.new("RGB", (190, 215), "white")
        tile.paste(Image.fromarray(cv2.cvtColor(t, cv2.COLOR_BGR2RGB)), (20, 55))
        dd = ImageDraw.Draw(tile)
        dd.text((3, 2), f"{r['page']} ({r['x']},{r['y']}) {'임시표' if r['acc'] else ''}", font=font, fill=(0, 0, 0))
        dd.text((3, 18), r["cat"].replace("분할 전 게이트 탈락", "게이트")[:16], font=font, fill=(180, 60, 0))
        dd.text((3, 34), f"h{f['h_sp']:.2f} w{f['w_sp']:.2f} 띠{f['bands']} 봉{f['peaks']}", font=font, fill=(60, 60, 60))
        dd.rectangle([0, 0, 189, 214], outline=(190, 190, 190))
        tiles.append(tile)
    per = 24
    for s in range(0, len(tiles), per):
        chunk = tiles[s:s + per]
        cols = 6
        rows = math.ceil(len(chunk) / cols)
        sheet = Image.new("RGB", (cols * 195 + 5, rows * 220 + 5), "white")
        for i, t in enumerate(chunk):
            sheet.paste(t, (5 + (i % cols) * 195, 5 + (i // cols) * 220))
        sheet.save(os.path.join(OUT_DIR, f"missing_blobs_{s // per + 1}.png"))


if __name__ == "__main__":
    main()
