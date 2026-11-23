"""88건반의 물리 배치와 늦은 재생 알림을 데이터 수준에서 검증한다."""
import importlib.util
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class PianoState(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('modules.piano_keyboard'),'건반 표시 모듈이 없습니다')
        from modules import piano_keyboard
        return piano_keyboard
    def test_88_keys_have_52_white_and_36_black_and_correct_boundaries(self):
        keys=self.api().keyboard_keys(1040,60)
        self.assertEqual(sorted(k['midi'] for k in keys),list(range(21,109)))
        white=[k for k in keys if not k['black']];black=[k for k in keys if k['black']]
        self.assertEqual((len(white),len(black)),(52,36))
        self.assertEqual((white[0]['midi'],white[0]['rect'][0]),(21,0))
        self.assertEqual((white[-1]['midi'],white[-1]['rect'][2]),(108,1040))
        for left,right in zip(white,white[1:]):self.assertAlmostEqual(left['rect'][2],right['rect'][0])
        middle=next(k for k in keys if k['midi']==60)
        self.assertFalse(middle['black']);self.assertEqual(middle['name'],'C4')
        for k in keys:
            x0,y0,x1,y1=k['rect'];self.assertTrue(0<=x0<x1<=1040 and 0<=y0<y1<=60)
    def test_stop_and_page_change_discard_late_events(self):
        cursor=self.api().PlaybackCursor();token=cursor.reset()
        plan=[dict(notes=[60,67],indices=[0,1,3]),dict(notes=[73],indices=[2])]
        self.assertTrue(cursor.apply(token,'plan',plan))
        self.assertTrue(cursor.apply(token,'start',0));self.assertEqual(cursor.notes,[60,67]);self.assertEqual(cursor.indices,[0,1,3])
        self.assertTrue(cursor.apply(token,'start',1));self.assertFalse(cursor.apply(token,'end',0))
        self.assertEqual(cursor.notes,[73])
        current=cursor.reset();self.assertNotEqual(current,token)
        for kind,arg in [('start',0),('end',1),('plan',plan),('finished',None)]:self.assertFalse(cursor.apply(token,kind,arg))
        self.assertEqual(cursor.notes,[]);self.assertEqual(cursor.indices,[])
        self.assertFalse(cursor.apply(current,'start',99))
    def test_finished_clears_both_overlays(self):
        cursor=self.api().PlaybackCursor();token=cursor.reset()
        cursor.apply(token,'plan',[dict(notes=[58],indices=[0])]);cursor.apply(token,'start',0)
        self.assertTrue(cursor.apply(token,'finished'))
        self.assertEqual(cursor.notes,[]);self.assertEqual(cursor.indices,[])

if __name__=='__main__':unittest.main()
