"""실제 WAV와 Windows 재생 API, GUI 버튼에 전달되는 수정/영역 데이터를 확인한다."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gui
from modules.label_audio import audio_groups, write_wav
from tools.check_label_edit_gui import capture
import winsound


def main():
    folder=Path('docs/review/label_audio');folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp,patch('gui.base_dir',return_value=tmp),patch.object(sys,'argv',['gui.py']):
        app=gui.SheetHelperApp();app.geometry('1150x760+30+30')
        try:
            app._set_input(str(Path('sample_images/KakaoTalk_20260731_162400402.png').resolve()))
            app.output_dir=tmp;app._run_photo=False;app._run_minor=False;app._run_legend=True;app._run_key_override=''
            app.result_path=app._convert_page(0,'');app._show_result();app.update()
            before=(Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())
            session=app._edit_session
            groups,skipped=audio_groups(session['doc'],bool(app.audio_check.get()))
            assert groups and not skipped
            wav=folder/'native_api_sample.wav'
            write_wav(groups[:2],wav,duration=.06)
            winsound.PlaySound(str(wav.resolve()),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            app.after(130,lambda:winsound.PlaySound(None,0))
            app.update()
            # 대기 없는 가짜 작업자 대신 실제 버튼의 불변 입력 캡처만 검사한다.
            with patch('gui.threading.Thread') as thread:
                app._listen_labels()
                doc,skip,cancel=thread.call_args.kwargs['args']
                assert doc==session['doc'] and doc is not session['doc'] and skip is True
                thread.return_value.start.assert_called_once()
            app._audio_thread=None
            original_doc=session['doc']
            try:
                session['doc']=dict(original_doc,labels=original_doc['labels'][:2])
                app._listen_labels()
                deadline=time.monotonic()+10
                while app._audio_thread.is_alive() and time.monotonic()<deadline:
                    app.update();time.sleep(.02)
                assert not app._audio_thread.is_alive(), '재생 작업자 종료 실패'
                app._stop_listening()
            finally:
                session['doc']=original_doc
            with patch('gui.threading.Thread') as thread:
                thread.return_value.start.side_effect=RuntimeError('시작 실패')
                app._listen_labels()
                assert app._audio_thread is None
            assert (Path(app.result_path).read_bytes(),Path(app.labels_path).read_bytes())==before
            app.sidebar._parent_canvas.yview_moveto(1);app.update()
            capture(app,folder/'controls.png')
            print(f'소스 GUI {len(session["doc"]["labels"])}라벨→{len(groups)}동시음 묶음, WAV/Windows API 성공; 기본 PNG·JSON 무변경')
        finally:
            winsound.PlaySound(None,0);app.destroy()
if __name__=='__main__':main()
