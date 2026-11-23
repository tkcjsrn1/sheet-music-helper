"""거대한 배열 없이 이미지 크기 경계와 실제 PDF 파서 실패를 재현한다."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
import fitz
import gui
from user_messages import conversion_failure_message


class InputBoundaryTests(unittest.TestCase):
    def test_bomb_preview_explains_without_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '큰 악보.png'
            Image.new('RGB', (32, 32), 'white').save(path)
            messages = []
            app = SimpleNamespace(_update_review_controls=lambda: None,
                                  _draw_placeholder=messages.append, log=messages.append)
            with patch.object(Image, 'MAX_IMAGE_PIXELS', 128):
                try:
                    gui.SheetHelperApp._load_preview_image(app, str(path))
                except Image.DecompressionBombError:
                    self.fail('큰 이미지 선택이 GUI 콜백 밖으로 예외를 내보냄')
            self.assertIsNone(app._preview_source)
            self.assertIn('해결:', '\n'.join(messages))
            self.assertIn('크기', '\n'.join(messages))

    def test_bomb_is_rejected_before_recognition_per_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            huge = Path(tmp)/'큰.png'
            Image.new('RGB', (32, 32)).save(huge)
            request = SimpleNamespace(input_paths=(str(huge),), output_dir=tmp, clef='auto',
                                      font_path='', font_size=18, text_color=(220,20,20),
                                      photo=False, legend=False)
            app = SimpleNamespace(_run_request=request, log=lambda message:None)
            with patch.object(Image, 'MAX_IMAGE_PIXELS', 128), patch('gui.preprocess') as recognize:
                with self.assertRaises(Image.DecompressionBombError):
                    gui.SheetHelperApp._convert_page(app, 0, '')
            recognize.assert_not_called()

    def test_large_page_failure_does_not_discard_the_next_valid_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            huge, good = Path(tmp)/'큰.png', Path(tmp)/'정상 입력.png'
            Image.new('RGB', (32,32)).save(huge)
            Image.new('RGB', (4,4)).save(good)
            messages=[]
            button=SimpleNamespace(configure=lambda **kw:None)
            app=SimpleNamespace(input_path=str(huge),_run_input_paths=(str(huge),str(good)),
                _run_all_pages=False,_converting=True,output_dir=tmp,result_path=None,labels_path=None,
                log=messages.append,after=lambda delay,fn:fn(),convert_btn=button,
                _show_result=lambda:None,_set_conversion_progress=lambda *args:None)
            def convert(page,suffix,source_path=None):
                if source_path==str(huge):
                    return gui.SheetHelperApp._convert_page(app,page,suffix,source_path)
                target=Path(tmp)/'정상 결과.png';Image.new('RGB',(4,4)).save(target)
                app.labels_path=str(Path(tmp)/'정상 라벨.json')
                Path(app.labels_path).write_text('{}',encoding='utf-8')
                return str(target)
            app._convert_page=convert
            with patch.object(Image,'MAX_IMAGE_PIXELS',128):
                gui.SheetHelperApp._convert_worker(app)
            self.assertFalse(app._converting)
            self.assertTrue(Path(app.result_path).is_file())
            text='\n'.join(messages)
            self.assertIn('성공 1 · 실패 1',text);self.assertIn('해결:',text)

    def test_korean_space_path_keeps_the_preview_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'한글 공백 악보.png';Image.new('RGB',(20,30),'white').save(path)
            before=path.read_bytes();timers=[]
            app=SimpleNamespace(_update_review_controls=lambda:None,_fit_zoom=lambda:None,
                after=lambda delay,fn:timers.append(fn))
            gui.SheetHelperApp._load_preview_image(app,str(path))
            self.assertEqual(app._preview_source.size,(20,30))
            app._preview_source.close()
            self.assertEqual(path.read_bytes(),before);self.assertEqual(len(timers),1)

    def test_truncated_and_empty_pdf_get_recovery_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in [('잘린 악보.pdf', b'%PDF-1.7\n1 0 obj << /Type /Catalog'),
                               ('빈 파일.pdf', b'')]:
                path = Path(tmp)/name
                path.write_bytes(data)
                try:
                    fitz.open(stream=path.read_bytes(), filetype="pdf")
                except (fitz.FileDataError, fitz.EmptyFileError) as error:
                    message = conversion_failure_message(error, str(path))
                    self.assertIsNotNone(message, type(error).__name__)
                    self.assertIn('PDF', message)
                    self.assertIn('해결:', message)
                else:
                    self.fail('손상 PDF가 실제 파서에서 거부되지 않음')

    def test_unknown_errors_stay_diagnostic(self):
        self.assertIsNone(conversion_failure_message(RuntimeError('제품 결함'), 'test.pdf'))


if __name__ == '__main__':
    unittest.main()
