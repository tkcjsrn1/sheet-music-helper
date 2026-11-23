"""Windows 실제 마우스 입력. 다른 창이 클릭 위치를 가리면 입력하지 않는다."""
import ctypes as ct
from ctypes import wintypes as wt
import json
import os
import time

class MouseInput(ct.Structure):
    _fields_=[('dx',wt.LONG),('dy',wt.LONG),('mouseData',wt.DWORD),('flags',wt.DWORD),('time',wt.DWORD),('extra',ct.c_size_t)]
class KeyboardInput(ct.Structure):
    _fields_=[('vk',wt.WORD),('scan',wt.WORD),('flags',wt.DWORD),('time',wt.DWORD),('extra',ct.c_size_t)]
class HardwareInput(ct.Structure):
    _fields_=[('message',wt.DWORD),('low',wt.WORD),('high',wt.WORD)]
class InputData(ct.Union):
    _fields_=[('mouse',MouseInput),('keyboard',KeyboardInput),('hardware',HardwareInput)]
class Input(ct.Structure):
    _anonymous_=('data',)
    _fields_=[('kind',wt.DWORD),('data',InputData)]

def click_at(expected, expected_pid, x, y):
    """호출자가 확인한 창/PID에만 입력한다. 가려진 좌표는 실패로 남긴다."""
    user=ct.WinDLL('user32',use_last_error=True)
    user.GetAncestor.argtypes=[wt.HWND,wt.UINT];user.GetAncestor.restype=wt.HWND
    user.WindowFromPoint.argtypes=[wt.POINT];user.WindowFromPoint.restype=wt.HWND
    user.SetCursorPos.argtypes=[ct.c_int,ct.c_int];user.SetCursorPos.restype=wt.BOOL
    user.GetCursorPos.argtypes=[ct.POINTER(wt.POINT)];user.GetCursorPos.restype=wt.BOOL
    user.GetWindowThreadProcessId.argtypes=[wt.HWND,ct.POINTER(wt.DWORD)]
    user.SendInput.argtypes=[wt.UINT,ct.POINTER(Input),ct.c_int]
    pid=wt.DWORD();user.GetWindowThreadProcessId(expected,ct.byref(pid))
    if pid.value!=expected_pid:raise RuntimeError('검사 대상으로 확인한 PID가 아닙니다.')
    if not user.SetCursorPos(x,y):raise RuntimeError('검사 좌표로 커서를 옮기지 못했습니다.')
    actual=wt.POINT()
    if not user.GetCursorPos(ct.byref(actual)):raise RuntimeError('실제 커서 위치를 확인하지 못했습니다.')
    if (actual.x,actual.y)!=(x,y):raise RuntimeError('커서가 검사 좌표 밖으로 제한돼 입력하지 않습니다.')
    hit=user.GetAncestor(user.WindowFromPoint(actual),2)
    hit_pid=wt.DWORD();user.GetWindowThreadProcessId(hit,ct.byref(hit_pid))
    event=dict(x=x,y=y,actual_xy=[actual.x,actual.y],expected_root=int(expected),hit_root=int(hit or 0),pid=hit_pid.value)
    log=os.environ.get('SMH_NATIVE_CLICK_LOG')
    if log:
        with open(log,'a',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
    if hit!=expected or hit_pid.value!=expected_pid:raise RuntimeError(f'클릭 위치를 다른 창이 가립니다: {event}')
    inputs=(Input*2)(Input(kind=0,mouse=MouseInput(flags=2)),Input(kind=0,mouse=MouseInput(flags=4)))
    sent=user.SendInput(2,inputs,ct.sizeof(Input))
    if sent!=2:
        up=Input(kind=0,mouse=MouseInput(flags=4));user.SendInput(1,ct.byref(up),ct.sizeof(Input))
        raise ct.WinError(ct.get_last_error())
    return event

def click_widget(widget):
    app=widget.winfo_toplevel();app.update()
    if not widget.winfo_viewable():raise RuntimeError('클릭할 위젯이 화면에 없습니다.')
    user=ct.WinDLL('user32',use_last_error=True)
    user.GetAncestor.argtypes=[wt.HWND,wt.UINT];user.GetAncestor.restype=wt.HWND
    user.SetForegroundWindow.argtypes=[wt.HWND]
    expected=user.GetAncestor(app.winfo_id(),2)
    user.SetForegroundWindow(expected);app.update()
    event=click_at(expected,os.getpid(),widget.winfo_rootx()+widget.winfo_width()//2,
                   widget.winfo_rooty()+widget.winfo_height()//2)
    # 입력 큐를 소비한 뒤 실제 제품 상태를 검사한다.
    deadline=time.monotonic()+.15
    while time.monotonic()<deadline:
        app.update();time.sleep(.005)
    return event

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('hwnd','pid','x','y'):parser.add_argument('--'+name,type=int,required=True)
    args=parser.parse_args()
    print(json.dumps(click_at(args.hwnd,args.pid,args.x,args.y),ensure_ascii=False))
