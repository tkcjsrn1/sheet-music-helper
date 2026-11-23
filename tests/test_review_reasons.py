"""사유 안내는 판정을 다시 계산하거나 원본 라벨을 바꾸지 않는다."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import user_messages


class ReviewReasonTests(unittest.TestCase):
    def reason(self, **fields):
        function = getattr(user_messages, 'label_review_reason', None)
        self.assertTrue(callable(function), '선택 라벨의 사람이 읽을 수 있는 사유 안내가 필요하다')
        return function(dict(dict(confidence='check', flags=[]), **fields))

    def test_recent_signals_explain_observation_without_proving_error(self):
        cases = {
            'double_acc': ('겹임시표', '아직'),
            'flat_propagated': ('뒤 음', '잘못'),
            'beam_gap': ('빔 사이', '음표가 아닐 수'),
            'narrow_hole': ('글자', '음표가 아닐 수'),
            'text_row': ('글자 줄', '음표가 아닐 수'),
            'beam_sloped': ('빔 위', '음표가 아닐 수'),
        }
        for flag, words in cases.items():
            with self.subTest(flag=flag):
                text = self.reason(flags=[flag])
                for word in words:
                    self.assertIn(word, text)
                self.assertNotIn(flag, text)

    def test_all_current_grade_signals_have_an_explanation(self):
        from modules import labels_io
        flags = labels_io._HIGH_PRECISION + labels_io._LOW_PRECISION + labels_io._REVIEW_REQUIRED
        for flag in flags:
            with self.subTest(flag=flag):
                text = self.reason(flags=[flag])
                self.assertNotIn('이유가 기록되지', text)
                self.assertNotIn(flag, text)
        for flag in labels_io._RECORDED_ONLY:
            with self.subTest(recorded_only=flag):
                self.assertIn('이유가 기록되지', self.reason(flags=[flag]))

    def test_multiple_reasons_deduplicate_and_leave_document_unchanged(self):
        function = getattr(user_messages, 'label_review_reason', None)
        self.assertTrue(callable(function))
        label = dict(confidence='check', flags=['double_acc', 'off_staff', 'beam_gap', 'double_acc'])
        before = json.dumps(label, ensure_ascii=False)
        text = function(label)
        self.assertEqual(text.count('겹임시표'), 1)
        self.assertIn('빔 사이', text)
        self.assertNotIn('off_staff', text)
        self.assertEqual(json.dumps(label, ensure_ascii=False), before)

    def test_recorded_only_does_not_create_new_uncertainty(self):
        function = getattr(user_messages, 'label_review_reason', None)
        self.assertTrue(callable(function))
        self.assertIn('추가 확인 사유', function(dict(confidence='certain', flags=['off_staff', 'no_ledger'])))
        for flags in ([], ['future_signal'], ['snap_residual']):
            self.assertIn('원본과 대조', self.reason(flags=flags))
        text = function(dict(edited=True, confidence='check', flags=['double_acc']))
        self.assertTrue(text.startswith('사용자 수정'))
        self.assertIn('원래 판정', text)
        self.assertIn('겹임시표', text)
        added = function(dict(edited=True, user_created=True, confidence='certain', flags=[]))
        self.assertIn('사용자가 추가', added)
        self.assertNotIn('원래 판정', added)

    def test_missing_or_malformed_flags_use_fallback_without_inventing_reason(self):
        for flags in (None, 'double_acc', {'double_acc': True}, 7):
            with self.subTest(flags=flags):
                text = self.reason(flags=flags)
                self.assertIn('원본과 대조', text)
                self.assertNotIn('겹임시표', text)

    def test_selecting_and_clearing_label_updates_visible_reason(self):
        import gui
        class Text:
            def __init__(self): self.text = ''
            def configure(self, **kwargs): self.text = kwargs['text']
            def delete(self, *args): self.text = ''
            def insert(self, _where, text): self.text = text
        labels = [dict(text='레', confidence='check', flags=['double_acc']),
                  dict(text='파', confidence='caution', flags=['chord_rescue_added'])]
        before = copy.deepcopy(labels)
        selection = [0]
        app = SimpleNamespace(_edit_list=SimpleNamespace(curselection=lambda:tuple(selection)),
            _edit_text=Text(), _edit_reason=Text(), _edit_session=dict(doc=dict(labels=labels)),
            _update_review_controls=lambda:None, _redraw_preview=lambda:None)
        gui.SheetHelperApp._select_edit_label(app)
        self.assertIn('겹임시표', app._edit_reason.text)
        self.assertEqual(app._edit_text.text, '레')
        selection[:] = [1]
        gui.SheetHelperApp._select_edit_label(app)
        self.assertIn('화음', app._edit_reason.text)
        self.assertNotIn('겹임시표', app._edit_reason.text)
        selection.clear()
        gui.SheetHelperApp._select_edit_label(app)
        self.assertIn('선택', app._edit_reason.text)
        self.assertEqual(labels, before)


if __name__ == '__main__':
    unittest.main()