# -*- coding: utf-8 -*-
"""오삭제율 측정 — **음표 → 라벨 방향**으로 센다.

라벨을 원본과 대조하는 전수 판정은 사라진 음을 못 센다(MEASUREMENT_PITFALLS C-4).
여기서는 정답 음표 머리를 먼저 정하고, 결과 라벨과 1:1로 짝지어 세 가지를 따로 센다.

- **오삭제**: 정답 머리는 있는데 짝지을 라벨이 없다
- **유령**: 라벨은 있는데 짝지을 정답 머리가 없다
- **음고 오류**: 짝은 맞는데 음이름+옥타브가 다르다

## 정답

- **PDF 쪽**(바흐·쇼팽): PDF 안의 음표 머리 글리프(`noteheads.*`)를 직접 읽는다. 위치는 글리프 윤곽의
  중심(300dpi 화소), 음고는 그 중심의 오선 반칸 위치와 **PDF의 음자리표 글리프**로 계산한다.
  작은 머리(꾸밈음 — 지원 범위 밖)는 따로 센다.
- **이미지 쪽**(RE:Aoharu): PDF가 없어 사람이 확대 그림으로 센다(`--strips`).

제품 코드는 읽기만 한다. 라벨은 `tools/check_accidental_fix.snapshot_page`(= main.py와 같은 순서)로 만든다.

    python tools/measure_omission_rate.py            # PDF 세 쪽 대조 + 불일치 확대 그림
    python tools/measure_omission_rate.py --strips   # RE:Aoharu 1쪽 보표별 라벨 그림(사람이 센다)
"""
import argparse
import io
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import cv2
import fitz
import numpy as np

import check_accidental_fix as C
from modules.preprocess import preprocess

OUT = os.path.join(ROOT, "debug", "omission")
DPI = 300
PDF_PAGES = [("bach", "test_scores/bach_minuet_Am.pdf", 0),
             ("db1", "test_scores/chopin_nocturne_Db_6-8.pdf", 0),
             ("bbm1", "test_scores/chopin_nocturne_Bbm.pdf", 0)]
LETTERS = "CDEFGAB"
# 맨 아랫줄 음: 높은음자리표 E4, 낮은음자리표 G2
BOTTOM = {"treble": ("E", 4), "bass": ("G", 2)}


def _outline_bbox(charstrings, name):
    from fontTools.pens.boundsPen import BoundsPen
    pen = BoundsPen(charstrings)
    charstrings[name].draw(pen)
    return pen.bounds                           # (xmin, ymin, xmax, ymax) 글리프 단위


def pdf_glyphs(path, page, prefixes=("noteheads.", "clefs.")):
    """PDF 한 쪽의 음표 머리·음자리표 글리프(prefixes로 고름): name, cx, cy(300dpi 화소), size_pt, 원점 ox · oy."""
    from fontTools.cffLib import CFFFontSet
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
    out = []
    k = DPI / 72.0
    for span in pg.get_texttrace():
        top = fonts.get(span["font"])
        if top is None:
            continue
        scale = span["size"] * top.FontMatrix[0]
        for _u, gid, origin, _bbox in span["chars"]:
            name = top.charset[gid]
            if not name.startswith(prefixes):
                continue
            b = _outline_bbox(top.CharStrings, name)
            if b is None:
                continue
            x0, y0, x1, y1 = b
            cx = (origin[0] + (x0 + x1) / 2 * scale) * k
            cy = (origin[1] - (y0 + y1) / 2 * scale) * k      # 글리프 y는 위가 +
            out.append(dict(name=name, cx=cx, cy=cy, size=round(span["size"], 2), ox=origin[0] * k, oy=origin[1] * k,
                            w=(x1 - x0) * scale * k, h=(y1 - y0) * scale * k))
    doc.close()
    return out


