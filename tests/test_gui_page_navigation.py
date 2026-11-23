"""쪽 넘기기는 현재 쪽의 수정 대상·기록·결과를 함께 바꾼다."""
import copy,hashlib,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes,save_labels
from modules.renderer import render_solfege_on_image

def main():
    assert callable(getattr(gui.SheetHelperApp,'_select_result_page',None)),'쪽 선택 경로가 없다'
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);pages=[]
        for index,text in enumerate(['미','파']):
            image=np.full((180,220,3),255,np.uint8);source=root/f'입력{index+1}.png';Image.fromarray(image).save(source)
            doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=220,height=180,dpi=300),music=dict(key_symbol='',key_count=0),staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],labels=[dict(staff=0,x=70,y=100,pitch='E4',text=text,confidence='check',edited=False)])
            options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,staff_spacings={0:10},text_offset_y=22)
            png=root/f'결과{index+1}.png';js=root/f'라벨{index+1}.json';frame=root/f'프레임{index+1}.png';Image.fromarray(image).save(frame)
            boxes=render_solfege_on_image(image,document_notes(doc),str(png),confidences=['check'],**options);save_labels(str(js),doc)
            pages.append(dict(original_doc=doc,doc=copy.deepcopy(doc),changes=[],image=image if index==0 else None,frame_path=str(frame),source_path=str(source),render_options=options,header_options=None,legend_options=None,original_png=str(png),original_json=str(js),original_placements=boxes,placements=boxes,png=str(png),json=str(js)))
        originals=[(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in pages]
        from unittest.mock import MagicMock
        name_app=SimpleNamespace(_page_sessions=pages,_page_index=1,_converting=False,page_nav=MagicMock(),page_label=MagicMock(),prev_page_btn=MagicMock(),next_page_btn=MagicMock(),file_label=MagicMock())
        gui.SheetHelperApp._update_page_controls(name_app)
        assert name_app.file_label.configure.call_args.kwargs['text']==Path(pages[1]['source_path']).name

        seen=[];messages=[]
        app=SimpleNamespace(_converting=False,_page_sessions=pages,_page_index=0,_edit_session=pages[0],result_path=pages[0]['png'],labels_path=pages[0]['json'],input_path=pages[0]['source_path'],input_paths=tuple(p['source_path'] for p in pages),output_dir=tmp,_edit_window=None,_region_start=None,log=messages.append,_close_label_editor=lambda:None,_stop_listening=lambda:None,_show_result=lambda:seen.append(app._edit_session),_redraw_preview=lambda:None)
        app._apply_label_changes=lambda changes,selected=0:gui.SheetHelperApp._apply_label_changes(app,changes,selected)
        select=lambda i:gui.SheetHelperApp._select_result_page(app,i)
        assert select(1) and app._edit_session is pages[1] and app._page_index==1
        label=pages[1]['doc']['labels'][0];before={k:label[k] for k in ('staff','x','y','pitch','text')}
        change=dict(action='set_text',before=before,after=dict(text='솔'))
        assert app._apply_label_changes([change]);edited=(app.result_path,app.labels_path)
        assert select(0) and app._edit_session['doc']==pages[0]['original_doc']
        assert select(1) and (app.result_path,app.labels_path)==edited and app._edit_session['doc']['labels'][0]['text']=='솔'
        gui.SheetHelperApp._undo_label_edit(app)
        assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==originals[1]
        assert select(0) and app.input_paths==tuple(p['source_path'] for p in pages)
        prior=(app._page_index,app._edit_session,app.result_path,app.labels_path)
        app._converting=True;assert not select(1);app._converting=False
        assert not select(-1) and not select(2)
        Path(pages[1]['png']).unlink();assert not select(1)
        assert prior==(app._page_index,app._edit_session,app.result_path,app.labels_path)
        assert (Path(pages[0]['png']).read_bytes(),Path(pages[0]['json']).read_bytes())==originals[0]
        assert pages[1]['image'] is None and np.array_equal(pages[0]['image'],np.full((180,220,3),255,np.uint8))
        if '--capture-dir' in sys.argv:
            import time
            from tools.check_label_edit_gui import capture
            review=Path(sys.argv[sys.argv.index('--capture-dir')+1]);review.mkdir(parents=True,exist_ok=True)
            Path(pages[1]['png']).write_bytes(originals[1][0])
            with patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
                app=gui.SheetHelperApp();app.output_dir=tmp
                try:
                    factor=app._get_window_scaling();gui.ctk.set_window_scaling(1/factor);gui.ctk.set_widget_scaling(1/factor)
                    until=time.monotonic()+1.2
                    while time.monotonic()<until:app.update();time.sleep(.02)
                    app.geometry('1280x700+20+20');app.update()
                    app._set_input(pages[0]['source_path']);app.input_paths=tuple(p['source_path'] for p in pages)
                    app._page_sessions=pages;app._page_index=0;app._edit_session=pages[0];app.result_path=pages[0]['png'];app.labels_path=pages[0]['json']
                    app._show_result();app.update();capture(app,review/'01_first_page.png')
                    app.next_page_btn.invoke();app.update();assert app._edit_session is pages[1]
                    assert app.file_label.cget('text')==Path(pages[1]['source_path']).name
                    app._open_label_editor([0]);app.update();app._edit_text.delete(0,'end');app._edit_text.insert(0,'솔');app._change_label('set_text');app.update()
                    assert app._edit_session['doc']['labels'][0]['text']=='솔'
                    app._edit_window.geometry(f'520x460+{app.winfo_rootx()+30}+{app.winfo_rooty()+40}')
                    capture(app,review/'02_edit_second_page.png')
                    app.prev_page_btn.invoke();app.update();assert app._edit_session is pages[0]
                    capture(app,review/'03_first_page_unchanged.png')
                    app.next_page_btn.invoke();app.update();assert app._edit_session['doc']['labels'][0]['text']=='솔'
                    app._undo_label_edit();app.update();assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==originals[1]
                    print('소스 Tk 이전/다음 버튼·둘째 쪽 수정·쪽별 기록 유지·세 화면 캡처: 통과')
                finally:app._close_label_editor();app._clear_result_pages();app.destroy()
    print('현재 쪽 수정·쪽별 기록 유지·되돌리기·첫 쪽 바이트 보존·실패 원자성: 통과')
if __name__=='__main__':main()
