"""Windows 기본 출력만 최대 6초 루프백 녹음. 마이크/설정 변경 없음."""
import ctypes as c,uuid,struct,time,threading,json,hashlib,sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
import subprocess, argparse
args=argparse.ArgumentParser();args.add_argument('--hwnd',type=int,required=True);args.add_argument('--play',nargs=2,type=int,required=True);args.add_argument('--stop',nargs=2,type=int,required=True);args.add_argument('--beep-control',action='store_true');a=args.parse_args()
root=Path.cwd();sys.path.insert(0,str(root));control=a.beep_control;out=root/('output/human-a964-remaining-20261015/beep' if control else 'output/human-a964-remaining-20261015/piano');out.mkdir(exist_ok=True)
P=c.c_void_p;U=c.c_uint32;PP=c.POINTER(P)
def guid(text):return c.create_string_buffer(uuid.UUID(text).bytes_le)
def check(hr):
    if hr<0:raise OSError(f'WASAPI HRESULT 0x{hr & 0xffffffff:08X}')
def method(obj,index,args=()):
    address=c.cast(obj,c.POINTER(c.POINTER(P))).contents[index]
    native=c.WINFUNCTYPE(c.c_long,P,*args)(address)
    def invoke(*values):
        result=native(obj,*values);check(result);return result
    return invoke
ole=c.WinDLL('ole32');ole.CoInitializeEx.argtypes=[P,U];ole.CoInitializeEx.restype=c.c_long
ole.CoCreateInstance.argtypes=[P,P,U,P,PP];ole.CoCreateInstance.restype=c.c_long
ole.CoTaskMemFree.argtypes=[P];ole.CoTaskMemFree.restype=None
check(ole.CoInitializeEx(None,0))
enumerator,device,client,capture,fmt=[P() for _ in range(5)];started=False;worker=None;cancel=threading.Event();errors=[]
try:
    check(ole.CoCreateInstance(guid('bcde0395-e52f-467c-8e3d-c4579291692e'),None,23,guid('a95664d2-9614-4f35-a746-de8db63617e6'),c.byref(enumerator)))
    method(enumerator,4,(c.c_int,c.c_int,PP))(0,1,c.byref(device))  # eRender/eMultimedia
    method(device,3,(P,U,P,PP))(guid('1cb9ad4c-dbfa-4c32-b178-c2f568a703b2'),23,None,c.byref(client))
    method(client,8,(PP,))(c.byref(fmt))
    head=c.string_at(fmt,18);tag,channels,rate,avg,align,bits,extra=struct.unpack('<HHIIHHH',head)
    rawfmt=c.string_at(fmt,18+extra)
    floating=tag==3 or tag==65534 and uuid.UUID(bytes_le=rawfmt[24:40]).fields[0]==3
    assert floating and bits==32,(tag,bits)
    method(client,3,(c.c_int,U,c.c_int64,c.c_int64,P,P))(0,0x20000,10000000,0,fmt,None)
    method(client,14,(P,PP))(guid('c8adbd64-e71e-48a0-a4de-185c395cd317'),c.byref(capture))
    nextsize=method(capture,5,(c.POINTER(U),));get=method(capture,3,(PP,c.POINTER(U),c.POINTER(U),P,P));release=method(capture,4,(U,))
    exe=root/'output/human-a964-remaining-20261015/app/악보헬퍼.exe'
    assert hashlib.sha256(exe.read_bytes()).hexdigest().upper()=='A7671CAF5505F70AEC3E8C2EA92118C6438B554CEE67B340B2679ED226C5339F'
    def play():
        try:
            if control:
                import winsound
                from modules.label_audio import write_wav
                write_wav([[86]],out/'beep_input.wav',duration=.28)
                winsound.PlaySound(str(out/'beep_input.wav'),winsound.SND_FILENAME|winsound.SND_NODEFAULT)
            else:
                probe=root/'output/human-a964-remaining-20261015/control.py'
                subprocess.run([sys.executable,str(probe),'click',str(a.hwnd),*map(str,a.play)],check=True)
                time.sleep(3)
                subprocess.run([sys.executable,str(probe),'click',str(a.hwnd),*map(str,a.stop)],check=True)
        except BaseException as error:errors.append(repr(error))
    method(client,10)();started=True;t0=time.perf_counter();chunks=[];packets=[];baseline=[]
    while time.perf_counter()-t0<6:
        elapsed=time.perf_counter()-t0
        if worker is None and elapsed>=.5:
            # 재생 전 출력에 다른 소리가 있는 경우 보존하지 않고 중단한다.
            if baseline and max(baseline)>1e-4:raise RuntimeError('재생 전 다른 출력음 감지: 녹음 중단')
            worker=threading.Thread(target=play);worker.start()
        frames=U();nextsize(c.byref(frames))
        while frames.value:
            data=P();count=U();flags=U();get(c.byref(data),c.byref(count),c.byref(flags),None,None)
            try:
                block=bytes(count.value*align) if flags.value&2 else c.string_at(data,count.value*align)
                values=np.frombuffer(block,dtype='<f4')
                if worker is None:baseline.append(float(np.max(np.abs(values))))
                chunks.append(block);packets.append(dict(seconds=elapsed,frames=count.value,flags=flags.value))
            finally:release(count.value)
            nextsize(c.byref(frames))
        time.sleep(.005)
    cancel.set();worker.join(timeout=3);assert not worker.is_alive() and not errors,errors
    samples=np.frombuffer(b''.join(chunks),dtype='<f4').reshape(-1,channels)
    assert len(samples) and np.max(np.abs(samples))>1e-4,'출력 녹음이 무음'
    wavfile.write(out/'piano_actual_output.wav',rate,samples)
    record=dict(rate=rate,channels=channels,bits=bits,float32=True,frames=len(samples),seconds=len(samples)/rate,peak=float(np.max(np.abs(samples))),rms=float(np.sqrt(np.mean(samples**2))),packet_count=len(packets),packets=packets,baseline_peak=max(baseline,default=0),first_expected_midi=86,duration_per_group=.28,exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest().upper(),source=('기존 write_wav 사인파 + winsound + WASAPI' if control else '실제a9646b4 exe GUI SendInput 듣기 클릭 + WASAPI shared loopback'),microphone_used=False,gui_clicked=not control)
    (out/'capture.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('실제 출력 녹음:',rate,channels,len(samples)/rate,'초',record['peak'],flush=True)
finally:
    cancel.set()
    if worker:worker.join(timeout=3)
    if started:method(client,11)()
    if fmt:ole.CoTaskMemFree(fmt)
    for obj in (capture,client,device,enumerator):
        if obj:method(obj,2)()
    ole.CoUninitialize()
