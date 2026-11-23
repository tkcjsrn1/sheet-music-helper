"""실제 입력 실패를 GUI 단일/여러 장 경로에서 사람말·해결 방법으로 안내한다."""
import os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import fitz
import gui,user_messages
from modules.preprocess import preprocess,PhotoRejectedError

def close_app(app):
    for timer in app.tk.splitlist(app.tk.call('after','info')):
        app.tk.call('after','cancel',timer)
    app.destroy()


def prepare_capture(app):
    if os.environ.get('SHEET_FAILURE_CAPTURE_DIR'):
        scale=app._get_window_scaling()
        gui.ctk.set_window_scaling(1/scale);gui.ctk.set_widget_scaling(1/scale)
        deadline=time.monotonic()+1.2
        while time.monotonic()<deadline:
            app.update();time.sleep(.02)
        app.geometry('1000x640+20+20');app.update()


def capture_if_requested(app, name):
    folder=os.environ.get('SHEET_FAILURE_CAPTURE_DIR')
    if folder:
        from tools.check_label_edit_gui import capture
        app.deiconify();app.update()
        app.sidebar._parent_canvas.yview_moveto(app.log_box.winfo_y()/app.sidebar.winfo_height());app.update()
        size=(app.winfo_width(),app.winfo_height())
        assert size==(1000,640),size
        capture(app,Path(folder)/name)


class FailureMessageTests(unittest.TestCase):

    def test_resize_error_uses_both_opencv_function_spellings(self):
        import cv2

        for name in ('cv::resize', 'resize'):
            with self.subTest(name=name):
                error = cv2.error('!dsize.empty()')
                error.func = name
                message = user_messages.conversion_failure_message(error, 'tiny.png')
                self.assertIn('이미지 크기', message)
        unrelated = cv2.error('!dsize.empty()')
        unrelated.func = 'warpAffine'
        self.assertIsNone(user_messages.conversion_failure_message(unrelated, 'tiny.png'))

    def test_real_failures_single_and_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,size in [('blank.png',(400,500)),('tiny.png',(1,1))]:Image.new('RGB',size,'white').save(root/name)
            (root/'broken.png').write_bytes(b'not an image')
            with fitz.open() as doc:
                doc.new_page(width=60,height=80)
                doc.save(root/'locked.pdf',encryption=fitz.PDF_ENCRYPT_AES_256,user_pw='test-only',owner_pw='owner-only')
            cases=[('blank.png','악보 줄'),('tiny.png','이미지 크기'),('broken.png','파일'),('locked.pdf','비밀번호')]
            class Button:
                def configure(self,**values):pass
            def worker(paths):
                messages=[]
                def page(number,suffix,source_path=None):return preprocess(source_path or str(paths[0]),pdf_page=number)
                app=SimpleNamespace(input_path=str(paths[0]),_run_input_paths=tuple(map(str,paths)),output_dir=tmp,_run_all_pages=False,_converting=True,
                    result_path=None,labels_path=None,log=messages.append,_convert_page=page,after=lambda delay,callback:callback(),
                    page_entry=SimpleNamespace(get=lambda:'1'),_clear_result_pages=lambda:None,_draw_placeholder=lambda message:None,
                    _set_conversion_progress=lambda *args:None)
                for name in ('convert_btn','open_result_btn','save_as_btn','report_btn','edit_btn'):setattr(app,name,Button())
                gui.SheetHelperApp._convert_worker(app)
                self.assertFalse(app._converting);self.assertIsNone(app.result_path);self.assertIsNone(app.labels_path)
                return '\n'.join(messages)
            for name,want in cases:
                message=worker([root/name]);self.assertIn(want,message);self.assertIn('해결:',message)
                self.assertNotIn('document closed or encrypted',message)
            message=worker([root/name for name,_ in cases]);self.assertIn('실패 4',message)
            self.assertEqual(message.count('해결:'),4);self.assertIn('비밀번호',message)
    def test_unexpected_errors_and_photo_rejection(self):
        self.assertTrue(callable(getattr(user_messages,'conversion_failure_message',None)))
        self.assertIsNone(user_messages.conversion_failure_message(RuntimeError('예상 밖 결함'),'not-a-pdf.png'))
        with tempfile.TemporaryDirectory() as tmp:
            pdf=Path(tmp)/'unlocked.pdf'
            with fitz.open() as doc:
                doc.new_page();doc.save(pdf)
            self.assertIsNone(user_messages.conversion_failure_message(ValueError('document closed or encrypted'),str(pdf)))
        self.assertIn('스캐너·복사기·거치대로 정면에서 다시 찍어 주세요',user_messages.conversion_failure_message(PhotoRejectedError(),'photo.png'))



