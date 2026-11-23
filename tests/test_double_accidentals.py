"""확정된 bb/## 입력을 표기·재생하고, 미확정 신호를 추측하지 않는다."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.pitch_calculator import PitchedNote
from modules.note_namer import to_solfege, to_solfege_batch
from modules import note_namer as naming
from modules.label_audio import pitch_to_midi, audio_groups


def note(letter="D", octave=4, x=100):
    return PitchedNote(x=x,y=100,note_name=letter,octave=octave,staff_index=0)


def label(pitch="D4", accidental="bb", **extra):
    return dict(staff=0,x=100,y=100,pitch=pitch,accidental=accidental,
                text="레bb",confidence="check",flags=["double_acc"],edited=False,**extra)


class DoubleAccidentalTests(unittest.TestCase):
    def apply_kinds(self, *args, **kwargs):
        apply = getattr(naming, "apply_double_accidentals", None)
        self.assertTrue(callable(apply), "CLI 종류 반환값을 소비하는 표기 연결 함수가 없습니다")
        return apply(*args, **kwargs)

    def test_cli_kind_mapping_updates_only_selected_final_notes(self):
        fixture=json.loads((Path(__file__).parent/"fixtures/double_accidentals/typed_inputs.json").read_text(encoding="utf-8"))
        notes=[PitchedNote(**row) for row in fixture["notes"]]
        acc=["b","natural","b","#"];named=to_solfege_batch(notes,accidentals=acc)
        before=copy.deepcopy((notes,acc,named))
        kinds={0:("bb","직접"),3:("##","직접")}
        actual_acc,actual_named=self.apply_kinds(notes,acc,named,kinds)
        self.assertEqual(actual_acc,fixture["accidentals"])
        self.assertEqual([t for _,t in actual_named],fixture["expected_text"])
        self.assertIs(actual_named[1],named[1]);self.assertIs(actual_named[2],named[2])
        self.assertTrue(all(n is source for source,(n,_) in zip(notes,actual_named)))
        self.assertEqual((notes,acc,named),before)

    def test_cli_propagation_is_consumed_without_extending_past_cancellation(self):
        notes=[note(x=x) for x in (100,200,300,400)]
        acc=["b","b","natural",""];named=to_solfege_batch(notes,accidentals=acc)
        actual_acc,actual_named=self.apply_kinds(notes,acc,named,{0:("bb","직접"),1:("bb","전파")})
        self.assertEqual(actual_acc,["bb","bb","natural",""])
        self.assertEqual([t for _,t in actual_named],["레bb","레bb","레","레"])

    def test_cli_no_hits_preserves_exact_array_objects(self):
        notes=[note()];acc=["b"];named=to_solfege_batch(notes,accidentals=acc)
        got_acc,got_named=self.apply_kinds(notes,acc,named,{})
        self.assertIs(got_acc,acc);self.assertIs(got_named,named)

    def test_cli_movable_context_is_passed_to_the_existing_namer(self):
        notes=[note("F")];acc=["#"];named=to_solfege_batch(notes,accidentals=acc)
        _,actual=self.apply_kinds(notes,acc,named,{0:("##","직접")},
                                  notation="solfege-movable",tonic="G")
        self.assertEqual(actual[0][1],"도")

    def test_cli_bad_mapping_or_stale_note_order_is_rejected_without_mutation(self):
        notes=[note()];acc=["b"];named=to_solfege_batch(notes,accidentals=acc)
        before=copy.deepcopy((notes,acc,named))
        for kinds in ({-1:("bb","직접")},{1:("##","직접")},{True:("bb","직접")},
                      {0:("?","직접")},{0:("x","직접")}):
            with self.subTest(kinds=kinds),self.assertRaises(ValueError):
                self.apply_kinds(notes,acc,named,kinds)
        with self.assertRaises(ValueError):self.apply_kinds(notes,[],named,{0:("bb","직접")})
        with self.assertRaises(ValueError):self.apply_kinds(notes,acc,[],{0:("bb","직접")})
        with self.assertRaises(ValueError):
            self.apply_kinds(notes,acc,[(note("F"),"파")],{0:("bb","직접")})
        self.assertEqual((notes,acc,named),before)

    def test_fixed_and_letter_keep_original_name_and_two_marks(self):
        for letter,acc,fixed,english in [("D","bb","레bb","Dbb"),("F","##","파##","F##"),
                                         ("B","##","시##","B##"),("C","bb","도bb","Cbb")]:
            for notation,want in [("solfege",fixed),("solfege-fixed",fixed),("letter",english)]:
                with self.subTest(letter=letter,acc=acc,notation=notation):
                    self.assertEqual(to_solfege(note(letter),accidental=acc,notation=notation),want)

    def test_explicit_double_replaces_the_key_signature(self):
        self.assertEqual(to_solfege(note("D"),("B","E","A","D"),"♭","bb"),"레bb")
        self.assertEqual(to_solfege(note("F"),("F",),"♯","##"),"파##")
        self.assertEqual(pitch_to_midi(label(),dict(key_letters=["D"],key_symbol="♭")),60)
        self.assertEqual(pitch_to_midi(label("F4","##"),dict(key_letters=["F"],key_symbol="♯")),67)

    def test_movable_uses_actual_pitch_instead_of_fixed_spelling(self):
        for letter,acc,tonic,want in [("D","bb","C","도"),("F","##","C","솔"),
                                      ("F","##","G","도"),("B","##","D","시")]:
            with self.subTest(letter=letter,acc=acc,tonic=tonic):
                self.assertEqual(to_solfege(note(letter),accidental=acc,
                                           notation="solfege-movable",tonic=tonic),want)

    def test_batch_consumes_final_values_without_propagating_or_mutating(self):
        fixture=json.loads((Path(__file__).parent/"fixtures/double_accidentals/typed_inputs.json").read_text(encoding="utf-8"))
        notes=[PitchedNote(**row) for row in fixture["notes"]]
        acc=fixture["accidentals"];before=copy.deepcopy((notes,acc))
        named=to_solfege_batch(notes,accidentals=acc)
        self.assertEqual([text for _,text in named],fixture["expected_text"])
        self.assertEqual([pitch_to_midi(dict(pitch=f"{n.note_name}{n.octave}",accidental=a,text=t),{})
                          for (n,t),a in zip(named,acc)],fixture["expected_midi"])
        self.assertTrue(all(a is b for a,(b,_) in zip(notes,named)))
        self.assertEqual((notes,acc),before)

    def test_midi_preserves_octave_crossings_and_double_semitones(self):
        for pitch,acc,want in [("D4","bb",60),("F4","##",67),("B4","##",73),
                               ("C4","bb",58),("C0","bb",10),("F9","##",127)]:
            with self.subTest(pitch=pitch,acc=acc):
                self.assertEqual(pitch_to_midi(label(pitch,acc),{}),want)
        with self.assertRaises(ValueError):pitch_to_midi(label("G9","##"),{})

    def test_edited_text_wins_without_destroying_original_double_or_grade(self):
        source=label();edited=dict(source,edited=True,text="파##");before=copy.deepcopy(edited)
        self.assertEqual(pitch_to_midi(edited,{}),67)
        self.assertEqual(edited,before)
        self.assertEqual(source["accidental"],"bb")
        self.assertEqual(source["confidence"],"check")
        self.assertEqual(source["flags"],["double_acc"])

    def test_check_exclusion_still_applies_and_user_confirmation_can_override(self):
        doc=dict(music={},labels=[dict(label(),x=10),dict(label("F4","##"),x=20),
                                dict(label("C4",None),x=30,text="도",confidence="certain",flags=[])])
        before=copy.deepcopy(doc)
        self.assertEqual(audio_groups(doc,False),([[60],[67],[60]],[]))
        groups,skipped=audio_groups(doc,True)
        self.assertEqual(groups,[[60]]);self.assertEqual(len(skipped),2)
        self.assertEqual(doc,before)
        doc["labels"][0].update(edited=True,text="레#")
        self.assertEqual(audio_groups(doc,True)[0],[[63],[60]])

    def test_edited_movable_double_keeps_the_modulation_region_tonic(self):
        row=dict(label("D5","bb"),edited=True,text="도",
                 key=dict(key_symbol="b",key_letters=["D"],tonic="Db"))
        music=dict(key_symbol="",key_letters=[],tonic="C",notation="solfege-movable")
        before=copy.deepcopy((row,music))
        self.assertEqual(pitch_to_midi(row,music),73)
        self.assertEqual((row,music),before)

    def test_double_flag_alone_never_promotes_a_single_or_a_missing_value(self):
        music=dict(key_letters=["F"],key_symbol="♯")
        self.assertEqual(pitch_to_midi(label("F4","#"),music),66)
        self.assertEqual(pitch_to_midi(label("F4",None),music),66)
        self.assertEqual(to_solfege(note("F"),("F",),"♯","#"),"파#")
        self.assertEqual(to_solfege(note("F"),("F",),"♯",""),"파#")

    def test_single_natural_and_missing_values_keep_existing_spelling(self):
        for acc,want in [("#","레#"),("b","레b"),("natural","레"),("","레b"),(None,"레b")]:
            with self.subTest(acc=acc):
                self.assertEqual(to_solfege(note(),("D",),"♭",acc),want)
        self.assertEqual(to_solfege(note("F"),("F",),"♯","natural",
                                   notation="solfege-movable",tonic="G"),"시b")

    def test_unconfirmed_aliases_remain_rejected_by_audio(self):
        for acc in ("x","𝄪","𝄫","###","bbb","#b"):
            with self.subTest(acc=acc),self.assertRaises(ValueError):
                pitch_to_midi(label(accidental=acc),{})


if __name__=="__main__":unittest.main(verbosity=2)
