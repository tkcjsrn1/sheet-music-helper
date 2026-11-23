"""공간 부족 안내는 계이름 줄을 요청했다가 실패한 현재 쪽에서만 표시한다."""
import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui

class Choice:
    def __init__(self,value):self.value=value
    def get(self):return self.value

class PlacementNotice(unittest.TestCase):
    message='이 쪽은 공간이 부족해 음표 옆으로 표시합니다.'
    def app(self,requested='near',rendered='near',message=None):
        session=dict(render_options={'placement_mode':rendered} if rendered else {},
            placement_notice=self.message if message is None else message,doc={'labels':[]})
        app=SimpleNamespace(settings={'placement_mode':requested},_edit_session=session,placement_notice=Mock(),
            _converting=False,_page_sessions=[],_page_index=0,prev_page_btn=Mock(),next_page_btn=Mock(),page_nav=Mock())
        app._update_placement_notice=lambda:gui.SheetHelperApp._update_placement_notice(app)
        return app
    def update(self,app):gui.SheetHelperApp._update_page_controls(app)
    def assert_notice(self,app,shown):
        self.assertIsNotNone(app.placement_notice.configure.call_args,'안내 갱신이 호출되지 않음')
        self.assertEqual(app.placement_notice.configure.call_args.kwargs['text'],self.message if shown else '')
        (app.placement_notice.grid if shown else app.placement_notice.grid_remove).assert_called()
        (app.placement_notice.grid_remove if shown else app.placement_notice.grid).assert_not_called()
    def test_request_and_current_page_must_both_be_lanes(self):
        for requested in ('near','lanes'):
            for rendered in ('near','lanes',None):
                with self.subTest(requested=requested,rendered=rendered):
                    app=self.app(requested,rendered);before=copy.deepcopy(app._edit_session)
                    self.update(app);self.assert_notice(app,requested==rendered=='lanes')
                    self.assertEqual(app._edit_session,before)
    def test_success_and_no_page_have_no_notice(self):
        app=self.app('lanes','lanes','');self.update(app);self.assert_notice(app,False)
        app=self.app('lanes','lanes');app._edit_session=None
        self.update(app);self.assert_notice(app,False)
    def test_switching_page_clears_and_restores_only_its_own_warning(self):
        app=self.app('lanes','lanes');fallback=app._edit_session;self.update(app);self.assert_notice(app,True)
        app.placement_notice.reset_mock();app._edit_session=dict(render_options={},placement_notice=self.message)
        self.update(app);self.assert_notice(app,False)
        app.placement_notice.reset_mock();app._edit_session=fallback
        self.update(app);self.assert_notice(app,True)
    def test_changing_setting_hides_warning_without_reconverting(self):
        app=self.app('lanes','lanes');before=copy.deepcopy(app._edit_session)
        self.update(app);self.assert_notice(app,True);app.placement_notice.reset_mock()
        app.clef_menu=Choice('자동 인식 (추천)');app.notation_menu=Choice('계이름 (고정도)')
        app.placement_menu=Choice('음표 옆(기본)');app.minor_check=Choice(0);app.photo_check=Choice(0);app.legend_check=Choice(1)
        app._schedule_style_refresh=Mock()
        app._validated_key_entry=Mock(return_value=('',True,''));app._update_key_feedback=Mock();app._save_settings=Mock()
        gui.SheetHelperApp._on_setting_changed(app)
        self.assert_notice(app,False);self.assertEqual(app.settings['placement_mode'],'near')
        app._schedule_style_refresh.assert_called_once_with(immediate=True)
        self.assertEqual(app._edit_session,before)
        app.placement_notice.reset_mock();app.placement_menu.value='계이름 줄'
        gui.SheetHelperApp._on_setting_changed(app);self.assert_notice(app,True)

if __name__=='__main__':unittest.main()
