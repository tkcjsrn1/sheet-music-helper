# -*- coding: utf-8 -*-
"""라벨 JSON CLI가 데이터층 안전장치를 호출하고 출력 경로를 나누는지 검증한다."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import (_confidence_values, _labels_output_path, main,
                  _pause_before_exit, _user_text, relabel)  # noqa: E402
from gui import DEFAULT_SETTINGS, SheetHelperApp, _prepare_cli_streams, _use_cli  # noqa: E402
from modules.preprocess import PhotoRejectedError, StaffNotFoundError  # noqa: E402
from user_messages import staff_count_confirmation  # noqa: E402
from modules.note_namer import (  # noqa: E402
    UnknownNoteNameError, normalize_key_override, resolve_tonic,
)


class KeyOverrideValidationTests(unittest.TestCase):
    def test_accepts_documented_key_formats(self) -> None:
        expected = {
            "D": "D",
            "Bb": "Bb",
            "B♭": "Bb",
            "F#": "F#",
            "F♯": "F#",
            "": "",
            "   ": "",
        }
        for raw, normalized in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalized, normalize_key_override(raw))

    def test_rejects_trailing_junk_and_unknown_letters(self) -> None:
        for raw in ("d", "Dfoo", "H", "가나다", "D#b", "D##", "Dbx",
                    "Fb", " D ", "D foo"):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(UnknownNoteNameError, "알 수 없는 조성"):
                    normalize_key_override(raw)

    def test_resolve_tonic_validates_before_using_override(self) -> None:
        with self.assertRaises(UnknownNoteNameError):
            resolve_tonic("♯", 1, "Dfoo")
        with self.assertRaisesRegex(UnknownNoteNameError, "단조"):
            resolve_tonic("♯", 1, "d")
        self.assertEqual("F", resolve_tonic("♯", 1, "D", minor=True))
        with self.assertRaises(UnknownNoteNameError):
            resolve_tonic("♯", 1, "Db", minor=True)
        self.assertEqual("C#", resolve_tonic("♯", 1, "A#", minor=True))

    def test_cli_rejects_invalid_key_before_creating_output(self) -> None:
        args = SimpleNamespace(input="missing.png", key="Dfoo", minor=False,
                               output_dir="output")
        with (patch("main.parse_args", return_value=args),
              patch("main.os.makedirs") as mkdir,
              patch("builtins.print") as printed):
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(1, stopped.exception.code)
        mkdir.assert_not_called()
        self.assertIn("예: D, Bb, F#", str(printed.call_args))

    def test_gui_marks_invalid_key_with_red_border_and_hint(self) -> None:
        class FakeWidget:
            def __init__(self, value=""):
                self.value = value
                self.options = {}

            def get(self):
                return self.value

            def configure(self, **kwargs):
                self.options.update(kwargs)

        app = SheetHelperApp.__new__(SheetHelperApp)
        app.key_entry = FakeWidget("Dfoo")
        app.minor_check = FakeWidget(False)
        app.key_feedback = FakeWidget()
        app._key_border_color = "normal-border"

        self.assertFalse(app._update_key_feedback())
        self.assertEqual(("#b3261e", "#ff766f"), app.key_entry.options["border_color"])
        self.assertIn("예: D, Bb, F#", app.key_feedback.options["text"])
        app._converting = False
        app.input_path = "score.png"
        app.log = lambda _message: None
        with patch("gui.threading.Thread") as worker:
            app.start_convert()
        worker.assert_not_called()

        app.key_entry.value = "d"
        self.assertFalse(app._update_key_feedback())
        self.assertIn("단조", app.key_feedback.options["text"])

        app.key_entry.value = "D"
        self.assertTrue(app._update_key_feedback())
        self.assertEqual("normal-border", app.key_entry.options["border_color"])
        self.assertEqual("", app.key_feedback.options["text"])


class RelabelSourceGuardTests(unittest.TestCase):
    def test_relabel_stops_when_data_layer_rejects_source(self) -> None:
        class FakeImage:
            shape = (700, 1000, 3)

        doc = {"source": {"page": 0}, "staves": [], "labels": []}
        args = SimpleNamespace(
            relabel="labels.json", font_size=18, color="#dc1414",
        )
        with (patch("modules.labels_io.load_labels", return_value=doc),
              patch("modules.labels_io.check_dpi", return_value=None),
              patch("modules.labels_io.check_source", return_value="다른 원본입니다") as guard,
              patch("modules.preprocess.load_image", return_value=FakeImage())):
            with self.assertRaises(SystemExit) as stopped:
                relabel(args, "wrong.png", "output")

        self.assertEqual(1, stopped.exception.code)
        guard.assert_called_once_with(doc, "wrong.png", (700, 1000, 3), 0)

    def test_relabel_passes_saved_confidences_to_renderer(self) -> None:
        class FakeImage:
            shape = (700, 1000, 3)

        doc = {
            "source": {"page": 0},
            "staves": [],
            "labels": [
                {"confidence": "check", "flags": ["clef_unknown"]},
                {"confidence": "future-value", "flags": ["clef_alto"]},
                {"confidence": "check", "edited": True},
            ],
        }
        args = SimpleNamespace(
            relabel="labels.json", font_size=18, color="#dc1414",
        )
        notes = [(object(), "도"), (object(), "레"), (object(), "미")]
        with (patch("modules.labels_io.load_labels", return_value=doc),
              patch("modules.labels_io.check_dpi", return_value=None),
              patch("modules.labels_io.check_source", return_value=None),
              patch("modules.labels_io.document_staves", return_value=[]),
              patch("modules.labels_io.document_notes", return_value=notes),
              patch("modules.preprocess.load_image", return_value=FakeImage()),
              patch("main.annotation_writer", return_value=(None, {"header": True})),
              patch("main.render_solfege_on_image") as render,
              patch("sys.stdout", new_callable=io.StringIO) as output):
            relabel(args, "score.png", "output")

        self.assertEqual(
            ["check", "future-value", "certain"],
            render.call_args.kwargs["confidences"],
        )
        self.assertEqual("check", doc["labels"][2]["confidence"])
        from modules.result_legend import ALTO_WARNING, UNKNOWN_CLEF_WARNING
        self.assertIn("[주의] " + ALTO_WARNING, output.getvalue())
        self.assertIn("[주의] " + UNKNOWN_CLEF_WARNING, output.getvalue())


class SharedPostprocessingTests(unittest.TestCase):
    def test_head_exclusions_keep_beam_then_ledger_order(self):
        from main import _filter_noteheads
        from unittest.mock import Mock
        result = object()
        stage = Mock()
        stage.beam.return_value = ([2, 3], [1])
        stage.ledger.return_value = ([3], [2])
        with (patch("modules.verify.drop_beam_ghosts", stage.beam),
              patch("modules.verify.drop_offstaff_ghosts", stage.ledger)):
            self.assertEqual(_filter_noteheads(result, [1, 2, 3]), ([3], [1], [2]))
        self.assertEqual([(call[0], call.args) for call in stage.mock_calls],
                         [("beam", (result, [1, 2, 3])), ("ledger", (result, [2, 3]))])


class ConfidenceValueTests(unittest.TestCase):
    def test_diagnostics_follow_note_order(self) -> None:
        notes = [
            (SimpleNamespace(staff_index=1, x=20, y=30), "도"),
            (SimpleNamespace(staff_index=0, x=10, y=15), "레"),
            (SimpleNamespace(staff_index=2, x=40, y=50), "미"),
        ]
        rows = [
            {"staff": 0, "x": 10, "y": 15, "vertical_clear": False},
            {"staff": 1, "x": 20, "y": 30, "weak_ink": 0.20},
        ]
        self.assertEqual(
            ["check", "caution", "certain"],
            _confidence_values(rows, notes),
        )


class ExeEntryPointTests(unittest.TestCase):
    def test_selftest_writes_png_and_json_and_returns_status(self) -> None:
        root = Path(__file__).resolve().parent.parent
        source = root / "sample_images" / "KakaoTalk_20260731_162400402.png"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "selftest"
            done = subprocess.run(
                [sys.executable, str(root / "gui.py"), "--selftest", str(source), str(output)],
                cwd=root, capture_output=True, timeout=120,
            )
            self.assertEqual(0, done.returncode, done.stderr.decode("utf-8", "replace"))
            base = source.stem
            self.assertTrue((output / f"{base}_계이름.png").is_file())
            labels = json.loads((output / f"{base}_라벨.json").read_text(encoding="utf-8"))
            self.assertGreater(len(labels["labels"]), 0)

            failed = subprocess.run(
                [sys.executable, str(root / "gui.py"), "--selftest", "없는_악보.png", str(output)],
                cwd=root, capture_output=True, timeout=30,
            )
            self.assertNotEqual(0, failed.returncode)

    def test_windowed_cli_reconfigures_cp949_output(self) -> None:
        out_bytes = io.BytesIO()
        err_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(out_bytes, encoding="cp949")
        stderr = io.TextIOWrapper(err_bytes, encoding="cp949")
        with patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
            _prepare_cli_streams()
            print("♯·♭")
            print("♯·♭", file=sys.stderr)
            stdout.flush()
            stderr.flush()
        self.assertEqual("♯·♭", out_bytes.getvalue().decode("utf-8").strip())
        self.assertEqual("♯·♭", err_bytes.getvalue().decode("utf-8").strip())

    def test_single_dropped_file_keeps_gui(self) -> None:
        self.assertFalse(_use_cli(["score.png"]))

    def test_cli_options_dispatch_to_main(self) -> None:
        self.assertTrue(_use_cli(["score.png", "--save-labels", "labels.json"]))
        self.assertTrue(_use_cli(["score.png", "--relabel", "labels.json"]))
        self.assertTrue(_use_cli(["--help"]))

    def test_windowed_cli_does_not_wait_for_hidden_input(self) -> None:
        fake_stdin = SimpleNamespace(isatty=lambda: False)
        with (patch.object(sys, "frozen", True, create=True),
              patch.object(sys, "stdin", fake_stdin),
              patch("builtins.input") as prompt):
            _pause_before_exit()
        prompt.assert_not_called()

    def test_closed_terminal_input_does_not_fail_after_conversion(self) -> None:
        # exe는 isatty가 참이어도 부모가 입력을 닫으면 EOF를 받을 수 있다.
        with (patch.object(sys, "frozen", True, create=True),
              patch.object(sys, "stdin", SimpleNamespace(isatty=lambda: True)),
              patch("builtins.input", side_effect=EOFError)):
            _pause_before_exit()

    def test_user_message_uses_plain_staff_wording(self) -> None:
        self.assertEqual(
            "악보 줄마다 확인한 뒤 악보 줄 8개를 찾았습니다",
            _user_text("보표별 확인한 뒤 보표 8개를 찾았습니다"),
        )

    def test_staff_count_confirmation_asks_for_source_check(self) -> None:
        self.assertEqual(
            "악보 줄 1개를 찾았습니다. 원본 악보의 줄 수와 맞는지 확인해 주세요.",
            staff_count_confirmation(1),
        )


class LabelOutputPathTests(unittest.TestCase):
    def test_default_path_uses_page_specific_base_name(self) -> None:
        self.assertEqual(
            os.path.join("out", "score_p2_라벨.json"),
            _labels_output_path(None, "out", "score_p2", "_p2"),
        )

    def test_explicit_path_gets_page_suffix(self) -> None:
        self.assertEqual(
            os.path.join("chosen", "labels_p2.json"),
            _labels_output_path(
                os.path.join("chosen", "labels.json"),
                "out", "score_p2", "_p2",
            ),
        )

    def test_explicit_single_page_path_is_unchanged(self) -> None:
        path = os.path.join("chosen", "labels.json")
        self.assertEqual(path, _labels_output_path(path, "out", "score", ""))


class GuiPhotoModeTests(unittest.TestCase):
    def test_checkbox_value_is_used_for_each_conversion(self) -> None:
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                app = SimpleNamespace(
                    _converting=False, input_path="score.png",
                    _validated_key_entry=lambda: ("", True, ""),
                    settings=dict(DEFAULT_SETTINGS), output_dir="output",
                    page_entry=SimpleNamespace(get=lambda: "1"),
                    clef_menu=SimpleNamespace(get=lambda: "자동 인식 (추천)"),
                    notation_menu=SimpleNamespace(get=lambda: "계이름 (고정도)"),
                    placement_menu=SimpleNamespace(get=lambda: "음표 옆(기본)"),
                    _current_font_path=lambda: "font.ttf",
                    minor_check=SimpleNamespace(get=lambda: 0),
                    photo_check=SimpleNamespace(get=lambda: int(enabled)),
                    legend_check=SimpleNamespace(get=lambda: 1),
                    all_pages_check=SimpleNamespace(get=lambda: 0),
                    _convert_worker=lambda: None,
                    _stop_listening=MagicMock(),
                    _close_label_editor=lambda: None,
                    _clear_result_pages=MagicMock(),
                    _set_conversion_progress=MagicMock(),
                    edit_btn=MagicMock(),
                    convert_btn=MagicMock(),
                )
                with patch("gui.threading.Thread"):
                    SheetHelperApp.start_convert(app)
                self.assertIs(app._run_photo, enabled)
                app._clear_result_pages.assert_called_once()
                app._stop_listening.assert_called_once()

    def test_default_off_keeps_original_preprocess_call(self) -> None:
        self.assertIs(DEFAULT_SETTINGS["photo"], False)
        self._run_worker(False, StaffNotFoundError("오선 없음"), {"pdf_page": 0})

    def test_on_rejection_shows_retake_message(self) -> None:
        logs = self._run_worker(True, PhotoRejectedError("기울기"),
                                {"pdf_page": 0, "photo": True})
        self.assertIn("스캐너·복사기·거치대로 정면에서 다시 찍어 주세요",
                      "\n".join(logs))

    def _run_worker(self, photo, error, expected_kwargs):
        logs = []
        with tempfile.TemporaryDirectory() as output_dir:
            app = SimpleNamespace(
                input_path="score.png", output_dir=output_dir,
                settings={"font_size": 18, "text_color": "#dc1414"},
                _run_photo=photo, _current_font_path=lambda: "font.ttf",
                _run_all_pages=False,
                clef_menu=SimpleNamespace(get=lambda: "자동 인식 (추천)"),
                page_entry=SimpleNamespace(get=lambda: "1"),
                log=logs.append, after=lambda *_args: None,
                convert_btn=MagicMock(),
            )
            app._convert_page = lambda page, suffix: SheetHelperApp._convert_page(app, page, suffix)
            with patch("gui.preprocess", side_effect=error) as called:
                SheetHelperApp._convert_worker(app)
            called.assert_called_once_with("score.png", **expected_kwargs)
        return logs


if __name__ == "__main__":
    unittest.main(verbosity=2)
