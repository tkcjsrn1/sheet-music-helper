"""신고 ZIP에는 네 파일만 들어가고 개인 경로는 남지 않는다."""

import copy
import hashlib
import json
import sys
import tempfile
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.feedback_bundle import save_feedback_bundle


def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        source = folder / "C_Users_홍길동_악보.png"
        result = folder / "result.png"
        labels = folder / "labels.json"
        source.write_bytes(b"input")
        result.write_bytes(b"output")
        doc = {"source": {"file": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "page": 0},
               "labels": [],
               "user_edits": {"version": 1,
                              "source": {"file": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "page": 0},
                              "changes": [{"action": "set_text", "after": {"text": "도"}}]}}
        labels.write_text(json.dumps(doc), encoding="utf-8")
        original_labels = labels.read_bytes()
        (folder / "build-info.json").write_text(json.dumps({"commit": "abc123"}),
                                                 encoding="utf-8")
        target = folder / "report.zip"
        save_feedback_bundle(str(source), str(result), str(labels),
                             {"font": "custom", "custom_font_path": r"C:\Users\홍길동\font.ttf",
                              "font_size": 18}, str(target), str(folder))
        with zipfile.ZipFile(target) as bundle:
            assert set(bundle.namelist()) == {"original.png", "result.png", "labels.json", "report.json"}
            assert bundle.read("original.png") == b"input"
            assert bundle.read("result.png") == b"output"
            saved = json.loads(bundle.read("labels.json"))
            expected = copy.deepcopy(doc)
            expected["source"]["file"] = "original.png"
            expected["user_edits"]["source"]["file"] = "original.png"
            assert saved == expected, "수정 기록에도 개인 원본 파일명이 남습니다"
            assert labels.read_bytes() == original_labels, "로컬 수정 기록을 바꿨습니다"
            report = json.loads(bundle.read("report.json"))
            assert report["build_commit"] == "abc123"
            assert "custom_font_path" not in report["settings"]
            assert "홍길동" not in "".join(bundle.namelist()) + bundle.read("labels.json").decode() + bundle.read("report.json").decode()

        # 신고 저장 위치를 잘못 골라도 원본·결과·수정 JSON을 덮어쓰면 안 된다.
        originals = {path: path.read_bytes() for path in (source, result, labels)}
        protected = [str(source), str(result), str(labels)]
        if sys.platform == 'win32':
            protected.append(str(source).upper())
        for destination in protected:
            try:
                save_feedback_bundle(str(source), str(result), str(labels), {}, destination, str(folder))
                raise AssertionError('입력 파일을 신고 ZIP으로 덮어썼습니다')
            except ValueError:
                pass
            assert all(path.read_bytes() == data for path, data in originals.items())
        # 기존 신고 ZIP을 같은 이름으로 다시 저장하는 동작은 유지한다.
        save_feedback_bundle(str(source), str(result), str(labels), {}, str(target), str(folder))
        with zipfile.ZipFile(target) as bundle:
            assert bundle.read('original.png') == b'input'
            assert bundle.read('result.png') == b'output'


        # 정상 신고는 재현 가능하고, 변환 후 바뀐 원본은 저장 전에 거부한다.
        from tools.replay_report import unpack_report
        unpacked, old, _ = unpack_report(target, folder / 'replay')
        assert unpacked.read_bytes() == source.read_bytes() and old['source']['sha256'] == doc['source']['sha256']
        previous_report = target.read_bytes()
        source.write_bytes(b'changed after conversion')
        messages = []
        import gui
        app = SimpleNamespace(_converting=False, input_path=str(source), result_path=str(result),
                              labels_path=str(labels), _edit_session=None,
                              settings={}, log=messages.append)
        with patch.object(gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
             patch.object(gui, 'base_dir', return_value=str(folder)):
            gui.SheetHelperApp.save_feedback(app)
        assert len(messages) == 1 and '저장 실패' in messages[0] and '다시 변환' in messages[0], messages
        assert target.read_bytes() == previous_report and labels.read_bytes() == original_labels
        assert source.read_bytes() == b'changed after conversion' and result.read_bytes() == b'output'
        source.write_bytes(b'input')
        # 해시 없는 신고도 재현할 수 없으므로 성공 저장으로 보이면 안 된다.
        damaged = copy.deepcopy(doc)
        del damaged['source']['sha256']
        labels.write_text(json.dumps(damaged), encoding='utf-8')
        try:
            save_feedback_bundle(str(source), str(result), str(labels), {}, str(target), str(folder))
            raise AssertionError('원본 해시 없는 신고를 저장했습니다')
        except ValueError:
            pass
        finally:
            labels.write_bytes(original_labels)
        assert target.read_bytes() == previous_report

        # ZIP에 넣는 순간 원본이 바뀌어도 검증한 사본과 라벨의 해시는 같다.
        write_entry = zipfile.ZipFile.writestr
        def change_during_write(bundle, name, data, *args, **kwargs):
            if name == 'original.png':
                source.write_bytes(b'changed during ZIP save')
            return write_entry(bundle, name, data, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'writestr', new=change_during_write):
            save_feedback_bundle(str(source), str(result), str(labels), {}, str(target), str(folder))
        assert source.read_bytes() == b'changed during ZIP save'
        unpacked, old, _ = unpack_report(target, folder / 'replay-snapshot')
        assert unpacked.read_bytes() == b'input' and old['source']['sha256'] == doc['source']['sha256']
        source.write_bytes(b'input')

        # 손상된 JSON은 기존 신고/입력을 유지하며 GUI 저장 실패 안내로 돌아온다.
        import gui
        manifest = folder / 'build-info.json'
        original_manifest = manifest.read_bytes()
        original_report = target.read_bytes()
        for damaged_path, original in ((labels, original_labels), (manifest, original_manifest)):
            for damaged in (None, [], '손상'):
                damaged_path.write_text(json.dumps(damaged), encoding='utf-8')
                messages = []
                app = SimpleNamespace(_converting=False, input_path=str(source), result_path=str(result),
                                      labels_path=str(labels), _edit_session=None,
                                      settings={}, log=messages.append)
                try:
                    with patch.object(gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
                         patch.object(gui, 'base_dir', return_value=str(folder)):
                        gui.SheetHelperApp.save_feedback(app)
                    assert len(messages) == 1 and '저장 실패' in messages[0], messages
                    assert target.read_bytes() == original_report, '실패하면서 기존 신고를 바꿨습니다'
                    assert source.read_bytes() == b'input' and result.read_bytes() == b'output'
                    assert damaged_path.read_text(encoding='utf-8') == json.dumps(damaged)
                finally:
                    damaged_path.write_bytes(original)


if __name__ == "__main__":
    main()