def truth_pitch(cx, cy, staves, clefs):
    """정답 음고: PDF 음자리표(같은 보표에서 왼쪽 가장 가까운 것) + 오선 반칸 위치."""
    st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - cy))
    left = [c for c in clefs if c["staff"] == st.index and c["cx"] < cx]
    kind = "bass" if left and max(left, key=lambda c: c["cx"])["name"].startswith("clefs.F") else "treble"
    step = int(round((st.line_ys[-1] - cy) / (st.spacing / 2.0)))
    letter, octave = BOTTOM[kind]
    i = LETTERS.index(letter) + step
    return st.index, f"{LETTERS[i % 7]}{octave + i // 7}", step, kind


def match(truth, labels, sp):
    """가까운 쌍부터 1:1로 짝짓는다. 가로 0.7sp · 세로 0.5sp 안(머리 하나 안)."""
    pairs = sorted(((abs(t["cx"] - l["x"]) + abs(t["cy"] - l["y"]), ti, li)
                    for ti, t in enumerate(truth) for li, l in enumerate(labels)
                    if abs(t["cx"] - l["x"]) <= sp * 0.7 and abs(t["cy"] - l["y"]) <= sp * 0.5))
    used_t, used_l, out = set(), set(), []
    for _d, ti, li in pairs:
        if ti in used_t or li in used_l:
            continue
        used_t.add(ti)
        used_l.add(li)
        out.append((ti, li))
    return out, used_t, used_l


