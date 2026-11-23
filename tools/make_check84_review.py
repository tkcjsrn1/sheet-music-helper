# -*- coding: utf-8 -*-
"""PR #84 후속 — 눈 확인이 필요한 새 check 28개(음고 오류 4 + 머리 없는 자리 24)의 확대 그림. 측정 전용.

입력: `tools/classify_unstable_checks.py`의 로그(`debug/classify_unstable.log`)에서 해당 행.
칸마다 라벨 좌표 중심 가로 ±4sp · 세로 ±6sp를 **결과 이미지(라벨 있음) | 원본** 으로 나란히 둔다.
결과 이미지는 제품 CLI(`main.run_page`)로 새로 만든다(`debug/check84/`). 한 장에 7칸, 긴 변 1600px 이하.

    python tools/make_check84_review.py        # → docs/review/check84/*.png · README.md
"""
import ast
import contextlib
import glob
import io
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402
from modules.notehead_detect import detect_noteheads  # noqa: E402
from modules.pitch_calculator import calculate_pitches  # noqa: E402
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts  # noqa: E402

OUT = os.path.join(ROOT, "docs", "review", "check84")
WORK = os.path.join(ROOT, "debug", "check84")
FONT = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 15)
FONT_B = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 17)
PER_SHEET = 7
SCALE = 1.25


def page_name(p):
    for k, v in (("bbm", "B♭m "), ("db", "D♭ "), ("em", "Em ")):
        if p.startswith(k):
            return v + p[len(k):] + "쪽"
    return p


def rows():
    out = []
    for line in io.open(os.path.join(ROOT, "debug", "classify_unstable.log"), encoding="utf-8"):
        line = line.strip()
        if line.startswith("('") and line.endswith(")"):
            r = ast.literal_eval(line)
            if r[5] in ("음고 틀림", "머리 없음"):
                out.append(r)
    out.sort(key=lambda r: (r[5] != "음고 틀림",))          # 음고 오류 먼저
    return out


def result_image(page, path, pg):
    """제품 CLI로 결과 이미지를 만들어 읽는다."""
    folder = os.path.join(WORK, page)
    os.makedirs(folder, exist_ok=True)
    found = glob.glob(os.path.join(folder, "*_계이름.png"))
    if not found:
        sys.argv = ["main.py"]
        import main
        args = main.parse_args()
        with contextlib.redirect_stdout(io.StringIO()):
            main.run_page(args, os.path.join(ROOT, path), pg, folder)
        found = glob.glob(os.path.join(folder, "*_계이름.png"))
    return cv2.imdecode(np.fromfile(found[0], np.uint8), cv2.IMREAD_COLOR)


def staff_info(res, x, y):
    """그 좌표 음표가 배정된 보표 번호(제품 음고 계산 결과) · 보표 목록."""
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    n = min(notes, key=lambda m: abs(m.x - x) + abs(m.y - y))
    return n.staff_index if abs(n.x - x) + abs(n.y - y) <= 4 else None


