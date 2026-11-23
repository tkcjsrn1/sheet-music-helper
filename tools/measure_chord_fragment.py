# -*- coding: utf-8 -*-
"""[B-1] 붙은 화음 머리가 분할 앞에서 사라지는 단계 추적. 측정 전용 — 제품 결과는 안 바꾼다.

[B] 1단계(`measure_chord_split.py`)에서 「성분 없음」·「분할 전 게이트 탈락」으로 분류된 붙은 화음 누락 머리를
제품 파이프라인 단계마다 잰다. 대조군은 **같은 오선 위치(선 위 / 칸 사이 · 오선 안 / 덧줄 구역)**의 살아남은 단일 머리.

단계(제품과 같은 연산, `notehead_detect`):
- S0 이진화 원본 (`res.binary`)
- S1 오선 제거 — `remove_staff_lines`가 지운 화소 중 **오선 5줄 y ± radius**(제품의 구제 창과 같은 반경) 안의 것만 지운 영상
- S2 덧줄 제거 — `remove_staff_lines` 결과 전부(나머지 = 덧줄 · 기타 긴 가로선)
- S3 세로 메움 — 보표 띠를 잘라 `MORPH_CLOSE`(1 × 0.4sp) (`patched`)
- S4 opening — 타원 0.65 × 0.5sp (`opened`)
- S5 연결 성분 — 제품 `connectedComponentsWithStats` 결과(가로챔), 분할 전 게이트 적용

각 단계에서 **머리 영역 R**(정답 중심, 반축 0.6 × 0.45sp 타원) 안 잉크의 가장 큰 연결 조각의 면적(E 단위, E = π·0.6·0.42 sp²)과
높이(sp)를 잰다. 「살아 있음」 = 면적 ≥ 0.5E 이고 높이 ≥ 0.68sp(제품 분할 전 게이트와 같은 값). 처음 죽은 단계 = 소실 단계.
S1~S2에서 지워진 화소가 R 안 어느 행에 있는지(오선 행 / 덧줄 행)도 센다.

해상도: 같은 PDF를 sp ≈ 11.5px(Aoharu와 같은 해상도, 177dpi)와 300dpi로 렌더해 `detect_noteheads` 원출력 기준 누락을 비교한다.

    python tools/measure_chord_fragment.py              # 단계 추적 · 해상도 · 그림
    python tools/measure_chord_fragment.py --binarize   # 이진화 구멍 확인 · 반사실(어두운 화소 채움)
"""
import math
import os
import sys
from collections import Counter, defaultdict

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure_chord_split as S  # noqa: E402  (ND 가로채기가 걸린다 — 결과는 안 바뀜)

ROOT, ND, C, M = S.ROOT, S.ND, S.C, S.M
from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402

OUT_DIR = S.OUT_DIR
STAGES = ["S0 이진화", "S1 오선 제거", "S2 덧줄 제거", "S3 세로 메움", "S4 opening", "S5 성분"]


# ---------------------------------------------------------------- 정답 · 묶음
def truth(name, path, pg, dpi=300):
    g = S.glyphs(path, pg)
    k = dpi / 300.0
    for q in g:
        q["cx"] *= k
        q["cy"] *= k
    heads = []
    for q in (q for q in g if q["name"].startswith("noteheads.")):
        if any(abs(q["cx"] - h["cx"]) < 2 * k and abs(q["cy"] - h["cy"]) < 2 * k for h in heads):
            continue
        heads.append(q)
    main = Counter(h["size"] for h in heads).most_common(1)[0][0]
    return [h for h in heads if abs(h["size"] - main) < 0.05]


def groups_of(heads, sp):
    grp_of, groups = {}, []
    for i in sorted(range(len(heads)), key=lambda i: (heads[i]["cx"], heads[i]["cy"])):
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
    return grp_of, groups


def position(h, st):
    """정답 중심의 오선 위치: 선 위 / 칸 사이, 오선 안 / 덧줄 구역."""
    half = st.spacing / 2.0
    k = int(round((h["cy"] - st.top) / half))
    on_line = (k % 2 == 0)
    inside = 0 <= k <= 8
    return ("선 위" if on_line else "칸 사이") + (" · 오선 안" if inside else " · 덧줄 구역")


