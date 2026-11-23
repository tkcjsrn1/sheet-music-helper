# -*- coding: utf-8 -*-
"""사진 입력 M1(`modules/photo_correct.py`) 회귀 검사 — 합성 보표만 쓴다(외부 파일 없음). 2026-09-28.

1. 기울인 보표를 바로잡아 통과한다(각도 부호 · 보표 수)
2. 기본 경로(photo=False)는 M1을 거치지 않는다 — 수평 영상은 그대로, 작은 기울기는 일반 모드 보정 기록을 확인한다
3. 회색 책상 위 종이 — 종이 밖을 잘라내고 통과한다(A-12)
4. 왼쪽 그림자 — **악보 내용을 잘라내지 않는다**(잘라내면 음자리표 쪽이 사라진다, 2026-09-28 실측)
5. 위아래 절반의 기울기가 다른 영상(원근 흉내) — 거부한다(「다시 찍어 주세요」)
"""
import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from modules.preprocess import preprocess, PhotoRejectedError  # noqa: E402

SP = 20
W, H = 1800, 2400
STAVES = 6


def page():
    """흰 종이에 보표 6개 + 보표마다 음표 머리 몇 개."""
    img = np.full((H, W, 3), 255, np.uint8)
    for k in range(STAVES):
        top = 250 + k * 330
        for i in range(5):
            cv2.line(img, (150, top + i * SP), (W - 150, top + i * SP), (0, 0, 0), 2)
        for j, x in enumerate(range(400, W - 250, 160)):
            cv2.ellipse(img, (x, top + (j % 8) * SP // 2), (11, 8), -20, 0, 360, (0, 0, 0), -1)
    return img


def rotate(img, deg, fill=(255, 255, 255)):
    m = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), deg, 1.0)
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=fill)


def save(img):
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(cv2.imencode(".png", img)[1].tobytes())
    return path


class PhotoCorrect(unittest.TestCase):
    def run_photo(self, img):
        path = save(img)
        try:
            return preprocess(path, photo=True)
        finally:
            os.remove(path)

    def test_rotated_page_is_straightened(self):
        r = self.run_photo(rotate(page(), 2.0))
        self.assertEqual(len(r.staves), STAVES)
        self.assertAlmostEqual(r.photo_correction.angle_deg, -2.0, delta=0.02)

    def test_upright_default_path_does_not_touch_the_image(self):
        from unittest.mock import patch
        image = page()
        path = save(image)
        try:
            with patch("modules.photo_correct.correct_photo", side_effect=AssertionError("기본 경로에서 M1 호출")):
                r = preprocess(path)
            self.assertEqual(len(r.staves), STAVES)
            self.assertIsNone(r.photo_correction)
            self.assertEqual(r.deskew_deg, 0.0)
            np.testing.assert_array_equal(r.original_bgr, image)
        finally:
            os.remove(path)

    def test_small_rotation_uses_normal_deskew_without_m1(self):
        from unittest.mock import patch
        image = rotate(page(), 2.0)
        path = save(image)
        try:
            with patch("modules.photo_correct.correct_photo", side_effect=AssertionError("일반 기울기 보정에서 M1 호출")):
                r = preprocess(path)
            self.assertEqual(len(r.staves), STAVES)
            self.assertIsNone(r.photo_correction)
            self.assertAlmostEqual(r.deskew_deg, -2.0, delta=0.02)
            self.assertEqual(r.original_bgr.shape, image.shape)
            self.assertFalse(np.array_equal(r.original_bgr, image))
        finally:
            os.remove(path)

    def test_gray_desk_is_cropped(self):
        pad = 200
        img = cv2.copyMakeBorder(page(), pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(140, 140, 140))
        r = self.run_photo(img)
        self.assertEqual(len(r.staves), STAVES)
        self.assertLess(r.original_bgr.shape[1], img.shape[1] - pad)   # 책상이 잘려 나갔다

    def test_left_shadow_keeps_the_music(self):
        img = page().astype(np.float32)
        img *= (0.45 + 0.55 * np.linspace(0, 1, W, dtype=np.float32))[None, :, None]
        r = self.run_photo(np.clip(img, 0, 255).astype(np.uint8))
        self.assertEqual(len(r.staves), STAVES)
        self.assertGreaterEqual(r.original_bgr.shape[1], W - 20)       # 왼쪽을 잘라내지 않았다

    def test_perspective_like_page_is_rejected(self):
        img = page()
        top, bottom = img[:H // 2], img[H // 2:]
        img = np.vstack([rotate(top, 0.0), rotate(bottom, 1.0)])      # 위는 수평, 아래는 1° — 전역 각 하나로 못 편다
        with self.assertRaises(PhotoRejectedError) as cm:
            self.run_photo(img)
        self.assertIn("다시 찍어", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
