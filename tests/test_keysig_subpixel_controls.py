# -*- coding: utf-8 -*-
"""C-11 정상 조표와 이동 위상의 회귀 검사. G♭ 두 위상은 아직 예상 실패다."""
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from measure_keysig_subpixel_controls import cases, trace_headers
from modules.preprocess import load_image, preprocess


class KeySignatureControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c['id']: c for c in cases()}

    def shifted(self, case_id, dx):
        image = load_image(str(self.cases[case_id]['path']), pdf_dpi=300)
        shifted = cv2.warpAffine(image, np.float64([[1, 0, dx], [0, 1, 0]]),
                                 (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
        with tempfile.TemporaryDirectory(prefix='keysig-controls-test-') as tmp:
            path = Path(tmp) / 'shift.png'
            ok, buf = cv2.imencode('.png', shifted)
            self.assertTrue(ok)
            buf.tofile(path)
            return trace_headers(preprocess(str(path)))

    def assert_source_signature(self, case_id, trace):
        symbol, count, letters = self.cases[case_id]['expected']
        self.assertTrue(trace['staves'], '빈 대조를 통과시키지 않는다')
        self.assertEqual(trace['signature'], [(symbol, count, tuple(letters))])

    def test_all_original_key_signatures_match_declared_sources(self):
        # ♯1~7·♭1~7·C장조 및 조표 없는 두 악보. 픽스처 누락은 실패다.
        self.assertEqual(len(self.cases), 17)
        for case_id, case in self.cases.items():
            with self.subTest(case=case_id):
                self.assert_source_signature(case_id, trace_headers(preprocess(str(case['path']))))

    def test_flat_six_identity_warp_matches_original_trace(self):
        original = trace_headers(preprocess(str(self.cases['Gb_major_flat6']['path'])))
        self.assertEqual(original, self.shifted('Gb_major_flat6', 0))

    def test_bach_negative_half_pixel_keeps_no_key_signature(self):
        # 양의 0.5px만 재면 같은 오류의 반대 방향 재현을 놓친다.
        self.assert_source_signature('bach_minuet_Am', self.shifted('bach_minuet_Am', -0.5))

    @unittest.expectedFailure
    def test_flat_six_negative_quarter_pixel_keeps_six_flats(self):
        # #136 이후에도 ♭6이 ♭5로 줄어든다. 고쳐지면 unexpected success로 알린다.
        self.assert_source_signature('Gb_major_flat6', self.shifted('Gb_major_flat6', -0.25))

    @unittest.expectedFailure
    def test_flat_six_positive_three_quarter_pixel_keeps_six_flats(self):
        # −0.25와 같은 부분화소 위상에서 ♭6 → ♭5가 남는다.
        self.assert_source_signature('Gb_major_flat6', self.shifted('Gb_major_flat6', 0.75))

    def test_flat_five_negative_quarter_pixel_keeps_five_flats(self):
        self.assert_source_signature('Db_major_flat5', self.shifted('Db_major_flat5', -0.25))

    def test_flat_five_positive_three_quarter_pixel_keeps_five_flats(self):
        self.assert_source_signature('Db_major_flat5', self.shifted('Db_major_flat5', 0.75))


if __name__ == '__main__':
    unittest.main(verbosity=2)