def nearest_staff(staves, cy):
    return min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - cy))


# ---------------------------------------------------------------- 단계 영상
def stages(res, st, no_staff):
    """보표 st의 띠 기준 단계 영상(페이지 좌표로 맞춘 bool 배열 dict)과 지운 화소 분류."""
    b = res.binary > 0
    removed = b & ~(no_staff > 0)
    sp = st.spacing
    radius = max(4, int(round(sp * 0.55)))
    near = np.zeros(b.shape[0], bool)
    for s in res.staves:
        for ly in s.line_ys:
            near[max(0, ly - radius):ly + radius + 1] = True
    rm_staff = removed & near[:, None]
    s1 = b & ~rm_staff
    up, down = ND._band_margins(st, res.staves)
    top = max(0, st.top - int(round(up)))
    bot = min(b.shape[0], st.bottom + int(round(down)))
    band = no_staff[top:bot, :]
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    patched = cv2.morphologyEx(band, cv2.MORPH_CLOSE, vk)
    kw, kh = max(3, int(sp * 0.65)) | 1, max(3, int(sp * 0.5)) | 1
    opened = cv2.morphologyEx(patched, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kw, kh)))

    def full(a):
        z = np.zeros_like(b)
        z[top:bot] = a > 0
        return z
    return dict(img=[b, s1, no_staff > 0, full(patched), full(opened)], rm_staff=rm_staff,
                rm_other=removed & ~near[:, None], top=top, bot=bot)


def head_region(shape, cx, cy, sp):
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return ((xx - cx) / (0.6 * sp)) ** 2 + ((yy - cy) / (0.45 * sp)) ** 2 <= 1.0


def piece(img, cx, cy, sp):
    """R 안 잉크의 가장 큰 조각: (면적 E, 높이 sp, 조각 수)."""
    x0, y0 = int(cx - sp), int(cy - sp)
    win = img[max(0, y0):int(cy + sp) + 1, max(0, x0):int(cx + sp) + 1]
    R = head_region(win.shape, cx - max(0, x0), cy - max(0, y0), sp)
    m = (win & R).astype(np.uint8)
    n, lab, st, _c = cv2.connectedComponentsWithStats(m, connectivity=8)
    E = math.pi * (sp * 0.6) * (sp * 0.42)
    if n <= 1:
        return 0.0, 0.0, 0
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    real = sum(1 for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.05 * E)
    return st[big, cv2.CC_STAT_AREA] / E, st[big, cv2.CC_STAT_HEIGHT] / sp, real


def alive(a, h):
    return a >= 0.5 and h >= 0.68


# ---------------------------------------------------------------- 한 쪽
def page(name, path, pg):
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    S._rec.clear()
    ND.detect_noteheads(res, contexts=analyze_staves(res))
    recs = list(S._rec)
    heads = truth(name, path, pg)
    grp_of, groups = groups_of(heads, sp)
    labels = C.snapshot_page(path, pg)["labels"]
    _pairs, used_t, _ul = M.match(heads, labels, sp)
    matched = set(used_t)
    cache, rows = {}, []
    no_staff = ND.remove_staff_lines(res.binary, res.staves)
    for hi, h in enumerate(heads):
        grp = groups[grp_of[hi]]
        in_chord = len(grp) >= 2
        rec, ci = S.comp_at(recs, h["cx"], h["cy"])
        f = S.features(rec, ci) if rec is not None else None
        final_ok = f is not None and S.gate_fail(f) is None
        if in_chord and hi not in matched and final_ok:
            continue                                   # 분할 단계 이후 누락(B-2) — 대상 밖
        kind = ("화음 · 누락" if hi not in matched else "화음 · 검출") if in_chord else ("단일 · 검출" if hi in matched else None)
        if kind is None:
            continue
        st = rec["staff"] if rec is not None else nearest_staff(staves, h["cy"])
        if st.index not in cache:
            cache[st.index] = stages(res, st, no_staff)
        stg = cache[st.index]
        vals = [piece(img, h["cx"], h["cy"], st.spacing) for img in stg["img"]]
        vals.append((f["area_E"], f["h_sp"], 1) if f is not None else (0.0, 0.0, 0))
        lost = next((i for i, (a, hh, _n) in enumerate(vals) if not (alive(a, hh) if i < 5 else (f is not None and S.gate_fail(f) is None))), None)
        R = head_region(res.binary.shape, h["cx"], h["cy"], st.spacing)
        nb = [heads[k] for k in grp if k != hi]
        near = min(nb, key=lambda q: abs(q["cy"] - h["cy"]) + abs(q["cx"] - h["cx"])) if nb else None
        rows.append(dict(page=name, x=round(h["cx"]), y=round(h["cy"]), kind=kind, pos=position(h, st), sp=st.spacing,
                         vals=vals, lost=lost, rm_staff=int((stg["rm_staff"] & R).sum()), rm_other=int((stg["rm_other"] & R).sum()),
                         R=int(R.sum()), ink=int((res.binary[R] > 0).sum()),
                         dx=(near["cx"] - h["cx"]) / sp if near else None, dy=(near["cy"] - h["cy"]) / sp if near else None,
                         n=len(grp), crop=_crop(res, stg, h["cx"], h["cy"], st.spacing)))
    return rows


