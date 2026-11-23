"""장치를 열거나 Tk 창을 만들지 않고 GUI 소비 경계를 검사한다."""
import copy,sys,threading,unittest,queue
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules import piano_keyboard as piano
import gui

class PianoDisplay(unittest.TestCase):
    def test_canvas_has_88_keys_and_distinguishes_selected_from_playing(self):
        self.assertTrue(hasattr(piano,'PianoKeyboard'),'Canvas 건반이 없습니다')
        rows=[]
        canvas=SimpleNamespace(winfo_width=lambda:1040,winfo_height=lambda:60,delete=lambda *a:None,
            create_rectangle=lambda *a,**kw:rows.append((a,kw)),create_text=lambda *a,**kw:None,
            selected={60},playing={67})
        piano.PianoKeyboard._draw(canvas)
        self.assertEqual(len(rows),88)
        colored={row[1]['tags'][1]:row[1]['fill'] for row in rows}
        self.assertEqual(colored['midi-60'],'#3B82F6');self.assertEqual(colored['midi-67'],'#F59E0B')
        self.assertEqual(sum(fill in ('#3B82F6','#F59E0B') for fill in colored.values()),2)
    def test_current_group_moves_both_displays_and_late_event_does_nothing(self):
        self.assertTrue(hasattr(gui.SheetHelperApp,'_apply_audio_event'),'재생 사건 소비가 없습니다')
        cursor=piano.PlaybackCursor();token=cursor.token
        app=SimpleNamespace(_playback=cursor,log=Mock(),_draw_audio_overlay=Mock(),_update_piano_keys=Mock(),audio_position=Mock())
        apply=lambda kind,value=None:gui.SheetHelperApp._apply_audio_event(app,token,kind,value)
        apply('plan',[dict(notes=[60,67],indices=[0,1,3])]);apply('start',0)
        self.assertEqual(cursor.notes,[60,67]);self.assertEqual(cursor.indices,[0,1,3])
        self.assertTrue(app._draw_audio_overlay.called);self.assertTrue(app._update_piano_keys.called)
        cursor.reset();app._draw_audio_overlay.reset_mock();app._update_piano_keys.reset_mock()
        apply('start',0);apply('finished')
        app._draw_audio_overlay.assert_not_called();app._update_piano_keys.assert_not_called()
    def test_outside_piano_range_is_reported_without_transposing_sound(self):
        cursor=piano.PlaybackCursor();token=cursor.token
        app=SimpleNamespace(_playback=cursor,_edit_session={'doc':{'labels':[]}},_review_index=None,
            piano_keyboard=Mock(),piano_frame=Mock(),audio_position=Mock(),log=Mock(),_draw_audio_overlay=Mock())
        app._update_piano_keys=MethodType(gui.SheetHelperApp._update_piano_keys,app)
        gui.SheetHelperApp._apply_audio_event(app,token,'plan',[dict(notes=[10],indices=[0])])
        gui.SheetHelperApp._apply_audio_event(app,token,'start',0)
        self.assertIn('표시 음역 밖',app.audio_position.configure.call_args.kwargs['text'])
        self.assertEqual(cursor.notes,[10])

    def test_empty_result_hides_previous_selected_keyboard(self):
        app=SimpleNamespace(_review_indices=lambda:[],_review_index=None,
            review_label=Mock(),prev_review_btn=Mock(),next_review_btn=Mock(),review_nav=Mock(),
            _converting=False,_preview_source=None,_edit_session=None,
            piano_keyboard=Mock(),piano_frame=Mock(),audio_position=Mock(),_playback=piano.PlaybackCursor())
        app._update_piano_keys=MethodType(gui.SheetHelperApp._update_piano_keys,app)
        gui.SheetHelperApp._update_review_controls(app)
        app.piano_frame.grid_remove.assert_called_once()

    def test_stop_invalidates_the_cursor_without_waiting_for_the_worker(self):
        self.assertTrue(hasattr(gui.SheetHelperApp,'_apply_audio_event'))
        cursor=piano.PlaybackCursor();token=cursor.token
        cursor.apply(token,'plan',[dict(notes=[60],indices=[0])]);cursor.apply(token,'start',0)
        app=SimpleNamespace(_audio_cancel=threading.Event(),_playback=cursor,
            _draw_audio_overlay=Mock(),_update_piano_keys=Mock(),audio_position=Mock())
        gui.SheetHelperApp._stop_listening(app)
        self.assertTrue(app._audio_cancel.is_set());self.assertNotEqual(cursor.token,token)
        self.assertEqual(cursor.indices,[]);self.assertEqual(cursor.notes,[])
        app._draw_audio_overlay.assert_called_once();app._update_piano_keys.assert_called_once()

    def test_selected_display_matches_edited_local_key_and_out_of_range_pitch(self):
        rows = [
            ({'pitch':'B3','text':'시b'}, {'key_letters':['B'],'key_symbol':'♭'}, 58, 'Bb3'),
            ({'pitch':'B3','text':'시','accidental':'natural'}, {'key_letters':['B'],'key_symbol':'♭'}, 59, 'B3'),
            ({'pitch':'B3','text':'도#','edited':True}, {}, 49, 'Db3'),
            ({'pitch':'D5','text':'레b','key':{'key_letters':['D'],'key_symbol':'♭'}}, {}, 73, 'Db5'),
            ({'pitch':'D4','text':'레bb','accidental':'bb'}, {}, 60, 'C4'),
            ({'pitch':'F4','text':'파##','accidental':'##'}, {}, 67, 'G4'),
            ({'pitch':'D5','text':'도','edited':True,'accidental':'bb','key':{'tonic':'Db'}},
             {'notation':'solfege-movable','tonic':'C'}, 73, 'Db5'),
            ({'pitch':'Bb0','text':'둘'}, {}, None, '해석 불가'),
            ({'pitch':'D0','text':'레bb','accidental':'bb'}, {}, 12, 'C0'),
            ({'pitch':'C0','text':'도bb','accidental':'bb'}, {}, 10, 'Bb-1'),
            ({'pitch':'G9','text':'솔'}, {}, 127, 'G9'),
        ]
        for row, music, midi, preview in rows:
            doc = dict(labels=[row], music=music)
            app = SimpleNamespace(_edit_session={'doc':doc}, _review_index=0, piano_keyboard=Mock(),
                                  piano_frame=Mock(), _playback=piano.PlaybackCursor(), audio_position=Mock())
            gui.SheetHelperApp._update_piano_keys(app)
            with self.subTest(row=row):
                app.piano_keyboard.set_notes.assert_called_once_with([] if midi is None else [midi], [])
                text = app.audio_position.configure.call_args.kwargs['text']
                self.assertIn(preview, text)
                self.assertIn(f"표기: {row['text']}", text)
                if midi is not None and not 21 <= midi <= 108:
                    self.assertIn('표시 음역 밖', text)

    def test_single_note_worker_plays_only_one_midi_pitch(self):
        app = SimpleNamespace(_audio_events=queue.Queue())
        cancel = threading.Event()
        with patch('modules.label_audio.play_piano') as play:
            gui.SheetHelperApp._play_edit_note(app, 61, cancel, 4)
        play.assert_called_once_with([[61]], cancel, duration=.65)

    def test_worker_sends_token_plan_callbacks_and_failure_to_queue(self):
        doc=dict(labels=[dict(staff=0,x=100,pitch='D4',text='레bb',accidental='bb',confidence='check'),
                         dict(staff=0,x=200,pitch='F4',text='파##',accidental='##',confidence='check')])
        before=copy.deepcopy(doc);cancel=threading.Event();token=42
        for failed in (False,True):
            with self.subTest(failed=failed):
                app=SimpleNamespace(_audio_events=queue.Queue(),log=Mock())
                def player(groups,event,on_group):
                    self.assertEqual(groups,[[60],[67]]);self.assertIs(event,cancel)
                    if failed:raise RuntimeError('주입: 장치 실패')
                    for i in range(len(groups)):on_group('start',i);on_group('end',i)
                with patch('modules.label_audio.play_piano',side_effect=player) as play:
                    gui.SheetHelperApp._audio_worker(app,doc,False,cancel,token)
                play.assert_called_once();app.log.assert_not_called()
                events=[]
                while not app._audio_events.empty():events.append(app._audio_events.get_nowait())
                self.assertTrue(all(e[0]==token for e in events))
                self.assertEqual(events[0],(token,'plan',[dict(notes=[60],indices=[0]),dict(notes=[67],indices=[1])]))
                self.assertEqual(events[-1],(token,'finished',None))
                callbacks=[(e[1],e[2]) for e in events if e[1] in ('start','end')]
                self.assertTrue(all(len(e)==4 and type(e[3])is float for e in events if e[1]in ('start','end')))
                self.assertEqual(callbacks,[] if failed else [('start',0),('end',0),('start',1),('end',1)])
                self.assertEqual(any(e[1]=='log' and '듣기 실패' in e[2] for e in events),failed)
                self.assertEqual(doc,before)