class PhotoRetryTests(unittest.TestCase):
    def test_normal_rotation_refusal_offers_explicit_retry_and_resets(self):
        from unittest.mock import patch
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from test_photo_correct import page,rotate,STAVES
        with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
            root=Path(tmp)
            one=root/'직접생성1도.png';Image.fromarray(rotate(page(),1)).save(one)
            normal=preprocess(str(one))
            self.assertEqual(len(normal.staves),STAVES)
            self.assertAlmostEqual(normal.deskew_deg,-1,delta=.02)
            source=root/'직접생성4도.png'
            Image.fromarray(rotate(page(),4)).save(source)
            gui.ctk.set_window_scaling(1);gui.ctk.set_widget_scaling(1)
            app=gui.SheetHelperApp();app.withdraw();app.output_dir=tmp
            prepare_capture(app)
            try:
                app._set_input(str(source))
                with patch('gui.threading.Thread'):app.start_convert()
                app._convert_worker();app.update()
                self.assertFalse(app._converting)
                self.assertIsNone(app.result_path)
                self.assertEqual(app.photo_retry_btn.winfo_manager(),'grid')
                self.assertEqual(app.photo_retry_btn.cget('state'),'normal')
                self.assertIn('사진 모드로 다시 시도해 보세요',app.log_box.get('1.0','end'))
                capture_if_requested(app,'normal_refusal.png')
                with patch('gui.threading.Thread'):app.photo_retry_btn.invoke()
                self.assertTrue(app._run_request.photo)
                self.assertEqual(app._run_request.input_paths,(str(source),))
                self.assertTrue(app.photo_check.get())
                self.assertEqual(app.photo_retry_btn.winfo_manager(),'')
                r=preprocess(str(source),photo=True)
                self.assertEqual(len(r.staves),STAVES)
                app._converting=False
                app._set_input(str(source))
                self.assertEqual(app.photo_retry_btn.winfo_manager(),'')
            finally:close_app(app)

    def test_photo_refusal_never_offers_retry_loop(self):
        from unittest.mock import patch
        import numpy as np
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from test_photo_correct import page,rotate,H
        image=page();image=np.vstack([rotate(image[:H//2],0),rotate(image[H//2:],1)])
        with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
            source=Path(tmp)/'다른기울기.png';Image.fromarray(image).save(source)
            gui.ctk.set_window_scaling(1);gui.ctk.set_widget_scaling(1)
            app=gui.SheetHelperApp();app.withdraw();app.output_dir=tmp
            prepare_capture(app)
            try:
                app._set_input(str(source));app.photo_check.select()
                with patch('gui.threading.Thread'):app.start_convert()
                app._convert_worker();app.update()
                self.assertFalse(app._converting)
                self.assertIsNone(app.result_path)
                self.assertEqual(app.photo_retry_btn.winfo_manager(),'')
                self.assertIn('스캐너·복사기·거치대로 정면에서 다시 찍어 주세요',app.log_box.get('1.0','end'))
                capture_if_requested(app,'photo_refusal.png')
            finally:close_app(app)

if __name__=='__main__':unittest.main()

