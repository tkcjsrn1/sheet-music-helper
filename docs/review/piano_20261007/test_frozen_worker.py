"""빌드 동봉 GUI 작업자와 피아노 모듈을 실제 WinMM으로 검증한다(UI 클릭 검사는 아님)."""
import copy,ctypes as ct,hashlib,json,marshal,sys,threading,types
from pathlib import Path
from unittest.mock import Mock,patch
from PyInstaller.archive.readers import CArchiveReader
root=Path.cwd();sys.path.insert(0,str(root));out=root/'output/piano-retest-20261007';out.mkdir(exist_ok=True)
exe=root/'dist/d6cf163eea02-20261007-160020-688938/악보헬퍼.exe'
sha=hashlib.sha256(exe.read_bytes()).hexdigest().upper()
assert sha=='D97C34ADA062B063B4D9FEDD845FBB0C28C6CE0D94E5797FDF97E3FD7E1DD4C8'
archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
gui=types.ModuleType('frozen_gui_probe');gui.__file__=str(root/'gui.py');sys.modules[gui.__name__]=gui
exec(marshal.loads(archive.extract('gui')),gui.__dict__)
audio=types.ModuleType('modules.label_audio');exec(pyz.extract('modules.label_audio'),audio.__dict__)
sys.modules[audio.__name__]=audio
native=ct.WinDLL;record=[]
doc=dict(music={},labels=[dict(staff=0,x=10,pitch='C4',confidence='certain'),dict(staff=1,x=10,pitch='E4',confidence='certain'),dict(staff=0,x=10,pitch='G4',confidence='certain'),dict(staff=0,x=20,pitch='D4',confidence='certain'),dict(staff=0,x=30,pitch='E4',confidence='certain'),dict(staff=0,x=40,pitch='B3',text='도#',edited=True,confidence='check'),dict(staff=0,x=50,pitch='C5',confidence='check')])
class StopDuringNote(threading.Event):
    def wait(self,timeout=None):
        timer=threading.Timer(.08,self.set);timer.start()
        try:return super().wait(timeout)
        finally:timer.cancel()
for name,cancel in [('complete',threading.Event()),('cancel_during_chord',StopDuringNote())]:
    devices=[]
    def observed_dll(library):
        dll=native(library)
        # 관찰 래퍼 바깥의 실제 ctypes 함수에도 올바른 64비트 서명을 유지한다.
        for key,args in [('midiOutShortMsg',[ct.c_void_p,ct.c_ulong]),('midiOutReset',[ct.c_void_p]),('midiOutClose',[ct.c_void_p])]:
            function=getattr(dll,key);function.argtypes=args;function.restype=ct.c_uint
            setattr(dll,key,Mock(wraps=function))
        devices.append(dll);return dll
    logs=[];app=types.SimpleNamespace(log=logs.append);before=copy.deepcopy(doc)
    with patch.object(ct,'WinDLL',side_effect=observed_dll):
        gui.SheetHelperApp._audio_worker(app,doc,True,cancel)
    assert doc==before and not any('실패' in row for row in logs),logs
    assert len(devices)==1
    dll=devices[0];messages=[call.args[1] for call in dll.midiOutShortMsg.call_args_list]
    notes=[(m>>8)&127 for m in messages if m&0xf0==0x90]
    off=[(m>>8)&127 for m in messages if m&0xf0==0x80]
    expected=[60,64,67,62,64,49] if name=='complete' else [60,64,67]
    assert notes==off==expected,(notes,off,expected)
    assert 0xc0 in messages[:messages.index(0x90|60<<8|80<<16)]
    dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()
    record.append(dict(case=name,note_on=notes,note_off=off,program=0,bank=0,reset=1,close=1,logs=logs,cancelled=cancel.is_set(),labels_unchanged=True,winmm_api_success=True,midi_messages=messages))
    print(name,notes,'실제 피아노 API/GUI 작업자/정리 통과',flush=True)
result=dict(exe=str(exe),exe_sha256=sha,source='exe에서 추출한 동봉 GUI/label_audio 코드, UI 생성 없이 실행',cases=record,speaker_listening_verified=False,exe_window_clicked=False,loopback_capture_available=False,microphone_used=False)
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
