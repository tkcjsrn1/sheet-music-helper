"""표시 방식은 설정/변환 스냅샷/수정본 재열기에서 유지되고 인식 JSON을 바꾸지 않는다."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace, MethodType
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import save_labels

class PlacementMode(unittest.TestCase):
    def close_app(self, app):
        # 이전 창의 예약 콜백이 재시작 검사로 넘어가지 않게 기존 fixture처럼 정리한다.
        widgets=[app]
        for widget in widgets:widgets.extend(widget.winfo_children())
        owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None) or [])}
        for timer in app.tk.splitlist(app.tk.call('after','info')):
            owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0])
            owner.after_cancel(timer) if owner else app.tk.call('after','cancel',timer)
        app.destroy()
    def test_new_input_clears_the_previous_page_fallback_notice(self):
        app=SimpleNamespace(_converting=False,settings={},_save_settings=Mock(),_close_label_editor=Mock(),_stop_listening=Mock(),
            _edit_session={'placement_notice':'이전 쪽의 공간 부족 안내'},_update_review_controls=Mock(),
            placement_notice=Mock(),prev_page_btn=Mock(),next_page_btn=Mock(),page_nav=Mock(),
            edit_btn=Mock(),file_label=Mock(),open_result_btn=Mock(),save_as_btn=Mock(),report_btn=Mock(),
            log=Mock(),_load_preview_image=Mock())
        app._update_placement_notice=MethodType(gui.SheetHelperApp._update_placement_notice,app)
        app._update_page_controls=MethodType(gui.SheetHelperApp._update_page_controls,app)
        app._clear_result_pages=MethodType(gui.SheetHelperApp._clear_result_pages,app)
        gui.SheetHelperApp._set_input(app,'new.png')
        app._stop_listening.assert_called_once()
        self.assertIsNone(app._edit_session)
        self.assertEqual(app.placement_notice.configure.call_args.kwargs['text'],'')
        app.placement_notice.grid_remove.assert_called_once()

    def test_setting_persists_and_invalid_value_returns_default(self):
        self.assertIn('placement_mode',gui.DEFAULT_SETTINGS)
        self.assertEqual(gui.DEFAULT_SETTINGS['placement_mode'],'near')
        with tempfile.TemporaryDirectory() as tmp, patch('gui.base_dir',return_value=tmp), patch.object(sys,'argv',['gui.py']):
            app=gui.SheetHelperApp();app.withdraw()
            try:
                app.placement_menu.set('계이름 줄');app._on_setting_changed()
                self.assertEqual(app.settings['placement_mode'],'lanes')
                self.assertEqual(app._load_settings()['placement_mode'],'lanes')
            finally:self.close_app(app)
            app=gui.SheetHelperApp();app.withdraw()
            try:
                self.assertEqual(app.placement_menu.get(),'계이름 줄')
                saved=Path(tmp)/'settings.json';v=json.loads(saved.read_text(encoding='utf-8'));v['placement_mode']='invalid'
                saved.write_text(json.dumps(v),encoding='utf-8')
                self.assertEqual(app._load_settings()['placement_mode'],'near')
            finally:self.close_app(app)

    def test_edited_folder_keeps_the_mode_without_label_metadata(self):
        self.assertIn('placement_mode',gui.DEFAULT_SETTINGS)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.png';frame=np.full((400,360,3),255,np.uint8)
            Image.fromarray(frame).save(source)
            doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=360,height=400,dpi=300),music=dict(key_symbol='',key_count=0),
                staves=[dict(id=0,line_ys=[90,110,130,150,170],spacing=20)],
                labels=[dict(staff=0,x=120,y=150,pitch='E4',text='미',confidence='check',edited=False)])
            original=copy.deepcopy(doc)
            from modules.labels_io import document_staves
            session=dict(original_doc=doc,doc=doc,changes=[],source_path=str(source),image=frame,
                render_options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,staff_spacings={0:20},staves=document_staves(doc),placement_mode='lanes'),header_options=None,legend_options=None)
            png=root/'original.png';js=root/'original.json'
            ps=gui._render_edit_document(session,doc,str(png));save_labels(str(js),doc)
            session.update(original_png=str(png),original_json=str(js),original_placements=ps,placements=ps)
            before={k:doc['labels'][0][k] for k in ('staff','x','y','pitch','text')}
            changes=[dict(action='set_text',before=before,after=dict(text='파'))]
            result=gui._save_edit_version(session,changes,str(root));folder=Path(result['png']).parent
            metadata=json.loads((folder/'재개정보.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['render_options']['placement_mode'],'lanes')
            self.assertEqual(doc,original)
            self.assertNotIn('placement_mode',result['doc'])
            loaded=gui._load_edit_version(str(folder),str(source),str(root))
            self.assertEqual(loaded['render_options']['placement_mode'],'lanes')
            self.assertEqual(loaded['doc'],result['doc'])
            self.assertEqual(Path(loaded['png']).read_bytes(),Path(result['png']).read_bytes())
            metadata['render_options']['placement_mode']='invalid';(folder/'재개정보.json').write_text(json.dumps(metadata),encoding='utf-8')
            with self.assertRaises(ValueError):gui._load_edit_version(str(folder),str(source),str(root))

if __name__=='__main__':unittest.main()
