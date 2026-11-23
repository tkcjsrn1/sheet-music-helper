"""700px 창의 고정 버튼·되돌리기 선택·빠른 목록/입력칸 전환을 소스 Tk로 검사한다."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes,save_labels
from modules.renderer import render_solfege_on_image
from tools.check_label_edit_gui import capture


def check_settings_wheel(app):
    """휠은 설정을 바꾸지 않고 패널로 전달된다. 클릭·드래그는 계속 값을 바꾼다."""
    settings_before=dict(app.settings)
    for name in ('clef_menu','notation_menu','font_menu','size_slider'):
        widget=getattr(app,name)
        targets=[widget._canvas]+([widget._text_label] if name.endswith('_menu') else [])
        for target in targets:
            for delta in (-120,120):
                app.sidebar._parent_canvas.yview_moveto(.2);app.update()
                value=widget.get();view=app.sidebar._parent_canvas.yview()
                target.event_generate('<MouseWheel>',delta=delta);app.update()
                assert widget.get()==value, f'{name}: 휠로 설정 값이 바뀜'
                assert app.sidebar._parent_canvas.yview()!=view, f'{name}: 휠이 패널을 스크롤하지 않음'
    slider=app.size_slider;initial=slider.get();canvas=slider._canvas
    canvas.event_generate('<Button-1>',x=int(canvas.winfo_width()*.8),y=8);app.update()
    clicked=slider.get();assert clicked!=initial,'슬라이더 클릭이 막힘'
    canvas.event_generate('<B1-Motion>',x=int(canvas.winfo_width()*.3),y=8);app.update()
    assert slider.get()!=clicked,'슬라이더 드래그가 막힘'
    slider.set(initial);app._on_size_slide(initial)
    assert app.settings==settings_before
    print('슬라이더/드롭다운 휠 값 유지·패널 스크롤·슬라이더 클릭/드래그: 통과')

def check_label_add_help(app, capture_dir):
    from tkinter.font import Font
    message='악보의 빈 곳을 두 번 클릭하면 라벨을 추가할 수 있습니다'
    texts=[w.cget('text') for w in app._edit_window.winfo_children() if isinstance(w,gui.ctk.CTkLabel)]
    assert any(message in text for text in texts),'수정/삭제 창에 라벨 추가 안내가 없음'
    if capture_dir:
        app._edit_window.geometry(f'520x460+{app.winfo_rootx()+30}+{app.winfo_rooty()+40}')
        capture(app,capture_dir/'label_editor_help.png')
    app._open_label_add(200,100);app.update()
    for entry in (app._add_pitch,app._add_text):
        needed=Font(root=app,font=entry._entry.cget('font')).measure(entry.cget('placeholder_text'))
        assert entry._entry.winfo_width()>=needed,'라벨 추가 예시 문구가 입력칸보다 넓음'
    if capture_dir:
        app._add_window.geometry(f'440x320+{app.winfo_rootx()+30}+{app.winfo_rooty()+40}')
        capture(app,capture_dir/'label_add_help.png')
    print('라벨 추가 안내·두 입력칸 예시 문구 폭: 통과')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture-dir',type=Path)
    p.add_argument('--phase',choices=('before','after'),default='after')
    args=p.parse_args()
    gui.ctk.set_window_scaling(1);gui.ctk.set_widget_scaling(1)
    with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
        app=gui.SheetHelperApp()
        # Windows DPI 대응은 유지하고 비교 캡처만 총 배율1로 맞춘다.
        scaling=app._get_window_scaling()
        gui.ctk.set_window_scaling(1/scaling);gui.ctk.set_widget_scaling(1/scaling)
        # CTk가 배율 변경 직후 1초 동안 창 크기를 잠그는 동안에는 기하 설정을 기다린다.
        deadline=time.monotonic()+1.2
        while time.monotonic()<deadline:
            app.update();time.sleep(.02)
        app.geometry('1280x700+20+20')
        try:
            folder=Path(tmp);source=folder/'화면검증용.png'
            Image.new('RGB',(1400,220),'white').save(source)
            app._set_input(str(source));app.update()
            app._draw_placeholder('화면 배치 검증\n악보 원본은 캡처에 포함하지 않았습니다.')
            app.update()
            if args.capture_dir:
                args.capture_dir.mkdir(parents=True,exist_ok=True)
                capture(app,args.capture_dir/f'gui_{args.phase}_1280x700.png')
            positions=lambda:[(b.winfo_rooty()-app.winfo_rooty(),b.winfo_height()) for b in (app.select_btn,app.convert_btn)]
            initial=positions()
            print('창 크기/배율',app.winfo_width(),app.winfo_height(),app._get_window_scaling(), '파일 선택·변환 (y,높이):',initial,flush=True)
            assert app.winfo_width()==1280 and app.winfo_height()==700
            assert all(0<=y and y+h<=700 for y,h in initial),'주요 버튼이 700px 창 밖으로 밀림'
            app.sidebar._parent_canvas.yview_moveto(1);app.update()
            assert positions()==initial,'설정 스크롤이 파일 선택/변환 버튼을 숨김'
            assert app.settings==dict(gui.DEFAULT_SETTINGS,last_input_dir=str(folder)),'입력 폴더 외 기본 인식 설정 변화'
            if args.phase=='before':return
            check_settings_wheel(app)
            # 정답 인식과 무관한 자체 생성 라벨/흰 이미지로 편집을 검사한다.
            doc=dict(schema=1,source=dict(sha256='ui-test',page=0,width=1400,height=220,dpi=300),
                music=dict(key_symbol='',key_count=0),staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],
                labels=[dict(staff=0,x=30+i*40,y=100,pitch='E4',text=f'미{i}',confidence='check',edited=False) for i in range(30)])
            image=np.full((220,1400,3),255,np.uint8)
            options=dict(font_path=r'C:\Windows\Fonts\malgun.ttf',font_size=18,staff_spacings={0:10},text_offset_y=22)
            png=folder/'원본결과.png';js=folder/'원본라벨.json'
            placements=render_solfege_on_image(image,document_notes(doc),str(png),confidences=['check']*30,**options)
            save_labels(str(js),doc)
            app._edit_session=dict(original_doc=copy.deepcopy(doc),doc=copy.deepcopy(doc),changes=[],image=image,
                render_options=options,header_options=None,legend_options=None,original_png=str(png),
                original_json=str(js),original_placements=placements,placements=placements)
            app.output_dir=tmp;app.result_path=str(png);app.labels_path=str(js)
            app._open_label_editor([17]);app.update()
            app._edit_text.delete(0,'end');app._edit_text.insert(0,'파')
            app._change_label('set_text');app._undo_label_edit();app.update()
            assert app._edit_list.curselection()==(17,),'수정 취소 대상 대신 목록 첫 행을 선택함'
            assert app._edit_text.get()=='미17'
            app._refresh_label_editor(12);app._change_label('delete');app._undo_label_edit();app.update()
            assert app._edit_list.curselection()==(12,),'삭제 취소로 복원한 라벨이 선택되지 않음'
            assert app._edit_session['doc']==doc
            if args.capture_dir:
                app._edit_window.geometry(f'520x460+{app.winfo_rootx()+30}+{app.winfo_rooty()+40}')
                app._preview_source=None;app._draw_placeholder('자체 생성 편집 테스트 · 악보 원본 제외')
                capture(app,args.capture_dir/'undo_restored_label.png')
            for index in [2,17,5,27]*25:
                app._edit_list.see(index);app.update()
                x,y,w,h=app._edit_list.bbox(index)
                app._edit_list.event_generate('<Button-1>',x=x+3,y=y+h//2)
                app._edit_list.event_generate('<ButtonRelease-1>',x=x+3,y=y+h//2)
                app._edit_text._entry.event_generate('<Button-1>',x=5,y=5)
                app._edit_text._entry.event_generate('<ButtonRelease-1>',x=5,y=5)
                app.update()
                assert app._edit_list.curselection()==(index,),'빠른 입력칸 클릭 뒤 선택이 이동함'
            print('설정 스크롤 뒤 버튼 고정·기본 설정 유지·수정/삭제 취소 대상 선택: 통과')
            print('소스 Tk 목록→입력칸 빠른 전환100회: 선택 이동 재현 안 됨 (exe 직접 클릭 검증과 구분)')
            check_label_add_help(app,args.capture_dir)
        finally:
            app._close_label_editor();app.destroy()

if __name__=='__main__':main()
