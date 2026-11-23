"""다쪽 변환의 준비 상태·움직이는 진행 표시·개인 입력 제외를 검사한다."""
import subprocess,sys,tempfile,time,unittest,threading
import numpy as np
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui

class PageProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=patch('gui.base_dir',return_value=self.temp.name);self.base.start()
        self.argv=patch.object(sys,'argv',['gui.py']);self.argv.start()
        self.app=gui.SheetHelperApp();self.app.withdraw()
        self.pages=[dict(source_path=f'입력{i}.png',original_doc={'source':{'page':0}}) for i in (1,2)]
    def tearDown(self):
        # 예약 콜백은 등록한 위젯에서 취소해야 자식 위젯이 중복 삭제하지 않는다.
        widgets=[self.app]
        for widget in widgets:widgets.extend(widget.winfo_children())
        owners={name:widget for widget in widgets for name in (getattr(widget,'_tclCommands',None) or [])}
        for timer in self.app.tk.splitlist(self.app.tk.call('after','info')):
            script=self.app.tk.call('after','info',timer)[0]
            owner=owners.get(str(script).split()[0])
            if owner:owner.after_cancel(timer)
            else:self.app.tk.call('after','cancel',timer)
        self.app.destroy();self.argv.stop();self.base.stop();self.temp.cleanup()

    def test_result_actions_are_above_preview_and_single_page_hides_navigation(self):
        app = self.app
        app._page_sessions = self.pages[:1]
        app._update_page_controls()
        self.assertEqual(app.page_nav.grid_info()['row'], 0)
        self.assertEqual(app.preview_canvas.grid_info()['row'], 2)
        for widget in app.save_as_btn, app.edit_btn:
            self.assertIs(widget.master, app.page_buttons)
            self.assertEqual(widget.winfo_manager(), 'grid')
        self.assertFalse(app.prev_page_btn.winfo_manager())
        self.assertFalse(app.next_page_btn.winfo_manager())
        self.assertFalse(app.page_progress.winfo_manager())
        app._converting = True
        app._set_conversion_progress(1, 1, '음표 검출')
        self.assertEqual(app.page_progress.winfo_manager(), 'pack')
        self.assertIn('음표 검출', app.page_label.cget('text'))

    def test_empty_result_always_disables_hidden_navigation(self):
        app=self.app;app._page_sessions=self.pages;app._page_index=0
        app._update_page_controls();self.assertEqual(app.next_page_btn.cget('state'),'normal')
        app._clear_result_pages()
        self.assertEqual(app.next_page_btn.cget('state'),'disabled','새 작업에 이전 활성 상태가 남음')
        self.assertEqual(app.prev_page_btn.cget('state'),'disabled')
    def test_processing_is_visibly_disabled_and_shows_current_page(self):
        app=self.app;app._page_sessions=self.pages;app._page_index=0;app._converting=True
        app._update_page_controls()
        self.assertEqual(app.next_page_btn.cget('state'),'disabled')
        self.assertNotEqual(app.next_page_btn.cget('fg_color'),gui.ctk.ThemeManager.theme['CTkButton']['fg_color'],'처리 중 버튼도 활성 색으로 보임')
        app._set_conversion_progress(2,2)
        self.assertIn('2쪽 처리 중',app.page_label.cget('text'))
        self.assertIn('2 / 2 처리 중',app.page_label.cget('text'))
        self.assertEqual(app.page_nav.winfo_manager(),'grid')
        self.assertEqual(app.page_progress.cget('mode'),'indeterminate')
        self.assertTrue(app.page_progress._loop_running)
        before=app.page_progress._indeterminate_value
        until=time.monotonic()+.15
        while time.monotonic()<until:app.update();time.sleep(.01)
        self.assertNotEqual(app.page_progress._indeterminate_value,before,'무거운 쪽에서도 진행 막대가 움직여야 함')
        self.assertFalse(app._select_result_page(1));app.next_page_btn.invoke()
        self.assertEqual(app._page_index,0)
        app._set_conversion_progress(2,2,'결과 합치는 중…')
        self.assertIn('결과 합치는 중',app.page_label.cget('text'))
        app._converting=False;app._update_page_controls()
        self.assertFalse(app.page_progress._loop_running)
        self.assertEqual(app.next_page_btn.cget('state'),'normal')
        self.assertEqual(app.next_page_btn.cget('fg_color'),gui.ctk.ThemeManager.theme['CTkButton']['fg_color'])
        self.assertEqual(app.page_progress.get(),1)
    def test_thread_start_failure_stops_progress(self):
        source=Path(self.temp.name)/'입력.png';gui.Image.new('RGB',(80,100),'white').save(source)
        app=self.app;app._set_input(str(source));app.input_paths=(str(source),str(source))
        with patch('gui.threading.Thread',side_effect=RuntimeError('주입: 시작 실패')):app.start_convert()
        self.assertFalse(app._converting)
        self.assertFalse(app.page_progress._loop_running)
        self.assertEqual(app.next_page_btn.cget('state'),'disabled')
    def test_real_worker_keeps_pending_page_disabled_then_unlocks(self):
        app=self.app;folder=Path(self.temp.name);sources=[folder/f'입력{i}.png' for i in (1,2)]
        for path in sources:gui.Image.new('RGB',(80,100),'white').save(path)
        app._set_input(str(sources[0]));app.input_paths=tuple(map(str,sources));app.output_dir=str(folder)
        waiting=threading.Event();release=threading.Event();seen=[];errors=[];worker=[]
        show=app._show_result
        progress=app._set_conversion_progress
        def delayed_progress(number,total,phase=''):
            if number==2:
                app.after(120,lambda:progress(number,total,phase))
            else:progress(number,total,phase)
        def shown():
            seen.append(app._converting);show()
        def convert(page,suffix,source_path=None):
            worker.append(threading.current_thread())
            if suffix=='_p2':
                waiting.set()
                if not release.wait(6):raise AssertionError('두번째 쪽 대기 해제 실패')
            png=folder/f'결과{suffix}.png';js=folder/f'라벨{suffix}.json'
            gui.Image.new('RGB',(80,100),'white').save(png);js.write_text('{}')
            session=dict(source_path=source_path,original_doc={'source':{'page':0}},doc={'labels':[]},changes=[],placements=[],frame_path=source_path,image=np.full((100,80,3),255,np.uint8),png=str(png),json=str(js))
            if not app._page_sessions:app._edit_session=session
            app._page_sessions.append(session);app.labels_path=str(js)
            return str(png)
        deadline=time.monotonic()+10;checked=False;animation=None
        def poll():
            nonlocal checked,animation
            try:
                if waiting.is_set() and not checked:
                    self.assertEqual(app.next_page_btn.cget('state'),'disabled')
                    # worker 진입 Event는 after 콜백 실행을 보장하지 않는다.
                    if app._conversion_status and app._conversion_status[0]==2:
                        self.assertIn('2쪽 처리 중',app.page_label.cget('text'))
                        self.assertTrue(app.page_progress._loop_running)
                        if animation is None:
                            animation=app.page_progress._indeterminate_value
                        elif animation!=app.page_progress._indeterminate_value:
                            app.next_page_btn.invoke();self.assertEqual(app._page_index,0)
                            checked=True;release.set()
                if checked and not app._converting:
                    self.assertEqual(seen,[False],'결과가 공개될 때 이미 잠금 해제돼야 함')
                    self.assertEqual(app.next_page_btn.cget('state'),'normal')
                    app.next_page_btn.invoke();self.assertEqual(app._page_index,1)
                    self.assertFalse(app.page_progress._loop_running)
                    app.quit();return
                if time.monotonic()>deadline:raise AssertionError('변환 콜백 완료 제한시간 초과')
            except BaseException as exc:
                errors.append(exc);release.set();app.quit();return
            app.after(20,poll)
        with patch.object(app,'_convert_page',side_effect=convert),patch.object(app,'_show_result',side_effect=shown),patch.object(app,'_set_conversion_progress',side_effect=delayed_progress):
            app.after(0,app.start_convert);app.after(20,poll);app.mainloop()
        release.set()
        for thread in set(worker):thread.join(timeout=2)
        if errors:raise errors[0]
        self.assertTrue(checked)
        self.assertTrue(worker and all(t is not threading.main_thread() for t in worker))

    def test_inputs_all_formats_are_ignored(self):
        paths=['inputs/check.pdf','inputs/check.txt','inputs/nested/check.musicxml']
        proc=subprocess.run(['git','check-ignore','--no-index',*paths],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,'inputs의 비이미지 원본도 제외해야 함')
        self.assertEqual(set(proc.stdout.splitlines()),set(paths))

if __name__=='__main__':unittest.main(verbosity=2)