class DirectKeyboardTests(unittest.TestCase):
    def test_hit_test_checks_black_first_and_half_open_white_edges(self):
        widget=SimpleNamespace(winfo_width=lambda:1040,winfo_height=lambda:60)
        hit=lambda x,y:piano.PianoKeyboard.hit_test(widget,x,y)
        keys=piano.keyboard_keys(1040,60)
        c_sharp=next(row['rect'] for row in keys if row['midi']==61)
        x=(c_sharp[0]+c_sharp[2])/2
        self.assertEqual(hit(x,1),61)
        self.assertEqual(hit(x,c_sharp[3]),62)
        self.assertEqual(hit(x-.1,59),60)
        self.assertEqual(hit(0,0),21)
        self.assertEqual(hit(1039.9,59.9),108)
        for outside in ((-1,2),(1040,30),(2,-1),(2,60)):
            self.assertIsNone(hit(*outside))
        click=Mock()
        widget._on_key_click=click
        widget.hit_test=hit
        piano.PianoKeyboard._key_clicked(widget,SimpleNamespace(x=x,y=1))
        piano.PianoKeyboard._key_clicked(widget,SimpleNamespace(x=-1,y=1))
        click.assert_called_once_with(61)

    def test_keyboard_click_replaces_preview_and_ignores_a_song(self):
        previous=Mock()
        previous.is_alive.return_value=True
        first_cancel=threading.Event()
        app=SimpleNamespace(_converting=False,_closing=False,
            _audio_thread=previous,_audio_cancel=first_cancel,_keyboard_note=None,
            _playback=piano.PlaybackCursor(),_draw_audio_overlay=Mock(),_update_piano_keys=Mock(),
            _play_keyboard_note=Mock(),_wake_audio_events=Mock(),log=Mock())
        app._stop_listening=MethodType(gui.SheetHelperApp._stop_listening,app)
        with patch('gui.threading.Thread') as thread:
            gui.SheetHelperApp._on_piano_key(app,60)
            thread.assert_not_called()
            self.assertFalse(first_cancel.is_set())
            app._keyboard_note=59
            gui.SheetHelperApp._on_piano_key(app,60)
            self.assertTrue(first_cancel.is_set())
            self.assertEqual(app._keyboard_note,60)
            self.assertEqual(thread.call_args.kwargs['args'],(60,app._audio_cancel,app._playback.token,previous))
            thread.return_value.start.assert_called_once()
        token=app._playback.token
        gui.SheetHelperApp._apply_audio_event(app,token-1,'keyboard_finished')
        self.assertEqual(app._keyboard_note,60)
        gui.SheetHelperApp._apply_audio_event(app,token,'keyboard_finished')
        self.assertIsNone(app._keyboard_note)

    def test_worker_waits_for_previous_note_and_plays_new_sample(self):
        app=SimpleNamespace(_audio_events=queue.Queue())
        previous=Mock()
        previous.is_alive.return_value=True
        cancel=threading.Event()
        with patch('modules.label_audio.play_piano') as play:
            play.side_effect=lambda *_args,**_kw:previous.join.assert_called_once()
            gui.SheetHelperApp._play_keyboard_note(app,60,cancel,7,previous)
            play.assert_called_once_with([[60]],cancel,duration=.55)
        self.assertEqual(app._audio_events.get_nowait(),(7,'keyboard_finished',None))
        with patch('modules.label_audio.play_piano') as play:
            cancel.set()
            gui.SheetHelperApp._play_keyboard_note(app,62,cancel,8,None)
            play.assert_not_called()

    def test_preview_sets_pressed_key_and_name(self):
        app=SimpleNamespace(_edit_session={'doc':{'labels':[]}},_review_index=None,
            piano_keyboard=Mock(),piano_frame=Mock(),audio_position=Mock(),
            _playback=piano.PlaybackCursor(),_keyboard_note=60)
        gui.SheetHelperApp._update_piano_keys(app)
        app.piano_keyboard.set_notes.assert_called_once_with([],[60])
        self.assertIn('건반 미리듣기: C4 (도 · MIDI 60)',app.audio_position.configure.call_args.kwargs['text'])




class EditKeyTests(unittest.TestCase):
    def test_space_and_delete_act_only_outside_edit_entry(self):
        entry=SimpleNamespace(winfo_class=lambda:'Entry')
        rows=SimpleNamespace(winfo_class=lambda:'Listbox')
        app=SimpleNamespace(focus_get=Mock(return_value=entry),_listen_edit_note=Mock(),_change_label=Mock())
        app._typing_input=MethodType(gui.SheetHelperApp._typing_input,app)
        def press(key,state=0):
            return gui.SheetHelperApp._quick_edit_shortcut(app,SimpleNamespace(keysym=key,state=state,widget=rows))
        for key in ('space','Delete'):
            self.assertIsNone(press(key))
        app._listen_edit_note.assert_not_called()
        app._change_label.assert_not_called()
        app.focus_get.return_value=rows
        self.assertEqual(press('space'),'break')
        self.assertEqual(press('Delete'),'break')
        self.assertIsNone(press('Delete',0x4))
        self.assertIsNone(press('space',0x4))
        app._listen_edit_note.assert_called_once_with()
        app._change_label.assert_called_once_with('delete')



if __name__=='__main__':unittest.main()