def run_pdf():
    os.makedirs(OUT, exist_ok=True)
    report = {}
    for page, path, pg in PDF_PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        staves = res.staves
        sp = float(np.median([s.spacing for s in staves]))
        g = pdf_glyphs(path, pg)
        clefs = []
        for c in (x for x in g if x["name"].startswith("clefs.")):
            st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"]))
            clefs.append(dict(c, staff=st.index))
        heads = []
        for x in (x for x in g if x["name"].startswith("noteheads.")):
            # 두 성부가 같은 음을 공유하면 PDF에 같은 자리 글리프가 두 번 있다 — 보이는 머리는 하나
            if any(abs(x["cx"] - h["cx"]) < 2 and abs(x["cy"] - h["cy"]) < 2 for h in heads):
                continue
            # 빠르기 표시(♩.=) 속 음표 — 가장 가까운 보표에서 6sp 넘게 떨어진 머리는 악보 음표가 아니다
            st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - x["cy"]))
            if x["cy"] < st.top - 6 * st.spacing or x["cy"] > st.bottom + 6 * st.spacing:
                continue
            heads.append(x)
        sizes = Counter(x["size"] for x in heads)
        main_size = sizes.most_common(1)[0][0]
        # 일반 머리 = 가장 흔한 글자 크기. 다른 크기(꾸밈음 · 빠르기 표시 ♩.= 속 음표)는 따로 센다
        normal = [h for h in heads if abs(h["size"] - main_size) < 0.05]
        small = [h for h in heads if abs(h["size"] - main_size) >= 0.05]
        for h in normal:
            h["staff"], h["pitch"], h["step"], h["clef"] = truth_pitch(h["cx"], h["cy"], staves, clefs)
        labels = C.snapshot_page(path, pg)["labels"]
        pairs, used_t, used_l = match(normal, labels, sp)
        missing = [normal[i] for i in range(len(normal)) if i not in used_t]
        ghosts = [labels[i] for i in range(len(labels)) if i not in used_l]
        wrong = [(normal[ti], labels[li]) for ti, li in pairs if normal[ti]["pitch"] != labels[li]["pitch"]]
        # 작은 머리(꾸밈음)에 라벨이 붙었나 — 유령 후보 중 꾸밈음 자리는 따로 뺀다
        _sp, _st, small_hit = match(small, ghosts, sp)
        ghosts_real = [ghosts[i] for i in range(len(ghosts)) if i not in small_hit]
        report[page] = dict(sp=round(sp, 1), heads=len(heads), normal=len(normal), small=len(small),
                            sizes=dict(sizes), labels=len(labels), matched=len(pairs),
                            missing=[dict(x=round(h["cx"]), y=round(h["cy"]), pitch=h["pitch"], name=h["name"])
                                     for h in missing],
                            ghosts=[dict(x=l["x"], y=l["y"], pitch=l["pitch"], text=l["text"], conf=l.get("confidence"))
                                    for l in ghosts_real],
                            small_labeled=len(small_hit),
                            wrong=[dict(x=l["x"], y=l["y"], truth=t["pitch"], got=l["pitch"], text=l["text"])
                                   for t, l in wrong])
        print(f"\n== {page}  sp={sp:.1f}  머리 글리프 {len(heads)} (일반 {len(normal)} · 작은 {len(small)}, 크기 {dict(sizes)})")
        print(f"   라벨 {len(labels)} · 짝 {len(pairs)} · 오삭제 후보 {len(missing)} · 유령 후보 {len(ghosts_real)}"
              f" (+꾸밈음 자리 라벨 {len(small_hit)}) · 음고 불일치 {len(wrong)}")
        items = ([(h["cx"], h["cy"], f"-{h['pitch']}") for h in missing]
                 + [(l["x"], l["y"], f"+{l['pitch']}/{l['text']}") for l in ghosts_real]
                 + [(l["x"], l["y"], f"{t['pitch']}!={l['pitch']}") for t, l in wrong])
        grid(res.original_bgr, items, os.path.join(OUT, f"{page}_mismatch.png"))
    json.dump(report, open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return report


def grid(img, items, path, r=60):
    if not items:
        return
    tiles = []
    for i, (x, y, title) in enumerate(items):
        x, y = int(round(x)), int(round(y))
        x0, y0 = max(0, x - r), max(0, y - r)
        c = cv2.resize(img[y0:y + r, x0:x + r].copy(), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.drawMarker(c, ((x - x0) * 3, (y - y0) * 3), (255, 120, 0), cv2.MARKER_CROSS, 16, 2)
        c = cv2.copyMakeBorder(c, 28, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(c, f"{i + 1} ({x},{y}) {title}", (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        tiles.append(cv2.resize(c, (360, 388)))
    while len(tiles) % 5:
        tiles.append(np.full_like(tiles[0], 255))
    g = np.vstack([np.hstack(tiles[k:k + 5]) for k in range(0, len(tiles), 5)])
    ok, buf = cv2.imencode(".png", g)
    buf.tofile(path)


def run_strips(page="aoharu1", path="sample_images/KakaoTalk_20260731_162400402.png"):
    """RE:Aoharu: 보표마다 원본 위에 라벨 위치를 찍은 띠 그림. 사람이 라벨 없는 머리를 센다."""
    os.makedirs(OUT, exist_ok=True)
    res = preprocess(os.path.join(ROOT, path), pdf_page=0)
    labels = C.snapshot_page(path, 0)["labels"]
    img = res.original_bgr
    for st in res.staves:
        sp = st.spacing
        y0, y1 = max(0, int(st.top - 4 * sp)), min(img.shape[0], int(st.bottom + 4 * sp))
        strip = img[y0:y1].copy()
        for l in labels:
            if y0 <= l["y"] < y1:          # 보표 사이 음표는 두 띠에 다 나오므로 라벨도 둘 다에 그린다
                cv2.circle(strip, (l["x"], l["y"] - y0), int(sp * 0.35), (0, 0, 255), 1)
        h, w = strip.shape[:2]
        for k, x in enumerate(range(0, w, w // 2 + 1)):
            part = strip[:, x:x + w // 2 + 40]
            part = cv2.resize(part, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_NEAREST)
            ok, buf = cv2.imencode(".png", part)
            buf.tofile(os.path.join(OUT, f"{page}_st{st.index}_{k}.png"))
    print(f"{page}: 보표 {len(res.staves)}개, 라벨 {len(labels)}개 → {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strips", action="store_true")
    a = ap.parse_args()
    run_strips() if a.strips else run_pdf()