def _crop(res, stg, cx, cy, sp):
    """그림용 — 머리 ±1.6sp 창만 남긴다(쪽 전체 영상을 들고 있지 않도록)."""
    x0, y0 = max(0, int(cx - 1.6 * sp)), max(0, int(cy - 1.6 * sp))
    x1, y1 = int(cx + 1.6 * sp), int(cy + 1.6 * sp)
    return dict(org=res.original_bgr[y0:y1, x0:x1].copy(), img=[im[y0:y1, x0:x1].copy() for im in stg["img"]],
                rm_staff=stg["rm_staff"][y0:y1, x0:x1].copy(), rm_other=stg["rm_other"][y0:y1, x0:x1].copy(),
                c=(cx - x0, cy - y0))


# ---------------------------------------------------------------- 해상도
def raw_miss(path, pg, dpi):
    """`detect_noteheads` 원출력 기준 누락(분할 · 뒤 규칙 포함, 유령 필터 전)."""
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi)
    sp = float(np.median([s.spacing for s in res.staves]))
    nh = ND.detect_noteheads(res, contexts=analyze_staves(res))
    heads = truth("", path, pg, dpi)
    grp_of, groups = groups_of(heads, sp)
    c = Counter()
    for hi, h in enumerate(heads):
        chord = len(groups[grp_of[hi]]) >= 2
        hit = any(abs(n.x - h["cx"]) <= 0.7 * sp and abs(n.y - h["cy"]) <= 0.5 * sp for n in nh)
        c[("화음" if chord else "단일", hit)] += 1
    return sp, c


def binarize_check(path, pg):
    """이진화 구멍 확인 + 반사실(측정 안에서만): `res.binary`에 원본의 확실히 어두운 화소(흐림 뒤 gray < 128)를 더하면?
    오선 · 보표는 그대로 두고 음표 머리 검출만 다시 돈다. 누락(화음/단일)과 **정답 머리와 짝이 없는 검출**(유령 후보) 수를 비교."""
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    sp = float(np.median([s.spacing for s in res.staves]))
    heads = truth("", path, pg)
    grp_of, groups = groups_of(heads, sp)
    gray = cv2.GaussianBlur(res.gray, (3, 3), 0)
    dark = gray < 128
    ctx = analyze_staves(res)
    out = {}
    for mode in ("제품", "어두운 화소 채움"):
        if mode != "제품":
            res.binary = np.where(dark, 255, res.binary).astype(np.uint8)
        nh = ND.detect_noteheads(res, contexts=ctx)
        c = Counter()
        hit_n = set()
        for hi, h in enumerate(heads):
            chord = len(groups[grp_of[hi]]) >= 2
            js = [j for j, n in enumerate(nh) if abs(n.x - h["cx"]) <= 0.7 * sp and abs(n.y - h["cy"]) <= 0.5 * sp]
            hit_n.update(js)
            c[("화음" if chord else "단일", bool(js))] += 1
        c["짝 없는 검출"] = len(nh) - len(hit_n)
        out[mode] = c
    rows = []
    b0 = preprocess(os.path.join(ROOT, path), pdf_page=pg).binary > 0
    for hi, h in enumerate(heads):
        R = head_region(b0.shape, h["cx"], h["cy"], sp)
        rows.append(dict(chord=len(groups[grp_of[hi]]) >= 2, name=h["name"],
                         dark=float(dark[R].mean()), ink=float(b0[R].mean())))
    return out, rows


