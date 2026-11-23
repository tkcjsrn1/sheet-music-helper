"""현재 쪽의 확인 필요·주의 순회는 저장 결과를 바꾸지 않는다."""
import copy, hashlib, json, sys, tempfile, time, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.labels_io import document_notes, save_labels
from modules.renderer import render_solfege_on_image

class ReviewNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.base=patch('gui.base_dir',return_value=self.temp.name);self.base.start()
        self.argv=patch.object(sys,'argv',['gui.py']);self.argv.start()
        self.app=gui.SheetHelperApp()
        factor=self.app._get_window_scaling()
        gui.ctk.set_window_scaling(1/factor);gui.ctk.set_widget_scaling(1/factor)
        self.app.geometry('1000x560+20+20' if CAPTURE else '1280x700+20+20')
        self.app.output_dir=self.temp.name;self.app.update()
        self.pages=[]
        for page in range(2):
            image=np.full((2200,1600,3),255,np.uint8)
            source=self.root/f'입력{page+1}.png';Image.fromarray(image).save(source)
            labels=[dict(staff=0,x=x,y=y,pitch='E4',text='미',confidence=c,edited=edited)
                    for x,y,c,edited in [(120,110,'certain',False),(250,110,'caution',False),
                                        (1300,1700,'check',False),(700,110,'check',True)]]
            doc=dict(schema=1,source=dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                page=0,width=1600,height=2200,dpi=300),music=dict(key_symbol='',key_count=0),
                staves=[dict(id=0,line_ys=[70,80,90,100,110],spacing=10)],labels=labels)
            png=self.root/f'결과{page+1}.png';js=self.root/f'라벨{page+1}.json'
            options=dict(font_path='C:/Windows/Fonts/malgun.ttf',font_size=20,staff_spacings={0:10},text_offset_y=22)
            boxes=render_solfege_on_image(image,document_notes(doc),str(png),
                confidences=['certain','caution','check','certain'],**options);save_labels(str(js),doc)
            self.pages.append(dict(original_doc=copy.deepcopy(doc),doc=copy.deepcopy(doc),changes=[],image=image,
                source_path=str(source),render_options=options,header_options=None,legend_options=None,
                original_png=str(png),original_json=str(js),original_placements=boxes,placements=boxes,
                png=str(png),json=str(js)))
        app=self.app;app._page_sessions=self.pages;app._edit_session=self.pages[0]
        app.result_path,app.labels_path=self.pages[0]['png'],self.pages[0]['json']
        app._show_result();app.update();app._preview_zoom=1;app._redraw_preview();app.update()
    def tearDown(self):
        self.app._close_label_editor()
        widgets=[self.app]
        for widget in widgets:widgets.extend(widget.winfo_children())
        owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None) or [])}
        for timer in self.app.tk.splitlist(self.app.tk.call('after','info')):
            script=self.app.tk.call('after','info',timer)[0]
            owner=owners.get(str(script).split()[0])
            if owner:owner.after_cancel(timer)
            else:self.app.tk.call('after','cancel',timer)
        self.app.destroy();self.argv.stop();self.base.stop();self.temp.cleanup()

    def test_main_shortcut_undoes_edit_but_keeps_entry_typing(self):
        app = self.app
        app._open_label_editor([1])
        app._change_label('set_text', text='라')
        app._close_label_editor()
        self.assertEqual(len(app._edit_session['changes']), 1)
        self.press(app.key_entry, '<Control-z>')
        self.assertEqual(len(app._edit_session['changes']), 1)
        self.press(app, '<Control-z>')
        self.assertEqual(app._edit_session['changes'], [])
        self.assertEqual(app._edit_session['doc']['labels'][1]['text'], '미')

    def test_review_confirm_preserves_text_and_original_confidence_and_is_undoable(self):
        app = self.app
        app.next_review_btn.invoke()
        label = app._edit_session['doc']['labels'][1]
        original = copy.deepcopy(label)
        app.review_confirm_btn.invoke()
        confirmed = app._edit_session['doc']['labels'][1]
        self.assertEqual(confirmed['text'], original['text'])
        self.assertEqual(confirmed['confidence'], original['confidence'])
        self.assertTrue(confirmed['edited'])
        self.assertNotIn(1, app._review_indices())
        self.assertEqual(app._edit_session['original_doc']['labels'][1], original)
        self.press(app, '<Control-z>')
        self.assertIn(1, app._review_indices())

    def test_single_click_selects_and_double_click_opens_editor_or_add(self):
        app = self.app
        canvas = self.show_preview_canvas()
        box = app._preview_box_for_label(1)
        click = SimpleNamespace(x=round((box['x'] + box['w']/2) - canvas.canvasx(0)),
                                y=round((box['y'] + box['h']/2) - canvas.canvasy(0)))
        blank = SimpleNamespace(x=300, y=340)
        self.press(app.key_entry, '<KeyPress-v>')
        with patch.object(app, '_open_label_editor') as editor, patch.object(app, '_open_label_add') as add:
            app._on_label_click(click)
            app.update()
            self.assertIs(app.focus_get(), canvas)
            self.assertEqual(app._review_index, 1)
            editor.assert_not_called()
            app._on_label_click(click, edit=True)
            editor.assert_called_once_with([1])
            app._on_label_click(blank)
            add.assert_not_called()
            app._on_label_click(blank, edit=True)
            add.assert_called_once()

    def test_navigation_scroll_editor_page_and_bytes(self):
        app=self.app;docs=copy.deepcopy([p['doc'] for p in self.pages])
        original=[(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages]
        self.assertIn('0 / 2',app.review_label.cget('text'))
        app.next_review_btn.invoke();self.assertEqual(app._review_index,1)
        self.assertIn('1 / 2',app.review_label.cget('text'))
        self.assertEqual(app.prev_review_btn.cget('state'),'disabled')
        app._open_label_editor();self.assertEqual(app._edit_list.curselection(),(1,))
        app.next_review_btn.invoke();app.update()
        self.assertEqual(app._review_index,2);self.assertEqual(app._edit_list.curselection(),(2,))
        self.assertIn('2 / 2',app.review_label.cget('text'))
        self.assertEqual(app.next_review_btn.cget('state'),'disabled')
        canvas=app.preview_canvas;box=next(b for b in self.pages[0]['placements'] if b['note'].x==1300)
        x=(box['x']+box['w']/2)*app._preview_zoom;y=(box['y']+box['h']/2)*app._preview_zoom
        self.assertLessEqual(canvas.canvasx(0),x);self.assertLess(x,canvas.canvasx(canvas.winfo_width()))
        self.assertLessEqual(canvas.canvasy(0),y);self.assertLess(y,canvas.canvasy(canvas.winfo_height()))
        self.assertTrue(canvas.find_withtag('label-selection'))
        if CAPTURE:
            from tools.check_label_edit_gui import capture
            CAPTURE.mkdir(parents=True,exist_ok=True)
            app._edit_window.geometry('460x300+40+300');app.update()
            capture(app,CAPTURE/'01_review_and_editor.png')
        app.prev_review_btn.invoke();self.assertEqual(app._edit_list.curselection(),(1,))
        app._converting=True;app._update_page_controls();app.next_review_btn.invoke()
        self.assertEqual(app._review_index,1);self.assertFalse(app._move_review_label(1))
        app._converting=False;app._update_page_controls()
        self.assertTrue(app._select_result_page(1));app.update()
        self.assertIsNone(app._review_index);self.assertIn('0 / 2',app.review_label.cget('text'))
        app.next_review_btn.invoke();self.assertEqual(app._review_index,1)
        if CAPTURE:
            capture(app,CAPTURE/'02_second_page.png')
        self.assertEqual([p['doc'] for p in self.pages],docs)
        self.assertEqual([(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages],original)
        app._load_preview_image(str(self.root/'없는결과.png'))
        self.assertIsNone(app._preview_source);self.assertFalse(app._move_review_label(1))
        self.assertEqual(app.next_review_btn.cget('state'),'disabled')
    def show_preview_canvas(self):
        app = self.app
        canvas = app.preview_canvas
        # Windows 제목 표시줄의 초기 숨김을 끝내고 캔버스가 보일 때부터 확인한다.
        deadline = time.monotonic() + 2
        while not canvas.winfo_ismapped() and time.monotonic() < deadline:
            app.deiconify()
            app.update()
            time.sleep(.01)
        self.assertTrue(canvas.winfo_ismapped(), app.state())
        return canvas

    def test_viewport_preserves_virtual_coordinates(self):
        app = self.app
        canvas = self.show_preview_canvas()

        def settle():
            deadline = time.monotonic() + .2
            while time.monotonic() < deadline:
                app.update()
                if app._preview_tile_after is None:
                    break
                time.sleep(.005)
            app.update()
            self.assertEqual(len(canvas.find_withtag('preview-tile')), 1)
            self.assertLessEqual(app._preview_photo.width(), canvas.winfo_width() + 64)
            self.assertLessEqual(app._preview_photo.height(), canvas.winfo_height() + 64)

        self.assertTrue(canvas.find_withtag('preview-tile'))
        for zoom in (1, 2, 8):
            with self.subTest(zoom=zoom):
                app._preview_zoom = zoom
                app._redraw_preview()
                app.update()
                self.assertEqual(tuple(map(int, canvas.cget('scrollregion').split())),
                                 (0, 0, 1600 * zoom, 2200 * zoom))
                box = next(b for b in self.pages[0]['placements'] if b['note'].x == 1300)
                x, y = box['x'] + box['w']//2, box['y'] + box['h']//2
                canvas.xview_moveto((x * zoom - 90) / (1600 * zoom))
                canvas.yview_moveto((y * zoom - 90) / (2200 * zoom))
                settle()
                px, py = round(x * zoom - canvas.canvasx(0)), round(y * zoom - canvas.canvasy(0))
                self.assertTrue(0 <= px < canvas.winfo_width() and 0 <= py < canvas.winfo_height())
                self.assertEqual((canvas.canvasx(px) / zoom, canvas.canvasy(py) / zoom), (x, y))
                click = SimpleNamespace(x=px, y=py)
                with patch.object(app, '_open_label_editor') as editor:
                    app._on_label_click(click, edit=True)
                    editor.assert_called_once_with([2])
                app.region_check.select()
                with patch.object(app, '_select_region') as region:
                    end = SimpleNamespace(x=px+5*zoom, y=py+7*zoom)
                    app._on_label_click(click)
                    app._drag_region(end)
                    rectangle, = canvas.find_withtag('region')
                    self.assertEqual(canvas.coords(rectangle), [v*zoom for v in (x, y, x+5, y+7)])
                    app._finish_region(end)
                    region.assert_called_once_with((x, y, x+5, y+7))
                token = app._playback.token
                app._playback.apply(token, 'plan', [dict(notes=[64], indices=[2])])
                app._playback.apply(token, 'start', 0)
                app._draw_audio_overlay()
                overlay, = canvas.find_withtag('audio-playing')
                self.assertEqual(canvas.coords(overlay),
                                 [(box['x']-4)*zoom, (box['y']-4)*zoom,
                                  (box['x']+box['w']+4)*zoom, (box['y']+box['h']+4)*zoom])
                canvas.yview_moveto(1)
                settle()
                self.assertGreater(canvas.canvasy(0), 0)
                tile, = canvas.find_withtag('preview-tile')
                self.assertGreaterEqual(canvas.coords(tile)[1] + app._preview_photo.height(),
                                        canvas.canvasy(canvas.winfo_height()) - 1)
                print(f'배율 {zoom} · 음표 (1300,1700) · 클릭 ({x},{y}) '
                      f'· 드래그 ({x},{y})→({x+5},{y+7}) · 가상 끝 {2200*zoom}')
        app.geometry('1100x600+20+20')
        app.update()
        settle()
        self.assertTrue(app._select_result_page(1))
        app.update()
        settle()
        self.assertFalse(canvas.find_withtag('audio-playing'))
        self.assertIs(app._edit_session, self.pages[1])
        app._preview_zoom = 8
        app._redraw_preview()
        canvas.xview_moveto((x * 8 - 90) / (1600 * 8))
        canvas.yview_moveto((y * 8 - 90) / (2200 * 8))
        settle()
        with patch.object(app, '_open_label_editor') as editor:
            app._on_label_click(SimpleNamespace(x=round(x*8-canvas.canvasx(0)),
                                               y=round(y*8-canvas.canvasy(0))), edit=True)
            editor.assert_called_once_with([2])

    def test_original_comparison_keeps_zoom_and_scroll(self):
        app = self.app
        canvas = self.show_preview_canvas()
        frame = app._edit_session['image']
        frame[1710:1740, 1280:1330] = (12, 34, 56)
        app._preview_zoom = 8
        app._redraw_preview()
        canvas.xview_moveto((1300 * 8 - 100) / (1600 * 8))
        canvas.yview_moveto((1725 * 8 - 100) / (2200 * 8))
        app.update()
        app._redraw_preview()
        before = (app._preview_zoom, canvas.xview(), canvas.yview(), canvas.cget('scrollregion'))
        documents = copy.deepcopy([page['doc'] for page in self.pages])
        png_before = Path(app.result_path).read_bytes()

        def point_color():
            tile, = canvas.find_withtag('preview-tile')
            left, top = canvas.coords(tile)
            # 8배 확대에서 같은 원본 위치의 Tk 색을 읽는다.
            return tuple(canvas.tk.call(str(app._preview_photo), 'get',
                                        int(1300*8-left), int(1725*8-top)))

        result_color = point_color()
        self.assertNotEqual(result_color, (56, 34, 12))
        self.assertEqual(app.preview_compare_btn.cget('text'), '원본 보기')
        app.preview_compare_btn.invoke()
        self.assertEqual(point_color(), (56, 34, 12))
        self.assertEqual((app._preview_zoom, canvas.xview(), canvas.yview(), canvas.cget('scrollregion')), before)
        self.assertEqual(app.preview_compare_btn.cget('text'), '결과 보기')
        px, py = int(1300*8-canvas.canvasx(0)), int(1725*8-canvas.canvasy(0))
        with patch.object(app, '_open_label_editor') as editor, patch.object(app, '_open_label_add') as add:
            app._on_label_click(SimpleNamespace(x=px, y=py))
            editor.assert_not_called()
            add.assert_not_called()
        app.preview_compare_btn.invoke()
        self.assertEqual(point_color(), result_color)
        self.assertEqual((app._preview_zoom, canvas.xview(), canvas.yview(), canvas.cget('scrollregion')), before)
        self.assertEqual(Path(app.result_path).read_bytes(), png_before)
        self.assertEqual([page['doc'] for page in self.pages], documents)
        app.preview_compare_btn.invoke()
        self.assertTrue(app._select_result_page(1))
        app.update()
        self.assertEqual(app.preview_compare_btn.cget('text'), '원본 보기')
        self.assertFalse(app._preview_original)

    def test_page_style_and_export_are_current_before_the_next_event(self):
        app = self.app
        self.show_preview_canvas()
        page = self.pages[1]
        first_path, second_path = [Path(item['png']) for item in self.pages]
        before = [path.read_bytes() for path in (first_path, second_path)]
        self.assertFalse(app.style_save_notice.winfo_ismapped())
        app.legend_check.deselect()
        app.settings['legend'] = False
        with patch.object(gui.colorchooser, 'askcolor', return_value=((10, 20, 90), '#0a145a')):
            app.pick_color()
        app._on_size_slide(32)
        self.assertIsNotNone(app._style_refresh_timer)
        self.assertTrue(app._select_result_page(1))
        self.assertIsNone(app._style_refresh_timer)
        self.assertEqual(page['render_options']['font_size'], 32)
        self.assertEqual(page['render_options']['text_color'], gui._hex_to_rgb(app.settings['text_color']))
        preview = Path(app.result_path).read_bytes()
        self.assertNotEqual(preview, before[1])
        app.update_idletasks()
        self.assertTrue(app.style_save_notice.winfo_ismapped())

        exported = self.root / '내보내기.png'
        with patch.object(gui.filedialog, 'asksaveasfilename', return_value=str(exported)):
            app.save_as_btn.invoke()
        self.assertEqual(exported.read_bytes(), preview)
        self.assertFalse(app.style_save_notice.winfo_ismapped())
        self.assertEqual([path.read_bytes() for path in (first_path, second_path)], before)

        app.placement_menu.set('계이름 줄')
        app._on_setting_changed()
        self.assertEqual(page['render_options']['placement_mode'], 'lanes')
        self.assertIn('공간', app.placement_notice.cget('text'))
        app.placement_menu.set('음표 옆(기본)')
        app._on_setting_changed()
        self.assertEqual(page['render_options'].get('placement_mode', 'near'), 'near')
        self.assertEqual(app.placement_notice.cget('text'), '')

        app.legend_check.select()
        app._on_setting_changed()
        self.assertIsNotNone(page['legend_options'])
        app.legend_check.deselect()
        app._on_setting_changed()
        self.assertIsNone(page['legend_options'])
        self.assertEqual(Path(app.result_path).read_bytes(), preview)
        self.assertFalse(app.style_save_notice.winfo_ismapped())
        self.assertTrue(app._select_result_page(0))
        self.assertEqual(self.pages[0]['render_options']['font_size'], 32)
        self.assertTrue(app._select_result_page(1))
        app.update_idletasks()
        self.assertFalse(app.style_save_notice.winfo_ismapped())
        app._on_size_slide(28)
        label = page['doc']['labels'][0]
        edit = dict(action='set_text', before={k: label[k] for k in ('staff', 'x', 'y', 'pitch', 'text')},
                    after={'text': '솔'})
        self.assertTrue(app._apply_label_changes([edit]))
        self.assertIsNone(app._style_refresh_timer)
        self.assertEqual(page['render_options']['font_size'], 28)
        self.assertEqual(page['doc']['labels'][0]['text'], '솔')
        self.assertFalse(app.style_save_notice.winfo_ismapped())
        self.assertNotEqual(Path(app.result_path).parent, Path(page['_style_folder']))
        self.assertEqual([path.read_bytes() for path in (first_path, second_path)], before)

    def test_page_style_failure_keeps_previous_page_and_pending_style(self):
        app = self.app
        app._on_size_slide(32)
        pending = app._style_refresh_timer
        current = app._edit_session, app.result_path, app.labels_path
        with patch.object(gui, '_restyle_edit_session', side_effect=OSError('쓰기 실패')):
            self.assertFalse(app._select_result_page(1))
        self.assertEqual((app._edit_session, app.result_path, app.labels_path), current)
        self.assertEqual(app._style_refresh_timer, pending)

    def test_quick_edit_buttons_and_keys_use_saved_edit_history(self):
        app = self.app
        page = self.pages[0]
        initial = Path(page['png']).read_bytes(), Path(page['json']).read_bytes()
        self.show_preview_canvas()
        label = page['doc']['labels'][0].copy()
        app._open_label_editor([0])
        saved = len(page['changes'])
        self.press(app._edit_text, '<KeyPress-2>')
        self.assertEqual(len(page['changes']), saved)
        self.press(app._edit_list, '<KeyPress-2>')
        self.assertEqual(page['doc']['labels'][0]['text'], '레')
        self.press(app._edit_list, '<KeyPress-numbersign>')
        self.assertEqual(page['doc']['labels'][0]['text'], '레#')
        self.press(app._edit_list, '<KeyPress-numbersign>')
        self.assertEqual(page['doc']['labels'][0]['text'], '레')
        self.press(app._edit_list, '<KeyPress-numbersign>')
        self.press(app._edit_list, '<KeyPress-b>')
        self.assertEqual(page['doc']['labels'][0]['text'], '레b')
        self.assertEqual(page['doc']['labels'][0]['pitch'], label['pitch'])
        buttons = self.quick_edit_buttons()
        buttons['b'].invoke()
        self.assertEqual(page['doc']['labels'][0]['text'], '레')
        buttons['b'].invoke()
        self.assertEqual(page['doc']['labels'][0]['text'], '레b')
        buttons['솔'].invoke()
        self.assertEqual(page['doc']['labels'][0]['text'], '솔')
        app._undo_label_edit()
        self.assertEqual(page['doc']['labels'][0]['text'], '레b')
        self.assertTrue((Path(app.result_path).parent / '재개정보.json').is_file())
        self.assertEqual((Path(page['original_png']).read_bytes(), Path(page['original_json']).read_bytes()), initial)

    def quick_edit_buttons(self):
        return {widget.cget('text'): widget for frame in self.app._edit_window.winfo_children()
                for widget in frame.winfo_children() if isinstance(widget, gui.ctk.CTkButton)}

    def test_quick_edit_follows_document_letter_notation(self):
        app = self.app
        self.show_preview_canvas()
        page = self.pages[0]
        page['doc']['music']['notation'] = page['original_doc']['music']['notation'] = 'letter'
        app._open_label_editor([0])
        buttons = self.quick_edit_buttons()
        self.assertEqual([key for key in buttons if key in ('C', 'D', 'E', 'F', 'G', 'A', 'B')],
                         ['C', 'D', 'E', 'F', 'G', 'A', 'B'])
        self.assertNotIn('도', buttons)
        self.press(app._edit_list, '<KeyPress-1>')
        self.assertEqual(page['doc']['labels'][0]['text'], 'C')
        buttons['F'].invoke()
        self.assertEqual(page['doc']['labels'][0]['text'], 'F')
        self.press(app._edit_list, '<KeyPress-7>')
        self.assertEqual(page['doc']['labels'][0]['text'], 'B')
        buttons['#'].invoke()
        self.assertEqual(page['doc']['labels'][0]['text'], 'B#')
        self.press(app._edit_list, '<KeyPress-numbersign>')
        self.assertEqual(page['doc']['labels'][0]['text'], 'B')

    def test_clipboard_image_starts_conversion_and_preserves_text_paste(self):
        app = self.app
        canvas = self.show_preview_canvas()
        old_dir = app.settings['last_input_dir']
        old_selection = app._edit_session
        self.focus(app.key_entry)
        with patch.object(gui.ImageGrab, 'grabclipboard') as clipboard:
            app._paste_clipboard_image(SimpleNamespace(widget=app.key_entry))
            clipboard.assert_not_called()
        with patch.object(gui.ImageGrab, 'grabclipboard', return_value=['file.png']):
            with patch.object(app, 'start_convert') as convert:
                self.press(canvas, '<Control-v>')
                convert.assert_not_called()
        self.assertIs(app._edit_session, old_selection)

        with patch.object(gui.ImageGrab, 'grabclipboard', return_value=Image.new('RGB', (42, 28))):
            with patch.object(Image.Image, 'save', side_effect=OSError('쓰기 실패')):
                self.press(canvas, '<Control-v>')
        self.assertIs(app._edit_session, old_selection)
        self.assertFalse(list((self.root / '붙여넣은 악보').glob('*.png')))

        clip = Image.new('RGBA', (42, 28), (0, 0, 0, 0))
        clip.putpixel((3, 5), (10, 20, 90, 255))
        with patch.object(gui.ImageGrab, 'grabclipboard', return_value=clip):
            with patch.object(app, 'start_convert') as convert:
                self.press(canvas, '<Control-v>')
                convert.assert_called_once_with()
        self.assertEqual(app.settings['last_input_dir'], old_dir)
        self.assertEqual(app.input_paths, (app.input_path,))
        with Image.open(app.input_path) as pasted:
            self.assertEqual(pasted.size, (42, 28))
            self.assertEqual(pasted.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(pasted.getpixel((3, 5)), (10, 20, 90))

    def test_notation_settings_refresh_page_and_reject_invalid_key(self):
        app = self.app
        self.show_preview_canvas()
        for page in self.pages:
            for doc in (page['doc'], page['original_doc']):
                doc['music'].update(notation='solfege-fixed', key_letters=[], tonic='')
        app.notation_menu.set('영문 (C D E)')
        app._on_setting_changed()
        self.assertEqual(app._edit_session['doc']['labels'][0]['text'], 'E')
        self.assertTrue(app._select_result_page(1))
        self.assertEqual(app._edit_session['doc']['labels'][0]['text'], 'E')
        self.assertEqual(json.loads(Path(app.labels_path).read_bytes())['music']['notation'], 'letter')
        path = app.result_path
        app.key_entry.delete(0, 'end')
        app.key_entry.insert(0, 'ZZ')
        app.notation_menu.set('계이름 (이동도)')
        app._on_setting_changed()
        self.assertEqual(app.result_path, path)
        app.key_entry.delete(0, 'end')
        app.key_entry.insert(0, 'E')
        app._on_setting_changed()
        self.assertEqual(app._edit_session['doc']['labels'][0]['text'], '도')

    def test_page_summary_tracks_edits_pages_and_reopened_exclusions(self):
        app = self.app
        page = self.pages[0]
        page['recognition_exclusions'] = dict(beam=2, offstaff=1, accidental=0, chord=1)
        app._update_page_controls()
        self.assertIn('라벨 4 · 확실 2 · 확인 필요 1 · 주의 1', app.page_label.cget('text'))
        self.assertIn('인식 제외 4', app.page_label.cget('text'))
        label = page['doc']['labels'][2]
        change = dict(action='set_text', before={k:label[k] for k in ('staff','x','y','pitch','text')},
                      after=dict(text='라'))
        self.assertTrue(app._apply_label_changes([change], 2))
        self.assertIn('라벨 4 · 확실 3 · 확인 필요 0 · 주의 1', app.page_label.cget('text'))
        reopened = gui._load_edit_version(str(Path(app.result_path).parent), page['source_path'], str(self.root))
        self.assertEqual(reopened['recognition_exclusions'], page['recognition_exclusions'])
        app._undo_label_edit()
        self.assertIn('확인 필요 1', app.page_label.cget('text'))
        self.assertTrue(app._select_result_page(1))
        self.assertIn('제외 기록 없음', app.page_label.cget('text'))
        app._page_sessions = []
        app._edit_session = reopened
        app._update_page_controls()
        self.assertIn('인식 제외 4', app.page_label.cget('text'))

    def test_preview_shortcuts_zoom_compare_move_and_respect_typing(self):
        app = self.app
        canvas = self.show_preview_canvas()
        app._preview_zoom = 1.
        app._redraw_preview()
        self.press(canvas, '<Control-equal>')
        self.assertGreater(app._preview_zoom, 1.)
        self.press(canvas, '<Control-minus>')
        self.assertAlmostEqual(app._preview_zoom, 1.)
        self.press(canvas, '<Control-equal>')
        self.press(canvas, '<Control-0>')
        self.assertEqual(app._preview_zoom, 1.)
        scroll = canvas.xview(), canvas.yview()
        self.press(canvas, '<KeyPress-v>')
        self.assertTrue(app._preview_original)
        self.assertEqual((canvas.xview(), canvas.yview()), scroll)
        self.press(app.key_entry, '<KeyPress-v>')
        self.assertTrue(app._preview_original)
        self.press(app.key_entry, '<KeyPress-Next>')
        self.assertEqual(app._page_index, 0)
        self.press(canvas, '<KeyPress-Next>')
        self.assertEqual(app._page_index, 1)
        self.assertFalse(app._preview_original)
        self.press(canvas, '<KeyPress-Prior>')
        self.assertEqual(app._page_index, 0)

    def test_export_applies_notation_to_unvisited_pages_and_releases_frame(self):
        import weakref
        import fitz
        import numpy as np
        frames = []
        def load(path):
            self.assertTrue(all(previous() is None for previous in frames))
            frame = np.asarray(Image.open(path).convert('RGB'))[:, :, ::-1].copy()
            frames.append(weakref.ref(frame))
            return frame
        old = []
        for index, session in enumerate(self.pages):
            session['original_doc']['music'].update(notation='solfege-fixed', key_letters=[], tonic='')
            if index:
                session['image'][0, 0] = [20, 40, 60]
            frame_path = self.root / f'프레임-{index}.png'
            Image.fromarray(session['image'][:, :, ::-1]).save(frame_path)
            old.append(Path(session['png']).read_bytes())
            session.update(image=None, frame_path=str(frame_path))
        style = dict(font_path='C:/Windows/Fonts/malgun.ttf', font_size=28,
                     text_color=(15,20,130), placement_mode='near', legend=False,
                     notation_state=('letter','',False))
        documents = []
        render = gui._render_edit_document
        def inspect_document(page, doc, path):
            self.assertEqual([label['text'] for label in doc['labels']], ['E'] * 4)
            self.assertEqual(page['render_options']['font_size'], 28)
            self.assertEqual(page['render_options']['text_color'], (15,20,130))
            documents.append(doc['music']['notation'])
            return render(page, doc, path)
        with (patch.object(gui, '_read_page_frame', new=load),
              patch.object(gui, '_render_edit_document', new=inspect_document)):
            folder = Path(gui._export_styled_batch(self.pages, str(self.root), style))
        self.assertEqual(documents, ['letter','letter'])
        results = sorted(folder.glob('*.png'))
        self.assertEqual(len(results), 2)
        for index, path in enumerate(results):
            self.assertNotEqual(path.read_bytes(), old[index])
            self.assertEqual(Path(self.pages[index]['png']).read_bytes(), old[index])
            self.assertIsNone(self.pages[index]['image'])
        self.assertEqual(Image.open(results[1]).getpixel((0,0)), (60,40,20))
        with fitz.open(folder/'전체_계이름.pdf') as pdf:
            self.assertEqual(len(pdf), 2)
            self.assertAlmostEqual(pdf[0].rect.width, 1600*72/300, places=3)
            self.assertAlmostEqual(pdf[0].rect.height, 2200*72/300, places=3)
        with patch.object(gui, '_save_image_pages_pdf', side_effect=OSError('주입: 합본 저장 실패')):
            with self.assertRaises(OSError):
                gui._export_styled_batch(self.pages, str(self.root), style)
        self.assertEqual(list(self.root.glob('전체계이름-*')), [folder])
        self.assertEqual(list(self.root.glob('.전체계이름-*')), [])

    def test_studio_palette_fixed_actions_and_theme_preserve_result(self):
        app = self.app
        self.assertEqual(gui.UI_COLORS['background'], ('#F3F5F8','#11141A'))
        self.assertIsInstance(app.sidebar, gui.ctk.CTkScrollableFrame)
        self.assertEqual(app.select_btn.grid_info()['column'], 0)
        self.assertEqual(app.select_images_btn.grid_info()['column'], 1)
        self.assertIs(app.select_btn.master, app.select_images_btn.master)
        actions = app.select_btn.master.master
        rail = actions.master
        self.assertEqual(rail.cget('width'), 316)
        self.assertAlmostEqual(rail.winfo_width(), round(rail._apply_widget_scaling(316)), delta=1)
        self.assertEqual(actions.winfo_width(), rail.winfo_width())
        cards = [w for w in app.sidebar.winfo_children() if isinstance(w, gui.ctk.CTkFrame)]
        self.assertEqual(len(cards), 5)
        self.assertTrue(all(card.cget('corner_radius') == 10 and card.cget('border_width') == 1
                            for card in cards))
        self.assertEqual(app.convert_btn.cget('fg_color'), gui.UI_COLORS['primary'])
        self.assertEqual(app.listen_btn.cget('fg_color'), gui.UI_COLORS['primary'])
        self.assertEqual(app.font_menu.cget('fg_color'), gui.UI_COLORS['secondary'])
        self.assertEqual(app.placement_notice.cget('fg_color'), gui.UI_COLORS['amber'])
        self.assertEqual(app.style_save_notice.cget('fg_color'), gui.UI_COLORS['blue'])
        before = [(button.winfo_rootx(),button.winfo_rooty())
                  for button in (app.select_btn,app.convert_btn)]
        app.sidebar._parent_canvas.yview_moveto(1)
        app.update()
        self.assertEqual(before, [(button.winfo_rootx(),button.winfo_rooty())
                                  for button in (app.select_btn,app.convert_btn)])
        saved = Path(app.result_path).read_bytes(), Path(app.labels_path).read_bytes()
        for mode, color in [('dark','#0D1016'),('light','#E8EDF3')]:
            if app.settings['appearance'] != mode:
                app.toggle_theme()
            app.update()
            self.assertEqual(app.preview_canvas.cget('background').lower(), color.lower())
        app._toggle_preview_original()
        self.assertEqual(app.preview_compare_btn.cget('fg_color'), gui.UI_COLORS['compare_active'])
        app._toggle_preview_original()
        self.assertEqual((Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes()),saved)
        self.assertTrue(app.practice_bar.winfo_viewable())
        self.assertLessEqual(max(int(widget.grid_info()['row'])
            for widget in app.practice_bar.winfo_children() if widget.winfo_manager()=='grid'), 1)

    def test_studio_dock_controls_fit_supported_window_sizes(self):
        app = self.app
        for width, height in ((1280, 700), (960, 640)):
            app.geometry(f'{width}x{height}+20+20')
            app.update()
            for widget in (app.listen_btn, app.stop_btn, app.practice_speed,
                           app.audio_delay_slider, app.practice_repeat):
                self.assertTrue(widget.winfo_viewable())
                self.assertGreaterEqual(widget.winfo_rootx(), app.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     app.winfo_rootx() + app.winfo_width())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     app.winfo_rooty() + app.winfo_height())

    def test_studio_editor_palette_and_theme_preserve_document(self):
        app = self.app
        original = copy.deepcopy(app._edit_session['doc'])
        app._open_label_editor([1])
        buttons = {button.cget('text'): button for frame in app._edit_window.winfo_children()
                   if isinstance(frame, gui.ctk.CTkFrame) for button in frame.winfo_children()
                   if isinstance(button, gui.ctk.CTkButton)}
        self.assertEqual(buttons['도'].cget('fg_color'), gui.UI_COLORS['secondary'])
        self.assertEqual(buttons['#'].cget('fg_color'), gui.UI_COLORS['compare_active'])
        self.assertEqual(buttons['b'].cget('fg_color'), gui.UI_COLORS['compare_active'])
        self.assertEqual(buttons['라벨 삭제'].cget('fg_color'), gui.UI_COLORS['danger'])
        for mode in ('dark', 'light'):
            if app.settings['appearance'] != mode:
                app.toggle_theme()
            app.update()
            self.assertEqual(app._edit_list.cget('background').lower(),
                             gui.UI_COLORS['surface'][mode == 'dark'].lower())
        self.assertEqual(app._edit_session['doc'], original)

    def test_preview_tile_matches_full_image_grid(self):
        with Image.fromarray(np.random.default_rng(0).integers(0, 256, (49, 53, 3), dtype=np.uint8)) as source:
            for zoom in (.71, 1, 2, 8):
                size = tuple(int(length*zoom) for length in source.size)
                resample = Image.Resampling.LANCZOS if zoom <= 2 else Image.Resampling.NEAREST
                with self.subTest(zoom=zoom), source.resize(size, resample) as full:
                    for bounds in ((4, 5, 17, 21), (size[0]-19, size[1]-18, *size)):
                        with gui._resize_preview_tile(source, size, bounds, resample) as tile:
                            with full.crop(bounds) as expected:
                                diff = np.abs(np.asarray(tile, dtype=np.int16) - np.asarray(expected))
                                self.assertLessEqual(int(diff.max()), 1)

    def focus(self,widget):
        app=self.app
        # Windows 제목 표시줄 초기화가 예약한 포커스 복구까지 실제 대상을 확인한다.
        deadline=time.monotonic()+2
        while True:
            app.update();widget.focus_force();app.update()
            focused=app.focus_get()
            if focused is widget or (focused and str(focused).startswith(str(widget)+'.')):
                break
            self.assertLess(time.monotonic(),deadline,'대상 위젯으로 포커스를 옮기지 못함')
            time.sleep(.01)
        return focused
    def press(self,widget,sequence):
        self.focus(widget).event_generate(sequence);self.app.update()
    def test_shortcuts_respect_input_focus_and_editor(self):
        app=self.app;doc=copy.deepcopy(app._edit_session['doc'])
        before=(Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())
        press=self.press
        press(app.preview_canvas,'<KeyPress-n>');self.assertEqual(app._review_index,1)
        press(app.preview_canvas,'<KeyPress-N>');self.assertEqual(app._review_index,2)
        press(app.preview_canvas,'<KeyPress-p>');self.assertEqual(app._review_index,1)
        for sequence in ('<Control-KeyPress-n>','<Alt-KeyPress-n>'):
            press(app.preview_canvas,sequence);self.assertEqual(app._review_index,1)
        for entry in (app.key_entry,app.page_entry):
            entry.delete(0,'end');press(entry,'<KeyPress-n>')
            self.assertEqual(entry.get(),'n');self.assertEqual(app._review_index,1)
        press(app.log_box,'<KeyPress-n>');self.assertEqual(app._review_index,1)
        app._open_label_editor()
        press(app._edit_list,'<KeyPress-n>');self.assertEqual(app._edit_list.curselection(),(2,))
        app._edit_text.delete(0,'end');press(app._edit_text,'<KeyPress-p>')
        self.assertEqual(app._edit_text.get(),'p');self.assertEqual(app._review_index,2)
        press(app._edit_list,'<KeyPress-P>');self.assertEqual(app._edit_list.curselection(),(1,))
        app._converting=True;press(app.preview_canvas,'<KeyPress-n>')
        self.assertEqual(app._review_index,1);app._converting=False
        self.assertEqual(app._edit_session['doc'],doc)
        self.assertEqual((Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes()),before)
    def test_help_shortcuts_keep_text_and_reuse_window(self):
        app=self.app;doc=copy.deepcopy(app._edit_session['doc'])
        before=(Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())
        self.press(app.preview_canvas,'<KeyPress-F1>')
        first=app._help_window;self.assertTrue(first.winfo_exists())
        self.press(first,'<KeyPress-F1>');self.assertIs(app._help_window,first)
        self.press(first,'<Escape>');self.assertFalse(first.winfo_exists())
        app.key_entry.delete(0,'end');self.press(app.key_entry,'<KeyPress-question>')
        self.assertEqual(app.key_entry.get(),'?');self.assertFalse(first.winfo_exists())
        self.press(app.key_entry,'<KeyPress-F1>');self.assertTrue(app._help_window.winfo_exists())
        self.assertEqual(app.key_entry.get(),'?');app._help_window.destroy()
        app._open_label_editor();self.press(app._edit_list,'<KeyPress-question>')
        self.assertTrue(app._help_window.winfo_exists());app._help_window.destroy()
        app._edit_text.delete(0,'end');self.press(app._edit_text,'<KeyPress-question>')
        self.assertEqual(app._edit_text.get(),'?');self.assertFalse(app._help_window.winfo_exists())
        self.assertEqual(app._edit_session['doc'],doc)
        self.assertEqual((Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes()),before)
    def test_identical_labels_select_their_own_placement(self):
        app=self.app;session=app._edit_session
        session['doc']['labels'].append(copy.deepcopy(session['doc']['labels'][2]))
        png=self.root/'같은위치.png'
        session['placements']=render_solfege_on_image(session['image'],document_notes(session['doc']),
            str(png),confidences=['certain','caution','check','certain','check'],**session['render_options'])
        session['original_doc']=copy.deepcopy(session['doc'])
        session.update(png=str(png),original_png=str(png),original_placements=session['placements'])
        save_labels(session['json'],session['doc']);app.result_path=str(png)
        app._load_preview_image(str(png));app.update()
        matches=[box for box in session['placements'] if box['note'].x==1300]
        self.assertEqual(len(matches),2)
        before=png.read_bytes();doc=copy.deepcopy(session['doc'])
        app.next_review_btn.invoke();app.next_review_btn.invoke()
        self.assertIs(app._selected_preview_box(),matches[0])
        app.next_review_btn.invoke();self.assertEqual(app._review_index,4)
        self.assertIs(app._selected_preview_box(),matches[1],'둘째 라벨도 첫 상자로 이동함')
        self.assertIn('3 / 3',app.review_label.cget('text'))
        self.assertEqual(session['doc'],doc);self.assertEqual(png.read_bytes(),before)
        if CAPTURE:
            from tools.check_label_edit_gui import capture
            capture(app,CAPTURE/'04_duplicate_label.png')
    def test_page_counts_follow_switch_edit_undo_and_empty_page(self):
        app=self.app
        before=[(Path(p['png']).read_bytes(),Path(p['json']).read_bytes()) for p in self.pages]
        self.assertIn('확인 필요 1 · 주의 1',app.page_label.cget('text'))
        app._page_sessions=self.pages[:1];app._update_page_controls()
        self.assertEqual(app.page_nav.winfo_manager(),'grid')
        self.assertEqual(app.next_page_btn.cget('state'),'disabled')
        app.next_review_btn.invoke();app._open_label_editor()
        app._edit_text.delete(0,'end');app._edit_text.insert(0,'레');app._change_label('set_text');app.update()
        self.assertIn('확인 필요 1 · 주의 0',app.page_label.cget('text'))
        app._undo_label_edit();app.update()
        self.assertIn('확인 필요 1 · 주의 1',app.page_label.cget('text'))
        app._page_sessions=self.pages;app._select_result_page(1);app.update()
        self.assertIn('2 / 2',app.page_label.cget('text'))
        if CAPTURE:
            from tools.check_label_edit_gui import capture
            capture(app,CAPTURE/'05_page_review_counts.png')
        self.pages[1]['doc']['labels']=[];app._update_page_controls()
        self.assertIn('확인 필요 0 · 주의 0',app.page_label.cget('text'))
        for p,(png,js) in zip(self.pages,before):
            self.assertEqual(Path(p['original_png']).read_bytes(),png)
            self.assertEqual(Path(p['original_json']).read_bytes(),js)
    def test_edit_delete_undo_region_and_empty_reset(self):
        app=self.app;app.next_review_btn.invoke();app._open_label_editor()
        app._edit_text.delete(0,'end');app._edit_text.insert(0,'레')
        app._change_label('set_text');app.update();self.assertIn('0 / 1',app.review_label.cget('text'))
        app._undo_label_edit();app.update();self.assertIn('1 / 2',app.review_label.cget('text'))
        self.assertIn('확인 필요 1 · 주의 1',app.page_label.cget('text'))
        app._change_label('delete');app.update();self.assertIn('/ 1',app.review_label.cget('text'))
        self.assertIn('확인 필요 1 · 주의 0',app.page_label.cget('text'))
        app._undo_label_edit();app.update();self.assertIn('1 / 2',app.review_label.cget('text'))
        self.assertIn('확인 필요 1 · 주의 1',app.page_label.cget('text'))
        app._select_region((0,0,600,600));app.update();self.assertIn('0 / 1',app.review_label.cget('text'))
        self.assertIn('확인 필요 0 · 주의 1',app.page_label.cget('text'))
        app.next_review_btn.invoke();self.assertEqual(app._review_index,1)
        if CAPTURE:
            from tools.check_label_edit_gui import capture
            capture(app,CAPTURE/'03_region_review.png')
        app._select_region(None);app.update();self.assertIn('0 / 2',app.review_label.cget('text'))
        for label in app._edit_session['doc']['labels']:label['confidence']='certain'
        app._update_review_controls();self.assertEqual(app.review_label.cget('text'),'확인 필요 없음')
        for button in (app.prev_review_btn,app.next_review_btn):
            self.assertEqual(button.cget('state'),'disabled')
            self.assertEqual(button.cget('fg_color'),('gray75','gray30'))
        self.assertFalse(app._move_review_label(1));self.assertEqual(app.next_review_btn.cget('state'),'disabled')
        app._set_input(self.pages[0]['source_path']);app.update()
        self.assertIsNone(app._review_index);self.assertEqual(app.review_nav.winfo_manager(),'')
        self.assertFalse(app._move_review_label(1))

    def test_windows_numlock_is_not_alt(self):
        from types import SimpleNamespace
        app=self.app;self.focus(app.preview_canvas)
        event=SimpleNamespace(keysym='n',char='n',keycode=78,state=8,widget=app.preview_canvas)
        app._review_shortcut(event)
        self.assertEqual(app._review_index,1)
        event.keysym='F1';event.char='';event.keycode=112
        app._help_shortcut(event);app.update()
        self.assertTrue(getattr(app,'_help_window',None) and app._help_window.winfo_exists())
        app._help_window.destroy()

    def test_windows_ime_process_key_keeps_input_and_ignores_late_text(self):
        from types import SimpleNamespace
        app=self.app;self.focus(app.preview_canvas)
        event=SimpleNamespace(keysym='??',char='',keycode=229,state=8,widget=app.preview_canvas)
        def state_for(*held):
            def fill(keys):
                for vk in held:keys[vk]=0x80
                return 1
            return fill
        with patch('ctypes.windll.user32.GetKeyboardState',side_effect=state_for(78)):
            app._review_shortcut(event);self.assertEqual(app._review_index,1)
            app._review_shortcut(event);self.assertEqual(app._review_index,2)
        with patch('ctypes.windll.user32.GetKeyboardState',side_effect=state_for(80)):
            app._review_shortcut(event);self.assertEqual(app._review_index,1)
        event.char='ㅜ';event.keycode=12636
        app._review_shortcut(event);self.assertEqual(app._review_index,1)
        event.char='';event.keycode=229
        with patch('ctypes.windll.user32.GetKeyboardState',side_effect=state_for(78,80)) as keys:
            app._review_shortcut(event);self.assertEqual(app._review_index,1)
            keys.reset_mock()
            for state in (4,0x20000):
                event.state=state;app._review_shortcut(event)
                self.assertEqual(app._review_index,1)
            event.state=8;self.focus(app.key_entry)
            app._review_shortcut(event);self.assertEqual(app._review_index,1)
            keys.assert_not_called()


    def test_ime_other_key_while_n_held_is_not_another_n(self):
        from types import SimpleNamespace
        app=self.app;self.focus(app.preview_canvas)
        app._review_index=1
        event=SimpleNamespace(keysym='??',char='',keycode=229,state=0,widget=app.preview_canvas)
        def keyboard_state(keys):
            keys[78]=0x80;keys[77]=0x80
            return 1
        with patch('ctypes.windll.user32.GetKeyState',side_effect=lambda vk:0x8000 if vk==78 else 0), \
             patch('ctypes.windll.user32.GetKeyboardState',side_effect=keyboard_state):
            app._review_shortcut(event)
        self.assertEqual(app._review_index,1)


CAPTURE=None
if __name__=='__main__':
    if '--capture-dir' in sys.argv:
        offset=sys.argv.index('--capture-dir');CAPTURE=Path(sys.argv[offset+1]);del sys.argv[offset:offset+2]
        CAPTURE.mkdir(parents=True,exist_ok=True)
    assert callable(getattr(gui.SheetHelperApp,'_help_shortcut',None)), '단축키 도움말 경로가 없다'
    assert callable(getattr(gui.SheetHelperApp,'_move_review_label',None)), '확인 필요 라벨 순회 경로가 없다'
    unittest.main()
