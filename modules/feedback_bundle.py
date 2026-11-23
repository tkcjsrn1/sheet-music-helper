"""문제 신고에 필요한 파일만 개인 경로 없이 ZIP으로 묶는다."""

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path


SAFE_SETTINGS = ("clef", "notation", "key", "minor", "photo", "font",
                 "font_size", "text_color", "appearance")


def save_feedback_bundle(input_path: str, result_path: str, labels_path: str,
                         settings: dict, output_path: str, app_dir: str) -> None:
    source = Path(input_path)
    result = Path(result_path)
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    if not isinstance(labels, dict):
        raise ValueError("라벨 JSON 형식이 올바르지 않습니다.")
    # 검사한 원본 사본을 그대로 묶어 저장 중 파일이 바뀌어도 해시를 맞춘다.
    original_bytes = source.read_bytes()
    origin = labels.get("source")
    if not isinstance(origin, dict) or origin.get("sha256") != hashlib.sha256(original_bytes).hexdigest():
        raise ValueError("원본 악보와 라벨 JSON이 일치하지 않습니다. 원본을 다시 변환한 뒤 신고용 파일을 저장해 주세요.")
    original_name = "original" + source.suffix.lower()
    # 수정 기록에도 원본명이 들어가므로 두 source를 같은 익명 이름으로 맞춘다.
    sources = [labels.get("source")]
    edits = labels.get("user_edits")
    if isinstance(edits, dict):
        sources.append(edits.get("source"))
    for origin in sources:
        if isinstance(origin, dict):
            origin["file"] = original_name

    manifest = Path(app_dir) / "build-info.json"
    if manifest.is_file():
        build_info = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(build_info, dict):
            raise ValueError("빌드 정보 JSON 형식이 올바르지 않습니다.")
        commit = build_info.get("commit", "unknown")
    else:
        try:
            found = subprocess.run(["git", "rev-parse", "HEAD"], cwd=app_dir,
                                   capture_output=True, text=True, check=False)
            commit = found.stdout.strip() if found.returncode == 0 else "unknown"
        except OSError:
            commit = "unknown"
    info = {"version": "1.0.0", "build_commit": commit,
            "settings": {key: settings[key] for key in SAFE_SETTINGS if key in settings}}

    target = Path(output_path)
    if target.resolve() in {source.resolve(), result.resolve(), Path(labels_path).resolve()}:
        raise ValueError('원본·결과 이미지·라벨 JSON에 신고 ZIP을 덮어쓸 수 없습니다. 다른 파일 이름으로 저장해 주세요.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".zip", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(original_name, original_bytes)
            bundle.write(result, "result.png")
            bundle.writestr("labels.json", json.dumps(labels, ensure_ascii=False, indent=2))
            bundle.writestr("report.json", json.dumps(info, ensure_ascii=False, indent=2))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