def main_binarize():
    pages = [p for p in C.PAGES if not p[0].startswith("aoharu")]
    tot, rows = defaultdict(Counter), []
    for name, path, pg in pages:
        out, r = binarize_check(path, pg)
        rows += r
        for k, c in out.items():
            tot[k].update(c)
        print(name, {k: (c[("화음", False)], c[("단일", False)], c["짝 없는 검출"]) for k, c in out.items()}, flush=True)
    print("\n## 6. 이진화 구멍 — 머리 영역 R 안: 원본 어두운 화소 비율 → 이진화 잉크 비율 (10% / 중앙 / 90%)\n")
    print("| 무리 | 글리프 | n | 원본 어두움 | 이진화 잉크 |\n|---|---|---:|---|---|")
    for chord in (True, False):
        for nm in sorted({r["name"] for r in rows}):
            rs = [r for r in rows if r["chord"] == chord and r["name"] == nm]
            if rs:
                print(f"| {'화음' if chord else '단일'} | {nm} | {len(rs)} | {q([r['dark'] for r in rs])} | {q([r['ink'] for r in rs])} |")
    print("\n## 7. 반사실 (측정 안에서만) — `detect_noteheads` 원출력\n")
    print("| 이진화 | 화음 누락 | 단일 누락 | 정답과 짝 없는 검출 |\n|---|---|---|---:|")
    for k, c in tot.items():
        ch, si = c[("화음", False)], c[("단일", False)]
        print(f"| {k} | {ch}/{ch + c[('화음', True)]} | {si}/{si + c[('단일', True)]} | {c['짝 없는 검출']} |")


def aoharu_chords():
    """Aoharu 골든 라벨 중 붙은 화음 모양(같은 x ±0.6sp, 세로 0.3~1.05sp)으로 이웃한 라벨 수 — 정답이 없어 라벨로만 센다."""
    out = []
    for p, sp in (("aoharu_p1", 11.5), ("aoharu_p2", 11.65), ("aoharu_p3", 11.5)):
        pts = []
        for line in open(os.path.join(ROOT, "tests", "golden", p + ".tsv"), encoding="utf-8"):
            t = line.rstrip("\n").split("\t")
            pts.append((int(t[1]), int(t[2])))
        inchord = sum(1 for a in pts if any(b != a and abs(b[0] - a[0]) <= 0.6 * sp and 0.3 * sp <= abs(b[1] - a[1]) <= 1.05 * sp for b in pts))
        out.append((p, len(pts), inchord))
    return out


