"""작업 시작 뒤 원본/설정 변경이 PNG·JSON·신고 원본에 섞이지 않는다."""
import sys
from pathlib import Path
import tempfile
import json
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui

def main():
    source=str(Path('sample_images/KakaoTalk_20260731_162400402.png').resolve())
    with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
        app=gui.SheetHelperApp();app.withdraw()
        try:
            app._set_input(source);app.output_dir=str(Path(tmp)/'baseline')
            app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
            png=app._convert_page(0,'')
            baseline=(Path(png).read_bytes(),Path(app.labels_path).read_bytes())
            app.output_dir=str(Path(tmp)/'job')
            with patch('gui.threading.Thread'):app.start_convert()
            # 단일 입력과 같게, 변환 중 여러 이미지 선택으로 다음 입력·표시가 섞이지 않는다.
            before_selection=(app.input_path,app.input_paths,app.file_label.cget('text'),app._run_request)
            with patch('gui.filedialog.askopenfilenames',return_value=('다른입력1.png','다른입력2.png')):
                app.select_images_btn.invoke()
            assert (app.input_path,app.input_paths,app.file_label.cget('text'),app._run_request)==before_selection, '변환 중 입력 선택이 섞였습니다'
            app.input_path='다른_원본.png';app.output_dir=str(Path(tmp)/'changed')
            app.settings['font_size']=50;app.settings['text_color']='#000000'
            app.clef_menu.set('모두 낮은음자리표');app.notation_menu.set('영문 (C D E)')
            app._current_font_path=lambda:(_ for _ in ()).throw(AssertionError('작업 중 글꼴 위젯 읽기'))
            png=app._convert_page(0,'')
            assert (Path(png).read_bytes(),Path(app.labels_path).read_bytes())==baseline
            assert Path(png).parent==Path(tmp)/'job'
            assert app._edit_session['source_path']==source
            assert app._edit_session['report_settings']['font_size']==18
            assert not (Path(tmp)/'changed').exists()
            app.result_path=png
            bundle=Path(tmp)/'report.zip'
            with patch('gui.filedialog.asksaveasfilename',return_value=str(bundle)) as dialog:
                app.save_feedback();app.save_as()
                dialog.assert_not_called()
            assert not bundle.exists(), '변환 중 결과 파일을 저장했습니다'
            app._converting=False
            with patch('gui.filedialog.asksaveasfilename',return_value=str(bundle)):
                app.save_feedback()
            with zipfile.ZipFile(bundle) as z:
                assert z.read('original.png')==Path(source).read_bytes()
                assert json.loads(z.read('report.json'))['settings']['font_size']==18
            exported=Path(tmp)/'exported.png'
            with patch('gui.filedialog.asksaveasfilename',return_value=str(exported)):
                app.save_as()
            assert exported.read_bytes()==baseline[0]
            app._set_input(source)
            app._current_font_path=lambda:r'C:\Windows\Fonts\malgun.ttf'
            app.clef_menu.set('자동 인식 (추천)');app.notation_menu.set('계이름 (고정도)')
            with patch('gui.threading.Thread',side_effect=RuntimeError('작업 시작 실패')):
                app.start_convert()
            assert not app._converting and app._run_request is None
            assert app.convert_btn.cget('state')=='normal' 
            # 대기 상태의 정상 여러 이미지 선택은 그대로 동작한다.
            second=str(Path(tmp)/'second.png');gui.Image.new('RGB',(20,20),'white').save(second)
            with patch('gui.filedialog.askopenfilenames',return_value=(source,second)):
                app.select_images_btn.invoke()
            assert app.input_path==source and app.input_paths==(source,second)
            assert app.file_label.cget('text').endswith('외 1장')
        finally:app.destroy()
    print('변환 원본·설정 고정, PNG/JSON 바이트 동일: 통과')

def check_failed_conversion():
    """실제 쪽 편집 캐시 저장 실패 뒤 이전 PNG와 새 JSON을 묶지 않는다."""
    source=str(Path('sample_images/KakaoTalk_20260731_162400402.png').resolve())
    with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
        root=Path(tmp);second=root/'copy.png';second.write_bytes(Path(source).read_bytes())
        app=gui.SheetHelperApp();app.withdraw();app.output_dir=str(root/'job')
        try:
            app._set_input(source)
            app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
            app.result_path=app._convert_page(0,'');app._show_result();app.update()
            baseline=(Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())
            row=app._edit_session['doc']['labels'][0]
            before={k:row[k] for k in ('staff','x','y','pitch','text')}
            assert app._apply_label_changes([dict(action='set_text',before=before,after=dict(text='사용자수정'))])
            saved=(Path(app.result_path),Path(app.labels_path))
            saved_bytes=tuple(p.read_bytes() for p in saved)
            app.input_paths=(source,str(second))
            with patch('gui.threading.Thread'):app.start_convert()
            original_save=gui.Image.Image.save
            def fail_cache(image,path,*args,**kwargs):
                if '.쪽편집-' in str(path):raise OSError('주입: 쪽 편집 캐시 저장 실패')
                return original_save(image,path,*args,**kwargs)
            with patch('gui.Image.Image.save',fail_cache):app._convert_worker()
            app.update()
            assert not app._converting
            assert app.result_path is None and app.labels_path is None, '실패 뒤 이전 PNG와 새 JSON이 남았습니다'
            assert app._edit_session is None and not app._page_sessions
            for button in (app.save_as_btn,app.report_btn,app.edit_btn,app.open_result_btn):
                assert button.cget('state')=='disabled'
            with patch('gui.filedialog.asksaveasfilename',return_value=str(root/'report.zip')) as dialog:
                app.save_feedback();app.save_as();dialog.assert_not_called()
            assert tuple(p.read_bytes() for p in saved)==saved_bytes, '이미 저장한 수정본이 바뀌었습니다'
            # 저장 공간이 회복되면 같은 입력을 다시 변환하고 첫 성공 쪽을 내보낸다.
            with patch('gui.threading.Thread'):app.start_convert()
            app._convert_worker();app.update()
            assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==baseline
            assert len(app._page_sessions)==2 and app._edit_session is app._page_sessions[0]
            assert app.save_as_btn.cget('state')=='normal' and app.report_btn.cget('state')=='normal'
            assert tuple(p.read_bytes() for p in saved)==saved_bytes
        finally:app._clear_result_pages();app.destroy()
    print('전체 변환 실패의 결과 혼합 차단·저장 수정본 보존·재시도: 통과')

if __name__=='__main__':
    main()
    check_failed_conversion()
