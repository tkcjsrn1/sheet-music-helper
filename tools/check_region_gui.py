"""영역 드래그 바인딩·선택 저장·전체 복귀를 소스 Tk 창에서 검사/캡처한다."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from tools.check_label_edit_gui import capture


def main():
    review=Path('docs/review/region_select');review.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
        app=gui.SheetHelperApp();app.geometry('1150x760+30+30')
        try:
            app._set_input(str(Path('sample_images/KakaoTalk_20260731_162400402.png').resolve()))
            app.output_dir=tmp;app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
            app.result_path=app._convert_page(0,'');app._show_result();app.update()
            session=app._edit_session
            before=Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes()
            app.region_check.master._parent_canvas.yview_moveto(1);app.update()
            capture(app,review/'01_before.png')
            labels=[r for r in session['doc']['labels'] if r['staff']==0][:6]
            left=max(0,min(r['x'] for r in labels)-10);right=max(r['x'] for r in labels)+10
            top=max(0,min(r['y'] for r in labels)-10);bottom=max(r['y'] for r in labels)+10
            canvas=app.preview_canvas;z=app._preview_zoom
            app.region_check.select()
            canvas.event_generate('<Button-1>',x=round(left*z),y=round(top*z))
            canvas.event_generate('<B1-Motion>',x=round(right*z),y=round(bottom*z))
            canvas.event_generate('<ButtonRelease-1>',x=round(right*z),y=round(bottom*z))
            app.update()
            assert session.get('region') and 0<len(session['doc']['labels'])<len(session['original_doc']['labels'])
            assert len(session['placements'])==len(session['doc']['labels'])
            capture(app,review/'02_selected.png')
            (review/'selected_result.png').write_bytes(Path(app.result_path).read_bytes())
            (review/'selected_labels.json').write_bytes(Path(app.labels_path).read_bytes())
            selected_count=len(session['doc']['labels'])
            app._select_region(None);app.update()
            assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==before
            capture(app,review/'03_restored.png')
            print(f'실제 Tk 드래그 바인딩 {len(session["doc"]["labels"])} → {selected_count} → 전체, PNG/JSON 바이트 복귀: 통과')
        finally:app.destroy()
if __name__=='__main__':main()
