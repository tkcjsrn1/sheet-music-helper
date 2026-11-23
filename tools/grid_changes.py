# -*- coding: utf-8 -*-
"""compare_change_impl 출력(debug/compare_<이름>.json)의 바뀐 라벨을 종류별 격자로 (2026-10-13). 칸 제목 = 쪽 · 좌표 · 표기.

    python tools/grid_changes.py <이름> <출력 폴더>
"""
import json, os, sys
from collections import defaultdict
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def main(name, out):
    import measure_sim_ledger_pair as S
    from modules.preprocess import load_image
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 12)
    P = {n: (p, pg) for _s, n, p, pg in S.pages()}
    items = json.load(open(os.path.join(ROOT, "debug", f"compare_{name}.json"), encoding="utf-8"))
    by = defaultdict(list)
    for it in items:
        by[it[0]].append(it)
    os.makedirs(out, exist_ok=True)
    cache = {}
    for kind, v in by.items():
        tiles = []
        for _k, nm, x, y, text in v:
            if nm not in cache:
                p, pg = P[nm]
                cache[nm] = cv2.cvtColor(load_image(os.path.join(ROOT, p), pdf_page=pg), cv2.COLOR_BGR2GRAY)
            g = cache[nm]; h = 55
            c = np.full((2 * h, 2 * h), 255, np.uint8)
            sub = g[max(0, y - h):y + h, max(0, x - h):x + h]
            c[max(0, h - y):max(0, h - y) + sub.shape[0], max(0, h - x):max(0, h - x) + sub.shape[1]] = sub
            t = Image.fromarray(c).convert("RGB").resize((170, 170)); d = ImageDraw.Draw(t)
            d.ellipse((78, 78, 92, 92), outline=(255, 0, 0), width=2)
            b = Image.new("RGB", (170, 190), "white"); b.paste(t, (0, 20))
            ImageDraw.Draw(b).text((2, 2), f"{nm[:14]} {x},{y} {text}", fill=(0, 0, 0), font=font); tiles.append(b)
        safe = kind.replace(" ", "").replace("·", "_").replace("(", "").replace(")", "")
        for k in range(0, len(tiles), 60):
            part = tiles[k:k + 60]
            S_ = Image.new("RGB", (10 * 174, ((len(part) + 9) // 10) * 194), (180, 180, 180))
            for j, t in enumerate(part):
                S_.paste(t, ((j % 10) * 174, (j // 10) * 194))
            p = os.path.join(out, f"{safe}_{k // 60 + 1}.png"); S_.save(p); print(p, len(part))


if __name__ == "__main__":
    main(*sys.argv[1:3])
