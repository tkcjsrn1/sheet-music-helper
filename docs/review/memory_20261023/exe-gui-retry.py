"""실제 015908d GUI 두 쪽 변환 계측. 기존 승인된 SendInput/PID 보호를 재사용한다."""
import ctypes as c,ctypes.wintypes as w,json,os,shutil,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).parent; ROOT=Path('F:/sheet-music-helper-progress-test-20261020')
OUT=BASE/'gui-retry-output';(OUT/'app').mkdir(parents=True,exist_ok=True)
# 원본·기존 검사 설정을 보존하려고 실행파일만 새 폴더로 복사한다.
exe=OUT/'app/악보헬퍼.exe'
shutil.copyfile(ROOT/'dist/015908d67789-20261020-074306-711821/악보헬퍼.exe',exe)
header=(ROOT/'output/native-linked-beta.py').read_text(encoding='utf-8').split('cmd=sys.argv[1]',1)[0]
ns={'__name__':'memory_gui'};exec(header,ns);ns['OUT']=OUT
u=ns['u'];u.GetForegroundWindow.restype=w.HWND
original_foreground=u.GetForegroundWindow();num=bool(u.GetKeyState(144)&1)
class GT(c.Structure):_fields_=[('cbSize',w.DWORD),('flags',w.DWORD),('active',w.HWND),('focus',w.HWND),('capture',w.HWND),('menu',w.HWND),('move',w.HWND),('caret',w.HWND),('rect',w.RECT)]
g=GT();g.cbSize=c.sizeof(g);assert u.GetGUIThreadInfo(0,c.byref(g))
im=c.WinDLL('imm32');im.ImmGetDefaultIMEWnd.argtypes=[w.HWND];im.ImmGetDefaultIMEWnd.restype=w.HWND
ime=im.ImmGetDefaultIMEWnd(g.focus);u.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.SendMessageW.restype=w.LPARAM
mode=int(u.SendMessageW(ime,0x283,1,0)) if ime else None
result=dict(numlock_before=num,ime_before=mode,input_scope='Aoharu p1 + Chopin Db p1 실제 GUI 선택·변환')
p=None;h=None

def wait_window(predicate,seconds=30):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        for v in ns['windows']():
            try:ns['guard_own_window'](v['hwnd'])
            except Exception:continue
            if predicate(v):return v
        time.sleep(.15)
    raise RuntimeError('검사 exe 창 대기 제한')

def click(hwnd,x,y):
    ns['activate_own'](hwnd)
    sys.path.insert(0,str(ROOT/'tests'));from _native_click import click_at
    pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(pid))
    return click_at(hwnd,pid.value,x,y)

def children(hwnd):
    values=[]
    @ns['CALLBACK']
    def cb(child,_):values.append(ns['info'](child));return True
    u.EnumChildWindows(hwnd,cb,0);return values
try:
    p=subprocess.Popen([str(exe)],cwd=exe.parent,creationflags=subprocess.CREATE_NO_WINDOW);result['launcher_pid']=p.pid
    root=wait_window(lambda v:v['title']=='악보헬퍼 - 계이름 자동 표기');h=root['hwnd'];result['gui_pid']=root['pid']
    u.MoveWindow(h,20,20,1150,760,True);ns['activate_own'](h);time.sleep(5)
    # 같은 배포판에서 앞서 통과한 좌표. 다른 창이 가리면 click_at이 입력을 막는다.
    result['select_click']=click(h,240,250)
    dialog=wait_window(lambda v:v['cls']=='#32770')
    edits=[v for v in children(dialog['hwnd']) if v['cls']=='Edit' and v['visible'] and v['rect'][2]-v['rect'][0]>200]
    e=max(edits,key=lambda v:v['rect'][1]);r=e['rect'];click(dialog['hwnd'],(r[0]+r[2])//2,(r[1]+r[3])//2)
    inputs={r['case']:r['input'] for r in json.loads((Path('F:/sheet-music-helper-beta-13d73f6-record-20261018')/'output/strict-double-connection/result.json').read_text(encoding='utf-8'))}
    paths=[inputs[k] for k in ('aoharu_p1','chopin_Db_p1')]
    ns['key'](17);ns['key'](65);ns['key'](65,True);ns['key'](17,True)
    ns['text'](' '.join('"'+v+'"' for v in paths));ns['key'](13);ns['key'](13,True);time.sleep(.8);assert not u.IsWindow(dialog['hwnd']),'파일 대화상자 닫힘 미확인'
    result['convert_click']=click(h,240,310)
    until=time.monotonic()+240
    while time.monotonic()<until:
        pngs=list((exe.parent/'output').glob('*_계이름.png'));docs=list((exe.parent/'output').glob('*_라벨.json'))
        if len(pngs)==2 and len(docs)==2 and all(v.stat().st_size for v in pngs+docs):
            time.sleep(5);result.update(completed=True,files=[str(v) for v in pngs+docs]);break
        assert p.poll() is None,'변환 완료 전 exe 종료'
        time.sleep(.2)
    else:raise RuntimeError('실제 GUI 2쪽 변환 240초 제한')
finally:
    if h and u.IsWindow(h):u.PostMessageW(h,16,0,0)
    if p:
        try:p.wait(timeout=8)
        except subprocess.TimeoutExpired:pass # 외부 Job이 자기 자식만 정리한다.
    if ime and u.IsWindow(ime):
        u.SendMessageW(ime,0x283,2,mode);result['ime_restored']=int(u.SendMessageW(ime,0x283,1,0))==mode
    else:result['ime_restored']='원래 컨텍스트 없음/소멸: 입력 모드 변경 명령은 보내지 않음'
    result['numlock_unchanged']=bool(u.GetKeyState(144)&1)==num
    if original_foreground and u.IsWindow(original_foreground):u.SetForegroundWindow(original_foreground)
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)

