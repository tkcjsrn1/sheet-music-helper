# -*- coding: utf-8 -*-
"""
1단계(preprocess.py) 검증용 테스트.

실제 스캔된 악보 이미지가 없어도 로직을 검증할 수 있도록,
PIL로 오선 2세트(보표 2개)와 음표 모양의 원(circle)을 직접 그려
합성 테스트 이미지를 만든 뒤 detect_staff_lines / group_into_staves가
올바르게 동작하는지 확인한다.

실행: python tests/test_preprocess.py
"""

import os
import sys

from PIL import Image, ImageDraw

# 상위 폴더(프로젝트 루트)를 import 경로에 추가해 modules 패키지를 불러올 수 있게 한다.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.preprocess import (  # noqa: E402
    preprocess,
    draw_debug_image,
    StaffNotFoundError,
)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_images")
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "debug")


def make_synthetic_sheet(path: str, width: int = 1000, height: int = 700) -> None:
    """오선 2개 보표(각 5줄) + 음표 원(notehead) 몇 개를 그린 합성 악보 이미지를 생성한다."""
    img = Image.new("L", (width, height), color=255)  # 흰 배경, 그레이스케일
    draw = ImageDraw.Draw(img)

    line_spacing = 20  # 오선 한 줄 간 간격(px)
    staff_gap = 150     # 보표와 보표 사이 간격(px)
    staff_top_ys = [100, 100 + staff_gap + line_spacing * 4]

    notehead_positions = []
    for staff_top in staff_top_ys:
        # 오선 5줄 그리기
        for i in range(5):
            y = staff_top + i * line_spacing
            draw.line([(50, y), (width - 50, y)], fill=0, width=2)

        # 음표 머리(타원) 몇 개를 오선 위/칸에 배치
        # 크기는 실제 악보 비율에 맞춤: 폭 약 1.1sp, 높이 약 0.7sp
        for i, x in enumerate(range(150, width - 150, 120)):
            y = staff_top + (i % 5) * (line_spacing // 2)
            draw.ellipse([x - 11, y - 7, x + 11, y + 7], fill=0)
            notehead_positions.append((x, y))

    img.save(path)
    print(f"합성 테스트 이미지 생성됨: {path} (음표 {len(notehead_positions)}개)")


def run_test() -> None:
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)

    sample_path = os.path.join(SAMPLE_DIR, "synthetic_test.png")
    make_synthetic_sheet(sample_path)

    try:
        result = preprocess(sample_path)
    except StaffNotFoundError as e:
        print(f"[실패] 오선 검출 실패: {e}")
        sys.exit(1)

    expected_staff_count = 2
    actual_staff_count = len(result.staves)
    print(f"검출된 보표 수: {actual_staff_count} (기대값: {expected_staff_count})")

    assert actual_staff_count == expected_staff_count, (
        f"보표 개수 불일치: 기대={expected_staff_count}, 실제={actual_staff_count}"
    )

    for st in result.staves:
        print(f"  - 보표 {st.index}: y={st.line_ys}, 간격 평균={st.spacing:.2f}px")
        # 합성 이미지에서 오선 간격을 20px로 그렸으므로, 검출된 간격도 근사해야 한다.
        assert abs(st.spacing - 20) <= 2, f"오선 간격 검출 오차가 큽니다: {st.spacing}"

    debug_path = os.path.join(DEBUG_DIR, "synthetic_test_debug.png")
    draw_debug_image(result, debug_path)
    print(f"디버그 이미지 저장됨: {debug_path}")
    print("[성공] 1단계(오선 검출) 테스트 통과")


if __name__ == "__main__":
    run_test()
