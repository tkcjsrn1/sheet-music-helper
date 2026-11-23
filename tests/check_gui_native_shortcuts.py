"""Windows 한/영 IME·NumLock 실제 SendInput 회귀 검사. 키보드/포커스를 움직이므로 별도 실행한다."""
import ctypes as ct
from ctypes import wintypes as wt
import copy,json,os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import gui
import check_gui_native_click as fixture
from _native_click import Input,KeyboardInput,click_widget

class NativeShortcutTests(unittest.TestCase):
    def setUp(self):
        self.records=[];self.patches=[]
        for name in ('_review_shortcut','_help_shortcut'):
            original=getattr(gui.SheetHelperApp,name)
            def observe(app,event,_original=original,_name=name):
                physical=None
                if event.keycode==229 and hasattr(self,'ime'):
                    self.ime.ImmGetVirtualKey.argtypes=[wt.HWND];physical=self.ime.ImmGetVirtualKey(self.user.GetFocus())
                self.records.append(dict(stage='received',handler=_name,ime_virtual_key=physical,queued_np={v:self.user.GetKeyState(v) for v in (78,80)} if hasattr(self,'user') else {},async_np={v:self.user.GetAsyncKeyState(v) for v in (78,80)} if hasattr(self,'user') else {},keysym=event.keysym,
                    keycode=event.keycode,char=event.char,state=event.state,tk_focus=str(app.focus_get())))
                return _original(app,event)
            job=patch.object(gui.SheetHelperApp,name,observe);job.start();self.patches.append(job)
        fixture.NativeClickTests.setUp(self)
        self.user=ct.WinDLL('user32',use_last_error=True);self.ime=ct.WinDLL('imm32')
        u=self.user;im=self.ime
        u.GetForegroundWindow.restype=wt.HWND;u.GetFocus.restype=wt.HWND
        u.GetAncestor.argtypes=[wt.HWND,wt.UINT];u.GetAncestor.restype=wt.HWND
        u.SendInput.argtypes=[wt.UINT,ct.POINTER(Input),ct.c_int]
        u.GetKeyboardLayout.restype=wt.HANDLE;u.ActivateKeyboardLayout.argtypes=[wt.HANDLE,wt.UINT]
        self.old_layout=u.GetKeyboardLayout(0);self.old_numlock=bool(u.GetKeyState(144)&1)
        layouts=(wt.HANDLE*32)();count=u.GetKeyboardLayoutList(32,layouts)
        korean=next((layouts[i] for i in range(count) if int(layouts[i])&0xffff==0x412),None)
        self.assertIsNotNone(korean,'설치된 한글 IME가 없어 실제 한/영 검사를 할 수 없습니다.')
        u.ActivateKeyboardLayout(korean,0)
        im.ImmGetContext.argtypes=[wt.HWND];im.ImmGetContext.restype=wt.HANDLE
        im.ImmGetConversionStatus.argtypes=[wt.HANDLE,ct.POINTER(wt.DWORD),ct.POINTER(wt.DWORD)]
        im.ImmReleaseContext.argtypes=[wt.HWND,wt.HANDLE]
        self.expected=u.GetAncestor(self.app.winfo_id(),2)
        self.focus(self.app.preview_canvas);self.old_native=self.mode()

    def pump(self,seconds=.12):
        until=time.monotonic()+seconds
        while time.monotonic()<until:self.app.update();time.sleep(.005)

    def focus(self,widget):
        click_widget(self.app.review_label);widget.focus_force();self.app.update()
        self.assertEqual(self.app.focus_get(),getattr(widget,'_entry',widget))

    def mode(self):
        hwnd=self.user.GetFocus();context=self.ime.ImmGetContext(hwnd)
        self.assertTrue(context,'실제 OS 포커스 창의 IME 컨텍스트가 없습니다.')
        conv=wt.DWORD();sentence=wt.DWORD()
        try:
            self.assertTrue(self.ime.ImmGetConversionStatus(context,ct.byref(conv),ct.byref(sentence)))
            return bool(conv.value&1)
        finally:self.ime.ImmReleaseContext(hwnd,context)

    def press(self,vk):
        u=self.user;self.app.update();foreground=u.GetForegroundWindow();pid=wt.DWORD()
        u.GetWindowThreadProcessId(foreground,ct.byref(pid));focused=self.app.focus_get()
        self.records.append(dict(stage='before_send',vk=vk,foreground=int(foreground or 0),
            expected=int(self.expected),pid=pid.value,expected_pid=os.getpid(),tk_focus=str(focused),
            tk_class=focused.winfo_class() if focused else None,native=self.mode(),numlock=bool(u.GetKeyState(144)&1)))
        self.assertEqual(foreground,self.expected);self.assertEqual(pid.value,os.getpid())
        down=Input(kind=1,keyboard=KeyboardInput(vk=vk));up=Input(kind=1,keyboard=KeyboardInput(vk=vk,flags=2))
        inputs=(Input*2)(down,up)
        self.assertEqual(u.SendInput(2,inputs,ct.sizeof(Input)),2)
        self.pump(.25)

    def test_real_ime_numlock_review_help_and_input_guard(self):
        app=self.app;before=[(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages]
        docs=copy.deepcopy([p['doc'] for p in self.pages])
        for numlock in (False,True):
            self.focus(app.preview_canvas)
            if bool(self.user.GetKeyState(144)&1)!=numlock:self.press(144)
            self.assertEqual(bool(self.user.GetKeyState(144)&1),numlock)
            for native in (False,True):
                self.focus(app.preview_canvas)
                if self.mode()!=native:self.press(21)
                self.assertEqual(self.mode(),native)
                app._review_index=None;app._update_review_controls()
                for vk,index in ((78,0),(78,1),(80,0)):
                    self.press(vk)
                    until=time.monotonic()+1
                    while app._review_index!=index and time.monotonic()<until:self.pump(.03)
                    self.assertEqual(app._review_index,index,(numlock,native,vk,self.records[-4:]))
                self.press(112)
                self.assertTrue(getattr(app,'_help_window',None) and app._help_window.winfo_exists())
                app._help_window.destroy();self.focus(app.key_entry)
                if self.mode()!=native:self.press(21)
                self.assertEqual(self.mode(),native)
                self.press(78);self.press(80);self.assertEqual(app._review_index,0)
                self.records.append(dict(stage='case_pass',native=native,numlock=numlock,input_guard=True))
        self.focus(app.preview_canvas)
        if not self.mode():self.press(21)
        app._review_index=None;app._update_review_controls()
        # 키 반복 타이머가 동작하기 전에 놓되, 입력 큐에서는 N을 누른 채 M을 누른다.
        inputs=(Input*4)(*(Input(kind=1,keyboard=KeyboardInput(vk=vk,flags=flags))
            for vk,flags in ((78,0),(77,0),(77,2),(78,2))))
        self.assertEqual(self.user.GetForegroundWindow(),self.expected)
        self.assertEqual(self.user.SendInput(4,inputs,ct.sizeof(Input)),4)
        self.pump(.25);self.assertEqual(app._review_index,0)
        self.records.append(dict(stage='held_n_other_m_pass',review=app._review_index))
        self.assertEqual([p['doc'] for p in self.pages],docs)
        self.assertEqual([(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages],before)

    def tearDown(self):
        try:
            if getattr(self,'user',None):
                if getattr(self.app,'_help_window',None) and self.app._help_window.winfo_exists():self.app._help_window.destroy()
                self.focus(self.app.preview_canvas)
                if bool(self.user.GetKeyState(144)&1)!=self.old_numlock:self.press(144)
                if self.mode()!=self.old_native:self.press(21)
                self.assertEqual(self.mode(),self.old_native)
                self.user.ActivateKeyboardLayout(self.old_layout,0)
            folder=Path('output/native-shortcut-check');folder.mkdir(parents=True,exist_ok=True)
            (folder/'events.json').write_text(json.dumps(self.records,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:
            fixture.NativeClickTests.tearDown(self)
            for job in self.patches:job.stop()

if __name__=='__main__':unittest.main()
