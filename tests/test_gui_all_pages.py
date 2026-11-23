"""GUI 다쪽 실행은 실패한 쪽을 건너뛰고 성공한 쪽만 PDF로 묶는다."""

import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gui import SheetHelperApp


def test_all_pages_continue_after_failure():
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "score.pdf"
        with fitz.open() as doc:
            for _ in range(3):
                doc.new_page(width=100, height=120)
            doc.save(source)

        class FakeApp:
            input_path = str(source)
            output_dir = tmp
            _run_all_pages = True
            _run_input_paths = (str(source),)
            _converting = True
            result_path = None
            labels_path = None

            def __init__(self):
                self.messages = []
                self.published_states = []
                self.progress = []
                self.convert_btn = self

            def log(self, message):
                self.messages.append(message)

            def configure(self, **_kwargs):
                pass

            def after(self, _delay, callback):
                callback()

            def _show_result(self):
                self.published_states.append(self._converting)

            def _set_conversion_progress(self, number, total, phase=""):
                self.progress.append((number, total, phase))

            def _convert_page(self, page, suffix):
                if page == 1:
                    raise ValueError("측정 불가")
                path = Path(tmp) / f"score{suffix}_계이름.png"
                Image.new("RGB", (100, 120), "white").save(path)
                self.labels_path = str(Path(tmp) / f"score{suffix}_라벨.json")
                Path(self.labels_path).write_text("{}", encoding="utf-8")
                return str(path)

        app = FakeApp()
        SheetHelperApp._convert_worker(app)
        # 같은 파일을 다시 변환해도 이전 합본이 새 결과를 막으면 안 된다.
        app._converting = True
        SheetHelperApp._convert_worker(app)
        with fitz.open(Path(tmp) / "score_계이름_전체.pdf") as output:
            assert len(output) == 2
        assert "실패한 쪽: 2" in "\n".join(app.messages)
        assert app.result_path.endswith("score_p1_계이름.png")
        assert app.labels_path.endswith("score_p1_라벨.json")
        assert not app._converting
        assert app.published_states and not any(app.published_states), "변환 잠금을 해제하기 전에 완료 결과를 보여줌"


def test_images_continue_after_failure_without_fitz():
    with tempfile.TemporaryDirectory() as tmp:
        sources = [Path(tmp) / f"score{n}.png" for n in range(1, 4)]
        for source in sources:
            Image.new("RGB", (100, 120), "white").save(source)

        class FakeApp:
            input_path = str(sources[0])
            output_dir = tmp
            _run_input_paths = tuple(map(str, sources))
            _run_all_pages = False
            _converting = True
            result_path = None
            labels_path = None

            def __init__(self):
                self.messages = []
                self.published_states = []
                self.progress = []
                self.convert_btn = self

            def log(self, message):
                self.messages.append(message)

            def configure(self, **_kwargs):
                pass

            def after(self, _delay, callback):
                callback()

            def _show_result(self):
                self.published_states.append(self._converting)

            def _set_conversion_progress(self, number, total, phase=""):
                self.progress.append((number, total, phase))

            def _convert_page(self, page, suffix, source_path=None):
                assert page == 0
                if source_path == str(sources[1]):
                    raise ValueError("측정 불가")
                path = Path(tmp) / f"{Path(source_path).stem}{suffix}_계이름.png"
                index = sources.index(Path(source_path))
                size, color = (((100, 125), "red"), (None, None), ((150, 75), "blue"))[index]
                with Image.new("RGB", size, color) as image:
                    image.save(path)
                self.labels_path = str(path).replace("_계이름.png", "_라벨.json")
                Path(self.labels_path).write_text("{}", encoding="utf-8")
                return str(path)

        app = FakeApp()
        SheetHelperApp._convert_worker(app)
        app._converting = True
        SheetHelperApp._convert_worker(app)
        former = Path(tmp) / "기존 PDF 결과.pdf"
        with Image.open(Path(tmp) / "score1_p1_계이름.png") as first, Image.open(Path(tmp) / "score3_p3_계이름.png") as last:
            first.save(former, "PDF", save_all=True, append_images=[last], resolution=300.0)
        with fitz.open(Path(tmp) / "score1_계이름_전체.pdf") as output, fitz.open(former) as baseline:
            assert len(output) == len(baseline) == 2
            for index, size in enumerate(((100, 125), (150, 75))):
                page, prior = output[index], baseline[index]
                assert abs(page.rect.width - size[0] * 72 / 300) < 1e-4
                assert abs(page.rect.height - size[1] * 72 / 300) < 1e-4
                assert page.get_pixmap(dpi=300).samples == prior.get_pixmap(dpi=300).samples
        assert "실패한 순서: 2" in "\n".join(app.messages)
        assert app.result_path.endswith("score1_p1_계이름.png")
        assert app.labels_path.endswith("score1_p1_라벨.json")
        assert not app._converting
        assert app.published_states and not any(app.published_states), "변환 잠금을 해제하기 전에 완료 결과를 보여줌"


def test_incomplete_pdf_does_not_replace_previous_result():
    from gui import _save_image_pages_pdf

    with tempfile.TemporaryDirectory() as tmp:
        original = Path(tmp) / "기존 합본.pdf"
        image_path = Path(tmp) / "첫 쪽.png"
        with Image.new("RGB", (100, 125), "white") as image:
            image.save(image_path)
            image.save(original, "PDF", resolution=300.0)
        before = original.read_bytes()
        try:
            _save_image_pages_pdf([image_path, Path(tmp) / "실패한 쪽.png"], original)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("두 번째 입력 오류를 숨기면 안 됨")
        assert original.read_bytes() == before
        assert sorted(p.name for p in Path(tmp).iterdir()) == sorted([image_path.name, original.name])


def test_exe_rejects_pdf_input():
    messages = []
    app = SimpleNamespace(_converting=False, input_path="score.pdf", log=messages.append)
    with patch.object(sys, "frozen", True, create=True):
        SheetHelperApp.start_convert(app)
    assert "PDF 입력은 소스 실행에서만" in "\n".join(messages)


if __name__ == "__main__":
    test_all_pages_continue_after_failure()
    test_images_continue_after_failure_without_fitz()
    test_incomplete_pdf_does_not_replace_previous_result()
    test_exe_rejects_pdf_input()
