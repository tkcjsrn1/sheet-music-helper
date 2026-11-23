"""범례는 악보 내용이 없는 종이 여백에만 놓는다."""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.result_legend import (add_keysig_header, add_legend,
                                   keysig_header_text, legend_font_size, LEGEND, ALTO_WARNING, alto_warning,
                                   UNKNOWN_CLEF_WARNING, clef_warnings)
from gui import FONT_LABELS
from modules.renderer import _find_korean_font



def missing_glyphs(font, text):
    """미지원 코드포인트와 같은 네모가 나오는 글자도 검사한다."""
    missing = font.getmask("\U0010ffff")
    missing_shape = (missing.size, bytes(missing))
    return [char for char in set(text) if not char.isspace()
            and (not font.getmask(char).getbbox()
                 or (font.getmask(char).size, bytes(font.getmask(char))) == missing_shape)]


def check_text_glyphs():
    texts = [LEGEND, ALTO_WARNING, UNKNOWN_CLEF_WARNING, keysig_header_text("", 0)]
    for symbol in ("♯", "♭"):
        for count in range(1, 8):
            texts.append(keysig_header_text(symbol, count, ""))
            for tonic in "ABCDEFG":
                for accidental in ("", "#", "b", "♯", "♭"):
                    texts.append(keysig_header_text(symbol, count, tonic + accidental))
    assert all("♯" not in text and "♭" not in text for text in texts)
    for path in set(FONT_LABELS.values()) | {_find_korean_font()}:
        if not Path(path).is_file():
            continue
        font = ImageFont.truetype(path, 32)
        assert missing_glyphs(font, "\U0010ffff") == ["\U0010ffff"]
        assert not missing_glyphs(font, "\n".join(texts)), path


def check_combined_decoration(folder, font, paper, expected_scans):
    from modules.result_legend import annotation_writer
    source = Image.new("RGB", (960, 720), (paper,)*3)
    ImageDraw.Draw(source).line((100, 240, 800, 240), fill="black", width=2)
    before, after = Path(folder) / f"before-{paper}.png", Path(folder) / f"after-{paper}.png"
    source.save(before)
    options = dict(symbol="♭", count=2, font_path=font, spacings=[20], first_staff_top=180)
    legend = dict(font_path=font, font_size=20)
    assert add_keysig_header(str(before), **options)
    assert add_legend(str(before), **legend)
    write, status = annotation_writer(str(after), header=options, legend=legend)
    with patch("modules.result_legend.cv2.connectedComponentsWithStats",
               wraps=cv2.connectedComponentsWithStats) as components:
        write(source)
    assert components.call_count == expected_scans
    assert status == {"header": True, "legend": True}
    with Image.open(before) as old, Image.open(after) as new:
        assert np.array_equal(np.asarray(old), np.asarray(new))


