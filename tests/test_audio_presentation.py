"""지연된 강조의 예약·중지·세대 격리를 Tk/오디오 장치 없이 검사한다."""
import itertools, json, sys, tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui
from modules.piano_keyboard import PlaybackCursor


class AudioPresentationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(gui.SheetHelperApp, "_schedule_audio_event"), "음원 지연을 반영하는 표시 예약이 없음")

    def app(self):
        pending = {}
        ids = itertools.count()
        def after(delay, callback):
            ident = str(next(ids))
            pending[ident] = (delay, callback)
            return ident
        app = SimpleNamespace(_playback=PlaybackCursor(), _audio_delayed={},
                              _audio_cancel=threading.Event(), after=after,
                              after_cancel=lambda ident: pending.pop(ident),
                              log=Mock(), _draw_audio_overlay=Mock(), _update_piano_keys=Mock(),
                              audio_position=Mock())
        app._apply_audio_event=MethodType(gui.SheetHelperApp._apply_audio_event,app)
        return app, pending

    def test_note_is_not_highlighted_at_midi_submission(self):
        app, pending = self.app();token=app._playback.token
        app._apply_audio_event(token,'plan',[dict(notes=[60],indices=[0])])
        gui.SheetHelperApp._schedule_audio_event(app,token,'start',0)
        self.assertEqual(app._playback.notes,[])
        self.assertEqual(len(pending),1)
        delay, callback=next(iter(pending.values()))
        self.assertGreater(delay,0)
        callback()
        self.assertEqual(app._playback.notes,[60])
        self.assertEqual(app._playback.indices,[0])
        self.assertFalse(app._audio_delayed)

    def test_end_and_finished_do_not_clear_before_the_last_audible_note(self):
        for kind in ('end','finished'):
            app,pending=self.app();token=app._playback.token
            app._apply_audio_event(token,'plan',[dict(notes=[60],indices=[0])])
            app._apply_audio_event(token,'start',0)
            gui.SheetHelperApp._schedule_audio_event(app,token,kind,0)
            self.assertEqual(app._playback.notes,[60])
            next(iter(pending.values()))[1]()
            self.assertEqual(app._playback.notes,[])

    def test_stop_cancels_pending_and_late_callback_cannot_relight(self):
        app,pending=self.app();token=app._playback.token
        app._apply_audio_event(token,'plan',[dict(notes=[60],indices=[0])])
        gui.SheetHelperApp._schedule_audio_event(app,token,'start',0)
        late=next(iter(pending.values()))[1]
        gui.SheetHelperApp._stop_listening(app)
        self.assertFalse(pending);self.assertFalse(app._audio_delayed)
        late()
        self.assertEqual(app._playback.notes,[])
        gui.SheetHelperApp._schedule_audio_event(app,token,'start',0)
        self.assertFalse(pending)

    def test_queue_wait_does_not_move_the_presentation_deadline(self):
        from unittest.mock import patch
        app,pending=self.app();token=app._playback.token
        for now in (100.02,100.12):
            with patch('time.perf_counter',return_value=now):
                try:gui.SheetHelperApp._schedule_audio_event(app,token,'start',0,issued_at=100.)
                except TypeError:self.fail('송신 시각을 받지 않아 UI 큐 대기가 보정에 더해짐')
        delays=[delay for delay,callback in pending.values()]
        self.assertAlmostEqual(100.02+delays[0]/1000,100.12+delays[1]/1000,delta=.002)

    def test_already_late_event_is_not_delayed_again(self):
        from unittest.mock import patch
        app,pending=self.app()
        with patch('time.perf_counter',return_value=101.):
            try:gui.SheetHelperApp._schedule_audio_event(app,app._playback.token,'start',0,issued_at=100.)
            except TypeError:self.fail('송신 시각이 없는 고정 재지연')
        self.assertEqual(next(iter(pending.values()))[0],0)

    def test_setting_normalizes_invalid_values_and_keeps_zero(self):
        app = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings.json'
            app.settings_path = str(settings)
            for value, expected in [(0, 0), (600, 600), (True, 220), (21, 220),
                                    (-10, 220), (610, 220), ('100', 220)]:
                settings.write_text(json.dumps({'audio_highlight_delay_ms': value}), encoding='utf-8')
                with self.subTest(value=value):
                    self.assertEqual(gui.SheetHelperApp._load_settings(app)['audio_highlight_delay_ms'], expected)

    def test_setting_retimes_pending_events_in_order_and_persists(self):
        app, pending = self.app()
        app.settings = {'audio_highlight_delay_ms': 600}
        app.audio_delay_slider = Mock()
        app.audio_delay_label = Mock()
        app._audio_delay_save_timer = None
        app._save_settings = Mock()
        app._schedule_audio_event = MethodType(gui.SheetHelperApp._schedule_audio_event, app)
        app._persist_audio_delay = MethodType(gui.SheetHelperApp._persist_audio_delay, app)
        app._apply_audio_event = Mock()
        token = app._playback.token
        with patch('time.perf_counter', return_value=100.10):
            app._schedule_audio_event(token, 'start', 0, 100.0)
            app._schedule_audio_event(token, 'end', 0, 100.05)
            self.assertEqual([row[0] for row in pending.values()], [500, 550])
            late = next(iter(pending.values()))[1]
            gui.SheetHelperApp._set_audio_highlight_delay(app, 0)
        self.assertEqual(app.settings['audio_highlight_delay_ms'], 0)
        self.assertIn('0ms', app.audio_delay_label.configure.call_args.kwargs['text'])
        self.assertEqual([row[0] for row in pending.values()], [0, 0, 250])
        late()
        app._apply_audio_event.assert_not_called()
        for _, callback in pending.values():
            callback()
        self.assertEqual([call.args[1] for call in app._apply_audio_event.call_args_list], ['start', 'end'])
        app._save_settings.assert_called_once_with()
        self.assertFalse(app._audio_delayed)

    def test_audio_pump_polls_fast_only_while_playing_or_presenting(self):
        from queue import Queue
        app = SimpleNamespace(_closing=False, _audio_events=Queue(), _audio_delayed={},
                              _audio_thread=None, after=Mock(), _schedule_audio_event=Mock())
        app._drain_audio_events = MethodType(gui.SheetHelperApp._drain_audio_events, app)
        for worker, pending, expected in [(None, {}, 80), (Mock(is_alive=Mock(return_value=True)), {}, 15),
                                           (None, {'pending': ()}, 15)]:
            app._audio_thread, app._audio_delayed = worker, pending
            app._audio_events.put((1, 'start', 0, 31.25))
            app._drain_audio_events()
            app.after.assert_called_with(expected, app._drain_audio_events)
            app._schedule_audio_event.assert_called_with(1, 'start', 0, 31.25)

    def test_plan_and_errors_are_not_delayed(self):
        app,pending=self.app();token=app._playback.token
        gui.SheetHelperApp._schedule_audio_event(app,token,'plan',[dict(notes=[67],indices=[0])])
        gui.SheetHelperApp._schedule_audio_event(app,token,'log','장치 오류')
        self.assertEqual(app._playback.plan[0]['notes'],[67])
        app.log.assert_called_once_with('장치 오류')
        self.assertFalse(pending)


if __name__=='__main__':unittest.main()
