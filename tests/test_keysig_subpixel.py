# -*- coding: utf-8 -*-
"""원본에 조표가 없는 바흐의 평행이동 회귀. 조표와 최종 표기를 독립 보호한다."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from measure_keysig_shift import measure

class KeySignatureShiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.runs=measure()['runs']
    def test_identity_warp_is_a_real_control(self):
        self.assertEqual(self.runs['original'],self.runs['0'])
    def test_other_measured_phases_keep_no_key_signature(self):
        for phase in ['original','0','0.25','0.75','1']:
            with self.subTest(phase=phase):
                for c in self.runs[phase]['keysigs'].values():
                    self.assertEqual((c['symbol'],c['count'],c['letters']),('',0,[]))
                self.assertEqual(self.runs[phase]['unmarked_B_flat'],[])
    def test_half_pixel_keeps_source_key_signature(self):
        # PR #136 수정 후 일반 회귀 검사다. 문턱이나 골든을 바꾸지 않는다.
        for c in self.runs['0.5']['keysigs'].values():
            self.assertEqual((c['symbol'],c['count'],c['letters']),('',0,[]))
    def test_half_pixel_does_not_flatten_unmarked_B(self):
        # 음이름 B와 옥타브만으로는 못 잡는다. 적용 반음과 최종 표기를 검사한다.
        notes=[n for n in self.runs['0.5']['notes'] if n['note_name']=='B' and not n['accidental']]
        self.assertTrue(notes,'빈 비교를 통과시키지 않는다')
        for n in notes:
            self.assertEqual((n['applied_alteration'],n['solfege']),(0,'시'))

if __name__=='__main__':unittest.main(verbosity=2)
