"""실제 커서를 못 옮기거나 다른 곳으로 제한되면 마우스 입력을 보내지 않는다."""
import os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import _native_click as native

class NativeClickGuardTests(unittest.TestCase):
    def windows(self,position=(100,200),move=True):
        def pid(_hwnd,ptr):ptr._obj.value=42;return 1
        def cursor(ptr):ptr._obj.x,ptr._obj.y=position;return 1
        return SimpleNamespace(GetAncestor=Mock(return_value=500),WindowFromPoint=Mock(return_value=500),
            GetWindowThreadProcessId=Mock(side_effect=pid),SetCursorPos=Mock(return_value=move),
            GetCursorPos=Mock(side_effect=cursor),SetForegroundWindow=Mock(),SendInput=Mock(return_value=2))
    def test_clipped_cursor_never_sends_click(self):
        api=self.windows(position=(5,6))
        with patch.object(native.ct,'WinDLL',return_value=api),patch.dict(os.environ,SMH_NATIVE_CLICK_LOG=''):
            with self.assertRaises(RuntimeError):native.click_at(500,42,100,200)
        api.SendInput.assert_not_called()
    def test_failed_move_never_sends_click(self):
        api=self.windows(move=False)
        with patch.object(native.ct,'WinDLL',return_value=api),patch.dict(os.environ,SMH_NATIVE_CLICK_LOG=''):
            with self.assertRaises(RuntimeError):native.click_at(500,42,100,200)
        api.SendInput.assert_not_called()
    def test_verified_actual_point_sends_click(self):
        api=self.windows()
        with patch.object(native.ct,'WinDLL',return_value=api),patch.dict(os.environ,SMH_NATIVE_CLICK_LOG=''):
            event=native.click_at(500,42,100,200)
        self.assertEqual(event['actual_xy'],[100,200]);self.assertEqual(api.SendInput.call_count,1)

if __name__=='__main__':unittest.main()