def main():
    check_text_glyphs()
    assert legend_font_size([11.3], 18) == 16
    assert legend_font_size([20.75], 18) == 23
    assert keysig_header_text("♭", 1) == "조표: b 1개로 읽음"
    assert keysig_header_text("", 0) == "조표: 없음으로 읽음"
    assert keysig_header_text("♯", 2, "D") == "조표: # 2개로 읽음 · 조성 D(사용자 지정)"
    labels = [{"flags": ["glyph_shape"]}, {"flags": ["clef_alto"], "edited": True}]
    assert alto_warning(labels) == ALTO_WARNING
    assert alto_warning([{"flags": None}, {"flags": 1}, {"flags": ["glyph_shape"]}]) == ""
    assert keysig_header_text("", 0, labels=labels) == "조표: 없음으로 읽음\n" + ALTO_WARNING
    unknown = [{"flags": ["clef_unknown"]}]
    both = labels + unknown + unknown
    assert clef_warnings(unknown) == [UNKNOWN_CLEF_WARNING]
    assert clef_warnings(both) == [ALTO_WARNING, UNKNOWN_CLEF_WARNING]
    assert clef_warnings([{"flags": None}, {"flags": 1}]) == []
    assert keysig_header_text("", 0, labels=both) == "조표: 없음으로 읽음\n" + "\n".join(clef_warnings(both))
    root = Path(__file__).resolve().parent.parent
    font = r"C:\Windows\Fonts\malgun.ttf"
    with tempfile.TemporaryDirectory() as tmp:
        check_combined_decoration(tmp, font, 255, 1)
        check_combined_decoration(tmp, font, 235, 2)
        headed = Path(tmp) / "headed.png"
        Image.new("RGB", (600, 800), "white").save(headed)
        assert add_keysig_header(str(headed), "♭", 1, font, [20],
                                 first_staff_top=180)
        before_legend = np.asarray(Image.open(headed).convert("RGB")).copy()
        assert add_legend(str(headed), font)
        after_legend = np.asarray(Image.open(headed).convert("RGB"))
        assert np.any(before_legend != after_legend)

        # 경고는 상단 여백에만 추가하고 알토가 아닌 신호는 기존 PNG 바이트 그대로 둔다.
        normal, unrelated, alto = [Path(tmp) / name for name in ("normal.png", "unrelated.png", "alto.png")]
        for target in (normal, unrelated, alto):
            Image.new("RGB", (2100, 800), "white").save(target)
        opts = dict(symbol="", count=0, font_path=font, spacings=[14], first_staff_top=176)
        assert add_keysig_header(str(normal), **opts)
        assert add_keysig_header(str(unrelated), labels=[{"flags": ["glyph_shape"]}], **opts)
        assert normal.read_bytes() == unrelated.read_bytes()
        assert add_keysig_header(str(alto), labels=labels, **opts)
        actual = np.asarray(Image.open(alto).convert("RGB"))
        changed = np.any(actual != 255, axis=2)
        assert np.any(changed) and np.where(changed)[0].max() < 176
        assert alto.read_bytes() != normal.read_bytes()
        # 두 경고를 한 머리말에 놓아 줄/악보/범례가 겹치지 않는지 확인한다.
        combined = Path(tmp) / "combined.png"
        score = Image.new("RGB", (2100, 800), "white")
        ImageDraw.Draw(score).line((100, 220, 2000, 220), fill="black", width=2)
        score.save(combined)
        assert add_keysig_header(str(combined), labels=both, **dict(opts, first_staff_top=120))
        header_pixels = np.asarray(Image.open(combined).convert("RGB")).copy()
        assert np.array_equal(header_pixels[220:], np.asarray(score)[220:])
        assert add_legend(str(combined), font)
        final = np.asarray(Image.open(combined).convert("RGB"))
        hy, hx = np.where(np.any(header_pixels[:220] != 255, axis=2))
        assert np.array_equal(header_pixels[hy.min():hy.max()+1, hx.min():hx.max()+1],
                              final[hy.min():hy.max()+1, hx.min():hx.max()+1])
        # 상단 여백이 부족하면 악보를 덮지 않고 전체 경고 배치를 생략한다.
        too_small = Path(tmp) / "too_small.png"
        score.save(too_small)
        before = too_small.read_bytes()
        assert not add_keysig_header(str(too_small), labels=both, **dict(opts, first_staff_top=50))
        assert too_small.read_bytes() == before

        for name in ("aoharu_p1.png", "chopin_Db_p1.png"):
            source = root / "docs" / "releases" / "c8504e2" / name
            target = Path(tmp) / name
            shutil.copyfile(source, target)
            before = np.asarray(Image.open(target).convert("RGB"))
            size = 16 if name.startswith("aoharu") else 21
            assert add_legend(str(target), font, size), name
            after = np.asarray(Image.open(target).convert("RGB"))
            changed = np.any(before != after, axis=2)
            assert np.any(changed), name
            ys, xs = np.where(changed)
            region = before[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            assert np.all(region.min(axis=2) >= 225), name

        black = Path(tmp) / "black.png"
        Image.new("RGB", (400, 200), "black").save(black)
        before = black.read_bytes()
        assert not add_legend(str(black), font)
        assert black.read_bytes() == before

        border = Path(tmp) / "dark_border.png"
        framed = Image.new("RGB", (600, 300), "white")
        ImageDraw.Draw(framed).rectangle((0, 0, 599, 299), outline="black", width=20)
        framed.save(border)
        before = border.read_bytes()
        assert not add_legend(str(border), font, 16, photo_input=True)
        assert border.read_bytes() == before


if __name__ == "__main__":
    main()
