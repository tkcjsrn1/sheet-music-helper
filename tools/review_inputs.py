# -*- coding: utf-8 -*-
"""사용자 실제 악보 점검 — `inputs/`의 이미지 · PDF를 지금 main으로 변환하고 「확실」 라벨 전부를 격자 그림으로 만든다(사람이 판정).

원본 · 결과 · 격자 그림은 커밋하지 않는다(`inputs/` · `debug/`는 저장소 밖으로 나가지 않는다). 경로만 WORKLOG에 적는다.
쪽마다: 결과 이미지(`<이름>_계이름.png`) · 라벨 JSON · 격자 `certain_<쪽>_<번호>.png`(칸 하나 = 라벨 하나, 빨간 원 = 머리 자리,
제목 = 번호 · 좌표 · 계이름) · 목록 `certain_<쪽>.tsv`(번호 · x · y · 보표 · 음고 · 계이름 — 사람이 판정 열을 채운다).

    python tools/review_inputs.py [폴더]     # 기본 inputs/ 전부 → debug/inputs_review/<이름>/
"""
import io
import contextlib
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
IN = os.path.join(ROOT, "inputs")
OUT = os.path.join(ROOT, "debug", "inputs_review")
EXT = (".png", ".jpg", ".jpeg", ".pdf")
COLS, ROWS, TILE = 8, 8, 200


def grid(gray, labels, sp, path_prefix, font):
    """「확실」 라벨마다 머리 둘레 ±3sp를 잘라 8×8 격자 그림 여러 장으로."""
    from PIL import Image, ImageDraw
    H, W = gray.shape
    h = int(sp * 3)
    tiles = []
    for i, l in enumerate(labels, 1):
        c = np.full((2 * h, 2 * h), 255, np.uint8)
        x, y = int(l["x"]), int(l["y"])
        sub = gray[max(0, y - h):min(H, y + h), max(0, x - h):min(W, x + h)]
        c[max(0, h - y):max(0, h - y) + sub.shape[0], max(0, h - x):max(0, h - x) + sub.shape[1]] = sub
        t = Image.fromarray(c).convert("RGB").resize((TILE, TILE))
        d = ImageDraw.Draw(t)
        d.ellipse((TILE / 2 - 9, TILE / 2 - 9, TILE / 2 + 9, TILE / 2 + 9), outline=(255, 0, 0), width=2)
        top = Image.new("RGB", (TILE, 24), "white")
        ImageDraw.Draw(top).text((3, 3), f"{i} ({x},{y}) {l['text']}", fill=(0, 0, 0), font=font)
        both = Image.new("RGB", (TILE, TILE + 24), "white")
        both.paste(top, (0, 0))
        both.paste(t, (0, 24))
        tiles.append(both)
    out = []
    per = COLS * ROWS
    for k in range(0, max(1, len(tiles)), per):
        part = tiles[k:k + per]
        sheet = Image.new("RGB", (COLS * (TILE + 4), max(1, (len(part) + COLS - 1) // COLS) * (TILE + 28)), (180, 180, 180))
        for j, t in enumerate(part):
            sheet.paste(t, ((j % COLS) * (TILE + 4), (j // COLS) * (TILE + 28)))
        p = f"{path_prefix}_{k // per + 1}.png"
        sheet.save(p)
        out.append(p)
    return out


def one(path):
    import main as MAIN
    from modules.preprocess import load_image, pdf_page_count
    from PIL import ImageFont
    import cv2
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    name = os.path.splitext(os.path.basename(path))[0]
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    pages = range(pdf_page_count(path)) if path.lower().endswith(".pdf") else [0]
    rows = []
    for pg in pages:
        js = os.path.join(d, f"labels_p{pg + 1}.json")
        sys.argv = ["main.py", path, "--page", str(pg), "--no-debug", "--output-dir", d, "--save-labels", js]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                MAIN.run_page(MAIN.parse_args(), path, pg, d)
        except SystemExit as e:
            rows.append((name, pg + 1, f"실패: {e}", 0, 0, ""))
            continue
        doc = json.load(open(js, encoding="utf-8"))
        cert = sorted((l for l in doc["labels"] if l["confidence"] == "certain"), key=lambda l: (l["staff"], l["x"]))
        sp = float(np.median([s["spacing"] for s in doc["staves"]])) if doc["staves"] else 20.0
        gray = cv2.cvtColor(load_image(path, pdf_page=pg), cv2.COLOR_BGR2GRAY)
        sheets = grid(gray, cert, sp, os.path.join(d, f"certain_p{pg + 1}"), font)
        with open(os.path.join(d, f"certain_p{pg + 1}.tsv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["번호", "x", "y", "보표", "음고", "계이름", "판정(맞음/유령/음고틀림/표기틀림)"])
            for i, l in enumerate(cert, 1):
                w.writerow([i, l["x"], l["y"], l["staff"], l["pitch"], l["text"], ""])
        rows.append((name, pg + 1, "완료", len(doc["labels"]), len(cert), " ".join(os.path.relpath(s, ROOT) for s in sheets)))
    return rows


def main(src=IN):
    files = sorted(os.path.join(src, f) for f in os.listdir(src) if f.lower().endswith(EXT)) if os.path.isdir(src) else []
    if not files:
        print("inputs/에 이미지 · PDF가 없습니다")
        return
    for f in files:
        for name, pg, st, n, c, sheets in one(f):
            print(f"{name} {pg}쪽 {st} · 라벨 {n} · 확실 {c} · 격자 {sheets}")


if __name__ == "__main__":
    main(*sys.argv[1:])
