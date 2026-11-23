# -*- coding: utf-8 -*-
"""
조표(♭), 임시표(♮), 박자표(3/4, 6/8) 합성 검증 테스트
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
from modules.note_namer import to_solfege_batch

SP = 20
TOP = 100


def _draw_treble_clef(img, x, y):
    """높은음자리표 근사 이미지 (폭 ~3.5sp, 세로 7sp)"""
    cv2.circle(img, (x + 30, y + 2 * SP), 15, 0, 3)
    cv2.line(img, (x + 30, y - int(SP * 1.5)), (x + 30, y + int(SP * 4.5)), 0, 4)
    cv2.circle(img, (x + 25, y + int(SP * 4.5)), 5, 0, -1)


def _draw_flat_keysig(img, x, y, count=2):
    """♭ 조표: B4(y+2sp), E5(y+0.5sp)"""
    flats_y = [y + 2 * SP, y + int(SP * 0.5), y - int(SP * 0.5)]
    for i in range(min(count, len(flats_y))):
        fx = x + i * 14
        fy = flats_y[i]
        cv2.line(img, (fx, fy - int(SP * 1.25)), (fx, fy + int(SP * 0.5)), 0, 2)
        cv2.ellipse(img, (fx + 4, fy + 2), (6, 6), 0, -90, 180, 0, 2)


def _draw_time_sig_34(img, x, y):
    """
    박자표 3/4.

    실제 조판에서 박자표 숫자는 오선을 **정확히 꽉 채운다** — 분자가 맨 윗줄에서
    가운뎃줄까지, 분모가 가운뎃줄에서 맨 아랫줄까지다. 박자표 판별식이 바로 이
    성질(위끝 ±0.05sp / 아래끝 +0.10~0.15sp, 악보 4종 실측)에 기대고 있으므로
    합성 이미지도 같은 규칙으로 그려야 의미 있는 검증이 된다.
    """
    thick = 6                              # 조판된 박자표 숫자는 아주 굵다
    for digit, top in (("3", y), ("4", y + 2 * SP)):
        scale = 1.0
        (_w, h), _b = cv2.getTextSize(digit, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        scale *= (2 * SP) / max(1, h)      # 글자 높이를 정확히 2sp로 맞춘다
        (w, h), _b = cv2.getTextSize(digit, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        cv2.putText(img, digit, (x, top + h), cv2.FONT_HERSHEY_SIMPLEX, scale, 0, thick)
        # 조판 숫자는 위·아래 끝이 굵은 가로 마무리로 오선 줄에 딱 맞물린다.
        # 이 마무리가 없으면 오선 제거가 글자 끝을 오선으로 오인해 지워버려
        # '오선을 꽉 채운다'는 박자표 판별 근거가 성립하지 않는다.
        for edge in (top, top + 2 * SP - thick // 2):
            cv2.rectangle(img, (x + 2, edge), (x + w - 2, edge + thick // 2), 0, -1)


def main():
    path = os.path.join(os.path.dirname(__file__), "..", "sample_images", "synthetic_flat_timesig.png")
    W, H = 1000, 300
    img = np.full((H, W), 255, dtype=np.uint8)

    for i in range(5):
        cy = TOP + i * SP
        cv2.line(img, (40, cy), (W - 40, cy), 0, 2)

    _draw_treble_clef(img, 50, TOP)
    _draw_flat_keysig(img, 110, TOP, count=2)  # B♭, E♭ (조표 2개)
    _draw_time_sig_34(img, 200, TOP)           # 3/4 박자표 (조표와 실제 조판만큼 띄움)

    # 첫 음표: B4 (x=260), E5 (x=380), B4+♮ (x=510)
    cv2.ellipse(img, (260, TOP + 2 * SP), (11, 8), 0, 0, 360, 0, -1)
    cv2.ellipse(img, (380, TOP + int(SP * 0.5)), (11, 8), 0, 0, 360, 0, -1)
    cv2.ellipse(img, (510, TOP + 2 * SP), (11, 8), 0, 0, 360, 0, -1)

    # ♮(자연표) 그려주기 (x=482)
    nx = 482
    ny = TOP + 2 * SP
    cv2.line(img, (nx, ny - int(SP * 1.1)), (nx, ny + int(SP * 0.5)), 0, 2)
    cv2.line(img, (nx + 9, ny - int(SP * 0.5)), (nx + 9, ny + int(SP * 1.1)), 0, 2)
    for dy in (-6, 7):
        cv2.line(img, (nx - 1, ny + dy - 2), (nx + 11, ny + dy + 2), 0, 4)

    ok, buf = cv2.imencode(".png", img)
    buf.tofile(path)

    res = preprocess(path)
    ctx = analyze_staves(res)
    noteheads = detect_noteheads(res, contexts=ctx)
    pitched = calculate_pitches(noteheads, res.staves, clef="treble")
    pitched.sort(key=lambda n: n.x)
    accs = annotate_accidentals(res, ctx, pitched)
    pitched, accs = remove_accidental_ghosts(pitched, accs, res.staves)

    key_letters, key_symbol = (), ""
    if ctx and ctx[0].clef_found:
        key_letters, key_symbol = ctx[0].key_letters, ctx[0].key_symbol

    named = to_solfege_batch(pitched, key_letters, key_symbol, accs, "solfege")
    solfeges = [s for _, s in named]
    print(f"검출된 조표: {key_symbol} {len(key_letters)}개 ({key_letters})")
    print(f"검출된 계이름: {solfeges}")

    # 음자리표도 본다 — 음고 계산에 treble을 고정으로 넣으므로, 검출이 bass로 뒤집혀도
    # 이 테스트의 계이름은 안 바뀐다. 실제 파이프라인은 검출값을 쓴다.
    assert ctx and ctx[0].clef_found and ctx[0].clef == "treble", \
        f"높은음자리표 기대, 실제 {ctx[0].clef if ctx else '보표 없음'}"
    assert (key_symbol, len(key_letters)) == ("♭", 2), \
        f"조표 ♭2개 기대, 실제 {key_symbol}{len(key_letters)}개"
    assert len(pitched) == 3, f"음표 3개 기대, 실제 {len(pitched)}개"
    assert solfeges == ["시b", "미b", "시"], f"계이름 결과 불일치: {solfeges}"
    print("[성공] ♭ 조표 + ♮ 임시표 + 3/4 박자표 합성 테스트 통과!")


if __name__ == "__main__":
    main()
