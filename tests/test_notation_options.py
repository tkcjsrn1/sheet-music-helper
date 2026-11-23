"""D-4 옥타브 표시는 인식값·순서를 바꾸지 않고 그릴 글씨만 만든다."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.note_namer import display_octaves

class OctaveDisplayTests(unittest.TestCase):
    def test_default_identity_and_enabled_copy(self):
        named=[(SimpleNamespace(octave=n),text) for n,text in [(4,'도'),(5,'도#'),(3,'시b'),(2,'F#'),(4,'라')]]
        self.assertIs(display_octaves(named),named)
        self.assertEqual([text for _,text in display_octaves(named,True)],['도4','도#5','시b3','F#2','라4'])
        self.assertEqual([text for _,text in named],['도','도#','시b','F#','라'])
        self.assertTrue(all(a[0] is b[0] for a,b in zip(named,display_octaves(named,True))))
    def test_manual_text_is_preserved(self):
        named=[(SimpleNamespace(octave=4),'직접 적은 도5'),(SimpleNamespace(octave=3),'시b')]
        self.assertEqual([s for _,s in display_octaves(named,True,[True,False])],['직접 적은 도5','시b3'])
        self.assertEqual(display_octaves([],True),[])
    def test_invalid_option_or_misaligned_flags_rejected(self):
        named=[(SimpleNamespace(octave=4),'도')]
        for enabled,edited in [('yes',None),(True,[]),(True,[1])]:
            with self.subTest(enabled=enabled,edited=edited),self.assertRaises(ValueError):
                display_octaves(named,enabled,edited)

if __name__=='__main__':unittest.main()
