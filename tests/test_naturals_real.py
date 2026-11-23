# -*- coding: utf-8 -*-
"""
♮(내추럴) 검출 — 실제 악보 회귀 테스트

지금까지 ♮은 합성 악보로만 확인됐다. 합성 글리프는 획이 곧고 간격이 일정해서
실제 인쇄 악보의 ♮(획이 기울고 오선과 겹침)을 대신하지 못한다.
그래서 바흐 미뉴에트 가단조(조표 없음, F♯이 임시표로 붙었다가 ♮으로 취소되는
전형적인 자리가 있다) 실물 PDF로 검증한다.

test_scores/bach_minuet_Am.pdf 가 없으면 건너뛴다.
"""

import os
import sys
import unittest
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts, filled_flags
from modules.labels_io import confidence_of, flags_of, mark_accidental_candidates
from modules.note_namer import to_solfege_batch
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts, diagnose_labels

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _score_context import context_summary, page_key  # noqa: E402

PDF = os.path.join(os.path.dirname(__file__), "..", "test_scores", "bach_minuet_Am.pdf")

# (x, y, 기대 음이름, 기대 표기) — 육안으로 ♮ 글리프를 확인한 자리
EXPECTED = [
    (526, 1102, "F3", "파"),
    (1508, 1364, "F5", "파"),
    (1312, 1874, "F5", "파"),
]


def main() -> None:
    if not os.path.isfile(PDF):
        print(f"[건너뜀] 테스트 악보가 없습니다: {PDF}")
        return

    result = preprocess(PDF, pdf_page=0)
    contexts = analyze_staves(result)
    noteheads = detect_noteheads(result, contexts=contexts)
    notes = calculate_pitches(noteheads, result.staves,
                              clef={i: c.clef for i, c in contexts.items()})
    accidentals = annotate_accidentals(result, contexts, notes)
    notes, accidentals = remove_accidental_ghosts(notes, accidentals, result.staves,
                                                  filled=filled_flags(notes, noteheads))
    # 조표는 **검출값**으로 표기한다. 예전엔 `()`를 고정으로 넣어 조표 판정이 뒤집혀도
    # 통과했다(실측: x 0.5px 이동에 ♭1로 뒤집힌다 — docs/SUBPIXEL_SHIFT.md §4).
    print(f"문맥: {context_summary(contexts)}")
    key_letters, key_symbol = page_key(contexts)
    assert (key_letters, key_symbol) == ((), ""), \
        f"가단조인데 조표가 {key_symbol}{len(key_letters)}로 판정됐습니다"
    clefs = context_summary(contexts).split()[-1]
    assert clefs == "TBTBTBTB", f"음자리표 배열이 {clefs} (기대 TBTBTBTB)"
    pairs = to_solfege_batch(notes, key_letters, key_symbol, accidentals, "solfege", [], "")

    n_natural = sum(1 for a in accidentals if a == "natural")
    print(f"♮으로 판정된 음표: {n_natural}개")
    assert n_natural >= 5, f"실제 악보에서 ♮이 거의 안 잡혔습니다 ({n_natural}개)"

    for x, y, pitch, text in EXPECTED:
        hit = [(n, t, accidentals[i]) for i, (n, t) in enumerate(pairs)
               if abs(n.x - x) <= 4 and abs(n.y - y) <= 4]
        assert hit, f"x={x} y={y} 자리의 음표를 찾지 못했습니다"
        note, got_text, acc = hit[0]
        got_pitch = f"{note.note_name}{note.octave}"
        print(f"  x={x:5d} y={y:5d}: {got_pitch} {acc} -> '{got_text}' "
              f"(기대 {pitch} natural -> '{text}')")
        assert acc == "natural", f"x={x}: ♮이 아니라 '{acc}'로 판정됐습니다"
        assert got_pitch == pitch, f"x={x}: 음고가 {got_pitch} (기대 {pitch})"
        assert got_text == text, f"x={x}: 표기가 '{got_text}' (기대 '{text}')"

    print("[성공] 실제 악보 ♮ 검출 테스트 통과")


