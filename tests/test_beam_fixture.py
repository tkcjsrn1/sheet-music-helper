# -*- coding: utf-8 -*-
"""빔 선율의 소스→음표 보존 검사와 별도 합성 후보의 빔 분기 검사."""
from collections import Counter
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from measure_beam_fixture import builder, measure, match_source
from modules.notehead_detect import Notehead
from modules.pitch_calculator import PitchedNote
from modules.preprocess import PreprocessResult, Staff
from modules.verify import drop_beam_ghosts


class BeamScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 파일이 없으면 skip하지 않고 실패한다. .ly·PDF·저장 정답 셋을 함께 검증한다.
        cls.expected = builder.expected_from_pdf()
        cls.report = measure()

    def test_source_and_pdf_truth_are_current(self):
        saved = json.loads(builder.EXPECTED.read_text(encoding='utf-8'))
        self.assertEqual(self.expected, saved)
        self.assertEqual(Counter(n['duration_denominator'] for n in saved['notes']), {8: 32, 16: 64, 2: 8})
        self.assertEqual(Counter(b['levels'] for b in saved['beams']), {1: 8, 2: 8})
        self.assertEqual(len({n['id'] for n in saved['notes']}), 104)

    def test_every_source_note_survives_each_stage_with_correct_pitch(self):
        self.assertEqual(self.report['staves'], 6)
        for stage, row in self.report['stages'].items():
            with self.subTest(stage=stage):
                self.assertEqual(row['missing'], [])
                self.assertEqual(row['duplicates'], [])
                self.assertEqual(row['wrong_pitch'], [])
                self.assertEqual(row['matched'], 104)
        self.assertEqual(self.report['final_accidentals'], [])

    def test_matcher_cannot_hide_loss_with_an_extra_or_changed_pitch(self):
        # 전체 개수가 같아도 좌표별 누락과 여분을 따로 찾는지 검사한다.
        truth = self.expected['notes']
        ideal = [PitchedNote(round(n['center_300dpi'][0]), round(n['center_300dpi'][1]),
                             n['pitch'][0], int(n['pitch'][1:]), n['staff_index']) for n in truth]
        self.assertEqual(match_source(truth, ideal)['missing'], [])
        for index, note in enumerate(truth):
            with self.subTest(id=note['id']):
                altered = list(ideal)
                altered[index] = replace(altered[index], x=0, y=0)
                row = match_source(truth, altered)
                self.assertEqual(row['missing'], [note['id']])
                self.assertEqual(len(row['extra']), 1)
                altered[index] = replace(ideal[index], octave=ideal[index].octave + 1)
                self.assertEqual([v['id'] for v in match_source(truth, altered)['wrong_pitch']], [note['id']])


class BeamBranchProbeTests(unittest.TestCase):
    """검출기 자연 출력이 아닌 시험용 빈 후보다. 실제 악보의 유령 검출 성능으로 세지 않는다."""
    def test_three_reasons_on_controlled_beam_geometry(self):
        # 단위는 sp. 빔 위, 넓게 벌린 두 빔 사이, 한 빔 아래의 빈 자리를 각각 지정한다.
        # 통상 16분음표 빔 틈은 좁아 '빔 위'가 먼저 발동하므로, '빔 사이'는 독립 합성 입력이다.
        for sp in (20, 30):
            staff = Staff([8 * sp + k * sp for k in range(5)], float(sp), 0)
            binary = np.zeros((20 * sp, 160 * sp), np.uint8)
            for y in staff.line_ys:
                binary[y, sp:-sp] = 255
            probes = []
            reasons = ['빔 위', '빔 사이', '빔에 닿음']
            for index, x in enumerate((40 * sp, 80 * sp, 120 * sp)):
                # 오선과 떨어진 0.5sp 두께·4sp 길이 빔. 픽셀 원본에서 마스크를 실제 계산한다.
                binary[4 * sp:round(4.5 * sp), x-2*sp:x+2*sp] = 255
                y = round(4.25 * sp) if index == 0 else round(5.25 * sp)
                if index == 1:
                    binary[6 * sp:round(6.5 * sp), x-2*sp:x+2*sp] = 255
                probes.append(Notehead(x, y, 0, filled=False))
            result = PreprocessResult(np.repeat((255-binary)[:, :, None], 3, axis=2),
                                      255-binary, binary, [staff])
            kept, drops = drop_beam_ghosts(result, probes)
            with self.subTest(sp=sp):
                self.assertEqual(kept, [])
                self.assertEqual([d['reason'] for d in drops], reasons)
                self.assertEqual([(d['x'], d['y']) for d in drops], [(p.x, p.y) for p in probes])
                # 같은 위치라도 filled 후보는 이 필터의 삭제 대상이 아니다.
                filled = [replace(p, filled=True) for p in probes]
                self.assertEqual(drop_beam_ghosts(result, filled), (filled, []))


if __name__ == '__main__':
    unittest.main(verbosity=2)
