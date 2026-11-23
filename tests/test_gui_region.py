"""영역 선택은 표시/저장 목록만 거르고 해제하면 원본 바이트로 돌아간다."""
from pathlib import Path
import copy
import sys
import tempfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gui import _save_edit_version
from modules.labels_io import document_notes,save_labels
from modules.renderer import render_solfege_on_image


def main():
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)
        doc=dict(schema=1,source=dict(sha256='abc',page=0,width=220,height=180,dpi=300),
                 staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],
                 labels=[dict(staff=0,x=50,y=100,pitch='E4',text='미',confidence='check'),
                         dict(staff=0,x=130,y=100,pitch='G4',text='솔',confidence='certain')])
        image=np.full((180,220,3),255,np.uint8)
        options=dict(font_path=r'C:\Windows\Fonts\malgun.ttf',font_size=18,staff_spacings={0:10},text_offset_y=22)
        png=p/'original.png';js=p/'original.json'
        boxes=render_solfege_on_image(image,document_notes(doc),str(png),confidences=['check','certain'],**options)
        save_labels(str(js),doc);before=png.read_bytes(),js.read_bytes();original=copy.deepcopy(doc)
        session=dict(original_doc=doc,doc=doc,image=image,render_options=options,
                     original_png=str(png),original_json=str(js),original_placements=boxes,
                     header_options=None,legend_options=None,region=(0,0,100,180))
        selected=_save_edit_version(session,[],tmp)
        assert len(selected['doc']['labels'])==1
        assert selected['doc']['labels'][0]['confidence']=='check'
        assert selected['doc']['selected_region']==[0,0,100,180]
        assert len(selected['placements'])==1 and selected['placements'][0]['note'].x==50
        assert doc==original and (png.read_bytes(),js.read_bytes())==before
        session['region']=None
        restored=_save_edit_version(session,[],tmp)
        assert (Path(restored['png']).read_bytes(),Path(restored['json']).read_bytes())==before
        session['region']=(0,0,0,180)
        try:_save_edit_version(session,[],tmp);assert False,'폭0 영역은 채택하지 않는다'
        except ValueError:pass
    print('영역만 표시/JSON 저장·원본 보존·해제 바이트 복귀: 통과')
if __name__=='__main__':main()
