"""실제 GUI가 저장한 RGB 색상이 JSON 왕복 뒤에도 재열기·되돌리기에 쓰인다."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import save_labels

class ReopenColorTests(unittest.TestCase):
    def test_style_debounce_and_stale_page(self):
        session = {}
        app = SimpleNamespace(_edit_session=session, _converting=False, _style_refresh_timer=None,
                              after=Mock(side_effect=['first', 'latest']), after_cancel=Mock(),
                              _refresh_page_style=Mock())
        app._cancel_style_refresh = lambda: gui.SheetHelperApp._cancel_style_refresh(app)
        gui.SheetHelperApp._schedule_style_refresh(app)
        gui.SheetHelperApp._schedule_style_refresh(app)
        app.after_cancel.assert_called_once_with('first')
        app.after.assert_called_with(180, app._refresh_page_style, session)
        app._edit_session = {}
        gui.SheetHelperApp._refresh_page_style(app, session)
        self.assertIsNone(app._style_refresh_timer)

    def test_notation_preserves_edits_region_midi_and_reopen(self):
        from modules.label_audio import pitch_to_midi
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame = np.full((180, 220, 3), 255, np.uint8)
            source = root / '입력.png'
            Image.fromarray(frame).save(source)
            labels = [dict(staff=0, x=x, y=100, pitch=pitch, text=text, accidental=acc,
                           confidence='certain', edited=False)
                      for x, pitch, text, acc in ((30, 'F4', '파#', None), (60, 'C4', '도#', None),
                                                   (100, 'E4', '미', None), (190, 'B4', '시', 'natural'))]
            labels[1]['key'] = dict(key_symbol='♯', key_count=2, key_letters=['F', 'C'], tonic='')
            doc = dict(schema=1, music=dict(notation='solfege-fixed', key_symbol='♯', key_count=1,
                       key_letters=['F'], tonic='', minor=False), labels=labels,
                       source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                                   page=0, width=220, height=180, dpi=300),
                       staves=[dict(id=0, line_ys=[60,70,80,90,100], spacing=10)])
            attrs = ('staff','x','y','pitch','text')
            changes = [dict(action='set_text', before={k: labels[0][k] for k in attrs}, after=dict(text='레')),
                       dict(action='delete', before={k: labels[2][k] for k in attrs}),
                       dict(action='add', after=dict(staff=0, x=140, y=100, pitch='C4', text='미'))]
            header = dict(symbol='♯', count=1, font_path='C:/Windows/Fonts/malgun.ttf',
                          spacings=[10], setting_size=18, user_key='', first_staff_top=60)
            opts = dict(font_path=header['font_path'], font_size=18, text_color=(220,20,20),
                        staff_spacings={0:10}, text_offset_y=22)
            session = dict(original_doc=doc, image=frame, render_options=opts,
                           header_options=header, legend_options=None, region=(0, 0, 170, 160))
            saved = gui._save_edit_version(session, changes, tmp)
            reopened = gui._load_edit_version(str(Path(saved['png']).parent), str(source), tmp)
            original_bytes = Path(saved['png']).read_bytes(), Path(saved['json']).read_bytes()
            updated = gui._restyle_edit_session(reopened, tmp, font_path=opts['font_path'],
                font_size=18, text_color=(220,20,20), placement_mode='near', legend=False,
                notation_state=('solfege-movable', 'D', True))
            self.assertEqual(updated['doc']['music']['tonic'], 'F')
            self.assertTrue(updated['doc']['music']['is_minor'])
            self.assertEqual(updated['doc']['music']['key_override'], 'D')
            self.assertEqual(updated['header_options']['user_key'], 'D')
            self.assertEqual([row['x'] for row in updated['doc']['labels']], [30, 60, 140])
            self.assertEqual([updated['doc']['labels'][i]['text'] for i in (0,2)], ['레','미'])
            self.assertEqual([pitch_to_midi(row, updated['doc']['music']) for row in updated['doc']['labels']],
                             [62, 61, 64])
            self.assertEqual(len(updated['changes']), 3)
            self.assertEqual((Path(saved['png']).read_bytes(), Path(saved['json']).read_bytes()), original_bytes)
            saved_again = gui._save_edit_version(updated, updated['changes'], tmp)
            opened = gui._load_edit_version(str(Path(saved_again['png']).parent), str(source), tmp)
            self.assertEqual(opened['doc'], updated['doc'])
            undo = gui._save_edit_version(dict(updated, region=None), [], tmp)
            self.assertEqual(undo['doc'], updated['original_doc'])
            self.assertEqual(json.loads(Path(undo['json']).read_bytes()), updated['original_doc'])

    def test_rgb_save_reopen_resave_and_undo(self):
        for color in ((220,20,20),(12,34,56)):
            with self.subTest(color=color),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);frame=np.full((180,220,3),255,np.uint8);source=root/'입력.png';Image.fromarray(frame).save(source)
                doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=220,height=180,dpi=300),
                    music=dict(key_symbol='',key_count=0),staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],
                    labels=[dict(staff=0,x=x,y=100,pitch='E4',text='미',confidence=conf,edited=False) for x,conf in ((50,'certain'),(130,'check'))])
                session=dict(original_doc=doc,image=frame,render_options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,text_color=color,staff_spacings={0:10},text_offset_y=22),header_options=None,legend_options=None)
                png=root/'원본.png';js=root/'원본.json';boxes=gui._render_edit_document(session,doc,str(png));save_labels(str(js),doc)
                session.update(original_png=str(png),original_json=str(js),original_placements=boxes)
                original=(png.read_bytes(),js.read_bytes())
                change=dict(action='set_text',before={k:doc['labels'][0][k] for k in ('staff','x','y','pitch','text')},after=dict(text='파'))
                saved=gui._save_edit_version(session,[change],str(root));folder=Path(saved['png']).parent
                metadata=json.loads((folder/'재개정보.json').read_text(encoding='utf-8'))
                self.assertEqual(metadata['render_options']['text_color'],list(color))
                reopened=gui._load_edit_version(str(folder),str(source),str(root))
                self.assertEqual(reopened['doc'],saved['doc']);self.assertEqual(reopened['changes'],[change])
                self.assertEqual(reopened['render_options']['text_color'],color)
                again=gui._save_edit_version(reopened,[change],str(root))
                self.assertEqual(Path(again['png']).read_bytes(),Path(saved['png']).read_bytes())
                undo=gui._save_edit_version(reopened,[],str(root))
                self.assertEqual((Path(undo['png']).read_bytes(),Path(undo['json']).read_bytes()),original)
                previous_png = Path(reopened['png']).read_bytes()
                previous_doc = copy.deepcopy(reopened['doc'])
                style = dict(font_path='C:/Windows/Fonts/malgun.ttf', font_size=22, text_color=(10, 20, 90),
                             placement_mode='near', legend=False)
                updated = gui._restyle_edit_session(reopened, str(root), **style)
                self.assertEqual(updated['doc'], previous_doc)
                self.assertEqual(updated['changes'], [change])
                self.assertNotEqual(Path(updated['png']).read_bytes(), previous_png)
                self.assertEqual(Path(reopened['png']).read_bytes(), previous_png)
                self.assertEqual(Path(updated['json']).read_bytes(), Path(reopened['json']).read_bytes())
                saved_style = gui._save_edit_version(updated, [change], str(root))
                reopened_style = gui._load_edit_version(str(Path(saved_style['png']).parent), str(source), str(root))
                self.assertEqual(reopened_style['render_options']['text_color'], style['text_color'])
                self.assertEqual(reopened_style['doc'], previous_doc)
                self.assertEqual(Path(reopened_style['png']).read_bytes(), Path(updated['png']).read_bytes())
                undo_style = gui._save_edit_version(reopened_style, [], str(root))
                self.assertEqual(Path(undo_style['png']).read_bytes(), Path(updated['original_png']).read_bytes())
                self.assertEqual(Path(undo_style['json']).read_bytes(), original[1])
                self.assertEqual((png.read_bytes(),js.read_bytes()),original)
                self.assertIsNone(gui._restyle_edit_session(updated, str(root), **style))
                photo = dict(updated, report_settings={'photo': True})
                self.assertIsNone(gui._restyle_edit_session(photo, str(root), **{**style, 'legend': True}))
                published=set(root.glob('재열기-*'));saved_bytes=(folder/'결과.png').read_bytes()
                for bad in (None,[],[1,2],[1,2,3,4],[-1,2,3],[256,2,3],[1.5,2,3],[True,2,3],'red'):
                    broken=copy.deepcopy(metadata);broken['render_options']['text_color']=bad
                    (folder/'재개정보.json').write_text(json.dumps(broken),encoding='utf-8')
                    with self.subTest(bad=bad),self.assertRaises(ValueError):gui._load_edit_version(str(folder),str(source),str(root))
                    self.assertEqual((folder/'결과.png').read_bytes(),saved_bytes)
                    self.assertEqual(set(root.glob('재열기-*')),published)
                self.assertEqual((png.read_bytes(),js.read_bytes()),original)

if __name__=='__main__':unittest.main()
