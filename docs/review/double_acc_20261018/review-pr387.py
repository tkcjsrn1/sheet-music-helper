import copy, importlib.util, json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from modules import labels_io as original
from modules.preprocess import Staff
from modules.pitch_calculator import PitchedNote
R=Path.cwd();out=R/'output/double-acc-20261018'
def load(path,name):
    source=subprocess.check_output(['git','show',f'origin/claude/key-change-audio:{path}']).decode('utf-8')
    file=out/Path(path).name.replace('.py','-pr387.py');file.write_text(source,encoding='utf-8')
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module
io=load('modules/labels_io.py','modules.review_labels_io')
audio=load('modules/label_audio.py','review_label_audio')
staff=Staff(line_ys=[70,90,110,130,150],spacing=20,index=0)
notes=[PitchedNote(x=100,y=110,note_name='D',octave=5,staff_index=0)]
args=dict(input_path=str(R/'tests/fixtures/double_accidentals/typed_inputs.json'),page=0,staves=[staff],
          notes_with_names=[(notes[0],'레')],image_shape=(240,600,3),accidentals=[''],
          key_symbol='',key_letters=(),tonic='C')
old=original.build_document(**args)
assert json.dumps(old,ensure_ascii=False,indent=2)==json.dumps(io.build_document(**args),ensure_ascii=False,indent=2)
assert old==io.build_document(**args,label_keys=[None])
key=dict(key_symbol='♭',key_count=4,key_letters=['B','E','A','D'],tonic='Db')
new=io.build_document(**args,label_keys=[key]);before=copy.deepcopy(new)
row=new['labels'][0];music=new['music'];assert row['key']==key
assert audio.pitch_to_midi(row,music)==73
assert audio.pitch_to_midi(old['labels'][0],music)==74
assert audio.pitch_to_midi(dict(row,accidental='natural'),music)==74
assert audio.pitch_to_midi(dict(row,accidental='#'),music)==75
assert audio.pitch_to_midi(dict(row,edited=True,text='도'),dict(music,notation='solfege-movable'))==73
file=out/'pr387-synthetic-roundtrip.json';io.save_labels(str(file),new)
assert io.load_labels(str(file))==before and new==before
# 자기 소비층 변경을 PR의 구간 조표 우선 처리에 합성해 충돌 여부만 검사한다(제품 연결 아님).
source=(out/'label_audio-pr387.py').read_text(encoding='utf-8')
needle="if acc in ('#','b'):alteration=1 if acc=='#' else -1"
assert source.count(needle)==1
ns={};exec(compile(source.replace(needle,"if acc in ('#','b','##','bb'):alteration=acc.count('#')-acc.count('b')"),'<pr387-plus-consumer>','exec'),ns)
assert ns['pitch_to_midi'](dict(row,accidental='bb'),music)==72
assert ns['pitch_to_midi'](dict(row,pitch='F4',accidental='##'),music)==67
result=dict(pr=387,baseline='origin/claude/key-change-audio',legacy_document_bytes_equal=True,
            no_region_document_equal=True,region_key_precedence=True,explicit_accidental_precedence=True,
            edited_movable_region_tonic=True,save_load_preserves_key=True,consumer_double_composition=True,
            recognition_run=False,product_files_changed=False)
(out/'pr387-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
