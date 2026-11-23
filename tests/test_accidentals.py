# -*- coding: utf-8 -*-
"""
임시표(♯/♭/♮) 검출 테스트

합성 오선지에 음표 4개를 그리고, 각각 앞에 ♯/♭/♮/(없음) 글리프를 그린 뒤
annotate_accidentals가 올바르게 분류하는지, 그리고 같은 마디 안에서
임시표가 지속되고 바라인을 넘으면 초기화되는지 검증한다.
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts

SP = 20  # 오선 간격(px)
TOP = 100


def _draw_sharp(img, x, y):
    """♯: 세로 막대 2개 + 가로 굵은 획 2개"""
    h = int(SP * 1.25)
    for dx in (0, 9):
        cv2.line(img, (x + dx, y - h), (x + dx, y + h), 0, 2)
    for dy in (-6, 7):
        cv2.line(img, (x - 5, y + dy - 2), (x + 14, y + dy + 2), 0, 4)


def _draw_flat(img, x, y):
    """♭: 세로 막대 1개 + 오른쪽 아래 고리(구멍 있는 반원)"""
    h = int(SP * 1.25)
    cv2.line(img, (x, y - h), (x, y + int(SP * 0.5)), 0, 2)
    cv2.ellipse(img, (x + 4, y + 2), (7, 7), 0, -90, 180, 0, 2)


def _draw_natural(img, x, y):
    """♮: 왼쪽 막대는 위로, 오른쪽 막대는 아래로 삐져나옴 + 가로 획 2개"""
    h = int(SP * 1.1)
    cv2.line(img, (x, y - h), (x, y + int(SP * 0.5)), 0, 2)          # 왼쪽(위로 김)
    cv2.line(img, (x + 9, y - int(SP * 0.5)), (x + 9, y + h), 0, 2)  # 오른쪽(아래로 김)
    for dy in (-6, 7):
        cv2.line(img, (x - 1, y + dy - 2), (x + 11, y + dy + 2), 0, 4)


def make_image(path):
    W, H = 900, 300
    img = np.full((H, W), 255, dtype=np.uint8)

    # 오선 5줄
    for i in range(5):
        y = TOP + i * SP
        cv2.line(img, (40, y), (W - 40, y), 0, 2)

    # 바라인: x=500 (마디 1: ~500, 마디 2: 500~)
    cv2.line(img, (500, TOP), (500, TOP + 4 * SP), 0, 2)

    note_y = TOP + 2 * SP  # 가운데 줄 (treble이라 치면 B4)

    # 마디 1: ♯ 붙은 음표(x=150) -> 같은 음 또 등장(x=300, 임시표 지속 기대)
    cv2.ellipse(img, (150, note_y), (11, 8), 0, 0, 360, 0, -1)
    _draw_sharp(img, 118, note_y)
    cv2.ellipse(img, (300, note_y), (11, 8), 0, 0, 360, 0, -1)

    # 마디 2 (바라인 이후): 같은 음이지만 임시표 초기화 기대(x=600),
    # ♭ 붙은 음표(x=700), ♮ 붙은 음표(x=800)
    cv2.ellipse(img, (600, note_y), (11, 8), 0, 0, 360, 0, -1)
    _draw_flat(img, 672, note_y)
    cv2.ellipse(img, (700, note_y), (11, 8), 0, 0, 360, 0, -1)
    _draw_natural(img, 772, note_y)
    cv2.ellipse(img, (800, note_y), (11, 8), 0, 0, 360, 0, -1)

    ok, buf = cv2.imencode(".png", img)
    buf.tofile(path)


def main():
    path = os.path.join(os.path.dirname(__file__), "..", "sample_images", "synthetic_accidental.png")
    make_image(path)

    result = preprocess(path)
    assert len(result.staves) == 1, f"보표 1개 기대, {len(result.staves)}개 검출"

    contexts = analyze_staves(result)
    noteheads = detect_noteheads(result, contexts=contexts)
    pitched = calculate_pitches(noteheads, result.staves, clef="treble")
    pitched.sort(key=lambda n: n.x)

    accs = annotate_accidentals(result, contexts, pitched)
    pitched, accs = remove_accidental_ghosts(pitched, accs, result.staves)
    xs = [n.x for n in pitched]
    assert len(pitched) == 5, f"음표 5개 기대, {len(pitched)}개 검출 (x={xs})"
    expected = ["#", "#", "", "b", "natural"]
    labels = ["♯직접", "♯지속(같은 마디)", "초기화(다음 마디)", "♭직접", "♮직접"]
    ok = True
    for i, (exp, got, lab) in enumerate(zip(expected, accs, labels)):
        mark = "OK" if exp == got else "FAIL"
        if exp != got:
            ok = False
        print(f"  x={pitched[i].x:4d} {lab}: 기대='{exp}' 검출='{got}' [{mark}]")

    if not ok:
        print("[실패] 임시표 테스트 실패")
        sys.exit(1)
    print("[성공] 임시표 검출/지속/초기화 테스트 통과")


if __name__ == "__main__":
    main()