# ---------------------------------------------------------------- 출력
def q(vals):
    if not vals:
        return "—"
    v = sorted(vals)
    return f"{v[len(v) // 10]:.2f} / {v[len(v) // 2]:.2f} / {v[(len(v) * 9) // 10]:.2f}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pages = [p for p in C.PAGES if not p[0].startswith("aoharu")]
    rows = []
    for name, path, pg in pages:
        r = page(name, path, pg)
        rows += r
        print(f"{name}: 화음 누락(분할 앞) {sum(1 for x in r if x['kind'] == '화음 · 누락')}", flush=True)

    lostrows = [r for r in rows if r["kind"] == "화음 · 누락"]
    print(f"\n## 1. 소실 단계 — 분할 앞 화음 누락 {len(lostrows)}개\n")
    poss = sorted({r['pos'] for r in rows})
    for kind in ("화음 · 누락", "화음 · 검출", "단일 · 검출"):
        rs = [r for r in rows if r["kind"] == kind]
        print(f"\n**{kind}** ({len(rs)})\n")
        print("| 소실 단계 | " + " | ".join(poss) + " | 합 |\n|---|" + "---:|" * (len(poss) + 1))
        for li in list(range(6)) + [None]:
            cnt = [sum(1 for r in rs if r["lost"] == li and r["pos"] == p) for p in poss]
            if sum(cnt):
                print(f"| {STAGES[li] if li is not None else '끝까지 살아 있음'} | " + " | ".join(map(str, cnt)) + f" | {sum(cnt)} |")

    print("\n## 2. 단계별 남은 크기 (면적 E · 높이 sp, 10% / 중앙 / 90%)\n")
    print("| 무리 · 위치 | n | " + " | ".join(STAGES) + " |\n|---|---:|" + "---|" * 6)
    for kind in ("화음 · 누락", "화음 · 검출", "단일 · 검출"):
        for p in poss:
            rs = [r for r in rows if r["kind"] == kind and r["pos"] == p]
            if not rs:
                continue
            cells = [f"{q([r['vals'][i][0] for r in rs])}<br>h {q([r['vals'][i][1] for r in rs])}" for i in range(6)]
            print(f"| {kind} · {p} | {len(rs)} | " + " | ".join(cells) + " |")

    print("\n## 3. 오선 · 덧줄 제거가 R(머리 영역)에서 지운 화소 비율 (R 안 잉크 대비, 10% / 중앙 / 90%)\n")
    print("| 무리 · 위치 | n | 오선 제거 | 덧줄 · 기타 제거 | S2 뒤 조각 수 ≥2 |\n|---|---:|---|---|---:|")
    for kind in ("화음 · 누락", "화음 · 검출", "단일 · 검출"):
        for p in poss:
            rs = [r for r in rows if r["kind"] == kind and r["pos"] == p]
            if rs:
                print(f"| {kind} · {p} | {len(rs)} | {q([r['rm_staff'] / max(1, r['ink']) for r in rs])} | "
                      f"{q([r['rm_other'] / max(1, r['ink']) for r in rs])} | {sum(1 for r in rs if r['vals'][2][2] >= 2)} |")

    print("\n## 4. 화음 누락 머리의 이웃 머리 (가장 가까운 같은 묶음 머리까지 dx · dy sp)\n")
    cnt = Counter()
    for r in lostrows:
        cnt["옆(2도, |dx|≥0.4)" if abs(r["dx"]) >= 0.4 else "위아래(3도 쌓임)"] += 1
    det = Counter("옆(2도, |dx|≥0.4)" if abs(r["dx"]) >= 0.4 else "위아래(3도 쌓임)" for r in rows if r["kind"] == "화음 · 검출")
    print(f"누락: {dict(cnt)} · 검출된 화음 머리: {dict(det)}")
    print("묶음 크기(누락):", dict(Counter(r["n"] for r in lostrows)), "· (검출):", dict(Counter(r["n"] for r in rows if r["kind"] == "화음 · 검출")))

    print("\n## 5. 해상도 — `detect_noteheads` 원출력 기준 누락 (화음 머리 / 단일 머리)\n")
    print("| 쪽 | dpi | sp(px) | 화음 누락 | 단일 누락 |\n|---|---:|---:|---|---|")
    tot = defaultdict(Counter)
    for name, path, pg in pages:
        for dpi in (177, 240, 300, 400):
            sp, c = raw_miss(path, pg, dpi)
            tot[dpi].update(c)
            ch, si = c[("화음", False)], c[("단일", False)]
            print(f"| {name} | {dpi} | {sp:.1f} | {ch}/{ch + c[('화음', True)]} | {si}/{si + c[('단일', True)]} |", flush=True)
    for dpi, c in sorted(tot.items()):
        ch, si = c[("화음", False)], c[("단일", False)]
        print(f"| **합** | {dpi} | | **{ch}/{ch + c[('화음', True)]} ({ch / max(1, ch + c[('화음', True)]) * 100:.0f}%)** | "
              f"{si}/{si + c[('단일', True)]} ({si / max(1, si + c[('단일', True)]) * 100:.1f}%) |")
    print("\nAoharu 골든(라벨 기준, 정답 없음):", aoharu_chords())
    _figures(rows)


