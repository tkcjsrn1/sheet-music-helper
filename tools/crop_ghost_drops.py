# -*- coding: utf-8 -*-
"""`remove_accidental_ghosts`가 지운 자리를 **잘라서 눈으로 본다**.

측정 전용. `modules/`는 읽기만 한다.

`CLAUDE.md` §3의 5번 — 「지울 후보를 전부 격자로 잘라 눈으로 본다. 정밀도 숫자만
보면 못 찾는다」. 이 규약을 이 건에 적용하는 도구다.

빨간 사각형 = 지워진 음표, 파란 사각형 = 그 삭제를 부른 '방아쇠' 음표.
크롭 위에 `지워진 x·음고·자기임시표`를 적는다.

OpenCV `imwrite`는 한글 경로에서 조용히 실패하므로 `imencode`로 쓴다(`CLAUDE.md` §6).

사용법:
    python tools/crop_ghost_drops.py <악보경로> [PDF쪽번호] [출력폴더]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

from measure_accidental_ghost_drops import survey


def _write(path, img):
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG 인코딩 실패")
    with open(path, "wb") as f:
        f.write(buf.tobytes())


def main():
    path = sys.argv[1]
    page = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "debug/ghost_drops"
    os.makedirs(out_dir, exist_ok=True)

    from modules.preprocess import preprocess
    _s, hits, _n, _a = survey(path, page)
    bgr = preprocess(path, pdf_page=page).original_bgr

    # 지워진 음표별로 한 장. 같은 것을 여러 방아쇠가 부르면 첫 방아쇠를 쓴다.
    by_drop = {}
    for h in hits:
        by_drop.setdefault(h["i"], h)

    made = []
    for n, (i, h) in enumerate(sorted(by_drop.items(), key=lambda kv: (kv[1]["y"], kv[1]["x"]))):
        cx = (h["x"] + h["trig_x"]) // 2
        cy = (h["y"] + h["trig_y"]) // 2
        half_w, half_h = 130, 90
        x0, x1 = max(0, cx - half_w), min(bgr.shape[1], cx + half_w)
        y0, y1 = max(0, cy - half_h), min(bgr.shape[0], cy + half_h)
        crop = bgr[y0:y1, x0:x1].copy()
        crop = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_NEAREST)

        def box(px, py, color):
            ax, ay = int((px - x0) * 2), int((py - y0) * 2)
            cv2.rectangle(crop, (ax - 22, ay - 18), (ax + 22, ay + 18), color, 2)

        box(h["x"], h["y"], (0, 0, 255))          # 지워진 것 — 빨강
        box(h["trig_x"], h["trig_y"], (255, 0, 0))  # 방아쇠 — 파랑
        tag = (f"drop x={h['x']} y={h['y']} {h['pitch']} acc={h['own_acc'] or '-'}"
               f" | trig {h['trig_pitch']} {h['trig_acc']} dx={h['dx_sp']:.2f}sp"
               f" dstep={h['dstep']:+.1f}")
        cv2.putText(crop, tag, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 200), 1)
        name = f"{n:03d}_x{h['x']}_y{h['y']}_{h['own_acc'] or 'none'}.png"
        _write(os.path.join(out_dir, name), crop)
        made.append(name)

    print(f"{len(made)}장 저장: {out_dir}")
    for m in made:
        print("  " + m)


if __name__ == "__main__":
    main()
