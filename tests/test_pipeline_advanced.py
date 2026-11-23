# -*- coding: utf-8 -*-
"""
전체 파이프라인(1~5단계) 심화 검증 테스트.

기본 test_preprocess.py보다 까다로운 케이스를 다룬다:
  - 레저선(ledger line) 위/아래에 걸친 음표 (예: 가운데 도=C4, 높은 라=A5)
  - 채워진 음표(4분음표, filled=True) vs 빈 음표(2분음표, filled=False) 구분
  - 실제 손으로 계산한 정답 음이름과 비교해 pitch_calculator 정확도 검증

실행: python tests/test_pipeline_advanced.py
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.preprocess import preprocess  # noqa: E402
from modules.notehead_detect import detect_noteheads  # noqa: E402
from modules.pitch_calculator import calculate_pitches  # noqa: E402
from modules.note_namer import to_solfege_batch  # noqa: E402
from modules.renderer import render_solfege_on_image  # noqa: E402

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_images")
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "debug")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

STAFF_TOP = 200
SPACING = 24  # 오선 간격(px) - 넉넉하게 잡아 음표 판별 여유 확보
BOTTOM_LINE_Y = STAFF_TOP + 4 * SPACING  # 최하단 오선 y = E4 기준선
HALF_STEP = SPACING / 2.0


def y_for_step(step: int) -> int:
    """치료블 클레프 기준, 최하단 오선(E4)에서 step(반칸 단위)만큼 떨어진 y좌표 계산"""
    return int(round(BOTTOM_LINE_Y - step * HALF_STEP))


def make_advanced_sheet(path: str, width: int = 900, height: int = 500) -> list:
    """
    레저선 음표 + 채워진/빈 음표가 섞인 악보를 합성 생성한다.
    반환값: [(x, y, expected_note_name, expected_octave, expected_filled), ...] 정답 리스트
    """
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)

    for i in range(5):
        y = STAFF_TOP + i * SPACING
        draw.line([(50, y), (width - 50, y)], fill=0, width=2)

    # (step, x, filled, 기대 음이름, 기대 옥타브)
    # step 계산 근거: 절대인덱스 = 30(E4) + step, letter=NOTE_CYCLE[abs%7], octave=abs//7
    plan = [
        (-2, 150, True, "C", 4),   # 레저선 아래 가운데 도 (4분음표, 채워짐)
        (0, 300, True, "E", 4),    # 최하단 오선 = E4 (4분음표, 채워짐)
        (3, 450, False, "A", 4),   # 두 번째 칸 위쪽 = A4 (2분음표, 빈 음표)
        (8, 600, True, "F", 5),    # 최상단 오선 위 = F5 (4분음표, 채워짐)
        (10, 750, False, "A", 5),  # 레저선 위 라 (2분음표, 빈 음표)
    ]

    expected = []
    r = 13  # 음표 가로 반지름(px) - 실제 악보 비율(폭 약 1.1sp, 높이 약 0.8sp)에 맞춤
    for step, x, filled, note_name, octave in plan:
        y = y_for_step(step)

        # 레저선 밖(오선 범위 밖)에 위치한 음표는 짧은 레저선을 함께 그린다 (시각적 사실성용)
        if y < STAFF_TOP - SPACING / 2 or y > BOTTOM_LINE_Y + SPACING / 2:
            draw.line([(x - r - 4, y), (x + r + 4, y)], fill=0, width=2)

        if filled:
            draw.ellipse([x - r, y - r * 0.75, x + r, y + r * 0.75], fill=0)
        else:
            # 빈 음표(2분음표): 테두리만 그려서 내부가 흰색으로 남도록 함 (fill_ratio 낮게)
            draw.ellipse([x - r, y - r * 0.75, x + r, y + r * 0.75], outline=0, width=3)

        expected.append((x, y, note_name, octave, filled))

    img.save(path)
    return expected


def run_test() -> None:
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sample_path = os.path.join(SAMPLE_DIR, "synthetic_advanced.png")
    expected = make_advanced_sheet(sample_path)

    # ---- 1단계 ----
    result = preprocess(sample_path)
    assert len(result.staves) == 1, f"보표 1개 기대, 실제 {len(result.staves)}개"
    print(f"[1단계] 보표 {len(result.staves)}개 검출, 간격={result.staves[0].spacing:.2f}px")

    # ---- 2단계 ----
    noteheads = detect_noteheads(result)
    print(f"[2단계] 음표 {len(noteheads)}개 검출 (기대 {len(expected)}개)")
    assert len(noteheads) == len(expected), (
        f"검출된 음표 수 불일치: 기대={len(expected)}, 실제={len(noteheads)}\n"
        f"검출 결과: {[(n.x, n.y, n.filled) for n in noteheads]}"
    )

    # x좌표 기준으로 정렬해 기대값과 1:1 매칭
    noteheads_sorted = sorted(noteheads, key=lambda n: n.x)
    expected_sorted = sorted(expected, key=lambda e: e[0])

    for nh, (ex, ey, e_note, e_oct, e_filled) in zip(noteheads_sorted, expected_sorted):
        assert abs(nh.x - ex) <= 5, f"x좌표 오차 큼: 검출={nh.x}, 기대={ex}"
        assert abs(nh.y - ey) <= 5, f"y좌표 오차 큼: 검출={nh.y}, 기대={ey}"
        assert nh.filled == e_filled, (
            f"채움 여부 판정 오류: x={nh.x} 검출={nh.filled}, 기대={e_filled}"
        )

    # ---- 3단계 ----
    pitched = calculate_pitches(noteheads_sorted, result.staves, clef="treble")
    print("[3단계] 음고 계산 결과:")
    for p, (ex, ey, e_note, e_oct, e_filled) in zip(pitched, expected_sorted):
        status = "OK" if (p.note_name == e_note and p.octave == e_oct) else "MISMATCH"
        print(f"  x={p.x:4d} -> {p.note_name}{p.octave}  (기대 {e_note}{e_oct})  [{status}]")
        assert p.note_name == e_note and p.octave == e_oct, (
            f"음고 계산 불일치: x={p.x} 검출={p.note_name}{p.octave}, 기대={e_note}{e_oct}"
        )

    # ---- 4단계 ----
    notes_with_solfege = to_solfege_batch(pitched)
    print("[4단계] 계이름 변환:", [s for _, s in notes_with_solfege])

    # ---- 5단계 ----
    output_path = os.path.join(OUTPUT_DIR, "result_advanced.png")
    render_solfege_on_image(result.original_bgr, notes_with_solfege, output_path)
    print(f"[5단계] 결과 이미지 저장: {output_path}")

    print("\n[성공] 심화 파이프라인 테스트 통과 (레저선 + 채워진/빈 음표 판별 포함)")


if __name__ == "__main__":
    run_test()
