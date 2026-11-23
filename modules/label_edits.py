"""D-3 사용자 수정 기록을 원본 라벨 JSON과 분리해 적용한다."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from pathlib import Path

from modules.labels_io import label_id


class EditError(ValueError):
    """원본이나 수정 대상이 확실하지 않아 수정을 적용할 수 없을 때."""


_SOURCE_FIELDS = ("sha256", "page", "width", "height", "dpi")
_TARGET_FIELDS = ("staff", "x", "y", "pitch", "text")


def _edit_music(after: dict) -> dict:
    basis = after["edit_music"]
    if (not isinstance(basis, dict) or set(basis) != {"notation", "tonic"}
            or any(not isinstance(value, str) for value in basis.values())):
        raise EditError("수정 표기의 조성 정보가 올바르지 않습니다.")
    return dict(basis)


def apply_edits(doc: dict, edits: dict) -> dict:
    """별도 수정 기록을 사본에 적용한다. 대상이 모호하면 아무것도 바꾸지 않는다."""
    if not isinstance(edits, dict) or edits.get("version") != 1:
        raise EditError("지원하지 않는 사용자 수정 기록입니다.")
    source = doc.get("source") or {}
    saved = edits.get("source") or {}
    if (not isinstance(source, dict) or not isinstance(saved, dict)
            or any(k not in source or k not in saved or source[k] != saved[k]
                   for k in _SOURCE_FIELDS)):
        raise EditError("수정 기록의 원본 파일·쪽·크기가 현재 라벨과 다릅니다.")
    if (type(source["width"]) is not int or type(source["height"]) is not int
            or source["width"] <= 0 or source["height"] <= 0):
        raise EditError("원본 이미지 크기가 올바르지 않습니다.")
    if not isinstance(edits.get("changes"), list):
        raise EditError("사용자 수정 목록이 없습니다.")

    result = copy.deepcopy(doc)
    labels = result["labels"]
    staves = {s["id"]: s for s in result["staves"]}
    for change in edits["changes"]:
        if not isinstance(change, dict):
            raise EditError("사용자 수정 항목이 객체가 아닙니다.")
        action = change.get("action")
        if action in ("set_text", "delete"):
            before = change.get("before") or {}
            if not isinstance(before, dict) or any(k not in before for k in _TARGET_FIELDS):
                raise EditError("수정 대상의 좌표·음고·이전 표기가 부족합니다.")
            matches = [i for i, label in enumerate(labels)
                       if all(label.get(k) == before[k] for k in _TARGET_FIELDS)]
            if len(matches) != 1:
                raise EditError("수정할 라벨을 정확히 하나 찾지 못했습니다.")
            if action == "delete":
                del labels[matches[0]]
                continue
            after = change.get("after") or {}
            if not isinstance(after, dict):
                raise EditError("수정 후 라벨이 객체가 아닙니다.")
            new_text = after.get("text")
            if not isinstance(new_text, str) or not new_text.strip():
                raise EditError("바꿀 계이름이 비어 있습니다.")
            labels[matches[0]]["text"] = new_text
            labels[matches[0]]["edited"] = True
            labels[matches[0]].pop("edit_music", None)
            if "edit_music" in after:
                labels[matches[0]]["edit_music"] = _edit_music(after)
        elif action == "add":
            after = change.get("after") or {}
            if not isinstance(after, dict) or any(k not in after for k in _TARGET_FIELDS):
                raise EditError("추가할 라벨의 보표·좌표·음고·표기를 모두 지정해 주세요.")
            staff = staves.get(after["staff"]) if type(after["staff"]) is int else None
            x, y = after["x"], after["y"]
            if (staff is None or type(x) is not int or type(y) is not int
                    or not 0 <= x < source["width"] or not 0 <= y < source["height"]):
                raise EditError("추가할 라벨의 보표나 좌표가 원본 범위를 벗어납니다.")
            if (not isinstance(after["pitch"], str)
                    or not re.fullmatch(r"[A-G][0-9]", after["pitch"])
                    or not isinstance(after["text"], str) or not after["text"].strip()):
                raise EditError("추가할 음고(C4 등)와 계이름을 확인해 주세요.")
            if any((label["staff"], label["x"], label["y"]) == (after["staff"], x, y)
                   for label in labels):
                raise EditError("그 자리에 이미 라벨이 있습니다.")
            spacing = float(staff["spacing"])
            bottom = float(staff.get("bottom_fit") or staff["line_ys"][-1])
            step = round((bottom - y) / (spacing / 2))
            nx = round(x / spacing, 3)
            labels.append(dict(id=label_id(after["staff"], step, nx),
                               staff=after["staff"], x=x, y=y, nx=nx,
                               pitch=after["pitch"], step=step, accidental=None,
                               text=after["text"], confidence="certain", flags=[],
                               edited=True, user_created=True))
            if "edit_music" in after:
                labels[-1]["edit_music"] = _edit_music(after)
        else:
            raise EditError(f"알 수 없는 수정 동작: {action!r}")
    return result


def display_confidences(doc: dict) -> list[str]:
    """사용자 확인은 그리기에만 반영하고 원래 인식 확신도는 보존한다."""
    return ["certain" if label.get("edited") is True
            else str(label.get("confidence") or "certain") for label in doc["labels"]]


def save_edits(path: str | Path, edits: dict) -> None:
    """기존 수정 파일은 새 JSON이 완전히 쓰인 뒤 교체한다."""
    path = Path(path)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            tmp_name = stream.name
            json.dump(edits, stream, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_edits(path: str | Path) -> dict:
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise EditError(f"사용자 수정 파일을 읽지 못했습니다: {exc}") from exc
