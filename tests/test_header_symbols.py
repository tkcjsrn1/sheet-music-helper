"""박자표 숫자·조표 유령 재발 방지: 실제 두 조판과 첫 음표 보존."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as CLI
from modules.clef_keysig import analyze_staves
from modules.preprocess import preprocess


class HeaderSymbols(unittest.TestCase):
    def test_quartet_numbers_are_header_and_real_first_notes_survive(self):
        for font, end in (("bravura", 365), ("leipzig", 362)):
            with self.subTest(font=font), tempfile.TemporaryDirectory() as out:
                path = ROOT / f"test_scores/verovio/beethoven_op18no1_{font}_p1.png"
                self.assertTrue(path.is_file(), "박자표 회귀 입력이 없습니다")
                result = preprocess(str(path))
                contexts = analyze_staves(result)
                for i in range(4):
                    self.assertGreaterEqual(contexts[i].header_end, end,
                                            "찾은 박자표 끝을 최종 경계에서 버렸습니다")
                    self.assertLess(contexts[i].header_end, 400, "첫 음표를 삼켰습니다")
                # 뒤 시스템의 비올라 음표·이음줄은 박자표와 다릅니다.
                self.assertEqual(contexts[6].header_end, 288 if font == "bravura" else 287)
                argv = ["main.py", str(path), "--no-debug", "--output-dir", out]
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    CLI.run_page(CLI.parse_args(), str(path), 0, out)
                labels = json.loads((Path(out) / (path.stem + "_라벨.json")).read_text(encoding="utf-8"))["labels"]
                self.assertFalse([r for r in labels if r["staff"] < 4 and 300 <= r["x"] <= end],
                                 "조표·3/4 숫자 획 위에 계이름이 남았습니다")
                for i in (0, 1):
                    first = [r for r in labels if r["staff"] == i and 400 <= r["x"] <= 415
                             and r["pitch"] == "F4" and r["text"] == "파"]
                    self.assertEqual(len(first), 1, "첫 실제 F4 음표가 사라졌습니다")

    def test_subpixel_shift_preserves_header_and_first_pitch(self):
        import cv2
        import numpy as np
        path = ROOT / "test_scores/verovio/beethoven_op18no1_bravura_p1.png"
        original = preprocess(str(path)).original_bgr
        for dx, dy in ((0.25, 0), (0.5, 0), (0.75, 0), (0, 0.5), (0.5, 0.5)):
            with self.subTest(dx=dx, dy=dy), tempfile.TemporaryDirectory() as out:
                moved = cv2.warpAffine(original, np.float32([[1,0,dx],[0,1,dy]]),
                                       (original.shape[1], original.shape[0]),
                                       flags=cv2.INTER_LINEAR, borderValue=(255,255,255))
                self.assertFalse(np.array_equal(original, moved), "재표본화가 생략된 대조입니다")
                p = Path(out) / "phase.png"
                cv2.imencode(".png", moved)[1].tofile(str(p))
                result = preprocess(str(p))
                contexts = analyze_staves(result)
                for i in range(4):
                    self.assertGreaterEqual(contexts[i].header_end, 365,
                                            "재표본화 뒤 박자표 경계가 다시 열렸습니다")
                    self.assertLess(contexts[i].header_end, 400)
                # 머리 존재만 보면 p와 붙어 y가 밀린 F4→E4 오판을 놓친다.
                # 실제 CLI의 임시표·구제·확신도 경로를 거친 최종 표기까지 본다.
                argv = ["main.py", str(p), "--no-debug", "--output-dir", out]
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                    CLI.run_page(CLI.parse_args(), str(p), 0, out)
                labels = json.loads((Path(out) / "phase_라벨.json").read_text(encoding="utf-8"))["labels"]
                self.assertFalse([r for r in labels if r["staff"] < 4 and 300 <= r["x"] <= 364])
                for i in (0, 1):
                    first = [r for r in labels if r["staff"] == i and 400 <= r["x"] <= 415]
                    self.assertEqual([(r["pitch"], r["text"]) for r in first], [("F4", "파")],
                                     "재표본화 뒤 첫 음의 음고·계이름이 달라졌습니다")

    def test_same_first_chord_in_all_parts_is_not_a_time_signature(self):
        import cv2
        result = preprocess(str(ROOT / "test_scores/verovio/beethoven_op18no1_bravura_p1.png"))
        image = result.original_bgr.copy()
        # 숫자 대신 모든 성부에 같은 9도 화음을 놓는다. 세로 정렬만으로는
        # 박자표의 증명이 아니며, 실제 기둥이 두 머리를 연결한다.
        for staff in result.staves[:4]:
            cv2.rectangle(image, (340, staff.top-10), (375, staff.bottom+10), (255,255,255), -1)
            for y in staff.line_ys:
                cv2.line(image, (340,y), (375,y), (0,0,0), 1)
            for y in (staff.top, staff.bottom):
                cv2.ellipse(image, (356,y), (10,7), -15, 0, 360, (0,0,0), -1)
            cv2.line(image, (365,staff.top), (365,staff.bottom), (0,0,0), 3)
        with tempfile.TemporaryDirectory() as out:
            path = Path(out) / "chords.png"
            cv2.imencode(".png",image)[1].tofile(str(path))
            chords = preprocess(str(path))
            contexts = analyze_staves(chords)
            for i in range(4):
                self.assertLess(contexts[i].header_end, 340, "같은 화음을 박자표로 지웠습니다")

    def test_already_covered_timesig_does_not_scan_the_first_note_again(self):
        # 첫 3/4 끝은306, 그 뒤 첫 음표의 기둥·깃도 기존 형태식에는414로 걸립니다.
        # 숫자를 이미 덮은 위치에서 재검색하지 않아야 합니다.
        path = ROOT / "test_scores/verovio/clara_polonaise_2_bravura_p1.png"
        contexts = analyze_staves(preprocess(str(path)))
        self.assertEqual([contexts[i].header_end for i in (0, 1)], [306, 306])

    def test_boundary_uses_image_coordinates_not_fixed_symbol_box(self):
        import cv2
        path = ROOT / "test_scores/verovio/beethoven_op18no1_bravura_p1.png"
        result = preprocess(str(path))
        # 이미지의 왼쪽에 여백을 추가해 모든 기호와 음표를 함께 이동합니다.
        shifted = cv2.copyMakeBorder(result.original_bgr, 0, 0, 73, 0, cv2.BORDER_CONSTANT, value=(255,255,255))
        with tempfile.TemporaryDirectory() as out:
            p = Path(out) / "shift.png"
            cv2.imencode(".png", shifted)[1].tofile(str(p))
            contexts = analyze_staves(preprocess(str(p)))
            for i in range(4):
                self.assertEqual(contexts[i].header_end, 365 + 73)


if __name__ == "__main__":
    unittest.main(verbosity=2)
