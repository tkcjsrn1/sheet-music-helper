"""같은 길이 재생의 구간·속도와 미래 시간목록을 실제 WinMM 경계에서 검증한다."""
import copy,ctypes,inspect,math,sys,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules import label_audio as audio


def device():
    calls=[]
    def caps(index,ptr,size):ptr._obj.name='Microsoft GS Wavetable Synth';ptr._obj.technology=7;return 0
    def opened(ptr,*args):ptr._obj.value=123;return 0
    dll=SimpleNamespace(midiOutGetNumDevs=Mock(return_value=1),midiOutGetDevCapsW=Mock(side_effect=caps),
        midiOutOpen=Mock(side_effect=opened),midiOutShortMsg=Mock(side_effect=lambda h,m:calls.append(m) or 0),
        midiOutReset=Mock(return_value=0),midiOutClose=Mock(return_value=0))
    return dll,calls


class PracticePlan(unittest.TestCase):
    def prepare(self,*args,**kw):
        self.assertTrue(hasattr(audio,'practice_plan'),'구간/시간 축 함수가 없음')
        return audio.practice_plan(*args,**kw)

    def setUp(self):
        self.plan=[dict(notes=[60,64],indices=[0,1]),dict(notes=[67],indices=[4]),dict(notes=[69],indices=[8])]

    def test_defaults_preserve_original_plan_and_equal_time(self):
        before=copy.deepcopy(self.plan);plan,times=self.prepare(self.plan)
        self.assertEqual(plan,self.plan);self.assertEqual(times,[.28]*3);self.assertEqual(self.plan,before)

    def test_boundary_in_chord_keeps_whole_chord_and_original_indices(self):
        plan,times=self.prepare(self.plan,start=1,end=4,speed=.5)
        self.assertEqual(plan,self.plan[:2]);self.assertEqual(times,[.56,.56])
        self.assertEqual(plan[0]['indices'],[0,1])

    def test_future_timing_is_independent_from_pitch_and_scaled_after_slicing(self):
        before=copy.deepcopy(self.plan)
        plan,times=self.prepare(self.plan,start=4,end=8,speed=.5,durations=[.1,.3,.7])
        self.assertEqual(plan,self.plan[1:]);self.assertEqual(times,[.6,1.4]);self.assertEqual(self.plan,before)
        self.assertEqual(self.prepare(self.plan,speed=1.5)[0],self.plan)

    def test_invalid_boundary_is_never_silently_moved(self):
        for kw in (dict(start=0),dict(end=4),dict(start=8,end=0),dict(start=3,end=8),dict(start=-1,end=4),dict(start=True,end=4),dict(start=0.,end=4)):
            with self.subTest(kw=kw),self.assertRaises(ValueError):self.prepare(self.plan,**kw)
        # 제외된 check의 경계 번호가 계획에 없으면 다른 음으로 넘어가지 않는다.
        with self.assertRaises(ValueError):self.prepare(self.plan[1:],start=0,end=8)

    def test_nonfinite_or_outside_speed_and_bad_timing_rejected(self):
        for speed in (.49,1.51,0,-1,float('nan'),float('inf'),True,'1'):
            with self.subTest(speed=speed),self.assertRaises(ValueError):self.prepare(self.plan,speed=speed)
        for times in ([],[.1],[.1,.2,0],[.1,-.2,.3],[.1,float('nan'),.3],[.1,True,.3],['.1',.2,.3]):
            with self.subTest(times=times),self.assertRaises(ValueError):self.prepare(self.plan,durations=times)
        self.assertEqual(self.prepare([]),([],[]))


