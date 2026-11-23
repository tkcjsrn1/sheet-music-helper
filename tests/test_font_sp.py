# -*- coding: utf-8 -*-
"""같은 설정값의 라벨 크기가 해당 보표 간격을 따른다."""

import os
import sys
import tempfile
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.renderer import _find_korean_font, render_solfege_on_image


def main():
    image = np.full((450, 800, 3), 255, dtype=np.uint8)
    small = SimpleNamespace(staff_index=0, x=120, y=120)
    large = SimpleNamespace(staff_index=1, x=600, y=320)
    with tempfile.TemporaryDirectory() as folder:
        placed = render_solfege_on_image(
            image, [(small, "도"), (large, "도")], os.path.join(folder, "font.png"),
            font_size=18, staff_spacings={0: 12, 1: 24})
    sizes = {p["note"].staff_index: (p["w"], p["h"]) for p in placed}
    canvas = ImageDraw.Draw(Image.new("RGB", (100, 100)))
    for idx, font_px in ((0, 16), (1, 26)):
        font = ImageFont.truetype(_find_korean_font(), font_px)
        box = canvas.textbbox((0, 0), "도", font=font)
        assert sizes[idx] == (box[2] - box[0], box[3] - box[1]), (idx, sizes)
    assert sizes[1][0] > sizes[0][0] * 1.5, sizes
    assert sizes[1][1] > sizes[0][1] * 1.5, sizes
    print("보표 간격 12px · 24px의 글꼴 비례: 통과")


if __name__ == "__main__":
    main()
