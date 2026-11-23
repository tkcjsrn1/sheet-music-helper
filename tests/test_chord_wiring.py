# -*- coding: utf-8 -*-
"""사진 모드에서는 두 번째 화음 검출 경로가 실행되지 않는다."""

import os
import sys
import contextlib
import io
import json
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import apply_chord_rescue, run_page


def main():
    pitched, accidentals, named, rows, warnings = [], [], [], [], []
    got = apply_chord_rescue(
        None, None, None, (), "", "solfege", "",
        pitched, accidentals, named, rows, warnings, enable=False)
    assert all(a is b for a, b in zip(got[:4],
                                      (pitched, accidentals, named, rows)))
    assert got[4:] == (0, 0)
    assert warnings == []

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    score = os.path.join(root, "test_scores", "chopin_nocturne_Db_6-8.pdf")
    args = SimpleNamespace(photo=False, save_source=False, no_debug=True,
                           audit=False, verify=False, clef="auto",
                           notation="solfege", key="", minor=False,
                           font_size=18, color="#dc1414", save_labels=None)
    with tempfile.TemporaryDirectory() as folder:
        with contextlib.redirect_stdout(io.StringIO()):
            run_page(args, score, 0, folder)
        with open(os.path.join(folder, "chopin_nocturne_Db_6-8_라벨.json"),
                  encoding="utf-8") as f:
            labels = json.load(f)["labels"]
    assert len(labels) == 262  # #329: 되찾음 2, DECISIONS §1-33 (#263의 260개에서 증가)
    duplicate = [l for l in labels if (l["x"], l["y"]) == (2332, 2838)]
    assert duplicate == []  # 새 C5/A4 구제 쌍 사이의 잘못된 B4가 기존 가운데 제외 규칙을 탐
    assert not any((l["x"], l["y"]) == (1972, 2809) for l in labels)
    added = {(1976, 2799): ("F5", "파"), (1976, 2824): ("D5", "레"),
             (2121, 2834): ("C5", "도"), (2197, 2834): ("C5", "도"),
             (2335, 2853): ("A4", "라")}
    for position, value in added.items():
        matches = [l for l in labels if (l["x"], l["y"]) == position]
        assert [(l["pitch"], l["text"]) for l in matches] == [value]
        assert "chord_rescue_added" in matches[0]["flags"]
    assert [(l["pitch"], l["text"]) for l in labels
            if (l["x"], l["y"]) == (2335, 2828)] == [("C5", "도#")]
    assert sum("chord_rescue_added" in l["flags"] for l in labels) == 25  # #329: 되찾음 2 중 E5만 구제 경로(+1), F5는 기본 검출; DECISIONS §1-33
    for position, value in {(1601, 2799): ("F5", "파"), (1586, 2815): ("E5", "미b")}.items():
        restored = [l for l in labels if (l["x"], l["y"]) == position]
        assert [(l["pitch"], l["text"]) for l in restored] == [value]
    assert all(l["confidence"] in {"caution", "check"} for l in labels
               if "chord_rescue_added" in l["flags"])
    print("사진 모드 우회·쇼팽 D♭ 1쪽 연결: 통과")


if __name__ == "__main__":
    main()
