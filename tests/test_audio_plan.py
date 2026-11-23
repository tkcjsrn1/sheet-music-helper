"""소리와 화면이 같은 재생 계획을 공유하고 MIDI 중복으로 라벨을 잃지 않는다."""
import copy
import ctypes
import inspect
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import modules.label_audio as audio

class PlaybackPlan(unittest.TestCase):
    def test_indices_follow_existing_groups_with_key_changes_edits_and_doubles(self):
        self.assertTrue(hasattr(audio,'audio_plan'),'음과 원래 라벨 대응을 주는 계획이 없습니다')
        label=lambda **kw:dict(dict(staff=0,x=20,y=40,pitch='D4',text='레',confidence='certain',accidental=None),**kw)
        doc=dict(music=dict(key_symbol='',key_letters=[]),labels=[
            label(pitch='D4',accidental='bb',text='레bb'),
            label(staff=1,pitch='C4',text='도'),
            label(x=10,pitch='F4',accidental='##',text='파##'),
            label(staff=2,x=1,pitch='D5',text='레b',key=dict(key_symbol='♭',key_letters=['D'])),
            label(x=30,pitch='B3',edited=True,text='도#',confidence='check'),
            label(x=30,pitch='A4',text='라',confidence='check'),
            label(x=40,text='읽을 수 없음',edited=True)])
        before=copy.deepcopy(doc)
        plan,skipped=audio.audio_plan(doc,True)
        self.assertEqual([row['notes'] for row in plan],[[67],[60],[49],[73]])
        self.assertEqual([row['indices'] for row in plan],[[2],[0,1],[4],[3]])
        self.assertEqual(len(skipped),2)
        self.assertEqual(audio.audio_groups(doc,True),([row['notes'] for row in plan],skipped))
        self.assertEqual(doc,before)

    def test_aoharu_first_chord_joins_hands_but_not_next_system(self):
        # RE:Aoharu 1쪽 첫 화음의 실제 좌표와 보표 간격.
        doc = dict(staves=[dict(id=i, spacing=sp) for i, sp in enumerate((11.3, 11.5, 11.5))],
                   labels=[dict(staff=0, x=421, pitch='D6'),
                           dict(staff=1, x=422, pitch='D4'),
                           dict(staff=1, x=422, pitch='G3'),
                           dict(staff=0, x=450, pitch='C6'),
                           dict(staff=2, x=422, pitch='D4')])
        before = copy.deepcopy(doc)
        self.assertEqual(audio.audio_plan(doc, False), (
            [dict(notes=[55, 62, 86], indices=[0, 1, 2]),
             dict(notes=[84], indices=[3]), dict(notes=[62], indices=[4])], []))
        self.assertEqual(doc, before)

    def test_chord_uses_first_x_and_keeps_label_order(self):
        doc = dict(staves=[dict(id=0, spacing=10)],
                   labels=[dict(staff=0, x=x, pitch='C4') for x in (105, 100, 110)])
        plan, _ = audio.audio_plan(doc, False)
        self.assertEqual([row['indices'] for row in plan], [[0, 1], [2]])

    def test_unknown_positions_are_excluded_without_guessing_a_group(self):
        self.assertTrue(hasattr(audio,'audio_plan'))
        rows=[dict(staff=s,x=x,pitch='C4',text='도') for s,x in [(True,1),(0,float('nan')),(-1,1),(0,1),(0,1.1)]]
        plan,skipped=audio.audio_plan(dict(labels=rows),False)
        self.assertEqual([p['notes'] for p in plan],[[60],[60]])
        self.assertEqual([p['indices'] for p in plan],[[3],[4]])
        self.assertEqual(len(skipped),3)

    def test_progress_is_after_sound_commands_and_failure_cleans_the_device(self):
        self.assertIn('on_group',inspect.signature(audio.play_piano).parameters)
        events=[]
        def caps(index,ptr,size):ptr._obj.name='Microsoft GS Wavetable Synth';ptr._obj.technology=7;return 0
        def opened(ptr,*args):ptr._obj.value=123;return 0
        dll=SimpleNamespace(midiOutGetNumDevs=Mock(return_value=1),midiOutGetDevCapsW=Mock(side_effect=caps),
            midiOutOpen=Mock(side_effect=opened),midiOutShortMsg=Mock(side_effect=lambda h,m:events.append(('msg',m)) or 0),
            midiOutReset=Mock(side_effect=lambda *args:events.append(('reset',None)) or 0),
            midiOutClose=Mock(return_value=0))
        cancel=Mock(is_set=Mock(return_value=False),
                    wait=Mock(side_effect=lambda duration:events.append(('wait',duration)) or False))
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            audio.play_piano([[60,64],[67]],cancel,on_group=lambda kind,i:events.append((kind,i)))
        starts=[i for i,e in enumerate(events) if e[0]=='start'];ends=[i for i,e in enumerate(events) if e[0]=='end']
        self.assertEqual([events[i] for i in starts],[('start',0),('start',1)])
        self.assertEqual([events[i] for i in ends],[('end',0),('end',1)])
        self.assertEqual(events[starts[0]-1],('msg',0x90|64<<8|80<<16))
        self.assertEqual(events[ends[0]-1],('msg',0x80|64<<8))
        self.assertEqual(events[ends[-1]+1:], [('wait', .45), ('reset', None)])
        dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()
        dll.midiOutReset.reset_mock();dll.midiOutClose.reset_mock()
        with patch.object(ctypes,'WinDLL',return_value=dll,create=True):
            with self.assertRaisesRegex(RuntimeError,'표시 실패'):
                audio.play_piano([[60]],cancel,on_group=lambda *args:(_ for _ in ()).throw(RuntimeError('표시 실패')))
        dll.midiOutReset.assert_called_once();dll.midiOutClose.assert_called_once()

if __name__=='__main__':unittest.main()
