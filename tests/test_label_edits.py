"""D-3 사용자 수정 기록은 원본 인식 결과를 보존하며 적용한다."""

import copy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.label_edits import EditError, apply_edits, load_edits, save_edits


def base_document():
    return {
        "schema": 1,
        "source": {"sha256": "abc", "page": 0, "width": 100, "height": 100, "dpi": 300},
        "staves": [{"id": 0, "line_ys": [40, 50, 60, 70, 80], "spacing": 10}],
        "labels": [
            {"id": "a", "staff": 0, "x": 20, "y": 80, "nx": 2.0,
             "pitch": "C4", "step": 0, "text": "도", "edited": False},
            {"id": "b", "staff": 0, "x": 40, "y": 75, "nx": 4.0,
             "pitch": "D4", "step": 1, "text": "레", "edited": False},
        ],
    }


def main():
    original = base_document()
    before = {k: original["labels"][0][k] for k in ("staff", "x", "y", "pitch", "text")}
    remove = {k: original["labels"][1][k] for k in ("staff", "x", "y", "pitch", "text")}
    edits = {
        "version": 1, "source": copy.deepcopy(original["source"]),
        "changes": [
            {"action": "set_text", "before": before, "after": {"text": "도#"}},
            {"action": "delete", "before": remove},
            {"action": "add", "after": {"staff": 0, "x": 60, "y": 70,
                                        "pitch": "E4", "text": "미"}},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "user-edits.json"
        save_edits(path, edits)
        assert load_edits(path) == edits
    changed = apply_edits(original, edits)
    assert original == base_document()
    assert [(l["x"], l["text"]) for l in changed["labels"]] == [(20, "도#"), (60, "미")]
    assert all(l["edited"] for l in changed["labels"])
    assert changed["labels"][1]["pitch"] == "E4"

    wrong_source = copy.deepcopy(edits)
    wrong_source["source"]["sha256"] = "other"
    try:
        apply_edits(original, wrong_source)
        assert False, "다른 원본은 거부해야 한다"
    except EditError:
        pass

    missing = copy.deepcopy(edits)
    missing["changes"][0]["before"]["pitch"] = "B4"
    try:
        apply_edits(original, missing)
        assert False, "짝이 없는 수정은 조용히 사라지면 안 된다"
    except EditError:
        pass


    malformed = copy.deepcopy(edits)
    malformed["changes"][0]["after"] = ["도#"]
    try:
        apply_edits(original, malformed)
        assert False, "잘못된 after는 EditError로 거부해야 한다"
    except EditError:
        pass
    assert original == base_document()


if __name__ == "__main__":
    main()