class PianoRepeat(unittest.TestCase):
    def test_repeat_restarts_indices_and_uses_per_group_time_with_one_device(self):
        self.assertIn('durations',inspect.signature(audio.play_piano).parameters)
        self.assertIn('repeat',inspect.signature(audio.play_piano).parameters)
        dll,calls=device();flag=threading.Event();events=[]
        cancel=SimpleNamespace(is_set=flag.is_set,wait=Mock(return_value=False))
        def event(kind,index):
            events.append((kind,index))
            if len(events)==8:flag.set()
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            audio.play_piano([[60,64],[67]],cancel,durations=[.56,.28],repeat=True,on_group=event)
        self.assertEqual(events,[('start',0),('end',0),('start',1),('end',1)]*2)
        self.assertEqual([v.args[0] for v in cancel.wait.call_args_list],[.56,.28]*2)
        self.assertEqual([m>>8&127 for m in calls if m&0xf0==0x90],[60,64,67]*2)
        dll.midiOutOpen.assert_called_once();dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()

    def test_stop_during_repeat_and_callback_failure_always_release_device(self):
        self.assertIn('repeat',inspect.signature(audio.play_piano).parameters)
        for failed in (False,True):
            dll,calls=device();cancel=SimpleNamespace(is_set=lambda:False,wait=Mock(return_value=True))
            with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
                if failed:
                    with self.assertRaisesRegex(RuntimeError,'화면 실패'):
                        audio.play_piano([[60]],cancel,repeat=True,on_group=lambda *a:(_ for _ in ()).throw(RuntimeError('화면 실패')))
                else:audio.play_piano([[60],[62]],cancel,repeat=True)
            self.assertEqual([m>>8&127 for m in calls if m&0xf0==0x90],[60])
            dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()
            if not failed:
                self.assertIn(0x80|60<<8,calls)
                cancel.wait.assert_called_once_with(.28)
            else:
                cancel.wait.assert_not_called()

    def test_bad_duration_list_never_opens_device(self):
        self.assertIn('durations',inspect.signature(audio.play_piano).parameters)
        for times in ([.1],[],[.1,0],[.1,float('inf')],[.1,True]):
            with self.subTest(times=times),patch.object(ctypes,'WinDLL',create=True) as dll:
                with self.assertRaises(ValueError):audio.play_piano([[60],[62]],threading.Event(),durations=times)
                dll.assert_not_called()



def wave_device(fail_open=False, preroll=0):
    dll, midi_calls = device()
    queue, operations = [], []
    position = submitted = 0

    def opened(handle, *args):
        handle._obj.value = 234
        return 2 if fail_open else 0

    def write(handle, header, size):
        nonlocal submitted
        h = header._obj
        frames = h.length // 4
        assert frames > 0 and h.data
        submitted += frames
        h.flags &= ~1
        queue.append((h, submitted))
        operations.append('write')
        return 0

    def elapsed(handle, ptr, size):
        nonlocal position, preroll
        if preroll:
            preroll -= 1
        else:
            position = min(submitted, position + 256)
        # TIME_BYTES도 처리해야 한다. int16 스테레오 1프레임은 4바이트다.
        ptr._obj.kind = 4
        ptr._obj.value = 4 * position
        for h, end in queue:
            if position >= end:
                h.flags |= 1
        queue[:] = [(h, end) for h, end in queue if position < end]
        return 0

    def reset(handle):
        operations.append('reset')
        for h, _ in queue:
            h.flags |= 1
        return 0

    def unprepare(handle, header, size):
        assert all(h.flags & 1 for h, _ in queue)
        operations.append('unprepare')
        return 0

    dll.waveOutOpen = Mock(side_effect=opened)
    dll.waveOutPrepareHeader = Mock(return_value=0)
    dll.waveOutWrite = Mock(side_effect=write)
    dll.waveOutGetPosition = Mock(side_effect=elapsed)
    dll.waveOutReset = Mock(side_effect=reset)
    dll.waveOutUnprepareHeader = Mock(side_effect=unprepare)
    dll.waveOutClose = Mock(side_effect=lambda handle: operations.append('close') or 0)
    return dll, midi_calls, operations, lambda: position