# 실제 원본 확대 대조로 확인한 삭제 피해 음표. 좌표 근접 허용은 위 기존 검사와 같은 4px.
# 추가 관찰 사례의 표기는 현 파이프라인 값이다(독립 음고 정답셋은 아님).
# 전파뿐 아니라 잘못된 raw 판정이 유발한 삭제도 포함한다.
ACCIDENTAL_VICTIMS = {
    ("chopin_nocturne_Db_6-8.pdf", 1): [(1303, 252, "시b")],
    ("chopin_nocturne_Db_6-8.pdf", 5): [(690, 2676, "솔")],
    ("chopin_nocturne_Bbm.pdf", 0): [
        (2279, 703, "시b"), (915, 1466, "레"), (1250, 1456, "미"),
        (991, 2846, "시b"), (1500, 2884, "미"),
        (522, 1417, "시b"), (574, 1426, "라"), (681, 1436, "솔"), (806, 1456, "미"),
    ],
    ("chopin_nocturne_Bbm.pdf", 3): [(582, 2920, "라b")],
    ("chopin_nocturne_Bbm.pdf", 4): [(985, 2996, "미")],
    ("chopin_nocturne_Bbm.pdf", 1): [(1276, 312, "솔b")],
    ("chopin_nocturne_Bbm.pdf", 5): [(1378, 334, "미")],
    ("chopin_nocturne_Db_6-8.pdf", 4): [(730, 2128, "시b"), (2152, 2109, "레b")],
    ("chopin_nocturne_Em.pdf", 3): [(1828, 449, "파#")],
}
GLYPHS_TO_KEEP_REMOVED = {
    ("chopin_nocturne_Db_6-8.pdf", 1): [(616, 2601)],
    ("chopin_nocturne_Db_6-8.pdf", 3): [(2000, 888)],
    ("chopin_nocturne_Db_6-8.pdf", 5): [(1664, 2020)],
    ("chopin_nocturne_Em.pdf", 2): [(2059, 260)],
    # filled=True인 임시표 획이다. 채워진 후보는 지우지 않는 설계라 이 셋은 남되 check여야 한다.
    ("chopin_nocturne_Bbm.pdf", 1): [(1499, 2515), (1880, 2524), (2202, 2515)],
}


@lru_cache(maxsize=None)
def _carry_page(filename, page):
    """각 쪽을 제품의 필터 순서대로 한 번만 처리한다."""
    path = os.path.join(os.path.dirname(PDF), filename)
    result = preprocess(path, pdf_page=page)
    contexts = analyze_staves(result)
    heads = detect_noteheads(result, contexts=contexts)
    heads, _ = drop_beam_ghosts(result, heads)
    heads, _ = drop_offstaff_ghosts(result, heads)
    notes = calculate_pitches(heads, result.staves,
                              clef={i: c.clef for i, c in contexts.items()})
    accs = annotate_accidentals(result, contexts, notes)
    # 제품(main.py)과 같이: 채워진 후보는 지우지 않고 check로 넘긴다
    flagged: list = []
    kept, kept_accs = remove_accidental_ghosts(notes, accs, result.staves,
                                               filled=filled_flags(notes, heads), flagged=flagged)
    found = [c for c in contexts.values() if c.clef_found]
    letters, symbol = (found[0].key_letters, found[0].key_symbol) if found else ((), "")
    before = to_solfege_batch(notes, letters, symbol, accs, "solfege", [], "")
    after = to_solfege_batch(kept, letters, symbol, kept_accs, "solfege", [], "")
    # 확신도도 제품 경로대로 — 진단 행 → 후보 표시 → flags_of → confidence_of
    rows = mark_accidental_candidates(diagnose_labels(result, kept), flagged)
    by_pos = {(int(r["staff"]), int(r["x"]), int(r["y"])): r for r in rows}
    conf = {(n.x, n.y): confidence_of(flags_of(by_pos.get((int(n.staff_index), int(n.x), int(n.y)), {})))
            for n in kept}
    return before, after, conf


def _near(pairs, x, y):
    return [(note, text) for note, text in pairs
            if abs(note.x - x) <= 4 and abs(note.y - y) <= 4]


