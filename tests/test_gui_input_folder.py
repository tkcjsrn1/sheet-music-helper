"""마지막 입력 폴더를 기억하되 취소·변환 중 선택·신고 ZIP에는 섞지 않는다."""
import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui

class InputFolderTests(unittest.TestCase):
    def close(self,app):
        # 이전 Tk 창의 예약 콜백이 다음 실행으로 넘어가지 않게 정리한다.
        widgets=[app]
        for widget in widgets:widgets.extend(widget.winfo_children())
        owners={name:w for w in widgets for name in (getattr(w,'_tclCommands',None) or [])}
        for timer in app.tk.splitlist(app.tk.call('after','info')):
            owner=owners.get(str(app.tk.call('after','info',timer)[0]).split()[0])
            owner.after_cancel(timer) if owner else app.tk.call('after','cancel',timer)
        app.destroy()
    def test_select_restart_cancel_and_removed_folder(self):
        with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
            root=Path(tmp);folder=root/'개인 악보';folder.mkdir()
            source=folder/'입력.png';gui.Image.new('RGB',(20,30),'white').save(source)
            app=gui.SheetHelperApp();app.withdraw()
            try:
                with patch('gui.filedialog.askopenfilename',return_value=str(source)) as chooser:
                    app.select_file()
                    self.assertIn('initialdir',chooser.call_args.kwargs)
                self.assertEqual(app.settings['last_input_dir'],str(folder))
                self.assertEqual(json.loads(Path(app.settings_path).read_text(encoding='utf-8'))['last_input_dir'],str(folder))
                with patch('gui.filedialog.askopenfilenames',return_value=()) as chooser:
                    app.select_images();self.assertEqual(chooser.call_args.kwargs['initialdir'],str(folder))
                self.assertEqual(app.settings['last_input_dir'],str(folder))
                second=folder/'둘째.png';gui.Image.new('RGB',(20,30),'white').save(second)
                app.settings['last_input_dir']=''
                with patch('gui.filedialog.askopenfilenames',return_value=(str(source),str(second))):app.select_images()
                self.assertEqual(app.input_paths,(str(source),str(second)))
                self.assertEqual(app.settings['last_input_dir'],str(folder))
                app._converting=True
                app._set_input(str(root/'other.png'))
                self.assertEqual(app.settings['last_input_dir'],str(folder));app._converting=False
            finally:self.close(app)
            app=gui.SheetHelperApp();app.withdraw()
            try:
                with patch('gui.filedialog.askopenfilename',return_value='') as chooser:
                    app.select_file();self.assertEqual(chooser.call_args.kwargs['initialdir'],str(folder))
                folder.rename(root/'removed')
                with patch('gui.filedialog.askopenfilenames',return_value=()) as chooser:
                    app.select_images();self.assertFalse(chooser.call_args.kwargs['initialdir'])
            finally:self.close(app)
            app=gui.SheetHelperApp();app.withdraw()
            try:self.assertEqual(app.settings['last_input_dir'],'')
            finally:self.close(app)
    def test_saved_invalid_types_and_report_privacy(self):
        from types import SimpleNamespace
        from modules.feedback_bundle import SAFE_SETTINGS
        self.assertNotIn('last_input_dir',SAFE_SETTINGS)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json'
            for value in (123,[],{},'없는폴더'):
                path.write_text(json.dumps({'last_input_dir':value}),encoding='utf-8')
                app=SimpleNamespace(settings_path=str(path))
                self.assertEqual(gui.SheetHelperApp._load_settings(app).get('last_input_dir'),'')

