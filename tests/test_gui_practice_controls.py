"""연습 옵션의 GUI 소비/문서 전환을 창과 실제 오디오 없이 검증한다."""
import copy,sys,queue,threading,unittest
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.piano_keyboard import PlaybackCursor

class Choice:
    def __init__(self,value=0):self.value=value
    def get(self):return self.value
    def select(self):self.value=1
    def deselect(self):self.value=0

class PracticeControls(unittest.TestCase):
    def app(self):
        for method in ('_practice_options','_set_practice_boundary','_clear_practice_range','_update_practice_controls'):
            self.assertTrue(hasattr(gui.SheetHelperApp,method),'연습 제어 GUI가 없음: '+method)
        labels=[dict(staff=0,x=10,y=10,pitch='D4',accidental='bb',text='레bb',confidence='check'),
                dict(staff=0,x=20,y=20,pitch='F4',accidental='##',text='파##',confidence='certain'),
                dict(staff=0,x=30,y=30,pitch='D5',text='레b',confidence='certain',key=dict(key_symbol='b',key_letters=['D']))]
        doc=dict(labels=labels,music=dict(notation='solfege'))
        app=SimpleNamespace(_edit_session=dict(doc=doc),_review_index=0,_practice_doc=doc,_practice_start=None,_practice_end=None,
            practice_speed=Choice(1.),practice_repeat=Choice(),practice_range_label=Mock(),practice_speed_label=Mock(),
            practice_bar=object(),_stop_listening=Mock(),log=Mock())
        app._practice_session=app._edit_session
        for method in ('_practice_options','_set_practice_boundary','_clear_practice_range','_update_practice_controls'):
            setattr(app,method,MethodType(getattr(gui.SheetHelperApp,method),app))
        return app

    def test_default_snapshot_has_no_change_to_legacy_playback_or_doc(self):
        app=self.app();before=copy.deepcopy(app._edit_session['doc'])
        self.assertIsNone(app._practice_options());self.assertEqual(app._edit_session['doc'],before)

    def test_boundary_selection_and_clear_stop_playback_but_keep_speed(self):
        app=self.app();app.practice_speed.value=.5
        self.assertTrue(app._set_practice_boundary('start'));app._review_index=2
        self.assertTrue(app._set_practice_boundary('end'));app.practice_repeat.select()
        self.assertEqual(app._practice_options(),dict(speed=.5,start=0,end=2,repeat=True))
        self.assertEqual(app._stop_listening.call_count,2)
        app._clear_practice_range();self.assertEqual(app._stop_listening.call_count,3)
        self.assertEqual((app._practice_start,app._practice_end),(None,None));self.assertFalse(app.practice_repeat.get())
        self.assertEqual(app.practice_speed.get(),.5)

    def test_page_edit_reopen_or_region_doc_replacement_clears_stale_boundaries(self):
        app=self.app();app._set_practice_boundary('start');app._review_index=1;app._set_practice_boundary('end');app.practice_repeat.select()
        app._edit_session=dict(doc=copy.deepcopy(app._edit_session['doc']))
        app._update_practice_controls()
        self.assertEqual((app._practice_start,app._practice_end),(None,None));self.assertFalse(app.practice_repeat.get())
        self.assertIsNone(app._practice_options())

    def test_two_page_sessions_sharing_a_doc_still_clear_boundaries(self):
        app=self.app();app._set_practice_boundary('start');app._review_index=1;app._set_practice_boundary('end');app.practice_repeat.select()
        app._edit_session=dict(app._edit_session)
        app._update_practice_controls()
        self.assertEqual((app._practice_start,app._practice_end),(None,None));self.assertFalse(app.practice_repeat.get())

    def test_missing_selection_and_partial_or_unbounded_repeat_rejected(self):
        app=self.app();app._review_index=None
        self.assertFalse(app._set_practice_boundary('start'));app._stop_listening.assert_not_called()
        app.practice_repeat.select()
        with self.assertRaises(ValueError):app._practice_options()
        app.practice_repeat.deselect();app._practice_start=0
        with self.assertRaises(ValueError):app._practice_options()

    def test_worker_slices_plan_but_keeps_original_label_indices_and_pitch(self):
        app=self.app();events=queue.Queue();fake=SimpleNamespace(_audio_events=events,log=Mock());doc=app._edit_session['doc'];before=copy.deepcopy(doc)
        self.assertIn('practice',__import__('inspect').signature(gui.SheetHelperApp._audio_worker).parameters)
        played=[]
        def play(groups,cancel,**kw):played.append((groups,kw));kw['on_group']('start',0);kw['on_group']('end',0)
        with patch('modules.label_audio.play_piano',side_effect=play):
            gui.SheetHelperApp._audio_worker(fake,doc,False,threading.Event(),7,dict(speed=.5,start=1,end=2,repeat=True))
        rows=[]
        while not events.empty():rows.append(events.get_nowait())
        plan=next(e[2] for e in rows if e[1]=='plan')
        self.assertEqual(plan,[dict(notes=[67],indices=[1]),dict(notes=[73],indices=[2])])
        self.assertEqual(played[0][0],[[67],[73]]);self.assertEqual(played[0][1]['durations'],[.56,.56]);self.assertTrue(played[0][1]['repeat'])
        self.assertEqual(doc,before)
        cursor=PlaybackCursor();token=cursor.token;cursor.apply(token,'plan',plan);cursor.apply(token,'start',0)
        self.assertEqual(cursor.indices,[1]);cursor.reset();self.assertFalse(cursor.apply(token,'start',0));self.assertEqual(cursor.notes,[])

    def test_excluded_boundary_reports_failure_without_starting_sound(self):
        app=self.app();events=queue.Queue();fake=SimpleNamespace(_audio_events=events,log=Mock())
        self.assertIn('practice',__import__('inspect').signature(gui.SheetHelperApp._audio_worker).parameters)
        with patch('modules.label_audio.play_piano') as played:
            gui.SheetHelperApp._audio_worker(fake,app._edit_session['doc'],True,threading.Event(),7,dict(speed=1.,start=0,end=2,repeat=True))
        played.assert_not_called();rows=[]
        while not events.empty():rows.append(events.get_nowait())
        self.assertTrue(any(e[1]=='log' and '경계 음' in str(e[2]) for e in rows))
        self.assertEqual(rows[-1],(7,'finished',None))

if __name__=='__main__':unittest.main()
