"""실제 Tk 건반/악보 오버레이는 저장 파일과 검토 선택을 바꾸지 않는다."""
import copy,hashlib,sys,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes,document_staves,save_labels
from modules.renderer import render_solfege_on_image
CAPTURE=Path(sys.argv[sys.argv.index('--capture')+1]) if '--capture' in sys.argv else None

class PianoWidget(unittest.TestCase):
    def test_selection_playback_cancel_page_and_saved_bytes(self):
        with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
            app=gui.SheetHelperApp();app.geometry('1280x700+20+20');app.update()
            try:
                root=Path(tmp);source=root/'합성 악보.png';frame=np.full((460,850,3),255,np.uint8)
                for y in (100,120,140,160,180,300,320,340,360,380):frame[y:y+1,50:800]=0
                Image.fromarray(frame[:,:,::-1]).save(source)
                labels=[dict(staff=0,x=120,y=170,pitch='D4',text='레bb',confidence='check',edited=False,accidental='bb'),
                    dict(staff=1,x=120,y=350,pitch='C4',text='도',confidence='certain',edited=False,accidental=None),
                    dict(staff=0,x=330,y=150,pitch='F4',text='파##',confidence='check',edited=False,accidental='##'),
                    dict(staff=0,x=560,y=130,pitch='D5',text='레b',confidence='certain',edited=False,accidental=None,key=dict(key_symbol='♭',key_letters=['D']))]
                doc=dict(schema=2,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0,width=850,height=460,dpi=300),
                    music=dict(key_symbol='',key_count=0),staves=[dict(id=i,line_ys=list(range(y,y+81,20)),spacing=20) for i,y in enumerate((100,300))],labels=labels)
                png=root/'결과.png';js=root/'라벨.json';options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=18,staff_spacings={0:20,1:20},staves=document_staves(doc),placement_mode='lanes')
                ps=render_solfege_on_image(frame,document_notes(doc),str(png),confidences=[l['confidence'] for l in labels],**options);save_labels(str(js),doc)
                self.assertTrue(all(p.get('lane') for p in ps),'통합 검사는 실제 계이름 줄 좌표를 써야 함')
                before=png.read_bytes(),js.read_bytes(),copy.deepcopy(doc)
                session=dict(original_doc=doc,doc=doc,changes=[],image=frame,source_path=str(source),render_options=options,header_options=None,legend_options=None,
                    original_png=str(png),original_json=str(js),original_placements=ps,placements=ps,png=str(png),json=str(js))
                app._page_sessions=[session,dict(session,source_path=str(source))];app._edit_session=session;app.result_path=str(png);app.labels_path=str(js)
                app.settings['placement_mode']='lanes';app.placement_menu.set('계이름 줄')
                app._show_result();app.update();self.assertTrue(app._move_review_label(1));app.update()
                self.assertFalse(app.placement_notice.winfo_viewable(),'줄 배치 성공에 공간 부족 안내가 뜨면 안 됨')
                self.assertEqual(app.piano_keyboard.selected,{60});self.assertEqual(len(app.piano_keyboard.find_withtag('piano-key')),88)
                def assert_boxes(tag,indices,padding):
                    expected=[]
                    for index in indices:
                        label=labels[index]
                        box=next(p for p in ps if (p['note'].staff_index,p['note'].x,p['note'].y,p['text'])==
                            (label['staff'],label['x'],label['y'],label['text']))
                        self.assertIs(app._preview_box_for_label(index),box)
                        z=app._preview_zoom
                        expected.append([(box['x']-padding)*z,(box['y']-padding)*z,
                            (box['x']+box['w']+padding)*z,(box['y']+box['h']+padding)*z])
                    actual=[app.preview_canvas.coords(i) for i in app.preview_canvas.find_withtag(tag)]
                    self.assertEqual(actual,expected)
                assert_boxes('label-selection',[0],3)
                self.assertIsNone(app._practice_options())
                self.assertTrue(app._set_practice_boundary('start'));app._review_index=2
                self.assertTrue(app._set_practice_boundary('end'))
                app.practice_speed.set(.5);app.practice_repeat.select();app._review_index=0
                app._update_review_controls();app._redraw_preview();app.update()
                self.assertEqual(app._practice_options(),dict(speed=.5,start=0,end=2,repeat=True))
                self.assertTrue(app.practice_bar.winfo_viewable())
                if CAPTURE:
                    from tools.check_label_edit_gui import capture
                    CAPTURE.mkdir(parents=True,exist_ok=True);capture(app,CAPTURE/'01_selected_double_flat.png')
                token=app._playback.token
                plan=[dict(notes=[60],indices=[0,1]),dict(notes=[67],indices=[2]),dict(notes=[73],indices=[3])]
                app._audio_events.put((token,'plan',plan));app._audio_events.put((token,'start',0));app.after_cancel(app._audio_timer);app._drain_audio_events();app.update()
                deadline=time.monotonic()+1
                while not app.piano_keyboard.playing and time.monotonic()<deadline:
                    app.update();time.sleep(.005)
                self.assertEqual(app.piano_keyboard.playing,{60});self.assertEqual(len(app.preview_canvas.find_withtag('audio-playing')),2)
                self.assertEqual(app._review_index,0)
                assert_boxes('audio-playing',[0,1],4)
                if CAPTURE:capture(app,CAPTURE/'02_chord_and_keys.png')
                app._preview_zoom*=1.1;app._redraw_preview();self.assertEqual(len(app.preview_canvas.find_withtag('audio-playing')),2)
                assert_boxes('label-selection',[0],3);assert_boxes('audio-playing',[0,1],4)
                app._apply_audio_event(token,'end',0);app._apply_audio_event(token,'start',1);app.update()
                self.assertEqual(app.piano_keyboard.playing,{67})
                if CAPTURE:capture(app,CAPTURE/'03_double_sharp_playback.png')
                self.assertTrue(app._select_result_page(1));app.update()
                self.assertEqual((app._practice_start,app._practice_end),(None,None))
                self.assertFalse(app.practice_repeat.get());self.assertEqual(app.practice_speed.get(),.5)
                app._apply_audio_event(token,'start',2)
                self.assertEqual(app.piano_keyboard.playing,set());self.assertEqual(app.preview_canvas.find_withtag('audio-playing'),())
                self.assertEqual((png.read_bytes(),js.read_bytes(),doc),before)
            finally:
                app._close_label_editor()
                # 콜백을 등록한 위젯에서 취소해야 destroy 때 명령을 두 번 지우지 않는다.
                widgets=[app]
                for widget in widgets:widgets.extend(widget.winfo_children())
                owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None) or [])}
                for timer in app.tk.splitlist(app.tk.call('after','info')):
                    owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0])
                    owner.after_cancel(timer) if owner else app.tk.call('after','cancel',timer)
                app._audio_timer=None
                app._close_app()

if __name__=='__main__':unittest.main(argv=[sys.argv[0]])
