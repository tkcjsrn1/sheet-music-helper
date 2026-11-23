"""재생은 실효 반음·사용자 표기·확인 등급·동시 화음을 지킨다."""
from pathlib import Path
import sys
import tempfile
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.label_audio import pitch_to_midi, audio_groups, write_wav

def main():
    music=dict(key_letters=['B'],key_symbol='♭',notation='solfege-fixed')
    label=dict(staff=0,x=20,y=30,pitch='B3',text='시b',confidence='check',accidental=None)
    assert pitch_to_midi(label,music)==58
    assert pitch_to_midi(dict(label,accidental='natural'),music)==59
    assert pitch_to_midi(dict(label,edited=True,text='도#'),music)==49
    assert pitch_to_midi(dict(label,edited=True,text='시#'),music)==60
    assert pitch_to_midi(dict(label,edited=True,text='도'),dict(notation='solfege-movable',tonic='D'))==50
    # 조바꿈 구간 라벨은 쪽 조표가 아니라 라벨의 구간 조표로 (#383 · Clara1 staff8 D5 「레b」 → 73)
    assert pitch_to_midi(dict(label,pitch='D5',text='레b',key=dict(key_symbol='♭',key_letters=['B','E','A','D'])),music)==73
    assert pitch_to_midi(dict(label,pitch='D5',text='레'),music)==74
    doc=dict(music=music,labels=[label,
        dict(label,staff=1,pitch='D4',confidence='certain',text='레'),
        dict(label,staff=0,x=10,pitch='C4',confidence='certain',text='도'),
        dict(label,staff=2,x=1,pitch='E4',confidence='certain',text='미')])
    groups,skipped=audio_groups(doc,False)
    assert groups==[[60],[58,62],[64]] and not skipped
    groups,skipped=audio_groups(doc,True)
    assert groups==[[60],[62],[64]] and len(skipped)==1
    doc['labels'][0]=dict(label,edited=True,text='시')
    assert audio_groups(doc,True)[0]==[[60],[59,62],[64]]
    doc['labels'][0]['text']='해석 불가'
    assert len(audio_groups(doc,False)[1])==1
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'tones.wav'
        duration=write_wav([[69],[60,64,67]],path,duration=.06)
        assert abs(duration-.12)<1e-8
        with wave.open(str(path),'rb') as wav:
            assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,44100,5292)
            assert any(wav.readframes(5292))
    check_piano()
    print('실효 반음·수정/추가·check 제외·시스템/x 순서·동시 화음 WAV: 통과')



def check_piano():
    # 실제 스피커 대신 WinMM 경계에서 음색·화음·중지·오류 정리를 확인한다.
    import ctypes
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    from modules.label_audio import play_piano

    def device():
        calls=[]
        def caps(index, ptr, size):
            ptr._obj.name='Microsoft GS Wavetable Synth'
            ptr._obj.technology=7
            return 0
        def opened(ptr, *args):
            ptr._obj.value=123
            return 0
        dll=SimpleNamespace(
            midiOutGetNumDevs=Mock(return_value=1),
            midiOutGetDevCapsW=Mock(side_effect=caps),
            midiOutOpen=Mock(side_effect=opened),
            midiOutShortMsg=Mock(side_effect=lambda h,m: calls.append(m) or 0),
            midiOutReset=Mock(return_value=0), midiOutClose=Mock(return_value=0))
        return dll,calls

    dll,calls=device()
    cancel=Mock(is_set=Mock(return_value=False),wait=Mock(return_value=False))
    with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
        play_piano([[60,64,67],[62]],cancel)
    notes=[m for m in calls if m & 0xf0 in (0x80,0x90)]
    assert notes==[0x90|n<<8|80<<16 for n in (60,64,67)]+[0x80|n<<8 for n in (60,64,67)]+[0x90|62<<8|80<<16,0x80|62<<8]
    assert 0xc0 in calls[:calls.index(notes[0])], '그랜드 피아노 프로그램 0'
    assert [call.args[0] for call in cancel.wait.call_args_list]==[.28,.28,.45]
    dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()

    dll,calls=device();cancel.wait=Mock(return_value=True)
    with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
        play_piano([[60],[62]],cancel)
    assert [m for m in calls if m & 0xf0==0x90]==[0x90|60<<8|80<<16]
    assert 0x80|60<<8 in calls
    dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()

    for reset_error in (False,True):
        dll,calls=device()
        dll.midiOutShortMsg.side_effect=lambda h,m: 1 if m & 0xf0==0x90 else 0
        if reset_error:dll.midiOutReset.return_value=1
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            try:play_piano([[60]],cancel)
            except OSError:pass
            else:raise AssertionError('재생 실패를 숨기면 안 됨')
        dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()

    # 재생 자체가 끝났어도 정리 실패를 성공으로 숨기지 않는다.
    for name in ('midiOutReset','midiOutClose'):
        dll,calls=device();getattr(dll,name).return_value=1
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            try:play_piano([[60]],cancel)
            except OSError as exc:assert '정리 실패' in str(exc)
            else:raise AssertionError('정리 실패를 숨기면 안 됨')
        dll.midiOutClose.assert_called_once()
    dll,calls=device();dll.midiOutOpen.side_effect=None;dll.midiOutOpen.return_value=1
    with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
        try:play_piano([[60]],cancel)
        except OSError:pass
        else:raise AssertionError('열기 실패를 숨기면 안 됨')
    dll.midiOutShortMsg.assert_not_called();dll.midiOutClose.assert_not_called()

    with patch.object(ctypes,'WinDLL',create=True) as load:
        play_piano([[60]],Mock(is_set=Mock(return_value=True)))
        for groups in ([[128]],[[]],[[True]]):
            try:play_piano(groups,cancel)
            except ValueError:pass
            else:raise AssertionError('잘못된 MIDI 값')
        for duration in (0,float('inf'),float('nan')):
            try:play_piano([[60]],cancel,duration)
            except ValueError:pass
            else:raise AssertionError('잘못된 재생 길이')
        load.assert_not_called()
    dll,calls=device();dll.midiOutGetNumDevs.return_value=0
    with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
        try:play_piano([[60]],cancel)
        except OSError as exc:assert '피아노' in str(exc)
        else:raise AssertionError('장치 부재를 숨기면 안 됨')
    dll.midiOutOpen.assert_not_called()
    import copy
    from gui import SheetHelperApp
    doc=dict(music={},labels=[dict(staff=0,x=1,pitch='C4',confidence='certain')])
    original=copy.deepcopy(doc)
    app=SimpleNamespace(log=Mock(),_audio_cancel=Mock(),destroy=Mock())
    with patch('modules.label_audio.play_piano') as play:
        SheetHelperApp._audio_worker(app,doc,False,cancel)
        play.assert_called_once_with([[60]],cancel)
    assert doc==original
    with patch('modules.label_audio.play_piano',side_effect=OSError('장치 없음')):
        SheetHelperApp._audio_worker(app,doc,False,cancel)
    assert any('듣기 실패' in call.args[0] for call in app.log.call_args_list)
    app._stop_listening=lambda:SheetHelperApp._stop_listening(app)
    SheetHelperApp._close_app(app)
    app._audio_cancel.set.assert_called_once();app.destroy.assert_called_once()
    print('피아노 프로그램·동시 화음·중지·실패 reset/close·입력 검증: 통과')

if __name__=='__main__':main()