class AccidentalDeletionTests(unittest.TestCase):
    """임시표 오삭제 18건 회귀 검사. 2026-09-22 채워진 후보를 지우지 않게 고쳐 18개 모두 통과한다
    (xfail 해제). 다시 실패하면 진짜 음표가 또 지워진 것이다."""

    def test_preconditions_are_real_candidates_before_accidental_filter(self):
        # 전단계 누락을 이 결함으로 오인하지 않도록 이 전제 검사는 xfail로 하지 않는다.
        for key, points in ACCIDENTAL_VICTIMS.items():
            before, _, _ = _carry_page(*key)
            for x, y, text in points:
                with self.subTest(page=key, x=x, y=y):
                    hits = _near(before, x, y)
                    self.assertEqual(1, len(hits))
                    self.assertEqual(text, hits[0][1])

    def _assert_survives(self, key, x, y, expected_confidence="check"):
        # 좌표마다 독립된 테스트에서 부른다. 같은 쪽의 다른 실패가 가리지 않게 한다.
        _, after, conf = _carry_page(*key)
        text = next(text for px, py, text in ACCIDENTAL_VICTIMS[key] if (px, py) == (x, y))
        hits = _near(after, x, y)
        self.assertEqual(1, len(hits), f"{key}: ({x}, {y}) 음표 삭제")
        self.assertEqual(text, hits[0][1])
        note = hits[0][0]
        self.assertEqual(expected_confidence, conf[(note.x, note.y)])

    def test_carry_db_p2_x1303_y252(self):
        self._assert_survives(("chopin_nocturne_Db_6-8.pdf", 1), 1303, 252)

    def test_carry_db_p6_x690_y2676(self):
        self._assert_survives(("chopin_nocturne_Db_6-8.pdf", 5), 690, 2676)

    def test_carry_bbm_p1_x2279_y703(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 2279, 703)

    def test_carry_bbm_p1_x915_y1466(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 915, 1466)

    def test_carry_bbm_p1_x1250_y1456(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 1250, 1456)

    def test_carry_bbm_p1_x991_y2846(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 991, 2846)

    def test_carry_bbm_p1_x1500_y2884(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 1500, 2884)

    def test_carry_bbm_p4_x582_y2920(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 3), 582, 2920)

    def test_carry_bbm_p5_x985_y2996(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 4), 985, 2996)

    def test_direct_bbm_p1_x522_y1417(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 522, 1417)

    def test_direct_bbm_p1_x574_y1426(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 574, 1426)

    def test_direct_bbm_p1_x681_y1436(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 681, 1436)

    def test_direct_bbm_p1_x806_y1456(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 0), 806, 1456)

    def test_direct_bbm_p2_x1276_y312(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 1), 1276, 312, expected_confidence="certain")

    def test_direct_bbm_p6_x1378_y334(self):
        self._assert_survives(("chopin_nocturne_Bbm.pdf", 5), 1378, 334)

    def test_direct_db_p5_x730_y2128(self):
        self._assert_survives(("chopin_nocturne_Db_6-8.pdf", 4), 730, 2128)

    def test_direct_db_p5_x2152_y2109(self):
        self._assert_survives(("chopin_nocturne_Db_6-8.pdf", 4), 2152, 2109)

    def test_direct_em_p4_x1828_y449(self):
        self._assert_survives(("chopin_nocturne_Em.pdf", 3), 1828, 449, expected_confidence="certain")

    @unittest.expectedFailure
    def test_known_residual_a19_em_p3_x2059_y260_stays_removed(self):
        # 알려진 잔여 A-19: 가짜 임시표를 걷어내면 라# 유령이 남는다.
        # 삭제 기대는 유지한다. 고쳐지면 예상 밖 성공으로 알려 준다.
        _, after, _ = _carry_page("chopin_nocturne_Em.pdf", 2)
        self.assertFalse(_near(after, 2059, 260),
                         "알려진 잔여 A-19: E단조 3쪽 (2059,260) 라# 유령")

    def test_existing_glyph_and_empty_space_removals_stay_removed(self):
        # 채워진 B♭m2쪽 세 곳은 check로 보존하고, 나머지 빈 후보는 계속 삭제한다.
        # A-19 한 점의 삭제 기대만 별도 예상 실패로 두고 후보 존재는 여기서 검사한다.
        for key, points in GLYPHS_TO_KEEP_REMOVED.items():
            before, after, conf = _carry_page(*key)
            for x, y in points:
                with self.subTest(page=key, x=x, y=y):
                    self.assertTrue(_near(before, x, y), "검사할 삭제 후보가 사라짐")
                    if key == ("chopin_nocturne_Em.pdf", 2) and (x, y) == (2059, 260):
                        continue  # 삭제 기대는 위의 독립 A-19 검사에서 유지한다.
                    hits = _near(after, x, y)
                    if key != ("chopin_nocturne_Bbm.pdf", 1):
                        self.assertFalse(hits, "빈 후보의 기존 삭제가 바뀜")
                        continue
                    self.assertEqual(1, len(hits), "채워진 후보가 다시 삭제됨")
                    for note, _text in hits:
                        self.assertEqual("check", conf[(note.x, note.y)],
                                         "글리프/빈 자리 유령이 확실한 라벨로 다시 살아남")


if __name__ == "__main__":
    main()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AccidentalDeletionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
