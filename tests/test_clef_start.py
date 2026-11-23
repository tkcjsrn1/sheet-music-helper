# -*- coding: utf-8 -*-
"""음자리표 클러스터 **시작점** 회귀 검사 (A-8 2단계, 2026-09-28).

음자리표 앞에 괄호 → 빈칸 → 시스템 세로줄이 오면, 짧은 빈칸이 `max_g` 안이라 괄호와 세로줄이 한 덩어리(1.48sp)로
붙어 음자리표 폭 조건(≥ 1.4sp)을 통과했다. 그 조각이 음자리표가 되어 음자리표 끝이 진짜 음자리표 **앞**에서 정해졌다.
지금까지는 음자리표 끝 상한 `xc + 5sp`가 가려 줬다(상한을 떼면 골든 p1 조표가 통째로 사라진다,
`docs/KEYSIG_CLEF_GAP.md` §9). 근거와 측정은 같은 문서.

- 합성: 괄호(0.85sp) · 빈칸(0.43sp) · 세로줄(0.26sp) · 빈칸(0.6sp) · 음자리표 — 음자리표 끝이 음자리표 오른쪽 틈에 와야 한다
- 실제: RE:Aoharu 1쪽 들여쓴 첫 시스템(보표 0·1)과 괄호에서 시작하는 보표들 — 없으면 건너뛴다
"""
import os
import sys
import unittest

import cv2
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from modules.preprocess import Staff, preprocess  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402

SP = 20
AOHARU_P1 = os.path.join(ROOT, "sample_images", "KakaoTalk_20260731_162400402.png")


def synthetic():
    """보표 하나: x 40 괄호 · x 57~65 빈칸 · x 66 세로줄 · x 71~85 빈칸(오선 행 밖 0.6sp) · x 86 음자리표(폭 ~1.7sp) · 그 뒤 빈칸."""
    h, w = 400, 400
    top = 150
    ys = [top + i * SP for i in range(5)]
    img = np.full((h, w), 255, np.uint8)
    for y in ys:
        cv2.line(img, (20, y), (w - 20, y), 0, 2)
    x = 40
    cv2.rectangle(img, (x, top - SP), (x + 16, ys[-1] + SP), 0, -1)            # 괄호 조각 0.85sp
    x = 66
    cv2.rectangle(img, (x, top), (x + 4, ys[-1]), 0, -1)                       # 세로줄 0.26sp
    cx = 103                                                                   # 음자리표: 고리 + 세로획. 세로줄과의 빈칸(오선 행 밖) 12px = 0.6sp (RE:Aoharu 0.61sp)
    cv2.circle(img, (cx, top + 2 * SP), 16, 0, 3)
    cv2.line(img, (cx, top - int(SP * 1.5)), (cx, ys[-1] + int(SP * 1.5)), 0, 4)
    binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)[1]
    staff = Staff(line_ys=ys, spacing=float(SP), index=0, bottom_fit=float(ys[-1]))
    return binary, staff, (cx - 18, cx + 18)


class SyntheticBraceBarline(unittest.TestCase):
    def test_clef_end_is_after_the_clef_not_the_brace(self):
        binary, staff, (clef_l, clef_r) = synthetic()
        ns = remove_staff_lines(binary, [staff])
        ctx = CK._analyze_one(ns, staff, binary.shape[0], single_system=True)
        self.assertTrue(ctx.clef_found)
        self.assertGreaterEqual(ctx.clef_end, clef_r - 2,
                                f"음자리표 끝 {ctx.clef_end}이 음자리표({clef_l}~{clef_r}) 안이나 앞이다 — 괄호 조각을 음자리표로 잡았다")


@unittest.skipUnless(os.path.isfile(AOHARU_P1), "RE:Aoharu 1쪽이 없다")
class AoharuClefStart(unittest.TestCase):
    """좌표는 `tools/measure_clef_start.py touch`·`tools/measure_clef_gap.py`로 잰 원본 1쪽 값."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = CK.analyze_staves(preprocess(AOHARU_P1))

    def test_indented_first_system(self):
        # 괄호 268 · 세로줄 282 · 음자리표 293~322 · 조표 336~
        for i in (0, 1):
            self.assertTrue(318 <= self.ctx[i].clef_end < 336, f"보표 {i} clef_end {self.ctx[i].clef_end}")

    def test_brace_start_staves_end_in_the_clef_key_gap(self):
        # 괄호 210 · 세로줄 225 · 음자리표 235~ · 음자리표-조표 틈 [265, 278]
        for i in (3, 5, 7, 9, 11):
            self.assertTrue(262 <= self.ctx[i].clef_end <= 278, f"보표 {i} clef_end {self.ctx[i].clef_end}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
