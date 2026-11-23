"""신고 요약은 사용자 수정·실패·빈 값을 성공 숫자로 숨기지 않는다."""
import json
import hashlib
import zipfile
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.replay_report import summarize_document
from tools.summarize_reports import summarize_reports

class IntakeTests(unittest.TestCase):
    def test_recorded_spacing_and_user_confirmed_labels(self):
        doc=dict(source=dict(width=1640,height=2360,dpi=300),
                 music=dict(key_symbol='♯',key_count=2),
                 staves=[dict(spacing=11.3),dict(spacing=11.5)],
                 labels=[dict(confidence='check'),dict(confidence='check',edited=True)],
                 user_edits=dict(changes=[dict(action='set_text'),dict(action='delete')]))
        s=summarize_document(doc,'PNG')
        self.assertEqual((s['sp']['median'],s['staves'],s['labels']),(11.4,2,2))
        self.assertEqual((s['check'],s['raw_check'],s['edited_labels'],s['edit_actions']),(1,2,1,2))
        self.assertEqual(s['key_signature'],dict(symbol='♯',count=2))
        doc['staves'][0]['spacing']=None
        self.assertIsNone(summarize_document(doc,'PNG')['sp'])
        doc['staves'][0]['spacing']=math.nan
        with self.assertRaises(ValueError):summarize_document(doc,'PNG')

    def test_batch_keeps_failure_and_continues_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);incoming=root/'incoming';incoming.mkdir()
            for name in ('a.zip','b.ZIP','c.zip'):(incoming/name).touch()
            stats=dict(input_type='PNG',width=100,height=200,sp=None,key_signature=None,
                       staves=0,labels=2,check=1,edited_labels=0,edit_actions=0)
            def replay(archive,output):
                output.mkdir()
                if archive.name=='b.ZIP':
                    (output/'reported_summary.json').write_text(json.dumps(dict(reported_commit='old',summary=stats)),encoding='utf-8')
                    raise ValueError('변환 실패 | 악보 줄 없음')
                return dict(reported_commit='old',current_commit='now',reported_summary=stats,
                            current_summary=stats,differences=[])
            with patch('tools.summarize_reports.replay',side_effect=replay) as call:
                result=summarize_reports(incoming,root/'out')
                self.assertEqual(call.call_count,3)
            self.assertEqual([r['status'] for r in result],['success','failed','success'])
            self.assertEqual(result[1]['reported']['labels'],2)
            self.assertIsNone(result[1]['current'])
            self.assertIn('변환 실패 \\| 악보 줄 없음',(root/'out/summary.md').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((root/'out/summary.json').read_text(encoding='utf-8')),result)
            with self.assertRaises(FileExistsError):summarize_reports(incoming,root/'out')
            with self.assertRaises(ValueError):summarize_reports(root/'missing',root/'empty')

    def test_rejected_settings_preserve_reported_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'broken-settings.zip'
            doc=dict(source=dict(sha256=hashlib.sha256(b'original').hexdigest(),width=100,height=200),
                     music=dict(key_symbol='',key_count=0),staves=[dict(spacing=12)],
                     labels=[dict(confidence='check')])
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('original.png',b'original');z.writestr('result.png',b'result')
                z.writestr('labels.json',json.dumps(doc))
                z.writestr('report.json',json.dumps(dict(build_commit='reported',settings=dict(clef='guess',photo=True))))
            rows=summarize_reports(archive,root/'out')
            self.assertEqual(rows[0]['status'],'failed')
            self.assertEqual(rows[0]['reported']['labels'],1)
            self.assertTrue(rows[0]['reported']['photo_mode'])
            self.assertIsNone(rows[0]['current'])

if __name__=='__main__':unittest.main()
