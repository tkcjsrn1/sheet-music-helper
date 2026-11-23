# -*- coding: utf-8 -*-
"""새 공개 악보에서 확인된 미지원 조건을 예상 실패로 고정한다.

modules의 현재 동작을 성공으로 포장하지 않는다. 문제가 고쳐져 아래 기대값을 모두
만족하면 ``unexpected success``로 테스트가 실패한다. 그때 원본 대조 후
``@expectedFailure``를 제거해야 한다.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.clef_keysig import analyze_staves
from modules.note_namer import to_solfege_batch
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.preprocess import preprocess
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "unsupported_scores")
KEY_SIGNATURE_FIXTURES = os.path.join(
    os.path.dirname(__file__), "fixtures", "key_signatures", "pdf",
)


def final_pitched_notes(filename: str):
    """렌더링 직전까지 남는 음표를 제품 파이프라인 순서로 돌려준다."""
    result = preprocess(os.path.join(FIXTURES, filename))
    contexts = analyze_staves(result)
    noteheads = detect_noteheads(result, contexts=contexts)
    noteheads, _ = drop_beam_ghosts(result, noteheads)
    noteheads, _ = drop_offstaff_ghosts(result, noteheads)
    pitched = calculate_pitches(
        noteheads,
        result.staves,
        clef={i: context.clef for i, context in contexts.items()},
    )
    accidentals = annotate_accidentals(result, contexts, pitched)
    pitched, _ = remove_accidental_ghosts(
        pitched, accidentals, result.staves,
    )
    return result, pitched


def notes_near(notes, points, radius: int = 5):
    """주어진 좌표 가까이에 최종 음표가 남은 곳만 반환한다."""
    return [
        (x, y)
        for x, y in points
        if any(abs(note.x - x) <= radius and abs(note.y - y) <= radius
               for note in notes)
    ]


class UnsupportedScoreExpectedFailures(unittest.TestCase):
    """현재 미지원임을 명시하는 실행 가능한 재현 사례."""

    @unittest.expectedFailure
    def test_old_scan_detects_all_eight_staves(self) -> None:
        """오래된 스캔도 실제 8보표를 전부 찾아야 한다(현재 일부만 찾음)."""
        result = preprocess(os.path.join(FIXTURES, "satie_ogive3_scan_60pct.jpg"))
        self.assertEqual(8, len(result.staves))

    @unittest.expectedFailure
    def test_three_staff_system_clef_and_key_signature(self) -> None:
        """3단 오르간의 높/낮/낮 음자리표와 4플랫을 읽어야 한다."""
        result = preprocess(os.path.join(FIXTURES, "bach_bwv639_three_staff.png"))
        self.assertEqual(3, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("treble", "♭", 4), ("bass", "♭", 4), ("bass", "♭", 4)],
            [(contexts[i].clef, contexts[i].key_symbol, contexts[i].key_count)
             for i in range(3)],
        )

    @unittest.expectedFailure
    def test_midpage_key_change_keeps_first_f_natural(self) -> None:
        """24마디 5플랫과 다음 시스템 4샤프를 구분하고 F5를 '파'로 써야 한다."""
        result = preprocess(os.path.join(FIXTURES, "chopin_raindrop_key_change.png"))
        self.assertEqual(4, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♭", 5), ("♭", 5), ("♯", 4), ("♯", 4)],
            [(contexts[i].key_symbol, contexts[i].key_count) for i in range(4)],
        )

        noteheads = detect_noteheads(result, contexts=contexts)
        pitched = calculate_pitches(
            noteheads, result.staves,
            clef={i: context.clef for i, context in contexts.items()},
        )
        accidentals = annotate_accidentals(result, contexts, pitched)
        pitched, accidentals = remove_accidental_ghosts(
            pitched, accidentals, result.staves,
        )
        named = to_solfege_batch(
            pitched,
            contexts[0].key_letters,
            contexts[0].key_symbol,
            accidentals,
            "solfege",
        )
        first_f = min(
            ((note, text) for note, text in named
             if note.staff_index == 0 and note.note_name == "F"),
            key=lambda item: abs(item[0].x - 368) + abs(item[0].y - 74),
        )
        self.assertLessEqual(abs(first_f[0].x - 368), 3)
        self.assertLessEqual(abs(first_f[0].y - 74), 3)
        self.assertEqual("파", first_f[1])

    @unittest.expectedFailure
    def test_midscore_key_signature_and_clef_are_not_labeled(self) -> None:
        """반복선 뒤 조표와 곡 중간 음자리표를 음표로 넘기지 않아야 한다."""
        result, notes = final_pitched_notes("beethoven_midscore_symbols.png")
        self.assertEqual(4, len(result.staves))
        symbol_points = [
            (1303, 182), (1322, 152), (1341, 192),
            (1303, 452), (1322, 421), (1341, 462),
            (642, 1116), (655, 1128),
        ]
        self.assertEqual([], notes_near(notes, symbol_points))

    @unittest.expectedFailure
    def test_triplet_beam_stem_intersection_is_not_labeled(self) -> None:
        """셋잇단 빔·기둥 교차점 (929,891)에 유령 라벨이 없어야 한다."""
        result, notes = final_pitched_notes("schubert_triplet_beam_stem.png")
        self.assertEqual(4, len(result.staves))
        self.assertEqual([], notes_near(notes, [(929, 891)]))

    def test_b_major_detects_five_sharps(self) -> None:
        """나장조 조표를 F/C/G/D/A의 샤프 5개로 읽어야 한다."""
        result = preprocess(
            os.path.join(KEY_SIGNATURE_FIXTURES, "06_B_major_sharp5.pdf")
        )
        self.assertEqual(8, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♯", 5, ("F", "C", "G", "D", "A"))] * 8,
            [(contexts[i].key_symbol, contexts[i].key_count, contexts[i].key_letters)
             for i in range(8)],
        )

    def test_f_sharp_major_detects_six_sharps(self) -> None:
        """올림바장조 조표를 F/C/G/D/A/E의 샤프 6개로 읽어야 한다."""
        result = preprocess(
            os.path.join(KEY_SIGNATURE_FIXTURES, "07_Fs_major_sharp6.pdf")
        )
        self.assertEqual(8, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♯", 6, ("F", "C", "G", "D", "A", "E"))] * 8,
            [(contexts[i].key_symbol, contexts[i].key_count, contexts[i].key_letters)
             for i in range(8)],
        )

    def test_c_sharp_major_detects_seven_sharps(self) -> None:
        """올림다장조 조표를 F/C/G/D/A/E/B의 샤프 7개로 읽어야 한다."""
        result = preprocess(
            os.path.join(KEY_SIGNATURE_FIXTURES, "13_Cs_major_sharp7.pdf")
        )
        self.assertEqual(8, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♯", 7, ("F", "C", "G", "D", "A", "E", "B"))] * 8,
            [(contexts[i].key_symbol, contexts[i].key_count, contexts[i].key_letters)
             for i in range(8)],
        )

    def test_g_flat_major_detects_six_flats(self) -> None:
        """내림사장조 조표는 B/E/A/D/G/C의 플랫 6개로 정상 판정한다."""
        result = preprocess(
            os.path.join(KEY_SIGNATURE_FIXTURES, "14_Gb_major_flat6.pdf")
        )
        self.assertEqual(8, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♭", 6, ("B", "E", "A", "D", "G", "C"))] * 8,
            [(contexts[i].key_symbol, contexts[i].key_count, contexts[i].key_letters)
             for i in range(8)],
        )

    def test_c_flat_major_detects_seven_flats(self) -> None:
        """내림다장조 조표를 B/E/A/D/G/C/F의 플랫 7개로 읽어야 한다."""
        result = preprocess(
            os.path.join(KEY_SIGNATURE_FIXTURES, "15_Cb_major_flat7.pdf")
        )
        self.assertEqual(8, len(result.staves))
        contexts = analyze_staves(result)
        self.assertEqual(
            [("♭", 7, ("B", "E", "A", "D", "G", "C", "F"))] * 8,
            [(contexts[i].key_symbol, contexts[i].key_count, contexts[i].key_letters)
             for i in range(8)],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
