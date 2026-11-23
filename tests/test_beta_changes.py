"""추가/삭제를 순증감으로 합치거나 중복 좌표·입력 차이를 숨기지 않는다."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.compare_beta_labels import count_changes


class BetaChangeTests(unittest.TestCase):
    def test_counts_and_input_guard(self):
        label = dict(staff=0, x=10, y=20, pitch='B4', text='시b', confidence='check')
        old = dict(source=dict(sha256='same', page=0, width=100, height=100, dpi=300), music=dict(notation='solfege'), labels=[label, dict(label, x=30)])
        new = copy.deepcopy(old)
        new['labels'] = [dict(label, text='시', confidence='certain'), dict(label, x=40)]
        counts, rows = count_changes(old, new)
        self.assertEqual(counts, dict(added=1, removed=1, text_changed=1, confidence_changed=1))
        self.assertEqual(len([r for r in rows if r['kind']=='label']), 3)
        duplicate = copy.deepcopy(old)
        duplicate['labels'] = [label, dict(label, id=1)]
        reordered = copy.deepcopy(duplicate)
        reordered['labels'].reverse()
        self.assertFalse(any(count_changes(duplicate, reordered)[0].values()))
        ambiguous = copy.deepcopy(duplicate)
        ambiguous['labels'] = [dict(label, text='도'), dict(label, text='레')]
        with self.assertRaisesRegex(ValueError, '모호'):
            count_changes(duplicate, ambiguous)
        with self.assertRaisesRegex(ValueError, '같은 입력'):
            count_changes(old, dict(new, source=dict(old['source'], sha256='other')))
        with self.assertRaisesRegex(ValueError, '표기 설정'):
            count_changes(old, dict(new, music=dict(notation='english')))


if __name__ == '__main__':
    unittest.main()
