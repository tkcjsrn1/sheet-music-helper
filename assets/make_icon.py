# -*- coding: utf-8 -*-
"""
앱 아이콘 생성 스크립트 (개발용, 한 번만 실행)

컨셉: 앱이 하는 일 그대로 — 오선지 위 음표에 빨간 계이름이 붙은 모습.
초록 그라데이션 라운드 사각형 배경 + 흰 오선 + 8분음표(♪) + 빨간 '도'.

화질: 도형에 안티앨리어싱이 적용되도록 4배 크기로 그린 뒤 LANCZOS로 축소하고,
      16~256px 각 크기를 개별 렌더링해 멀티사이즈 ICO로 저장한다.

실행: venv/Scripts/python assets/make_icon.py  ->  assets/icon.ico, icon.png 생성
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))

TOP_COLOR = (52, 168, 105)     # 밝은 초록
BOTTOM_COLOR = (20, 92, 56)    # 짙은 초록

SS = 4  # 슈퍼샘플링 배율


def _render(size: int) -> Image.Image:
    """지정 크기의 아이콘을 4배 해상도로 그린 뒤 축소해 반환한다."""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    # 세로 그라데이션 배경
    grad = Image.new("RGBA", (big, big))
    gd = ImageDraw.Draw(grad)
    for y in range(big):
        t = y / max(1, big - 1)
        col = tuple(
            int(TOP_COLOR[i] + (BOTTOM_COLOR[i] - TOP_COLOR[i]) * t) for i in range(3)
        ) + (255,)
        gd.line([(0, y), (big, y)], fill=col)

    mask = Image.new("L", (big, big), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)

    # 오선 5줄 (반투명 흰색) — 작은 크기에서는 3줄만 그려 뭉개짐 방지
    n_lines = 5 if size >= 32 else 3
    lw = max(SS, big // 44)
    y_start, y_step = (0.34, 0.11) if n_lines == 5 else (0.36, 0.16)
    for i in range(n_lines):
        y = big * (y_start + y_step * i)
        d.line([(big * 0.10, y), (big * 0.90, y)], fill=(255, 255, 255, 110), width=lw)

    # 직접 그린 음표와 한글 자모 획. 글꼴이나 글리프를 읽지 않는다.
    def points(*coordinates):
        return [(round(big * x), round(big * y)) for x, y in coordinates]

    ink = (255, 255, 255, 255)
    d.ellipse(points((0.26, 0.60), (0.50, 0.80)), fill=ink)
    d.rounded_rectangle(points((0.43, 0.23), (0.50, 0.70)), radius=big // 35, fill=ink)
    d.polygon(points((0.46, 0.23), (0.63, 0.32), (0.70, 0.42), (0.69, 0.53),
                     (0.63, 0.45), (0.55, 0.40), (0.46, 0.36)), fill=ink)

    if size >= 24:
        d.rounded_rectangle(points((0.66, 0.07), (0.94, 0.34)), radius=big // 20, fill=ink)
        red = (198, 33, 44, 255)
        width = max(SS, big // 33)
        d.line(points((0.862, 0.127), (0.751, 0.127), (0.751, 0.200), (0.859, 0.200)),
               fill=red, width=width, joint="curve")
        d.line(points((0.799, 0.237), (0.799, 0.279)), fill=red, width=width)
        d.line(points((0.721, 0.278), (0.879, 0.278)), fill=red, width=width)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = {s: _render(s) for s in sizes}

    imgs[256].save(os.path.join(HERE, "icon.png"))

    # 멀티사이즈 ICO: 각 크기를 개별 렌더링한 이미지로 저장
    imgs[256].save(
        os.path.join(HERE, "icon.ico"),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=[imgs[s] for s in sizes if s != 256],
    )
    print("생성 완료: assets/icon.ico, assets/icon.png (16~256px, 안티앨리어싱)")


if __name__ == "__main__":
    main()
