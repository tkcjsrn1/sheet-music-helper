"""GUI 라벨 편집은 원본을 보존하고 저장 실패 때 이전 결과를 유지한다."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes, save_labels
from modules.renderer import render_solfege_on_image


def main():
    save = getattr(gui, "_save_edit_version", None)
    assert callable(save), "GUI 수정본 PNG·JSON·기록의 안전한 저장 경로가 필요하다"
    with tempfile.TemporaryDirectory() as folder:
        parent = Path(folder)
        doc = dict(schema=1, source=dict(sha256="abc", page=0, width=220, height=180, dpi=300),
                   music=dict(key_symbol="", key_count=0),
                   staves=[dict(id=0, line_ys=[60,70,80,90,100], spacing=10)],
                   labels=[dict(staff=0,x=50,y=100,pitch="E4",text="미",confidence="check",edited=False),
                           dict(staff=0,x=130,y=100,pitch="E4",text="미",confidence="certain",edited=False)])
        image=np.full((180,220,3),255,np.uint8)
        options=dict(font_path=r"C:\Windows\Fonts\malgun.ttf",font_size=18,
                     staff_spacings={0:10},text_offset_y=22)
        png=parent/'original.png'; js=parent/'original.json'
        placements=render_solfege_on_image(image,document_notes(doc),str(png),
                                           confidences=['check','certain'],**options)
        save_labels(str(js),doc)
        original=copy.deepcopy(doc); before=(png.read_bytes(),js.read_bytes())
        session=dict(original_doc=doc, image=image, render_options=options,
                     header_options=None,legend_options=None,original_png=str(png),
                     original_json=str(js),original_placements=placements)
        with patch('gui.render_solfege_on_image', side_effect=AssertionError('무편집 재렌더 금지')):
            unchanged=save(session,[],str(parent))
        assert unchanged['png']==str(png) and unchanged['json']==str(js)
        target=lambda label:{k:label[k] for k in ('staff','x','y','pitch','text')}
        changes=[dict(action='set_text',before=target(doc['labels'][0]),after=dict(text='파')),
                 dict(action='delete',before=target(doc['labels'][1]))]
        result=save(session,changes,str(parent))
        saved=json.loads(Path(result['json']).read_text(encoding='utf-8'))
        record=json.loads(Path(result['edits']).read_text(encoding='utf-8'))
        assert len(saved['labels'])==1 and saved['labels'][0]['text']=='파'
        assert saved['labels'][0]['edited'] and saved['labels'][0]['pitch']=='E4'
        assert saved['labels'][0]['confidence']=='check', '원래 확신도는 JSON에 보존한다'
        # 사용자 확인 뒤에는 진한 글씨만 남고, 삭제한 라벨과 점선은 그리지 않는다.
        expected=parent/'certain-only.png'
        expected_boxes=render_solfege_on_image(image,document_notes(saved),str(expected),
                                              confidences=['certain'],**options)
        assert Path(result['png']).read_bytes()==expected.read_bytes(), '사용자 수정에 check 점선이 남았다'
        assert len(result['placements'])==len(expected_boxes)==1
        assert result['placements'][0]['note'].x==50
        assert record['changes']==changes and record['description']=='사용자 수정'
        assert saved['user_edits']==record
        assert Path(result['png']).read_bytes()!=before[0]
        assert doc==original and (png.read_bytes(),js.read_bytes())==before
        dirs=set(parent.iterdir())
        with patch('modules.label_edits.save_edits',side_effect=OSError('디스크 오류')):
            try:
                save(session,changes,str(parent))
                assert False,'저장 실패를 성공으로 처리하면 안 된다'
            except OSError:
                pass
        assert set(parent.iterdir())==dirs
        # 마지막 수정 취소는 원본 바이트와 경로로 되돌아간다.
        restored=save(session,[],str(parent))
        assert Path(restored['png']).read_bytes()==before[0]
        assert Path(restored['json']).read_bytes()==before[1]
        # GUI 상태도 저장에 성공한 뒤에만 바뀌고, 실패·취소는 원본을 유지한다.
        messages=[]
        app=SimpleNamespace(_edit_session=dict(session, doc=doc, changes=[], placements=placements),
            output_dir=str(parent),result_path=str(png),labels_path=str(js),_edit_window=None,
            log=messages.append,_redraw_preview=lambda:None,_converting=False,_stop_listening=Mock())
        app._apply_label_changes=lambda changes,selected=0:gui.SheetHelperApp._apply_label_changes(app,changes,selected)
        app._apply_label_changes(changes)
        app._stop_listening.assert_called_once()
        assert len(app._edit_session['doc']['labels'])==1
        prior=(app.result_path,app.labels_path,copy.deepcopy(app._edit_session['doc']))
        with patch('gui._save_edit_version',side_effect=OSError('디스크 오류')):
            gui.SheetHelperApp._apply_label_changes(app,[])
        assert (app.result_path,app.labels_path,app._edit_session['doc'])==prior
        gui.SheetHelperApp._undo_label_edit(app)
        assert app._edit_session['changes']==changes[:1]
        gui.SheetHelperApp._undo_label_edit(app)
        assert (app.result_path,app.labels_path)==(str(png),str(js))
        assert app._edit_session['doc']==original
        # 머리 좌표가 아닌, 렌더러가 옮긴 글씨 상자 + 스크롤/확대로 선택한다.
        p=placements[0]; hit=[]
        canvas=SimpleNamespace(canvasx=lambda x:x+30,canvasy=lambda y:y+20,
                               focus_set=lambda:None)
        app=SimpleNamespace(_converting=False,_preview_zoom=2,preview_canvas=canvas,
            _edit_session=dict(doc=doc,placements=placements),
            _open_label_editor=lambda indices:hit.extend(indices))
        event=SimpleNamespace(x=(p['x']+p['w']/2)*2-30,y=(p['y']+p['h']/2)*2-20)
        gui.SheetHelperApp._on_label_click(app,event,edit=True)
        assert hit==[0],hit
        hit.clear()
        app._edit_session['placements']=[p,dict(p,note=placements[1]['note'],text='미')]
        gui.SheetHelperApp._on_label_click(app,event,edit=True)
        assert hit==[0,1],'겹친 상자 중 하나를 임의로 고르면 안 된다'
        blank=[]
        app._open_label_add=lambda x,y:blank.append((x,y))
        gui.SheetHelperApp._on_label_click(app,SimpleNamespace(x=330,y=260),edit=True)
        assert blank==[(180,140)], '빈 자리 클릭이 추가 창을 열어야 한다'
        gui.SheetHelperApp._on_label_click(app,SimpleNamespace(x=409.6,y=260),edit=True)
        assert blank==[(180,140),(219,140)], '마지막 이미지 픽셀도 추가할 수 있어야 한다'
        gui.SheetHelperApp._on_label_click(app,SimpleNamespace(x=-40,y=260),edit=True)
        assert blank==[(180,140),(219,140)], '이미지 밖 클릭은 추가하지 않는다'
        # 추가도 기존 저장 경로를 거쳐야 하며 세 번 되돌리면 원본 바이트로 복귀한다.
        app=SimpleNamespace(_edit_session=dict(session,doc=doc,changes=[],placements=placements),
            output_dir=str(parent),result_path=str(png),labels_path=str(js),_edit_window=None,
            log=messages.append,_redraw_preview=lambda:None,_converting=False,_stop_listening=Mock())
        app._apply_label_changes=lambda rows,selected=0:gui.SheetHelperApp._apply_label_changes(app,rows,selected)
        app._apply_label_changes(changes)
        assert gui.SheetHelperApp._add_user_label(app,180,100,'1','C4','도')
        assert app._edit_session['doc']['labels'][-1]['user_created']
        assert app._edit_session['doc']['labels'][-1]['pitch']=='C4'
        assert len(app._edit_session['changes'])==3
        prior=copy.deepcopy(app._edit_session['doc'])
        assert not gui.SheetHelperApp._add_user_label(app,180,100,'1','C4','도')
        assert not gui.SheetHelperApp._add_user_label(app,180,100,'보표 선택','D4','레')
        assert app._edit_session['doc']==prior
        for _ in range(3):
            gui.SheetHelperApp._undo_label_edit(app)
        assert app._edit_session['doc']==doc
        assert Path(app.result_path).read_bytes()==before[0]
        assert Path(app.labels_path).read_bytes()==before[1]
    print('무편집 원본 보존·수정/삭제 저장·취소·저장 실패·확대/스크롤 선택: 통과')

if __name__=='__main__':
    main()