def crop(img, x, y, sp):
    h, w = img.shape[:2]
    x0, x1 = int(x - 4 * sp), int(x + 4 * sp)
    y0, y1 = int(y - 6 * sp), int(y + 6 * sp)
    pad = cv2.copyMakeBorder(img, 400, 400, 400, 400, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    c = pad[y0 + 400:y1 + 400, x0 + 400:x1 + 400].copy()
    cx, cy = x - x0, y - y0
    cv2.circle(c, (int(cx), int(cy)), int(sp * 0.9), (0, 160, 255), 2)   # 라벨 좌표 표시(주황 원)
    return cv2.resize(c, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA)


def tile(no, r, res_img, org_img, sp, staff):
    page, x, y, pitch, text, kind, truth = r
    a, b = crop(res_img, x, y, sp), crop(org_img, x, y, sp)
    gap = 8
    body = np.full((a.shape[0], a.shape[1] * 2 + gap, 3), 255, np.uint8)
    body[:, :a.shape[1]] = a
    body[:, a.shape[1] + gap:] = b
    head_h = 58
    t = Image.new("RGB", (body.shape[1], head_h + body.shape[0]), "white")
    t.paste(Image.fromarray(cv2.cvtColor(body, cv2.COLOR_BGR2RGB)), (0, head_h))
    d = ImageDraw.Draw(t)
    d.text((4, 2), f"#{no}  {page_name(page)}  ({x}, {y})  [{kind}]", font=FONT_B, fill=(0, 0, 0))
    d.text((4, 24), f"라벨 {pitch} ({text}) · 자동 정답 {truth} · 배정 보표 {staff}", font=FONT, fill=(40, 40, 40))
    d.text((4, head_h - 16), "결과(라벨)", font=FONT, fill=(120, 120, 120))
    d.text((a.shape[1] + gap + 4, head_h - 16), "원본", font=FONT, fill=(120, 120, 120))
    d.rectangle([0, 0, t.width - 1, t.height - 1], outline=(180, 180, 180))
    return t


def sheet(tiles, path):
    cols = 2
    rows_n = math.ceil(len(tiles) / cols)
    tw = max(t.width for t in tiles)
    th = max(t.height for t in tiles)
    g = 12
    s = Image.new("RGB", (cols * tw + (cols + 1) * g, rows_n * th + (rows_n + 1) * g), "white")
    for i, t in enumerate(tiles):
        s.paste(t, (g + (i % cols) * (tw + g), g + (i // cols) * (th + g)))
    if max(s.size) > 1600:
        k = 1600 / max(s.size)
        s = s.resize((int(s.width * k), int(s.height * k)), Image.LANCZOS)
    s.save(path)
    return s.size


def main():
    os.makedirs(OUT, exist_ok=True)
    items = rows()
    assert len(items) == 28, len(items)
    pages = {p: (path, pg) for p, path, pg in C.PAGES}
    cache, tiles, dist_rows, meta = {}, [], [], []
    for no, r in enumerate(items, 1):
        page, x, y = r[0], r[1], r[2]
        path, pg = pages[page]
        if page not in cache:
            res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
            cache[page] = (res, result_image(page, path, pg))
        res, res_img = cache[page]
        sp = float(np.median([s.spacing for s in res.staves]))
        staff = staff_info(res, x, y)
        tiles.append(tile(no, r, res_img, res.original_bgr, sp, staff))
        meta.append((no, r, staff))
        if r[5] == "음고 틀림":
            st = {s.index: s for s in res.staves}
            near = sorted(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))[:2]
            between = any(a.bottom < y < b.top for a in res.staves for b in res.staves if b.index == a.index + 1)
            own = st.get(staff)
            dist_rows.append((no, r, staff,
                              (y - (own.top + own.bottom) / 2) / own.spacing if own else None,
                              [(s.index, (y - (s.top + s.bottom) / 2) / s.spacing, s.top, s.bottom) for s in near],
                              between))
    files = []
    for i in range(0, len(tiles), PER_SHEET):
        name = f"check84_{i // PER_SHEET + 1}.png"
        size = sheet(tiles[i:i + PER_SHEET], os.path.join(OUT, name))
        files.append((name, i + 1, min(i + PER_SHEET, len(tiles)), size))
    md = ["# PR #84 후속 — 눈 확인이 필요한 새 check 28개 (2026-09-29)", "",
          "`tools/make_check84_review.py`로 만들었다. 각 칸: 라벨 좌표 중심 가로 ±4sp · 세로 ±6sp, **왼쪽 결과(라벨) · 오른쪽 원본**, "
          "주황 원이 라벨 좌표. 「자동 정답」은 PDF 음표 머리 글리프 + 가장 가까운 보표 기준 음고(`classify_unstable_checks.py`) — "
          "**눈으로 확인한 값이 아니다.** 「배정 보표」는 제품 음고 계산이 그 음표를 붙인 보표 번호.", "",
          "| 파일 | 칸 | 크기(px) |", "|---|---|---|"]
    md += [f"| `{n}` | #{a}~#{b} | {w}×{h} |" for n, a, b, (w, h) in files]
    md += ["", "## 칸 목록", "", "| # | 쪽 | 좌표 | 분류 | 라벨 음고(표기) | 자동 정답 | 배정 보표 |", "|---|---|---|---|---|---|---|"]
    md += [f"| {no} | {page_name(r[0])} | ({r[1]}, {r[2]}) | {r[5]} | {r[3]} ({r[4]}) | {r[6]} | {staff} |" for no, r, staff in meta]
    md += ["", "## 음고 오류 4개 — 보표까지 거리 (sp, 보표 중심 기준, 음표가 아래면 +)", "",
           "| # | 쪽 · 좌표 | 라벨 → 자동 정답 | 배정 보표 · 거리 | 가장 가까운 두 보표 (번호: 거리 · 위줄~아래줄 y) | 두 보표 사이인가 |",
           "|---|---|---|---|---|---|"]
    for no, r, staff, d_own, near, between in dist_rows:
        nd = " / ".join(f"{i}: {d:+.2f}sp · {t}~{b}" for i, d, t, b in near)
        md.append(f"| {no} | {page_name(r[0])} ({r[1]}, {r[2]}) | {r[3]} → {r[6]} | {staff} · "
                  f"{d_own:+.2f}sp | {nd} | {'예' if between else '아니오'} |")
    n_between = sum(1 for d in dist_rows if d[5])
    md += ["", f"**음고 오류 4개 중 두 보표 사이(한 보표 아래줄과 다음 보표 위줄 사이)에 있는 음표: {n_between}개.**", ""]
    io.open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
