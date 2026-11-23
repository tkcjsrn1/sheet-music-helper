"""실제 Windows 마우스 입력이 세 GUI 버튼의 제품 콜백까지 도달하는지 검사한다."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_page_progress as progress
from modules.labels_io import document_notes,save_labels
from modules.renderer import render_solfege_on_image
import hashlib
import numpy as np
from _native_click import click_widget

class NativeClickTests(unittest.TestCase):
    def setUp(self):
        progress.PageProgressTests.setUp(self)
        app=self.app;self.root=Path(self.temp.name);self.pages=[]
        for number in (1,2):
            source=self.root/f'입력{number}.png';image=np.full((180,220,3),255,np.uint8)
            progress.gui.Image.fromarray(image).save(source)
            doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=220,height=180,dpi=300),
                music=dict(key_symbol='',key_count=0),staves=[dict(id=0,line_ys=[60,70,80,90,100],spacing=10)],
                labels=[dict(staff=0,x=x,y=100,pitch='E4',text='미',confidence=conf,edited=False) for x,conf in ((50,'caution'),(130,'check'))])
            png=self.root/f'결과{number}.png';js=self.root/f'라벨{number}.json'
            options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,staff_spacings={0:10},text_offset_y=22)
            boxes=render_solfege_on_image(image,document_notes(doc),str(png),confidences=['caution','check'],**options);save_labels(str(js),doc)
            self.pages.append(dict(source_path=str(source),original_doc=copy.deepcopy(doc),doc=doc,changes=[],image=image,
                png=str(png),json=str(js),original_png=str(png),original_json=str(js),placements=boxes,original_placements=boxes,
                render_options=options,header_options=None,legend_options=None))
        app._page_sessions=self.pages;app._edit_session=self.pages[0];app.result_path=self.pages[0]['png'];app.labels_path=self.pages[0]['json']
        app.geometry('1000x700+20+20');app.deiconify();app.attributes('-topmost',True);app._show_result();app.update()
        if DISCONNECT:
            for button in (self.app.next_page_btn,self.app.next_review_btn,self.app.convert_btn):
                button.configure(command=lambda:None)
    tearDown = progress.PageProgressTests.tearDown

    def test_next_page_by_real_click(self):
        before=[(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages]
        event=click_widget(self.app.next_page_btn)
        self.assertEqual(event['expected_root'],event['hit_root'])
        self.assertEqual(self.app._page_index,1)
        self.assertIn('2 / 2',self.app.page_label.cget('text'))
        for p,old in zip(self.pages,before):
            self.assertEqual((Path(p['png']).read_bytes(),Path(p['json']).read_bytes()),old)

    def test_next_review_by_real_click(self):
        doc=copy.deepcopy(self.app._edit_session['doc'])
        click_widget(self.app.next_review_btn)
        self.assertEqual(self.app._review_index,0)
        self.assertIn('1 / 2',self.app.review_label.cget('text'))
        self.assertEqual(self.app._edit_session['doc'],doc)

    def test_convert_by_real_click(self):
        self.app._set_input(self.pages[0]['source_path']);self.app.update()
        with patch('gui.threading.Thread') as worker:
            click_widget(self.app.convert_btn)
            self.assertTrue(self.app._converting)
            self.assertEqual(self.app._run_request.input_paths,(self.pages[0]['source_path'],))
            self.assertEqual(self.app.convert_btn.cget("state"),"disabled")
        self.app._converting=False

DISCONNECT='--disconnect-buttons' in sys.argv
if DISCONNECT:sys.argv.remove('--disconnect-buttons')
if __name__=='__main__':unittest.main()