def _figures(rows):
    """대표 사례: 화음 누락 10(소실 단계 · 위치가 고르게) + 같은 위치 단일 머리 대조 2 — 단계별 확대."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    lost = [r for r in rows if r["kind"] == "화음 · 누락"]
    pick, seen = [], Counter()
    for r in sorted(lost, key=lambda r: (r["page"], r["x"])):
        key = (r["lost"], r["pos"])
        if seen[key] < 2 and len(pick) < 10:
            seen[key] += 1
            pick.append(r)
    for p in {r["pos"] for r in pick}:
        ctrl = [r for r in rows if r["kind"] == "단일 · 검출" and r["pos"] == p and r["page"] == pick[0]["page"]]
        if ctrl and len(pick) < 12:
            pick.append(ctrl[0])
    panels, scale = 6, 4
    tiles = []
    for r in pick:
        sp = r["sp"]
        cr = r["crop"]
        imgs = [cv2.cvtColor(cr["org"], cv2.COLOR_BGR2RGB)]
        for i, a in enumerate(cr["img"]):
            v = np.full(a.shape + (3,), 255, np.uint8)
            v[a] = (0, 0, 0)
            if i == 1:
                v[cr["rm_staff"]] = (230, 40, 40)
            if i == 2:
                v[cr["rm_staff"]] = (250, 170, 170)
                v[cr["rm_other"]] = (40, 90, 230)
            imgs.append(v)
        row = []
        for v in imgs:
            v = cv2.resize(v, None, fx=scale * 20 / sp, fy=scale * 20 / sp, interpolation=cv2.INTER_NEAREST)
            k = scale * 20 / sp
            c = (int(cr["c"][0] * k), int(cr["c"][1] * k))
            cv2.ellipse(v, c, (int(0.6 * sp * scale * 20 / sp), int(0.45 * sp * scale * 20 / sp)), 0, 0, 360, (0, 170, 60), 1)
            row.append(v)
        hgt = max(v.shape[0] for v in row)
        wid = sum(v.shape[1] for v in row) + 6 * len(row)
        t = Image.new("RGB", (wid, hgt + 40), "white")
        xx = 0
        for v in row:
            t.paste(Image.fromarray(np.ascontiguousarray(v)), (xx, 40))
            xx += v.shape[1] + 6
        d = ImageDraw.Draw(t)
        vals = " · ".join(f"{a:.2f}E/{h:.2f}" for a, h, _n in r["vals"])
        d.text((3, 2), f"{r['page']} ({r['x']},{r['y']}) [{r['kind']}] {r['pos']} · 소실 {STAGES[r['lost']] if r['lost'] is not None else '없음'}",
               font=font, fill=(0, 0, 0))
        d.text((3, 20), vals, font=font, fill=(90, 90, 90))
        tiles.append(t)
    head = ["원본", "이진화", "오선 제거(빨강=지움)", "덧줄 제거(파랑=지움)", "세로 메움", "opening"]
    for s in range(0, len(tiles), 6):
        chunk = tiles[s:s + 6]
        W = max(t.width for t in chunk)
        sheet = Image.new("RGB", (W + 10, sum(t.height + 10 for t in chunk) + 30), "white")
        d = ImageDraw.Draw(sheet)
        pw = chunk[0].width // 6
        for i, h in enumerate(head):
            d.text((5 + i * pw, 6), h, font=font, fill=(0, 0, 0))
        yy = 30
        for t in chunk:
            sheet.paste(t, (5, yy))
            yy += t.height + 10
        if max(sheet.size) > 1600:
            k = 1600 / max(sheet.size)
            sheet = sheet.resize((int(sheet.width * k), int(sheet.height * k)), Image.LANCZOS)
        sheet.save(os.path.join(OUT_DIR, f"fragment_stages_{s // 6 + 1}.png"))


if __name__ == "__main__":
    main_binarize() if "--binarize" in sys.argv else main()
