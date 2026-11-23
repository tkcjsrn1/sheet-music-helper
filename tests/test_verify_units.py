# -*- coding: utf-8 -*-
"""판정 함수의 합성 이미지 회귀 기준. 실행: python tests/test_verify_units.py"""

import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.preprocess import PreprocessResult, Staff
from modules.notehead_detect import Notehead
from modules.verify import (
    LEDGER_RUN_SP, beam_mask, beam_mask_strict, drop_offstaff_ghosts,
    ledger_run_sp, needed_ledger_ys,
)


def make_staff(sp):
    return Staff([8 * sp + k * sp for k in range(5)], float(sp), 0)


def horizontal_run(image, x, y, length):
    start = x - length // 2
    image[y, start:start + length] = 255


class LedgerRunTests(unittest.TestCase):
    def test_head_width_fails_and_ledger_width_passes(self):
        for sp in (10, 20, 30):
            for width, passes in ((1.2, False), (2.0, True)):
                with self.subTest(sp=sp, width=width):
                    image = np.zeros((8 * sp, 12 * sp), np.uint8)
                    x, y = 6 * sp, 4 * sp
                    horizontal_run(image, x, y, round(width * sp))
                    run = ledger_run_sp(image, x, y, sp)
                    self.assertAlmostEqual(run, width)
                    self.assertEqual(run >= LEDGER_RUN_SP, passes)

    def test_hollow_center_is_bridged_but_large_gap_is_not(self):
        for sp in (10, 20, 30):
            for gap, passes in ((0.4, True), (0.8, False)):
                with self.subTest(sp=sp, gap=gap):
                    image = np.zeros((8 * sp, 12 * sp), np.uint8)
                    x, y = 6 * sp, 4 * sp
                    horizontal_run(image, x, y, 2 * sp)
                    half_gap = round(gap * sp / 2)
                    image[y, x - half_gap:x + half_gap] = 0
                    self.assertEqual(ledger_run_sp(image, x, y, sp) >= LEDGER_RUN_SP, passes)

    def test_blank_and_vertical_outside_rows_have_no_run(self):
        image = np.zeros((40, 80), np.uint8)
        for y in (-10, 20, 50):
            with self.subTest(y=y):
                self.assertEqual(ledger_run_sp(image, 40, y, 10), 0.0)


class NeededLedgerTests(unittest.TestCase):
    def test_inside_staff_and_before_first_ledger_are_not_targets(self):
        for sp in (10, 20, 30):
            staff = make_staff(sp)
            for y in (staff.top, staff.top + sp // 2, staff.bottom,
                      staff.top - sp // 2, staff.bottom + sp // 2,
                      staff.top - sp + 1, staff.bottom + sp - 1):
                with self.subTest(sp=sp, y=y):
                    self.assertIsNone(needed_ledger_ys(staff, y))

    def test_line_and_space_need_the_same_number_of_ledgers(self):
        for sp in (10, 20, 30):
            staff = make_staff(sp)
            for direction, base in ((-1, staff.top), (1, staff.bottom)):
                for k in (1, 2, 3):
                    expected = [base + direction * sp * n for n in range(1, k + 1)]
                    for fraction in (0, 0.5):
                        y = round(base + direction * (k + fraction) * sp)
                        with self.subTest(sp=sp, direction=direction, k=k, fraction=fraction):
                            self.assertEqual(needed_ledger_ys(staff, y), expected)


class OffstaffTests(unittest.TestCase):
    def test_complete_ledgers_keep_head_and_missing_ledger_drops_head(self):
        for sp in (10, 20, 30):
            for direction in (-1, 1):
                with self.subTest(sp=sp, direction=direction):
                    staff = make_staff(sp)
                    binary = np.zeros((20 * sp, 16 * sp), np.uint8)
                    base = staff.top if direction < 0 else staff.bottom
                    y = round(base + direction * 2.5 * sp)
                    good = Notehead(4 * sp, y, 0)
                    bad = Notehead(10 * sp, y, 0, filled=False)
                    for head in (good, bad):
                        cv2.ellipse(binary, (head.x, head.y), (round(0.6 * sp), round(0.3 * sp)),
                                    0, 0, 360, 255, -1 if head.filled else 1)
                    for n in (1, 2):
                        horizontal_run(binary, good.x, base + direction * n * sp, 2 * sp)
                    # 첫 덧줄만 있으면 더 바깥 음표에 필요한 두 번째 덧줄을 대신할 수 없다.
                    horizontal_run(binary, bad.x, base + direction * sp, 2 * sp)
                    result = PreprocessResult(np.zeros((*binary.shape, 3), np.uint8),
                                              np.zeros_like(binary), binary, [staff])
                    kept, dropped = drop_offstaff_ghosts(result, [good, bad])
                    self.assertEqual(kept, [good])
                    self.assertEqual([(d['x'], d['y'], d['reason']) for d in dropped],
                                     [(bad.x, bad.y, '오선 밖인데 덧줄 없음')])

    def test_empty_input(self):
        self.assertEqual(drop_offstaff_ghosts(None, []), ([], []))


class BeamMaskTests(unittest.TestCase):
    def test_crossing_beam_survives_only_in_wide_mask(self):
        for sp in (20, 30):
            with self.subTest(sp=sp):
                staff = make_staff(sp)
                # 페이지 폭 기준 오선 커널보다 짧고, 빔 커널보다 긴 4sp 빔.
                image = np.zeros((20 * sp, 160 * sp), np.uint8)
                for y in staff.line_ys:
                    image[y, sp:-sp] = 255
                x, y = 80 * sp, staff.line_ys[2]
                half_height = round(0.3 * sp)
                image[y - half_height:y + half_height, x - 2 * sp:x + 2 * sp] = 255
                wide = beam_mask(image, [staff])
                strict = beam_mask_strict(image, [staff])
                roi = np.s_[y - half_height:y + half_height, x - sp:x + sp]
                self.assertGreater(np.count_nonzero(wide[roi]), wide[roi].size // 2)
                self.assertEqual(np.count_nonzero(strict[roi]), 0)
                # 빔과 떨어진 순수 오선은 두 방식 모두 남기지 않는다.
                self.assertEqual(np.count_nonzero(wide[:, 2 * sp:4 * sp]), 0)
                self.assertEqual(np.count_nonzero(strict[:, 2 * sp:4 * sp]), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
