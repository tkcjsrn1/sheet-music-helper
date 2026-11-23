"""D-3 GUI 실제 변환·무편집 바이트 대조·편집 화면 기록. 인식 판정은 바꾸지 않는다.

python tools/check_label_edit_gui.py --baseline-dir output/d3-before-gui
캡처는 테스트 앱 위젯을 조작한 실제 Windows 화면이다. 사람이 클릭한 검증은 별도다.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PIL import ImageGrab, ImageStat
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import gui


def capture(app, path):
    # 다른 창의 화면을 앱 캡처로 잘못 기록하지 않도록 테스트 앱만 앞에 둔다.
    app.attributes('-topmost',True)
    app.lift()
    if app._edit_window is not None:
        app._edit_window.attributes('-topmost',True)
        app._edit_window.lift()
    if getattr(app,'_add_window',None) is not None:
        app._add_window.attributes('-topmost',True)
        app._add_window.lift()
    app.update()
    time.sleep(.3)
    app.update()
    frame=ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),
                              app.winfo_rootx()+app.winfo_width(),
                              app.winfo_rooty()+app.winfo_height()))
    if max(ImageStat.Stat(frame).stddev)<3:
        raise RuntimeError('대화형 데스크톱 캡처 확인 불가 (검거나 단색 화면)')
    frame.save(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-dir',type=Path,required=True)
    parser.add_argument('--capture',action='store_true')
    parser.add_argument('--review-dir',type=Path,default=ROOT/'docs/review/label_edit')
    args=parser.parse_args()
    os.chdir(ROOT)
    output=ROOT/'output/d3-after-gui';output.mkdir(parents=True,exist_ok=True)
    review=args.review_dir;review.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as isolated, patch('gui.base_dir',return_value=isolated), patch.object(sys,'argv',['gui.py']):
        gui.ctk.set_widget_scaling(.8)
        gui.ctk.set_window_scaling(.8)
        app=gui.SheetHelperApp()
        app.geometry("1100x700+30+30")
        if not args.capture:
            app.withdraw()
        try:
            app.output_dir=str(output)
            for source in ['sample_images/KakaoTalk_20260731_162400402.png','test_scores/chopin_nocturne_Db_6-8.pdf']:
                app._set_input(source)
                app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
                app.result_path=app._convert_page(0,'')
                app._show_result();app.update()
                for result in (app.result_path,app.labels_path):
                    p=Path(result)
                    assert p.read_bytes()==(args.baseline_dir/p.name).read_bytes(),p
                    print('무편집 바이트 일치:',p.name,flush=True)
            session=app._edit_session
            target=next(i for i,label in enumerate(session['doc']['labels']) if label['confidence']=='check')
            original=session['doc']['labels'][target]
            box=next(p for p in session['placements'] if
                     (p['note'].x,p['note'].y,p['note'].staff_index)==(original['x'],original['y'],original['staff']))
            app._preview_zoom=.55;app._redraw_preview();app.update()
            app.preview_canvas.xview_moveto(max(0,(box['x']-200)/app._preview_source.width))
            app.preview_canvas.yview_moveto(max(0,(box['y']-200)/app._preview_source.height))
            if args.capture:
                capture(app,review/'01_before.png')
            canvas=app.preview_canvas
            click_x=round((box['x']+box['w']/2)*app._preview_zoom-canvas.canvasx(0))
            click_y=round((box['y']+box['h']/2)*app._preview_zoom-canvas.canvasy(0))
            assert 0 <= click_x < canvas.winfo_width() and 0 <= click_y < canvas.winfo_height()
            canvas.event_generate('<Button-1>',x=click_x,y=click_y);app.update()
            assert app._edit_window is not None and app._edit_list.curselection()==(target,)
            print('실제 Canvas 클릭 바인딩·확대/스크롤 뒤 대상 선택: 통과',flush=True)
            app._edit_window.geometry(f'520x460+{app.winfo_rootx()+20}+{app.winfo_rooty()+30}');app._edit_window.lift();app.update()
            app._edit_text.delete(0,'end');app._edit_text.insert(0,'미' if original['text']!='미' else '레')
            if args.capture:
                capture(app,review/'02_editing.png')
            app._change_label('set_text');app.update()
            assert session['doc']['labels'][target]['edited']
            assert session['doc']['labels'][target]['confidence']==original['confidence']=='check'
            assert session['doc']['labels'][target]['pitch']==original['pitch']
            saved=Path(app.result_path)
            assert saved.is_file() and Path(app.labels_path).is_file()
            app._close_label_editor();app.update()
            if args.capture:
                capture(app,review/'03_saved.png')
            (review/'edited_example.json').write_text(Path(app.labels_path).read_text(encoding='utf-8'),encoding='utf-8')
            (review/'edits_example.json').write_text((saved.parent/'사용자수정.json').read_text(encoding='utf-8'),encoding='utf-8')
            (review/'saved_result.png').write_bytes(saved.read_bytes())
            print('실제 GUI 수정·JSON edited·별도 저장: 통과',flush=True)
            # 빈 자리에서도 같은 확대/스크롤 환산으로 추가 창을 연다.
            ax,ay=original['x'],original['y']+330
            canvas=app.preview_canvas
            canvas.event_generate('<Button-1>',
                x=round(ax*app._preview_zoom-canvas.canvasx(0)),
                y=round(ay*app._preview_zoom-canvas.canvasy(0)))
            app.update()
            assert app._add_window is not None
            app._add_window.geometry(f'440x320+{app.winfo_rootx()+150}+{app.winfo_rooty()+150}')
            app._add_staff.set(str(original['staff']+1))
            app._add_pitch.insert(0,'B3');app._add_text.insert(0,'시b')
            if args.capture:
                capture(app,review/'04_add_dialog.png')
            app._add_confirm.invoke();app.update()
            assert app._add_window is None
            added=session['doc']['labels'][-1]
            assert added['user_created'] and added['edited'] and added['pitch']=='B3'
            assert abs(added['x']-ax)<=1 and abs(added['y']-ay)<=1
            if args.capture:
                capture(app,review/'05_added.png')
            (review/'added_example.json').write_text(Path(app.labels_path).read_text(encoding='utf-8'),encoding='utf-8')
            (review/'added_result.png').write_bytes(Path(app.result_path).read_bytes())
            app._open_label_editor([len(session['doc']['labels'])-1]);app._change_label('delete')
            assert not any(l.get('user_created') for l in session['doc']['labels'])
            app._close_label_editor()
            for _ in range(3):
                app._undo_label_edit();app.update()
            assert not session['changes'] and session['doc']==session['original_doc']
            assert Path(app.result_path).read_bytes()==Path(session['original_png']).read_bytes()
            assert Path(app.labels_path).read_bytes()==Path(session['original_json']).read_bytes()
            if args.capture:
                capture(app,review/'06_undo.png')
            print('빈 자리 실제 클릭·보표/음고/표기 입력·추가·삭제·3회 되돌리기 원본 복귀: 통과',flush=True)

        finally:
            app.destroy()

if __name__=='__main__':
    main()
