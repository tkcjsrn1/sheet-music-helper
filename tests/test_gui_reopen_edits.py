"""수정본 재열기는 원본 검사·수정/삭제/추가·연속 되돌리기를 보존한다."""
import copy,hashlib,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes,save_labels
from modules.renderer import render_solfege_on_image

def check_multipage_reopen(root, doc, options, review=None):
    """둘째 쪽 저장→재열기→추가 수정→연속 취소를 실제 GUI 핸들러로 검사한다."""
    import time
    from tools.check_label_edit_gui import capture
    pages=[]
    for index in range(2):
        frame=np.full((180,220,3),255,np.uint8)
        frame[1,1]=[30+index,60,120]  # 서로 다른 원본 해시, BGR 왕복도 확인한다.
        source=root/f'입력{index+1}.png';Image.fromarray(frame[:,:,::-1]).save(source)
        original=copy.deepcopy(doc);original['source']['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        original['source']['file']=source.name
        session=dict(original_doc=original,doc=copy.deepcopy(original),changes=[],image=frame,source_path=str(source),render_options=options,header_options=None,legend_options=None,report_settings={})
        png=root/f'쪽{index+1}.png';js=root/f'쪽{index+1}.json';frame_path=root/f'프레임{index+1}.png';Image.fromarray(frame[:,:,::-1]).save(frame_path)
        boxes=gui._render_edit_document(session,original,str(png));save_labels(str(js),original)
        session.update(original_png=str(png),original_json=str(js),original_placements=boxes,placements=boxes,png=str(png),json=str(js),frame_path=str(frame_path))
        if index:session['image']=None
        pages.append(session)
    original_second=(Path(pages[1]['png']).read_bytes(),Path(pages[1]['json']).read_bytes())
    with patch('gui.base_dir',return_value=str(root)),patch.object(sys,'argv',['gui.py']):
        app=gui.SheetHelperApp();app.output_dir=str(root)
        try:
            if review:
                factor=app._get_window_scaling();gui.ctk.set_window_scaling(1/factor);gui.ctk.set_widget_scaling(1/factor)
                until=time.monotonic()+1.2
                while time.monotonic()<until:app.update();time.sleep(.02)
                app.geometry('1280x700+20+20');app.update()
            else:app.withdraw()
            app._set_input(pages[0]['source_path']);app.input_paths=tuple(p['source_path'] for p in pages)
            app._page_sessions=pages;app._page_index=0;app._edit_session=pages[0];app.result_path=pages[0]['png'];app.labels_path=pages[0]['json'];app._show_result();app.update()
            app.next_page_btn.invoke();app.update()
            assert app._edit_session is pages[1] and app.file_label.cget('text')=='입력2.png'
            assert app.input_paths==tuple(p['source_path'] for p in pages)
            app._open_label_editor([0]);app.update();app._edit_text.delete(0,'end');app._edit_text.insert(0,'솔');app._change_label('set_text');app.update()
            destination=root/'내보낸수정본';destination.mkdir()
            with patch('gui.filedialog.askdirectory',return_value=str(destination)):app._export_label_edits()
            saved_folder=next(destination.glob('사용자수정-*'));saved_doc=json.loads((saved_folder/'라벨.json').read_text(encoding='utf-8'))
            assert saved_doc['labels'][0]['text']=='솔' and saved_doc['source']['sha256']==pages[1]['original_doc']['source']['sha256']
            saved_png=(saved_folder/'결과.png').read_bytes();app._close_label_editor();app.update()
            if review:capture(app,review/'04_second_page_saved.png')
            with patch('gui.filedialog.askdirectory',return_value=str(saved_folder)),patch('gui.filedialog.askopenfilename',return_value=pages[1]['source_path']):app.reopen_edits_btn.invoke();app.update()
            assert app._edit_session['doc']==saved_doc and Path(app.result_path).read_bytes()==saved_png
            assert np.array_equal(app._edit_session['image'][1,1],[31,60,120])
            assert app.file_label.cget('text')=='입력2.png'
            app._open_label_editor([0]);app.update();app._edit_text.delete(0,'end');app._edit_text.insert(0,'라');app._change_label('set_text');app.update()
            assert len(app._edit_session['changes'])==2 and app._edit_session['doc']['labels'][0]['text']=='라'
            if review:
                app._edit_window.geometry(f'520x460+{app.winfo_rootx()+30}+{app.winfo_rooty()+40}');capture(app,review/'05_reopened_continue.png')
            app._undo_label_edit();app.update();assert app._edit_session['doc']==saved_doc and Path(app.result_path).read_bytes()==saved_png
            app._undo_label_edit();app.update();app._close_label_editor()
            assert app._edit_session['doc']==pages[1]['original_doc']
            assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==original_second
            if review:capture(app,review/'06_undo_original.png')
        finally:app._close_label_editor();app._clear_result_pages();app.destroy()
    print('둘째 쪽 수정·내보내기·재열기·추가수정·연속취소·원본 PNG/JSON·BGR 보존: 통과')


def main():
    load=getattr(gui,'_load_edit_version',None)
    assert callable(load),'수정본 폴더 다시 열기 경로가 없다'
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp); source=root/'source.png'; Image.new('RGB',(220,180),'white').save(source)
        doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=220,height=180,dpi=300),
                 music=dict(key_symbol='',key_count=0),staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],
                 labels=[dict(staff=0,x=50,y=100,pitch='E4',text='미',confidence='check',edited=False),
                         dict(staff=0,x=130,y=100,pitch='E4',text='미',confidence='certain',edited=False)])
        options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,staff_spacings={0:10},text_offset_y=22)
        frame=np.full((180,220,3),255,np.uint8); png=root/'original.png'; js=root/'original.json'
        placements=render_solfege_on_image(frame,document_notes(doc),str(png),confidences=['check','certain'],**options)
        save_labels(str(js),doc); before=(png.read_bytes(),js.read_bytes())
        session=dict(original_doc=doc,doc=doc,source_path=str(source),image=frame,render_options=options,
                     header_options=None,legend_options=None,original_png=str(png),original_json=str(js),original_placements=placements)
        target=lambda row:{k:row[k] for k in ('staff','x','y','pitch','text')}
        changes=[dict(action='set_text',before=target(doc['labels'][0]),after=dict(text='파')),
                 dict(action='delete',before=target(doc['labels'][1])),
                 dict(action='add',after=dict(staff=0,x=180,y=100,pitch='C4',text='도'))]
        saved=gui._save_edit_version(session,changes,str(root)); folder=Path(saved['png']).parent
        fresh_output = root / '새 설치' / 'output'
        assert not fresh_output.exists()
        loaded=load(str(folder),str(source),str(fresh_output))
        assert Path(loaded['original_png']).parent.parent == fresh_output
        assert loaded['doc']==saved['doc'] and loaded['changes']==changes
        assert Path(loaded['png']).read_bytes()==Path(saved['png']).read_bytes()
        assert loaded['original_doc']==doc and np.array_equal(loaded['image'],frame)
        for count in (2,1,0):
            restored=gui._save_edit_version(loaded,changes[:count],str(root))
        assert Path(restored['png']).read_bytes()==before[0] and Path(restored['json']).read_bytes()==before[1]
        # 없는 원본·다른 원본·손상 기록은 열지 않는다.
        raw=source.read_bytes(); source.unlink()
        try: load(str(folder),str(source),str(root)); assert False,'원본 없이 열었다'
        except (ValueError,OSError): pass
        source.write_bytes(raw+b'changed')
        try: load(str(folder),str(source),str(root)); assert False,'해시가 다른데 열었다'
        except ValueError: pass
        source.write_bytes(raw)
        metadata=folder/'재개정보.json'; original=metadata.read_bytes()
        metadata.write_text('{broken',encoding='utf-8')
        try: load(str(folder),str(source),str(root)); assert False,'손상 기록으로 열었다'
        except ValueError: pass
        metadata.write_bytes(original)
        # 손상된 간격 목록은 GUI 콜백 예외가 아니라 열기 거부로 처리한다.
        for bad_spacing in (None, [], [10], 10, {'0': float('inf')}, {'0': float('nan')}, {'0': 0}, {'0': -10}):
            damaged = json.loads(original)
            damaged['render_options']['staff_spacings'] = bad_spacing
            metadata.write_text(json.dumps(damaged), encoding='utf-8')
            try: load(str(folder),str(source),str(root)); assert False,'손상된 간격 목록으로 열었다'
            except ValueError: pass
        messages = []
        app = SimpleNamespace(_converting=False,output_dir=str(root),result_path='이전',log=messages.append)
        with patch('gui.filedialog.askdirectory',return_value=str(folder)),patch('gui.filedialog.askopenfilename',return_value=str(source)):
            gui.SheetHelperApp._open_saved_edits(app)
        assert app.result_path == '이전' and '보표 간격' in messages[-1]
        metadata.write_bytes(original)
        # 글꼴 경로/위치 값 손상도 콜백에서 빠져나가지 않고 이전 결과를 유지한다.
        saved_bytes=(Path(saved['png']).read_bytes(),Path(saved['json']).read_bytes())
        saved_folders=set(root.glob('재열기-*'))
        for field,bad_value in (('font_path',{}),('text_offset_y',float('inf'))):
            damaged=json.loads(original);damaged['render_options'][field]=bad_value
            metadata.write_text(json.dumps(damaged),encoding='utf-8')
            messages=[]
            app=SimpleNamespace(_converting=False,output_dir=str(root),result_path='이전',log=messages.append)
            with patch('gui.filedialog.askdirectory',return_value=str(folder)),patch('gui.filedialog.askopenfilename',return_value=str(source)):
                gui.SheetHelperApp._open_saved_edits(app)
            assert app.result_path=='이전' and '열지 않았습니다' in messages[-1]
            assert (Path(saved['png']).read_bytes(),Path(saved['json']).read_bytes())==saved_bytes
            assert set(root.glob('재열기-*'))==saved_folders
        metadata.write_bytes(original)
        metadata.unlink()
        try: load(str(folder),str(source),str(root)); assert False,'이전 형식을 임의 복원했다'
        except ValueError: pass
        metadata.write_bytes(original)
        final_json=folder/'라벨.json'; valid_json=final_json.read_bytes()
        altered=json.loads(valid_json); altered['labels'][0]['text']='다름'; save_labels(str(final_json),altered)
        try: load(str(folder),str(source),str(root)); assert False,'수정 기록과 다른 라벨을 열었다'
        except ValueError: pass
        final_json.write_bytes(valid_json)
        messages=[]
        app=SimpleNamespace(_converting=False,output_dir=str(root),result_path='이전',log=messages.append)
        with patch('gui.filedialog.askdirectory',return_value=str(folder)),patch('gui.filedialog.askopenfilename',return_value=str(source)),patch('gui._load_edit_version',side_effect=ValueError('원본 해시 불일치')):
            gui.SheetHelperApp._open_saved_edits(app)
        assert app.result_path=='이전' and '원본 해시 불일치' in messages[-1]
        assert (png.read_bytes(),js.read_bytes())==before
        review=None
        if '--capture-dir' in sys.argv:
            review=Path(sys.argv[sys.argv.index('--capture-dir')+1]);review.mkdir(parents=True,exist_ok=True)
        check_multipage_reopen(root,doc,options,review)
        if '--capture-dir' in sys.argv:
            import time
            from tools.check_label_edit_gui import capture
            review=Path(sys.argv[sys.argv.index('--capture-dir')+1]);review.mkdir(parents=True,exist_ok=True)
            with patch('gui.base_dir',return_value=str(root)),patch.object(sys,'argv',['gui.py']):
                app=gui.SheetHelperApp();app.output_dir=str(root)
                try:
                    factor=app._get_window_scaling();gui.ctk.set_window_scaling(1/factor);gui.ctk.set_widget_scaling(1/factor)
                    until=time.monotonic()+1.2
                    while time.monotonic()<until:app.update();time.sleep(.02)
                    app.geometry('1280x700+20+20');app.update()
                    app._draw_placeholder('저장한 수정본 다시 열기 · 자체 생성 이미지')
                    capture(app,review/'01_before_open.png')
                    with patch('gui.filedialog.askdirectory',return_value=str(folder)),patch('gui.filedialog.askopenfilename',return_value=str(source)):
                        app.reopen_edits_btn.invoke();app.update()
                    assert app._edit_session['changes']==changes
                    capture(app,review/'02_reopened.png')
                    app._open_label_editor([0]);app.update();app._undo_label_edit();app.update()
                    assert app._edit_session['changes']==changes[:2]
                    capture(app,review/'03_continue_undo.png')
                    for _ in range(2):app._undo_label_edit();app.update()
                    assert app._edit_session['doc']==doc
                    assert Path(app.result_path).read_bytes()==before[0] and Path(app.labels_path).read_bytes()==before[1]
                    print('소스 Tk 재열기 버튼·연속 되돌리기·세 화면 캡처: 통과')
                finally:app._close_label_editor();app.destroy()
    print('재열기·수정/삭제/추가 연속 되돌리기·원본 거부·무편집 바이트 유지: 통과')
if __name__=='__main__':main()