class HeadlessFolderTests(unittest.TestCase):
    def test_only_folder_changes_after_select(self):
        from types import SimpleNamespace
        class App:
            _set_input=gui.SheetHelperApp._set_input
            _save_settings=gui.SheetHelperApp._save_settings
            select_file=gui.SheetHelperApp.select_file
            select_images=gui.SheetHelperApp.select_images
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'악보';folder.mkdir();source=folder/'입력.png';source.write_bytes(b'fixture')
            app=App();app.settings=dict(gui.DEFAULT_SETTINGS);app.settings_path=str(root/'settings.json');app._converting=False
            for name in ('_close_label_editor','_clear_result_pages','_update_review_controls','_stop_listening'):
                setattr(app,name,lambda:None)
            for name in ('edit_btn','file_label','open_result_btn','save_as_btn','report_btn'):
                setattr(app,name,SimpleNamespace(configure=lambda **kw:None))
            app.log=lambda text:None;app._load_preview_image=lambda path:None
            before=dict(app.settings)
            with patch('gui.filedialog.askopenfilename',return_value=str(source)):
                app.select_file()
            self.assertEqual(app.settings.get('last_input_dir'),str(folder))
            self.assertEqual({k:v for k,v in app.settings.items() if k!='last_input_dir'},
                             {k:v for k,v in before.items() if k!='last_input_dir'})
            saved=gui.SheetHelperApp._load_settings(app)
            self.assertEqual(saved,app.settings)
            with patch('gui.filedialog.askopenfilenames',return_value=()) as chooser:
                app.select_images();self.assertEqual(chooser.call_args.kwargs['initialdir'],str(folder))
            self.assertEqual(app.settings,saved)
            app._converting=True;app._set_input(str(root/'other.png'))
            self.assertEqual(app.settings,saved)

    def test_private_folder_not_in_report_zip(self):
        import zipfile
        from modules.feedback_bundle import save_feedback_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);private=root/'개인 악보';private.mkdir();source=private/'입력.png';source.write_bytes(b'input')
            result=root/'결과.png';result.write_bytes(b'result');labels=root/'라벨.json'
            labels.write_text(json.dumps(dict(source=dict(file=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),page=0),labels=[])),encoding='utf-8')
            target=root/'신고.zip'
            (root/'recent_files.json').write_text(json.dumps([str(source)],ensure_ascii=False),'utf8')
            save_feedback_bundle(str(source),str(result),str(labels),dict(gui.DEFAULT_SETTINGS,last_input_dir=str(private)),str(target),str(root))
            with zipfile.ZipFile(target) as bundle:
                self.assertNotIn('recent_files.json',bundle.namelist())
                report=json.loads(bundle.read('report.json'))
                self.assertNotIn('last_input_dir',report['settings'])
                self.assertNotIn(str(private),json.dumps(report,ensure_ascii=False))
                self.assertEqual(report['settings']['font_size'],18)

    def test_invalid_folder_types_and_stale_path(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json'
            for value in (123,[],{},'없는폴더'):
                with self.subTest(value=value):
                    path.write_text(json.dumps({'last_input_dir':value}),encoding='utf-8')
                    self.assertEqual(gui.SheetHelperApp._load_settings(SimpleNamespace(settings_path=str(path))).get('last_input_dir'),'')


class DropFilesTests(unittest.TestCase):
    def test_file_types_and_drop_order(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            png,tiff,pdf,text=[str(root/name) for name in ('악보 하나.PNG','둘째.tiff','악보.pdf','기타.txt')]
            for path in (png,tiff,pdf,text):
                Path(path).touch()
            app=SimpleNamespace(_converting=False,_closing=False,start_convert=Mock(),log=Mock())
            def drop(paths, busy=False):
                gui.SheetHelperApp._handle_dropped_files(app,paths,busy)
            with patch.object(sys,'frozen',False,create=True):
                for paths in ((png,), (tiff,png), (pdf,)):
                    app.start_convert.reset_mock()
                    drop(paths)
                    app.start_convert.assert_called_once_with(dropped_paths=paths)
                for paths, hint in (((), '파일이 없습니다'), ((str(root),), '폴더'),
                                    ((png,text), '지원하지 않는'), ((png,pdf), '이미지'),
                                    (None, '경로'), ((str(root/'없는.png'),),'파일')):
                    app.start_convert.reset_mock()
                    drop(paths)
                    app.start_convert.assert_not_called()
                    self.assertIn(hint,app.log.call_args.args[0])
            with patch.object(sys,'frozen',True,create=True):
                drop((pdf,))
                app.start_convert.assert_not_called()
                self.assertIn('exe에서는 이미지',app.log.call_args.args[0])
            drop((png,),busy=True)
            self.assertIn('변환',app.log.call_args.args[0])
            app._converting=True
            drop((png,))
            app.start_convert.assert_not_called()

    def test_wndproc_releases_drop_and_restores_original(self):
        import ctypes as ct
        from types import SimpleNamespace
        from unittest.mock import Mock
        names=[r'C:\악보 하나.png', r'C:\아주 긴 폴더 이름\둘째.jpg']
        delivered=[]
        def query(handle,index,buffer,size):
            if index==0xffffffff:
                return len(names)
            name=names[index]
            if buffer is not None:
                self.assertEqual(size,len(name)+1)
                buffer.value=name
            return len(name)
        user=SimpleNamespace(GetAncestor=Mock(return_value=200),
            SetWindowLongPtrW=Mock(return_value=300),CallWindowProcW=Mock(return_value=71))
        shell=SimpleNamespace(DragAcceptFiles=Mock(),DragQueryFileW=Mock(side_effect=query),DragFinish=Mock())
        with patch.object(ct,'WinDLL',side_effect=[user,shell],create=True), \
             patch.object(ct,'WINFUNCTYPE',ct.CFUNCTYPE,create=True), \
             patch.object(ct,'set_last_error',create=True),patch.object(ct,'get_last_error',return_value=5,create=True):
            hook=gui._WindowsFileDrop(100,delivered.append)
        try:
            self.assertEqual(hook._dispatch(200,16,0,0),71)
            user.CallWindowProcW.assert_called_once_with(300,200,16,0,0)
            self.assertEqual(hook._dispatch(200,0x233,400,0),0)
            shell.DragFinish.assert_called_once_with(400)
            self.assertEqual(delivered,[tuple(names)])
            shell.DragQueryFileW.side_effect=OSError('HDROP')
            self.assertEqual(hook._dispatch(200,0x233,401,0),0)
            self.assertEqual(delivered,[tuple(names),None])
            shell.DragFinish.assert_called_with(401)
        finally:
            self.assertTrue(hook.close())
        self.assertTrue(hook.close())
        self.assertEqual([c.args for c in shell.DragAcceptFiles.call_args_list],[(200,True),(200,False)])
        user.SetWindowLongPtrW.assert_called_with(200,-4,300)
        self.assertEqual(user.SetWindowLongPtrW.call_count,2)

    def test_drop_failure_restores_previous_sheets_and_files(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
            root=Path(tmp)
            app=gui.SheetHelperApp()
            app.withdraw()
            old=root/'악보.png'
            incoming=root/'다른 폴더'/'악보.png'
            incoming.parent.mkdir()
            for p in (old,incoming):
                gui.Image.new('RGB',(24,36),'white').save(p)
            app._set_input(str(old))
            output=Path(app.output_dir)
            output.mkdir(exist_ok=True)
            png=output/'악보_계이름.png'
            labels=output/'악보_라벨.json'
            png.write_bytes(b'old image');labels.write_bytes(b'old labels')
            session=dict(doc=dict(labels=[]),source_path=str(old),png=str(png),json=str(labels),placements=[])
            app._edit_session=session
            app._page_sessions=[session]
            app.result_path,app.labels_path=str(png),str(labels)
            preview=app._preview_source
            app._page_cache=Mock()
            saved_cache=app._page_cache
            errors=[]
            class ImmediateThread:
                def __init__(self,*,target,daemon):self.target=target
                def start(self):self.target()
            def fail(page,suffix):
                request=app._run_request
                self.assertEqual(request.input_paths,(str(incoming),))
                path=Path(request.output_dir)
                self.assertNotEqual(path,output)
                (path/png.name).write_bytes(b'new incomplete image')
                app.labels_path=str(path/labels.name)
                errors.append(path)
                raise gui.RendererError('합성 검사 실패')
            try:
                with patch('gui.threading.Thread',ImmediateThread),patch.object(app,'_convert_page',side_effect=fail):
                    app._handle_dropped_files((str(incoming),))
                    app.update()
                self.assertEqual(len(errors),1)
                self.assertFalse(errors[0].exists())
                self.assertFalse(app._converting)
                self.assertIs(app._edit_session,session)
                self.assertIs(app._preview_source,preview)
                self.assertIs(app._page_cache,saved_cache)
                saved_cache.cleanup.assert_not_called()
                self.assertEqual(app.input_paths,(str(old),))
                self.assertEqual((app.result_path,app.labels_path),(str(png),str(labels)))
                self.assertEqual((png.read_bytes(),labels.read_bytes()),(b'old image',b'old labels'))
            finally:
                InputFolderTests().close(app)




class RecentFilesTests(unittest.TestCase):
    def test_recent_list_caps_deduplicates_and_recovers_from_bad_json(self):
        from types import SimpleNamespace,MethodType
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            app=SimpleNamespace(_recent_path=str(folder/'recent_files.json'),log=Mock())
            app._load_recent_files=MethodType(gui.SheetHelperApp._load_recent_files,app)
            file=Path(app._recent_path)
            inputs=[folder/f'악보 {i}.png' for i in range(7)]
            for path in inputs:
                path.touch()
            file.write_text('잘못된 JSON',encoding='utf8')
            self.assertEqual(app._load_recent_files(),[])
            gui.SheetHelperApp._remember_recent_files(app,[str(p) for p in inputs])
            self.assertEqual(json.loads(file.read_text('utf8')),[str(p) for p in inputs[:5]])
            gui.SheetHelperApp._remember_recent_files(app,[str(inputs[4]),str(inputs[5]),str(inputs[4])])
            self.assertEqual(app._load_recent_files(),[str(inputs[i]) for i in (4,5,0,1,2)])
            inputs[5].unlink()
            self.assertEqual(app._load_recent_files(),[str(inputs[i]) for i in (4,0,1,2)])
            self.assertEqual(sorted(p.name for p in folder.glob('*.json')),['recent_files.json'])

    def test_only_successful_conversion_records_existing_input(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'악보.png';image.touch()
            app=SimpleNamespace(input_path=str(image),output_dir=tmp,_run_all_pages=False,
                page_entry=Mock(),_convert_page=Mock(return_value='결과.png'),
                _recent_path=str(Path(tmp)/'recent_files.json'),_remember_recent_files=Mock(),
                _show_result=Mock(),log=Mock(),after=lambda _ms,callback:callback(),
                _clear_result_pages=Mock(),_draw_placeholder=Mock(),
                open_result_btn=Mock(),save_as_btn=Mock(),report_btn=Mock(),edit_btn=Mock(),convert_btn=Mock())
            app.page_entry.get.return_value='1'
            gui.SheetHelperApp._convert_worker(app)
            app._remember_recent_files.assert_called_once_with((str(image),))
            app._remember_recent_files.reset_mock()
            app._convert_page.side_effect=gui.RendererError('출력 오류')
            gui.SheetHelperApp._convert_worker(app)
            app._remember_recent_files.assert_not_called()

    def test_recent_command_checks_deleted_file_and_busy_state(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'악보.png'
            image.touch()
            app=SimpleNamespace(_converting=False,start_convert=Mock(),log=Mock())
            gui.SheetHelperApp._open_recent_file(app,str(image))
            app.start_convert.assert_called_once_with(dropped_paths=(str(image),))
            app.start_convert.reset_mock()
            app._converting=True
            gui.SheetHelperApp._open_recent_file(app,str(image))
            app.start_convert.assert_not_called()
            app._converting=False
            image.unlink()
            gui.SheetHelperApp._open_recent_file(app,str(image))
            app.start_convert.assert_not_called()
            self.assertIn('파일',app.log.call_args.args[0])




class SettingsValidationTests(unittest.TestCase):
    def test_invalid_saved_color_uses_default_and_keeps_other_settings(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            cache = SimpleNamespace(settings_path=path)
            for color in ('#f00', 'darkred', '#00xz00', '#1234567'):
                path.write_text(json.dumps({'text_color': color, 'last_input_dir': folder}), encoding='utf-8')
                settings = gui.SheetHelperApp._load_settings(cache)
                self.assertEqual(settings['text_color'], gui.DEFAULT_SETTINGS['text_color'])
                self.assertEqual(settings['last_input_dir'], folder)
            path.write_text('{"text_color":"#1D4ED8"}', encoding='utf-8')
            self.assertEqual(gui.SheetHelperApp._load_settings(cache)['text_color'], '#1D4ED8')
            path.write_text('null', encoding='utf-8')
            self.assertEqual(gui.SheetHelperApp._load_settings(cache)['text_color'], gui.DEFAULT_SETTINGS['text_color'])

if __name__=='__main__':unittest.main()