class GrandPiano(unittest.TestCase):
    def test_stereo_pitched_pcm_has_overlap_and_a_faded_tail(self):
        import tempfile
        import wave
        import numpy as np

        def pcm(path, groups, durations):
            audio.write_piano_wav(groups, path, durations=durations)
            with wave.open(str(path), 'rb') as wav:
                self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (2, 2, 44100))
                return np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, 2)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'piano.wav'
            mixed = pcm(path, [[60], [67]], [.22, .19])
            solo = pcm(path, [[67]], [.19])
            self.assertTrue(np.array_equal(mixed, pcm(path, [[60], [67]], [.22, .19])))
        self.assertEqual(len(mixed), round((.22+.19+.45)*44100))
        self.assertTrue(np.all(mixed[0] == 0) and np.all(mixed[-1] == 0))
        self.assertFalse(np.array_equal(mixed[:, 0], mixed[:, 1]))
        self.assertLess(np.abs(mixed.astype(np.int32)).max(), 32767)
        first = mixed[900:5000,0]
        peak = np.abs(np.fft.rfft(first*np.hanning(len(first)))).argmax()*44100/len(first)
        self.assertAlmostEqual(peak, 261.63, delta=18)
        self.assertGreater(np.mean(np.abs(mixed[9702:11202].astype(float) - solo[:1500])), 40)
        self.assertGreater(np.abs(mixed[18081:20000].astype(float)).mean(), 40)

    def test_wave_callbacks_follow_frames_and_retain_the_same_indices(self):
        dll, midi, operations, position = wave_device(preroll=6)
        got = []
        cancel = SimpleNamespace(is_set=lambda: False, wait=lambda _: False)
        with patch.object(ctypes, 'WinDLL', return_value=dll, create=True):
            audio.play_piano([[60], [67]], cancel, durations=[.12, .22],
                             on_group=lambda tag, index: got.append((tag,index,position())))
        self.assertEqual([(tag, i) for tag, i, _ in got],
                         [('start',0),('end',0),('start',1),('end',1)])
        for (_, _, actual), time in zip(got, (0, .12, .12, .34)):
            self.assertAlmostEqual(actual / 44100, time, delta=.012)
        self.assertGreater(got[0][2], 0)
        self.assertEqual(midi, [])
        self.assertEqual(operations[-1], 'close')

    def test_wave_cancel_returns_queued_buffers_without_replaying(self):
        dll, midi, operations, _position = wave_device()
        cancel, got = threading.Event(), []

        def on_group(tag, index):
            got.append((tag,index))
            if tag == 'start' and len(got) == 3:
                cancel.set()

        with patch.object(ctypes, 'WinDLL', return_value=dll, create=True):
            audio.play_piano([[60]], cancel, duration=.05, repeat=True, on_group=on_group)
        self.assertEqual(got, [('start',0),('end',0)]*2)
        self.assertFalse(midi)
        self.assertLess(operations.index('reset'), operations.index('unprepare'))
        self.assertEqual(operations[-1], 'close')

    def test_wave_device_loss_resumes_at_the_next_group(self):
        dll, midi, operations, position = wave_device()
        elapsed = dll.waveOutGetPosition.side_effect
        dll.waveOutGetPosition.side_effect = lambda *a: 2 if position() >= 2048 else elapsed(*a)
        got = []
        cancel = SimpleNamespace(is_set=lambda: False, wait=lambda _: False)
        with patch.object(ctypes, 'WinDLL', return_value=dll, create=True):
            audio.play_piano([[60], [67]], cancel, durations=[.22, .19],
                             on_group=lambda *a: got.append(a))
        self.assertEqual(got, [('start',0),('end',0),('start',1),('end',1)])
        self.assertEqual([m >> 8 & 127 for m in midi if m & 0xf0 == 0x90], [67])
        self.assertEqual(operations[-1], 'close')

    def test_wave_open_error_falls_back_to_gm_with_the_same_callbacks(self):
        dll, midi, _operations, _position = wave_device(fail_open=True)
        got = []
        cancel = SimpleNamespace(is_set=lambda:False, wait=Mock(return_value=False))
        with patch.object(ctypes, 'WinDLL', return_value=dll, create=True):
            audio.play_piano([[60]], cancel, duration=.65, on_group=lambda *a:got.append(a))
        self.assertEqual(got, [('start',0),('end',0)])
        self.assertIn(0x90|60<<8|80<<16, midi)
        self.assertEqual([c.args[0] for c in cancel.wait.call_args_list],[.65,.45])



if __name__=='__main__':unittest.main()
