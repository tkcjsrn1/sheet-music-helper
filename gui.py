# -*- coding: utf-8 -*-
"""
악보헬퍼 GUI (customtkinter)

- 파일 선택(이미지/PDF) 또는 exe 아이콘 위로 드래그 앤 드롭(인자 전달) 지원
- 음자리표 자동 인식(높은/낮은 혼합 악보 지원), 조표(♯/♭) 자동 반영
- 계이름 표기 폰트/크기/색상 설정 (settings.json으로 저장되어 다음 실행에도 유지)
- 라이트/다크 테마 전환
- 변환 진행 로그 + 결과 이미지 미리보기

실행: python gui.py [악보파일경로]
"""

import filecmp
import json
import queue
import re
import os
import shutil
import sys
import threading
import time
import tempfile
import uuid
import traceback
from dataclasses import dataclass
from math import ceil, floor

import customtkinter as ctk
from tkinter import colorchooser, filedialog, Canvas, Listbox, Menu, TclError
from PIL import Image, ImageGrab, ImageTk

from modules.engine_mask_cache import clear_mask_cache, with_mask_cache
from modules.preprocess import preprocess, SheetMusicImageError, StaffNotFoundError, PhotoRejectedError
from modules.notehead_detect import detect_noteheads, NoteheadDetectionError
from modules.clef_keysig import analyze_staves
from modules.pitch_calculator import calculate_pitches, UnsupportedClefError
from modules.note_namer import (
    UnknownNoteNameError, normalize_key_override, to_solfege_batch,
)
from modules.renderer import render_solfege_on_image, RendererError
from user_messages import staff_count_confirmation, conversion_failure_message, label_review_reason

UI_COLORS = {
    "background": ("#F3F5F8", "#11141A"),
    "surface": ("#FFFFFF", "#1B202A"),
    "border": ("#E2E8F0", "#2A3140"),
    "canvas": ("#E8EDF3", "#0D1016"),
    "primary": ("#2563EB", "#3B82F6"),
    "primary_hover": ("#1D4ED8", "#2563EB"),
    "primary_disabled_text": ("#DBEAFE", "#BFDBFE"),
    "secondary": ("#FFFFFF", "#232A36"),
    "secondary_hover": ("#EEF2F7", "#2E3747"),
    "button_border": ("#CBD5E1", "#384254"),
    "text": ("#1E293B", "#E2E8F0"),
    "option_button": ("#E2E8F0", "#334155"),
    "option_hover": ("#CBD5E1", "#475569"),
    "option_text": ("#0F172A", "#F1F5F9"),
    "ghost_hover": ("#E2E8F0", "#252C38"),
    "muted": ("#475569", "#94A3B8"),
    "danger": ("#FEE2E2", "#3F1D24"),
    "danger_hover": ("#FECACA", "#5B2330"),
    "danger_text": ("#B91C1C", "#FCA5A5"),
    "amber": ("#FEF3C7", "#3A260D"),
    "amber_text": ("#92400E", "#FCD34D"),
    "blue": ("#EFF6FF", "#172554"),
    "compare_active": ("#DBEAFE", "#1E3A5F"),
    "compare_text": ("#1D4ED8", "#BFDBFE"),
}


def _configure_ui_theme() -> None:
    """기본 위젯은 중립색으로 두고 주요 동작만 별도로 강조한다."""
    ctk.set_default_color_theme("blue")
    theme = ctk.ThemeManager.theme
    for widget in ("CTk", "CTkToplevel"):
        theme[widget]["fg_color"] = UI_COLORS["background"]
    theme["CTkFrame"].update(fg_color=UI_COLORS["surface"],
        top_fg_color=UI_COLORS["surface"], border_color=UI_COLORS["border"], corner_radius=10)
    theme["CTkLabel"]["text_color"] = UI_COLORS["text"]
    theme["CTkButton"].update(fg_color=UI_COLORS["secondary"],
        hover_color=UI_COLORS["secondary_hover"], border_width=1,
        border_color=UI_COLORS["button_border"], text_color=UI_COLORS["text"],
        text_color_disabled=UI_COLORS["muted"], corner_radius=7)
    theme["CTkOptionMenu"].update(fg_color=UI_COLORS["secondary"],
        button_color=UI_COLORS["option_button"], button_hover_color=UI_COLORS["option_hover"],
        text_color=UI_COLORS["option_text"])
    theme["DropdownMenu"].update(fg_color=UI_COLORS["surface"],
        hover_color=UI_COLORS["secondary_hover"], text_color=UI_COLORS["text"])
    theme["CTkEntry"].update(fg_color=UI_COLORS["secondary"],
        border_color=UI_COLORS["button_border"], text_color=UI_COLORS["text"],
        placeholder_text_color=UI_COLORS["muted"])
    theme["CTkTextbox"].update(fg_color=UI_COLORS["background"],
        border_color=UI_COLORS["border"], text_color=UI_COLORS["text"])
    theme["CTkCheckBox"].update(fg_color=UI_COLORS["muted"], hover_color=UI_COLORS["option_hover"],
        border_color=UI_COLORS["button_border"], text_color=UI_COLORS["text"])
    theme["CTkSlider"].update(progress_color=UI_COLORS["muted"],
        button_color=UI_COLORS["muted"], button_hover_color=UI_COLORS["text"],
        fg_color=UI_COLORS["border"])
    theme["CTkProgressBar"].update(progress_color=UI_COLORS["primary"], fg_color=UI_COLORS["border"])
    theme["CTkScrollbar"].update(button_color=UI_COLORS["button_border"],
        button_hover_color=UI_COLORS["muted"])
    theme["CTkFont"].update(family="맑은 고딕", size=12)


CLEF_LABELS = {
    "자동 인식 (추천)": "auto",
    "모두 높은음자리표": "treble",
    "모두 낮은음자리표": "bass",
}

FONT_LABELS = {
    "맑은 고딕": r"C:\Windows\Fonts\malgun.ttf",
    "맑은 고딕 굵게": r"C:\Windows\Fonts\malgunbd.ttf",
    "굴림": r"C:\Windows\Fonts\gulim.ttc",
    "바탕": r"C:\Windows\Fonts\batang.ttc",
}
CUSTOM_FONT_OPTION = "직접 선택 (내 글꼴 파일)..."

QUICK_SOLFEGE = '도레미파솔라시'
QUICK_LETTERS = 'CDEFGAB'

PLACEMENT_LABELS = {"음표 옆(기본)": "near", "계이름 줄": "lanes"}

NOTATION_LABELS = {
    "계이름 (고정도)": "solfege-fixed",
    "계이름 (이동도)": "solfege-movable",
    "영문 (C D E)": "letter",
}
# 옛 settings.json 호환: 예전 이름으로 저장된 값도 그대로 열리게 한다
LEGACY_NOTATION_LABELS = {"계이름 (도레미)": "계이름 (고정도)"}

IMAGE_FILETYPES = [
    ("악보 이미지", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
]
_IMAGE_EXTENSIONS = {pattern[1:] for _, patterns in IMAGE_FILETYPES for pattern in patterns.split()}
_PDF_EXE_MESSAGE = "⚠ PDF 입력은 소스 실행에서만 지원합니다. exe에서는 이미지로 저장해 선택해 주세요."
SOURCE_FILETYPES = [
    ("악보 파일", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf"),
    *IMAGE_FILETYPES,
    ("PDF", "*.pdf"),
    ("모든 파일", "*.*"),
]


def _filetypes_for_runtime(frozen: bool | None = None) -> list[tuple[str, str]]:
    """배포 exe에서는 실제로 처리할 수 있는 이미지 형식만 보여준다."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return IMAGE_FILETYPES if frozen else SOURCE_FILETYPES

_PREVIEW_MARGIN = 32
_PREVIEW_REDRAW_MS = 40


def _resize_preview_tile(source, size, bounds, resample, *, original_bgr=None):
    """전체 확대와 같은 화소 격자를 유지하며 필요한 원본 사각형만 읽는다."""
    left, top, right, bottom = bounds
    width, height = size
    x0, x1 = (x * source.width / width for x in (left, right))
    y0, y1 = (y * source.height / height for y in (top, bottom))
    # LANCZOS가 전체 확대와 같은 주변 화소를 보게 한다.
    pad_x = ceil(3 * max(1, source.width / width))
    pad_y = ceil(3 * max(1, source.height / height))
    crop_left = max(0, floor(x0) - pad_x)
    crop_top = max(0, floor(y0) - pad_y)
    crop_right = min(source.width, ceil(x1) + pad_x)
    crop_bottom = min(source.height, ceil(y1) + pad_y)
    box = (x0 - crop_left, y0 - crop_top, x1 - crop_left, y1 - crop_top)
    if original_bgr is None:
        crop = source.crop((crop_left, crop_top, crop_right, crop_bottom))
    else:
        crop = Image.fromarray(original_bgr[crop_top:crop_bottom, crop_left:crop_right, ::-1])
    with crop:
        return crop.resize((right - left, bottom - top), resample, box=box)


AUDIO_HIGHLIGHT_DELAY_MS = 220
_AUDIO_ACTIVE_POLL_MS = 15
_AUDIO_IDLE_POLL_MS = 80
_AUDIO_DELAY_MAX_MS = 600
_AUDIO_DELAY_STEP_MS = 10


def _valid_audio_delay(value) -> int:
    if type(value) is int and 0 <= value <= _AUDIO_DELAY_MAX_MS and value % _AUDIO_DELAY_STEP_MS == 0:
        return value
    return AUDIO_HIGHLIGHT_DELAY_MS


DEFAULT_SETTINGS = {
    "audio_highlight_delay_ms": AUDIO_HIGHLIGHT_DELAY_MS,
    "clef": "자동 인식 (추천)",
    "notation": "계이름 (고정도)",
    # 이동도 계이름에서 '도'로 삼을 으뜸음. 비워 두면 조표를 보고 장조로 판단한다.
    "key": "",
    "minor": False,
    "photo": False,
    "legend": True,
    "placement_mode": "near",
    "font": "맑은 고딕",
    "custom_font_path": "",
    "font_size": 18,
    "text_color": "#dc1414",
    "appearance": "light",
    "last_input_dir": "",
}


def base_dir() -> str:
    """exe로 패키징된 경우 exe가 있는 폴더, 아니면 이 스크립트가 있는 폴더."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel: str) -> str:
    """PyInstaller 번들 내부(asset) 리소스 경로를 해석한다."""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, rel)


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass(frozen=True)
class _PreviousDropResult:
    state: dict
    file_text: str
    region_selected: bool


@dataclass(frozen=True)
class _ConversionRequest:
    """메인 스레드에서 확정한 입력·표기 설정. 작업 중 화면 변경과 분리한다."""
    input_paths: tuple
    output_dir: str
    page: int
    all_pages: bool
    clef: str
    notation: str
    key: str
    minor: bool
    photo: bool
    legend: bool
    font_path: str
    font_size: int
    text_color: tuple
    report_settings: tuple
    previous_drop: _PreviousDropResult | None = None


def _recognition_summary(session: dict) -> str:
    from collections import Counter
    from modules.label_edits import display_confidences

    doc = session.get('doc', {'labels': []})
    labels = doc['labels']
    counts = Counter(display_confidences(doc))
    caution, check = counts['caution'], counts['check']
    text = f'라벨 {len(labels)} · 확실 {len(labels)-caution-check} · 확인 필요 {check} · 주의 {caution}'
    excluded = session.get('recognition_exclusions')
    if excluded is None:
        return text + ' · 제외 기록 없음'
    total = sum(excluded.values())
    details = [f'{caption} {excluded[key]}' for key, caption in
               (('beam', '빔'), ('offstaff', '오선 밖'), ('accidental', '임시표'), ('chord', '화음'))
               if excluded.get(key)]
    return text + f' · 인식 제외 {total}' + (f" ({', '.join(details)})" if details else '')


def _render_edit_document(session: dict, doc: dict, png: str):
    """저장·재열기에서 같은 렌더링 설정을 사용한다."""
    from modules.label_edits import display_confidences
    from modules.labels_io import document_notes
    from modules.result_legend import annotation_writer
    status={}
    options=dict(session['render_options'])
    if options.get('placement_mode')=='lanes':options['layout_status']=status
    header = dict(session['header_options'], labels=doc['labels']) if session['header_options'] else None
    writer, _ = annotation_writer(png, header=header, legend=session['legend_options'] or None)
    placements = render_solfege_on_image(session['image'], document_notes(doc), png,
        confidences=display_confidences(doc), image_writer=writer, **options)
    session['placement_notice']=status.get('message','')
    return placements


def _relabel_document(doc: dict, notation: str, key_override: str, minor: bool) -> dict:
    from modules.labels_io import document_notes
    from modules.note_namer import resolve_tonic

    original_music = doc['music']
    minor = bool(key_override and minor)
    movable = notation == 'solfege-movable'
    tonic = (resolve_tonic(original_music.get('key_symbol', ''), original_music.get('key_count', 0),
                           key_override, minor) if movable else '')
    music = dict(original_music, notation=notation, key_override=key_override,
                 minor=minor, is_minor=minor, tonic=tonic)
    labels = []
    groups = {}
    for source, (note, _text) in zip(doc['labels'], document_notes(doc)):
        label = dict(source)
        local = source.get('key')
        context = local or music
        symbol = context.get('key_symbol', '')
        letters = tuple(context.get('key_letters', ()))
        if local is not None:
            local_tonic = resolve_tonic(symbol, len(letters)) if movable and not key_override else tonic
            label['key'] = dict(local, tonic=local_tonic)
        else:
            local_tonic = tonic
        groups.setdefault((letters, symbol, local_tonic), []).append((label, note))
        labels.append(label)
    for (letters, symbol, local_tonic), group in groups.items():
        named = to_solfege_batch([note for _, note in group], letters, symbol,
            [label.get('accidental') or '' for label, _ in group], notation, tonic=local_tonic)
        for (label, _), (_, text) in zip(group, named):
            label['text'] = text
    return dict(doc, music=music, labels=labels)


def _relabel_changes(original: dict, relabeled: dict, changes: list) -> list:
    fields = ('staff', 'x', 'y', 'pitch')
    first_text = {}
    local_keys = {}
    for old, new in zip(original['labels'], relabeled['labels']):
        location = tuple(old[field] for field in fields)
        first_text[location + (old['text'],)] = new['text']
        local_keys[location] = old.get('key') or {}
    revised = []
    for change in changes:
        item = dict(change)
        before = change.get('before')
        audio = original['music']
        if before is not None:
            location = tuple(before[field] for field in fields)
            text = first_text.pop(location + (before['text'],), before['text'])
            item['before'] = dict(before, text=text)
            audio = {**audio, **local_keys.get(location, {})}
            if change['action'] == 'delete':
                local_keys.pop(location, None)
        if 'after' in change:
            after = dict(change['after'])
            after.setdefault('edit_music', dict(notation=audio.get('notation', ''),
                                                tonic=audio.get('tonic', '')))
            item['after'] = after
        revised.append(item)
    return revised


def _apply_document_edits(original: dict, changes: list, region) -> tuple[dict, dict]:
    from modules.label_edits import apply_edits
    from modules.label_region import filter_region

    record = dict(version=1, description='사용자 수정', source=original['source'], changes=changes)
    doc = apply_edits(original, record)
    if changes:
        doc['user_edits'] = record
    if region is not None:
        doc = filter_region(doc, *region)
        doc['selected_region'] = list(region)
    return doc, record


def _restyle_edit_session(session: dict, parent: str, *, font_path: str, font_size: int,
                          text_color: tuple, placement_mode: str, legend: bool,
                          notation_state: tuple[str, str, bool] | None = None) -> dict | None:
    """원래 인식·편집 기록을 보존하며 새 표기의 결과와 되돌리기 기준을 준비한다."""
    from modules.result_legend import legend_font_size

    style = dict(font_path=font_path, font_size=font_size, text_color=text_color,
                 text_offset_y=max(14, font_size + 4))
    options = session['render_options']
    legend = legend and not session.get('report_settings', {}).get('photo', False)
    renotate = False
    if notation_state is not None:
        notation, key_override, minor = notation_state
        minor = bool(key_override and minor)
        music = session['original_doc']['music']
        old_key = music.get('key_override', session.get('report_settings', {}).get('key', ''))
        renotate = ((notation, key_override, minor)
                    != (music.get('notation', 'solfege-fixed'), old_key,
                        bool(music.get('is_minor', music.get('minor', False)) and old_key)))
    if (not renotate and all(options.get(key) == value for key, value in style.items())
            and options.get('placement_mode', 'near') == placement_mode
            and bool(session['legend_options']) == legend):
        return None
    updated = dict(session, render_options={**options, **style, 'placement_mode': placement_mode})
    updated.setdefault('_style_saved_png', session['png'])
    if session['header_options'] is not None:
        updated['header_options'] = dict(session['header_options'], font_path=font_path,
                                         setting_size=font_size)
    spacings = options.get('staff_spacings', {}).values()
    updated['legend_options'] = (dict(font_path=font_path, font_size=legend_font_size(spacings, font_size))
                                 if legend else None)

    if renotate:
        original_doc = _relabel_document(session['original_doc'], notation, key_override, minor)
        changes = _relabel_changes(session['original_doc'], original_doc, session['changes'])
        doc = (_apply_document_edits(original_doc, changes, session.get('region'))[0]
               if changes or session.get('region') is not None else original_doc)
        updated.update(original_doc=original_doc, changes=changes, doc=doc)
        if updated['header_options'] is not None:
            updated['header_options']['user_key'] = key_override if notation == 'solfege-movable' else ''

    folder = tempfile.mkdtemp(prefix='.표기-', dir=parent)
    try:
        if renotate:
            from modules.labels_io import save_labels
            updated['original_json'] = os.path.join(folder, '인식라벨.json')
            save_labels(updated['original_json'], updated['original_doc'])
            updated['json'] = updated['original_json']
            if updated['doc'] is not updated['original_doc']:
                updated['json'] = os.path.join(folder, '라벨.json')
                save_labels(updated['json'], updated['doc'])
        else:
            for field in ('original_json', 'json'):
                if os.path.dirname(session[field]) == session.get('_style_folder'):
                    target = os.path.join(folder, os.path.basename(session[field]))
                    if not os.path.exists(target):
                        shutil.copyfile(session[field], target)
                    updated[field] = target
        original = os.path.join(folder, '인식결과.png')
        placements = _render_edit_document(updated, updated['original_doc'], original)
        updated.update(original_png=original, original_placements=placements,
                       original_placement_notice=updated['placement_notice'])
        png = original
        if session['changes'] or session.get('region') is not None:
            png = os.path.join(folder, '결과.png')
            placements = _render_edit_document(updated, updated['doc'], png)
        updated.update(png=png, placements=placements, _style_folder=folder)
        return updated
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def _save_edit_version(session: dict, changes: list, parent: str) -> dict:
    """수정본과 재열기 정보를 새 폴더로 공개한다. 실패하면 원본을 보존한다."""
    from modules.label_edits import save_edits
    from modules.labels_io import save_labels
    region = session.get('region')
    if not changes and region is None:
        return dict(doc=session['original_doc'], placements=session['original_placements'],
                    png=session['original_png'], json=session['original_json'], edits=None,
                    placement_notice=session.get('original_placement_notice',''))
    doc, record = _apply_document_edits(session['original_doc'], changes, region)
    with tempfile.TemporaryDirectory(prefix='.라벨수정-', dir=parent) as tmp:
        png = os.path.join(tmp, '결과.png')
        render_session=dict(session)
        placements = _render_edit_document(render_session, doc, png)
        save_labels(os.path.join(tmp, '라벨.json'), doc)
        if changes:
            save_edits(os.path.join(tmp, '사용자수정.json'), record)
        # 되돌리기는 최종 라벨에서 추측하지 않고 저장한 원본과 기록으로 재현한다.
        import hashlib
        save_labels(os.path.join(tmp, '인식원본.json'), session['original_doc'])
        frame_path = os.path.join(tmp, '편집원본.png')
        Image.fromarray(session['image'][:, :, ::-1]).save(frame_path)
        with open(frame_path, 'rb') as stream:
            frame_hash = hashlib.sha256(stream.read()).hexdigest()
        metadata = dict(version=1, image_sha256=frame_hash,
            render_options={k:v for k,v in session['render_options'].items() if k != 'staves'},
            use_staves='staves' in session['render_options'],
            header_options=session['header_options'], legend_options=session['legend_options'],
            region=region, report_settings={k: v for k, v in session.get('report_settings', {}).items()
                                            if k != 'audio_highlight_delay_ms'})
        if 'recognition_exclusions' in session:
            metadata['recognition_exclusions'] = session['recognition_exclusions']
        with open(os.path.join(tmp, '재개정보.json'), 'w', encoding='utf-8') as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
        folder = os.path.join(parent, ('사용자수정-' if changes else '선택영역-') + uuid.uuid4().hex)
        os.replace(tmp, folder)
    return dict(doc=doc, placements=placements, png=os.path.join(folder, '결과.png'),
                json=os.path.join(folder, '라벨.json'), edits=(os.path.join(folder, '사용자수정.json') if changes else None),
                placement_notice=render_session.get('placement_notice',''))


def _load_edit_version(folder: str, source_path: str, parent: str) -> dict:
    """원본·PNG·JSON·수정 기록을 확인한 뒤에만 재열기 세션을 공개한다."""
    import hashlib
    import math
    import numpy as np
    from pathlib import Path
    from modules.label_edits import apply_edits, load_edits
    from modules.labels_io import load_labels, save_labels, document_staves, check_source, check_dpi, LabelSchemaError
    folder = Path(folder)
    if not (folder / '재개정보.json').is_file():
        raise ValueError('재열기 정보가 없는 이전 수정본입니다. 원본을 다시 변환한 뒤 수정본을 저장해 주세요.')
    if not os.path.isfile(source_path):
        raise ValueError('원본 악보 파일이 없습니다. 수정본을 열지 않았습니다.')
    try:
        metadata = json.loads((folder / '재개정보.json').read_text(encoding='utf-8'))
        if not isinstance(metadata, dict) or type(metadata.get('version')) is not int or metadata['version'] != 1:
            raise ValueError('지원하지 않는 재열기 정보입니다.')
        original = load_labels(str(folder / '인식원본.json'))
        doc = load_labels(str(folder / '라벨.json'))
        if not isinstance(original.get('source', {}).get('sha256'), str) or not original['source']['sha256']:
            raise ValueError('원본 해시가 없어 수정본을 열 수 없습니다.')
        frame_path = folder / '편집원본.png'
        if hashlib.sha256(frame_path.read_bytes()).hexdigest() != metadata['image_sha256']:
            raise ValueError('편집 원본 이미지의 해시가 다릅니다.')
        with Image.open(frame_path) as opened:
            image = np.asarray(opened.convert('RGB'))[:, :, ::-1].copy()
        reason = check_dpi(original) or check_source(original, source_path, image.shape, original['source']['page'])
        if reason:
            raise ValueError(reason)
        record = load_edits(folder / '사용자수정.json') if (folder / '사용자수정.json').is_file() else dict(version=1, source=original['source'], changes=[])
        expected = apply_edits(original, record)
        if record['changes']:
            expected['user_edits'] = record
        region = metadata.get('region')
        if region is not None:
            from modules.label_region import filter_region
            expected = filter_region(expected, *region)
            expected['selected_region'] = list(region)
        if expected != doc:
            raise ValueError('라벨 JSON과 사용자 수정 기록이 일치하지 않습니다.')
        options = metadata['render_options']
        allowed = {'font_path','font_size','text_color','text_offset_y','staff_spacings','placement_mode'}
        if not isinstance(options, dict) or set(options) - allowed:
            raise ValueError('저장된 렌더링 설정이 올바르지 않습니다.')
        options = dict(options)
        if options.get('placement_mode','near') not in PLACEMENT_LABELS.values():
            raise ValueError('저장된 표시 방식이 올바르지 않습니다.')
        if 'text_color' in options:
            color = options['text_color']
            if not isinstance(color, (list, tuple)) or len(color) != 3 or any(
                    type(channel) is not int or not 0 <= channel <= 255 for channel in color):
                raise ValueError('저장된 글자 색은 0~255 정수 RGB 세 값이어야 합니다.')
            # JSON은 RGB 튜플을 배열로 저장하지만 Pillow에는 튜플로 돌려준다.
            options['text_color'] = tuple(color)
        if 'staff_spacings' in options:
            if not isinstance(options['staff_spacings'], dict):
                raise ValueError('저장된 보표 간격 목록이 올바르지 않습니다.')
            options['staff_spacings'] = {int(k):float(v) for k,v in options['staff_spacings'].items()}
            if any(not math.isfinite(v) or v <= 0 for v in options['staff_spacings'].values()):
                raise ValueError('저장된 보표 간격은 양의 유한한 수여야 합니다.')
        if metadata['use_staves']:
            options['staves'] = document_staves(original)
        session = dict(original_doc=original, doc=doc, changes=record['changes'], image=image,
            source_path=source_path, render_options=options, header_options=metadata['header_options'],
            legend_options=metadata['legend_options'], report_settings=metadata.get('report_settings',{}), region=region)
        exclusions = metadata.get('recognition_exclusions')
        if (isinstance(exclusions, dict) and set(exclusions) == {'beam', 'offstaff', 'accidental', 'chord'}
                and all(type(v) is int and v >= 0 for v in exclusions.values())):
            session['recognition_exclusions'] = exclusions
        os.makedirs(parent, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.수정본재열기-', dir=parent) as tmp:
            original_png = os.path.join(tmp, '원본결과.png')
            session['original_placements'] = _render_edit_document(session, original, original_png)
            session['original_placement_notice']=session.get('placement_notice','')
            save_labels(os.path.join(tmp, '원본라벨.json'), original)
            current_png = os.path.join(tmp, '현재결과.png')
            session['placements'] = _render_edit_document(session, doc, current_png)
            with Image.open(folder / '결과.png') as saved, Image.open(current_png) as rendered:
                if not np.array_equal(np.asarray(saved.convert('RGB')), np.asarray(rendered.convert('RGB'))):
                    raise ValueError('결과 PNG와 라벨 JSON이 일치하지 않습니다.')
            target = os.path.join(parent, '재열기-' + uuid.uuid4().hex)
            os.replace(tmp, target)
        session.update(original_png=os.path.join(target,'원본결과.png'), original_json=os.path.join(target,'원본라벨.json'),
                       png=str(folder/'결과.png'), json=str(folder/'라벨.json'))
        return session
    except (KeyError, TypeError, AttributeError, OverflowError, LabelSchemaError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'수정본 정보가 손상됐습니다: {exc}') from exc


def _save_image_pages_pdf(paths, destination):
    """성공한 출력 이미지를 순서대로 한 쪽씩 기록한다."""
    directory = os.path.dirname(os.path.abspath(destination))
    with tempfile.TemporaryDirectory(prefix='.합본-', dir=directory) as folder:
        staged = os.path.join(folder, os.path.basename(destination))
        for index, path in enumerate(paths):
            with Image.open(path) as source, source.convert("RGB") as page:
                page.save(staged, "PDF", append=index > 0, resolution=300.0)
        os.replace(staged, destination)


def _read_page_frame(path):
    import numpy as np

    with Image.open(path) as image:
        return np.asarray(image.convert('RGB'))[:, :, ::-1].copy()


def _export_styled_batch(sessions, parent, style, progress=None):
    '''모든 결과를 만든 뒤 한 폴더로 게시한다. 원본 배열은 한 쪽씩 놓는다.'''
    target = os.path.join(parent, '전체계이름-' + uuid.uuid4().hex[:12])
    with tempfile.TemporaryDirectory(prefix='.전체계이름-', dir=parent) as folder:
        paths = []
        for number, session in enumerate(sessions, 1):
            if progress:
                progress(number, len(sessions))
            page = dict(session)
            if page['image'] is None:
                page['image'] = _read_page_frame(page['frame_path'])
            with tempfile.TemporaryDirectory(prefix='.쪽-', dir=folder) as scratch:
                updated = _restyle_edit_session(page, scratch, **style)
                name = os.path.splitext(os.path.basename(page['source_path']))[0]
                png = os.path.join(folder, f'{number:03d}-{name}.png')
                shutil.copyfile((updated or page)['png'], png)
                paths.append(png)
                del updated, page
        _save_image_pages_pdf(paths, os.path.join(folder, '전체_계이름.pdf'))
        os.replace(folder, target)
    return target


class _WindowsFileDrop:
    """Tk 바깥쪽 HWND의 파일 드롭을 받아 원래 창 프로시저에 다른 메시지를 전달한다."""

    def __init__(self, tk_hwnd, deliver):
        import ctypes as ct
        from ctypes import wintypes as win

        user = ct.WinDLL("user32", use_last_error=True)
        shell = ct.WinDLL("shell32", use_last_error=True)
        long_ptr = ct.c_ssize_t
        wndproc = ct.WINFUNCTYPE(long_ptr, win.HWND, win.UINT, win.WPARAM, win.LPARAM)

        self._set_proc = getattr(user, "SetWindowLongPtrW", None) or user.SetWindowLongW
        self._forward = user.CallWindowProcW
        self._accept = shell.DragAcceptFiles
        self._query = shell.DragQueryFileW
        self._finish = shell.DragFinish
        signatures = (
            (user.GetAncestor, (win.HWND, win.UINT), win.HWND),
            (self._set_proc, (win.HWND, ct.c_int, long_ptr), long_ptr),
            (self._forward, (ct.c_void_p, win.HWND, win.UINT, win.WPARAM, win.LPARAM), long_ptr),
            (self._accept, (win.HWND, win.BOOL), None),
            (self._query, (win.HANDLE, win.UINT, win.LPWSTR, win.UINT), win.UINT),
            (self._finish, (win.HANDLE,), None),
        )
        for fn, args, result in signatures:
            fn.argtypes, fn.restype = args, result
        self._hwnd = user.GetAncestor(tk_hwnd, 2) or tk_hwnd  # GA_ROOT
        self._deliver = deliver
        self._buffer = ct.create_unicode_buffer
        self._callback = wndproc(self._dispatch)
        ct.set_last_error(0)
        self._previous = self._set_proc(self._hwnd, -4, ct.cast(self._callback, ct.c_void_p).value)
        if not self._previous:
            raise OSError(ct.get_last_error(), "파일 드롭 훅을 등록할 수 없습니다.")
        self._accept(self._hwnd, True)

    def _dispatch(self, hwnd, message, wparam, lparam):
        if message != 0x0233:  # WM_DROPFILES
            return self._forward(self._previous, hwnd, message, wparam, lparam)
        paths = None
        try:
            count = self._query(wparam, 0xffffffff, None, 0)
            read = []
            for index in range(count):
                length = self._query(wparam, index, None, 0)
                buffer = self._buffer(length + 1)
                if not length or self._query(wparam, index, buffer, len(buffer)) != length:
                    raise ValueError("드롭 경로가 비어 있거나 잘렸습니다.")
                read.append(buffer.value)
            paths = tuple(read)
        except Exception:
            # ctypes 콜백 경계에서 오류를 Tk 쪽 안내로 돌린다.
            pass
        finally:
            self._finish(wparam)
        try:
            self._deliver(paths)
        except (TclError, RuntimeError):
            pass
        return 0

    def close(self):
        if not self._previous:
            return True
        self._accept(self._hwnd, False)
        if not self._set_proc(self._hwnd, -4, self._previous):
            return False
        self._previous = 0
        return True


class SheetHelperApp(ctk.CTk):
    def __init__(self) -> None:
        _configure_ui_theme()
        super().__init__()

        self.title("악보헬퍼 - 계이름 자동 표기")
        self.geometry("1150x760")
        self.minsize(960, 640)

        icon = resource_path(os.path.join("assets", "icon.ico"))
        if os.path.isfile(icon):
            try:
                self.iconbitmap(icon)
            except Exception:
                pass  # 아이콘 실패는 치명적이지 않음

        self.settings_path = os.path.join(base_dir(), "settings.json")
        self._recent_path = os.path.join(os.path.dirname(self.settings_path), "recent_files.json")
        self.settings = self._load_settings()

        ctk.set_appearance_mode(self.settings["appearance"])
        self.configure(fg_color=UI_COLORS["background"])

        self.input_path: str | None = None
        self.input_paths: tuple[str, ...] = ()
        self.result_path: str | None = None
        self.labels_path: str | None = None
        self.output_dir = os.path.join(base_dir(), "output")
        self._converting = False
        self._edit_session = None
        self._review_index = None
        self._page_sessions = []
        self._page_index = 0
        self._page_cache = None
        self._conversion_status = None
        self._region_start = None
        self._audio_thread = None
        self._keyboard_note = None
        self._audio_cancel = threading.Event()
        from modules.piano_keyboard import PlaybackCursor
        self._playback = PlaybackCursor()
        self._audio_events = queue.Queue()
        self._audio_timer = None
        self._audio_delayed = {}
        self._audio_delay_save_timer = None
        self._practice_start = self._practice_end = None
        self._practice_doc = self._practice_session = None
        self._closing = False
        self._windows_drop = None
        self._drop_timer = None
        self._pending_drops = []
        self.protocol("WM_DELETE_WINDOW", self._close_app)
        self._edit_window = None
        self._add_window = None

        # 미리보기(원본/결과 공용) 상태
        self._preview_source: Image.Image | None = None
        self._preview_zoom = 1.0
        self._preview_photo = None  # ImageTk.PhotoImage GC 방지 참조
        self._preview_tile_after = None
        self._preview_original = False
        self._style_refresh_timer = None
        self._sync_page_style = False

        self._build_layout()
        self._apply_settings_to_widgets()
        self._audio_timer = self.after(_AUDIO_IDLE_POLL_MS, self._drain_audio_events)
        self.bind('<KeyPress>', self._review_shortcut, add='+')
        self.bind('<KeyPress>', self._help_shortcut, add='+')
        self.bind('<KeyPress>', self._preview_shortcut, add='+')
        self.bind('<Control-v>', self._paste_clipboard_image, add='+')
        if sys.platform == 'win32':
            self.bind('<Map>', self._enable_file_drop, add='+')
        if getattr(self, "_settings_note", ""):
            self.log(self._settings_note)

        # exe 아이콘 위로 파일을 드래그해 실행한 경우: 자동으로 로드 + 변환
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self._set_input(sys.argv[1])
            self.after(400, self.start_convert)

    # ------------------------------------------------------------------
    # 설정 저장/복원
    # ------------------------------------------------------------------
    def _load_settings(self) -> dict:
        merged = dict(DEFAULT_SETTINGS)
        self._settings_note = ""      # 로그 위젯이 생긴 뒤 보여줄 안내
        try:
            # utf-8-sig: 메모장으로 저장하면 앞에 BOM(EF BB BF)이 붙는데,
            # 그냥 utf-8로 읽으면 JSON 파싱이 깨져 설정이 통째로 무시된다
            # (사용자에게는 '설정이 저절로 초기화됐다'로 보인다).
            with open(self.settings_path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError("설정 파일은 JSON 객체여야 합니다.")
            for k in merged:
                if k in saved and isinstance(saved[k], type(merged[k])):
                    merged[k] = saved[k]
        except FileNotFoundError:
            pass  # 첫 실행: 기본값으로 시작한다 (안내할 것 없음)
        except (OSError, ValueError) as e:
            # 조용히 삼키면 왜 초기화됐는지 알 길이 없다
            self._settings_note = (f"⚠ 설정 파일을 읽지 못해 기본값으로 시작합니다 "
                                   f"({type(e).__name__}: {e}) — {self.settings_path}")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", merged["text_color"]):
            merged["text_color"] = DEFAULT_SETTINGS["text_color"]
        if merged["font"] == "custom":
            if not os.path.isfile(merged["custom_font_path"]):
                merged["font"] = DEFAULT_SETTINGS["font"]
        elif merged["font"] not in FONT_LABELS:
            merged["font"] = DEFAULT_SETTINGS["font"]
        if merged["clef"] not in CLEF_LABELS:
            merged["clef"] = DEFAULT_SETTINGS["clef"]
        merged["notation"] = LEGACY_NOTATION_LABELS.get(merged["notation"],
                                                        merged["notation"])
        if merged["notation"] not in NOTATION_LABELS:
            merged["notation"] = DEFAULT_SETTINGS["notation"]
        if merged["placement_mode"] not in PLACEMENT_LABELS.values():
            merged["placement_mode"] = "near"
        merged["audio_highlight_delay_ms"] = _valid_audio_delay(merged["audio_highlight_delay_ms"])
        merged["font_size"] = max(10, min(48, int(merged["font_size"])))
        if not os.path.isdir(merged["last_input_dir"]):
            merged["last_input_dir"] = ""
        return merged

    def _save_settings(self) -> None:
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 저장 실패해도 동작에는 지장 없음

    # ------------------------------------------------------------------
    # 레이아웃
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 주요 작업은 고정하고 설정 카드만 스크롤한다.
        rail = ctk.CTkFrame(self, width=316, corner_radius=0, fg_color=UI_COLORS["background"])
        rail.grid(row=0, column=0, sticky="nsew")
        rail.grid_propagate(False)
        rail.grid_columnconfigure(0, weight=1)
        rail.grid_rowconfigure(1, weight=1)
        actions = ctk.CTkFrame(rail, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        sidebar = ctk.CTkScrollableFrame(rail, width=288, corner_radius=0, fg_color="transparent")
        sidebar.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar = sidebar
        header = ctk.CTkFrame(actions, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="악보헬퍼", font=ctk.CTkFont(size=23, weight="bold")).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="?", width=30, height=30, command=self._show_shortcuts,
            fg_color="transparent", hover_color=UI_COLORS["ghost_hover"],
            text_color=UI_COLORS["muted"], border_width=0).grid(row=0, column=1, padx=4)
        self.theme_btn = ctk.CTkButton(header, text="☾", width=30, height=30,
            command=self.toggle_theme, fg_color="transparent", border_width=0,
            hover_color=UI_COLORS["ghost_hover"], text_color=UI_COLORS["muted"])
        self.theme_btn.grid(row=0, column=2)
        files = ctk.CTkFrame(actions, fg_color="transparent")
        files.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
        files.grid_columnconfigure((0, 1), weight=1, uniform="files")
        self.select_btn = ctk.CTkButton(files, text="악보 파일 선택", height=34, width=120,
                                       command=self.select_file)
        self.select_btn.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        self.select_images_btn = ctk.CTkButton(files, text="여러 이미지 선택", height=34, width=120,
                                              command=self.select_images)
        self.select_images_btn.grid(row=0, column=1, padx=(3, 0), sticky="ew")
        ctk.CTkButton(actions, text="클립보드 붙여넣기 (Ctrl+V)", height=32,
                      command=self._paste_clipboard_image).grid(
            row=2, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.convert_btn = ctk.CTkButton(actions, text="✨ 계이름 달기", height=42,
            font=ctk.CTkFont(size=16, weight="bold"), command=self.start_convert,
            fg_color=UI_COLORS["primary"], hover_color=UI_COLORS["primary_hover"],
            text_color="#FFFFFF", text_color_disabled=UI_COLORS["primary_disabled_text"], border_width=0)
        self.convert_btn.grid(row=3, column=0, padx=16, pady=(0, 6), sticky="ew")
        self.file_label = ctk.CTkLabel(actions, text="선택된 파일 없음", font=ctk.CTkFont(size=11),
            text_color=UI_COLORS["muted"], wraplength=280, justify="left", anchor="w")
        self.file_label.grid(row=4, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.photo_retry_btn = ctk.CTkButton(actions, text="사진 모드로 다시", command=self._retry_photo)
        self.photo_retry_btn.grid(row=5, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.photo_retry_btn.grid_remove()

        # ---- 인식 설정 ----
        card = self._section(sidebar, 0, "인식 설정")
        self.recent_btn = ctk.CTkButton(card, text="최근 악보...", height=29,
                                       command=self._show_recent_files)
        self.recent_btn.grid(row=1, column=0, padx=12, pady=(2, 5), sticky="ew")
        self._recent_menu = Menu(card, tearoff=False)
        row = 2

        self._caption(card, row, "음자리표"); row += 1
        self.clef_menu = ctk.CTkOptionMenu(card, values=list(CLEF_LABELS.keys()), height=32,
                                           command=lambda _v: self._on_setting_changed())
        self.clef_menu.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="ew"); row += 1

        pdf_caption = self._caption(card, row, "PDF 페이지 (PDF일 때만)")
        row += 1
        self.page_entry = ctk.CTkEntry(card, height=32, placeholder_text="1")
        self.page_entry.insert(0, "1")
        self.page_entry.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="ew"); row += 1

        self.all_pages_check = ctk.CTkCheckBox(card, text="PDF 전체 쪽 처리")
        self.all_pages_check.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="w"); row += 1
        if getattr(sys, "frozen", False):
            self.all_pages_check.configure(state="disabled")
            for widget in (pdf_caption, self.page_entry, self.all_pages_check):
                widget.grid_remove()

        self.photo_check = ctk.CTkCheckBox(
            card, text="사진 모드 (정면 촬영)", command=self._on_setting_changed,
        )
        self.photo_check.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="w"); row += 1

        # ---- 표기 설정 ----
        card = self._section(sidebar, 1, "계이름 표기")
        row = 1

        self._caption(card, row, "표기 방식"); row += 1
        self.notation_menu = ctk.CTkOptionMenu(card, values=list(NOTATION_LABELS.keys()), height=32,
                                               command=lambda _v: self._on_setting_changed())
        self.notation_menu.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="ew"); row += 1
        self._caption(card, row, "표시 방식"); row += 1
        self.placement_menu = ctk.CTkOptionMenu(card, values=list(PLACEMENT_LABELS), height=32,
            command=lambda _v: self._on_setting_changed())
        self.placement_menu.grid(row=row, column=0, padx=12, pady=(0,8), sticky="ew"); row += 1

        # 이동도는 '무엇을 도로 볼지'가 있어야 정해진다. 조표만으로는 장조인지
        # 나란한 단조인지 알 수 없지만 자리표는 같으므로, 비워 두면 조표대로
        # 장조로 읽는다. 단조로 읽고 싶을 때만 으뜸음을 적고 '단조'를 켠다.
        self._caption(card, row, "조성 (이동도일 때만, 비우면 조표대로)"); row += 1
        key_row = ctk.CTkFrame(card, fg_color="transparent")
        key_row.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="ew"); row += 1
        key_row.grid_columnconfigure(0, weight=1)
        self.key_entry = ctk.CTkEntry(key_row, height=32, placeholder_text="예: D, Bb, F#")
        self.key_entry.grid(row=0, column=0, sticky="ew")
        self._key_border_color = self.key_entry.cget("border_color")
        self.key_entry.bind("<KeyRelease>", lambda _e: self._update_key_feedback())
        self.key_entry.bind("<FocusOut>", lambda _e: self._on_setting_changed())
        self.key_entry.bind("<Return>", lambda _e: self._on_setting_changed())
        self.minor_check = ctk.CTkCheckBox(
            key_row, text="단조", width=60,
            command=self._on_setting_changed,
        )
        self.minor_check.grid(row=0, column=1, padx=(8, 0))
        self.key_feedback = ctk.CTkLabel(
            card, text="", height=0, font=ctk.CTkFont(size=11),
            text_color=("#b3261e", "#ff766f"), anchor="w",
        )
        self.key_feedback.grid(row=row, column=0, padx=12, pady=(0, 4), sticky="ew"); row += 1

        self._caption(card, row, "글꼴"); row += 1
        self.font_menu = ctk.CTkOptionMenu(
            card, values=list(FONT_LABELS.keys()) + [CUSTOM_FONT_OPTION], height=32,
            command=self._on_font_selected,
        )
        self.font_menu.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="ew"); row += 1

        size_row = ctk.CTkFrame(card, fg_color="transparent")
        size_row.grid(row=row, column=0, padx=12, pady=(0, 2), sticky="ew"); row += 1
        size_row.grid_columnconfigure(0, weight=1)
        self._caption(size_row, 0, "글자 크기", grid=False).grid(row=0, column=0, sticky="w")
        self.size_value_label = ctk.CTkLabel(size_row, text="100%", font=ctk.CTkFont(size=12, weight="bold"))
        self.size_value_label.grid(row=0, column=1, sticky="e")

        self.size_slider = ctk.CTkSlider(
            card, from_=10, to=40, number_of_steps=30, scroll_step=0, command=self._on_size_slide
        )
        self.size_slider.grid(row=row, column=0, padx=12, pady=(0, 8), sticky="ew"); row += 1
        # CTk 스크롤 패널은 슬라이더의 휠을 제외하므로 패널 캔버스로 전달한다.
        self.size_slider.bind('<MouseWheel>', lambda e: sidebar._parent_canvas.event_generate('<MouseWheel>', delta=e.delta))

        color_row = ctk.CTkFrame(card, fg_color="transparent")
        color_row.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="ew"); row += 1
        color_row.grid_columnconfigure(1, weight=1)
        self._caption(color_row, 0, "글자 색", grid=False).grid(row=0, column=0, sticky="w")
        self.color_swatch = ctk.CTkButton(
            color_row, text="", width=34, height=24, corner_radius=6,
            hover=False, command=self.pick_color, border_width=1,
        )
        self.color_swatch.grid(row=0, column=1, padx=(10, 6), sticky="e")
        self.color_btn = ctk.CTkButton(color_row, text="색 선택...", width=88, height=26,
                                       command=self.pick_color)
        self.color_btn.grid(row=0, column=2, sticky="e")

        self.legend_check = ctk.CTkCheckBox(
            card, text="결과 이미지에 표시 안내 넣기", command=self._on_setting_changed,
        )
        self.legend_check.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="w"); row += 1

        card = self._section(sidebar, 2, "저장 · 편집")
        tools = ctk.CTkFrame(card, fg_color="transparent")
        tools.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))
        tools.grid_columnconfigure((0, 1), weight=1, uniform="tools")
        self.open_result_btn = ctk.CTkButton(tools, text="크게 보기", height=32, width=100,
                                             state="disabled", command=self.open_result)
        self.open_folder_btn = ctk.CTkButton(tools, text="결과 폴더", height=32, width=100,
                                             state="disabled", command=self.open_folder)
        self.export_pages_btn = ctk.CTkButton(tools, text="전체 쪽 PNG / PDF", height=32, width=100,
                                               state="disabled", command=self.export_all_pages)
        self.reopen_edits_btn = ctk.CTkButton(tools, text="수정본 다시 열기", height=32, width=100,
                                               command=self._open_saved_edits)
        self.report_btn = ctk.CTkButton(tools, text="문제 신고용 저장", height=32, width=100,
                                        state="disabled", command=self.save_feedback)
        restore = ctk.CTkButton(tools, text="전체 라벨 보기", height=32, width=100,
                                command=lambda: self._select_region(None))
        for index, button in enumerate((self.open_result_btn, self.open_folder_btn,
                self.export_pages_btn, self.reopen_edits_btn, self.report_btn, restore)):
            button.grid(row=index // 2, column=index % 2, padx=3, pady=3, sticky="ew")
        self.region_check = ctk.CTkCheckBox(card, text="드래그로 영역 선택")
        self.region_check.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")
        card = self._section(sidebar, 3, "듣기 설정")
        self.audio_check = ctk.CTkCheckBox(card, text="확인 필요 음은 듣기에서 제외")
        self.audio_check.select()
        self.audio_check.grid(row=1, column=0, padx=12, pady=(4, 6), sticky="w")
        ctk.CTkLabel(card, text="건반 옆 [▶ 듣기]로 음높이를 확인합니다.\n빠르기와 시차는 건반 아래에서 조절하세요.",
            font=ctk.CTkFont(size=11), text_color=UI_COLORS["muted"], justify="left").grid(
                row=2, column=0, padx=12, pady=(0, 10), sticky="w")
        card = self._section(sidebar, 4, "실행 로그")
        self.log_box = ctk.CTkTextbox(card, height=110, font=ctk.CTkFont(size=11), state="disabled")
        self.log_box.grid(row=1, column=0, padx=10, pady=(2, 10), sticky="ew")

        # ---- 오른쪽 미리보기 영역 (원본 선택 시 원본, 변환 후 결과 표시. 휠로 확대/축소) ----
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(2, weight=1)
        self.page_nav = ctk.CTkFrame(self.preview_frame, corner_radius=10, border_width=1)
        self.page_nav.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        self.page_buttons = ctk.CTkFrame(self.page_nav, fg_color='transparent')
        self.page_buttons.pack(fill='x')
        self.page_buttons.grid_columnconfigure(1, weight=1)
        self.prev_page_btn = ctk.CTkButton(self.page_buttons, text='이전 쪽', width=68,
            command=lambda: self._select_result_page(self._page_index - 1))
        self.page_label = ctk.CTkLabel(self.page_buttons, text='', wraplength=220, justify='left')
        self.next_page_btn = ctk.CTkButton(self.page_buttons, text='다음 쪽', width=68,
            command=lambda: self._select_result_page(self._page_index + 1))
        self.edit_btn = ctk.CTkButton(self.page_buttons, text='라벨 수정', width=82,
            state='disabled', command=self._open_label_editor)
        self.save_as_btn = ctk.CTkButton(self.page_buttons, text='다른 이름으로 저장', width=128,
            state='disabled', command=self.save_as)
        for column, widget in enumerate((self.prev_page_btn, self.page_label, self.next_page_btn,
                                         self.edit_btn, self.save_as_btn)):
            widget.grid(row=0, column=column, padx=4, pady=6)
        self.page_label.grid_configure(sticky='w', padx=10)
        self.page_progress = ctk.CTkProgressBar(self.page_nav, mode='indeterminate', height=6)
        self.page_progress.pack(fill='x', padx=8, pady=(0, 6))
        self.page_progress.set(0)
        self.page_nav.grid_remove()

        self.review_nav = ctk.CTkFrame(self.preview_frame, corner_radius=10, border_width=1)
        self.review_nav.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        self.prev_review_btn = ctk.CTkButton(self.review_nav, text='◀ 이전', width=90,
            state='disabled', command=lambda: self._move_review_label(-1))
        self.prev_review_btn.pack(side='left', padx=8, pady=6)
        self.review_label = ctk.CTkLabel(self.review_nav, text='확인 필요 없음')
        self.review_label.pack(side='left', expand=True)
        self.review_confirm_btn = ctk.CTkButton(self.review_nav, text='확인 완료', width=82,
            state='disabled', command=self._confirm_review_label)
        self.review_confirm_btn.pack(side='left', padx=4, pady=6)
        self.next_review_btn = ctk.CTkButton(self.review_nav, text='다음 확인 필요 ▶', width=160,
            state='disabled', command=lambda: self._move_review_label(1))
        self.next_review_btn.pack(side='right', padx=8, pady=6)
        self.preview_compare_btn = ctk.CTkButton(self.review_nav, text='원본 보기', width=90,
            state='disabled', command=self._toggle_preview_original)
        self.preview_compare_btn.pack(side='right', padx=8, pady=6)
        self.review_nav.grid_remove()

        canvas_bg = self._apply_appearance_mode(UI_COLORS["canvas"])
        self.preview_canvas = Canvas(
            self.preview_frame, bg=canvas_bg, highlightthickness=0, bd=0,
        )
        self.preview_canvas.grid(row=2, column=0, sticky="nsew")
        self.preview_vscroll = ctk.CTkScrollbar(
            self.preview_frame, orientation="vertical", command=self.preview_canvas.yview
        )
        self.preview_vscroll.grid(row=2, column=1, sticky="ns")
        self.preview_hscroll = ctk.CTkScrollbar(
            self.preview_frame, orientation="horizontal", command=self.preview_canvas.xview
        )
        self.preview_hscroll.grid(row=3, column=0, sticky="ew")
        self.preview_canvas.configure(
            yscrollcommand=lambda first, last: self._preview_view_changed(self.preview_vscroll, first, last),
            xscrollcommand=lambda first, last: self._preview_view_changed(self.preview_hscroll, first, last),
        )
        self.preview_canvas.bind("<Configure>", self._preview_resized)

        self.placement_notice = ctk.CTkLabel(self.preview_frame, text='', wraplength=600,
            justify='left', corner_radius=8, padx=12, pady=7,
            fg_color=UI_COLORS['amber'], text_color=UI_COLORS['amber_text'])
        self.placement_notice.grid(row=4, column=0, columnspan=2, sticky='ew', padx=8, pady=4)
        self.placement_notice.grid_remove()

        self.style_save_notice = ctk.CTkLabel(self.preview_frame, wraplength=600, justify='left',
            corner_radius=8, padx=12, pady=7, fg_color=UI_COLORS['blue'], text_color=UI_COLORS['compare_text'],
            text='현재 표기가 미리보기에 적용됨 · 이미지로 남기려면 [다른 이름으로 저장]')
        self.style_save_notice.grid(row=5, column=0, columnspan=2, sticky='ew', padx=8, pady=4)
        self.style_save_notice.grid_remove()

        from modules.piano_keyboard import PianoKeyboard
        self.piano_frame = ctk.CTkFrame(self.preview_frame, corner_radius=10, border_width=1)
        self.piano_frame.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        status = ctk.CTkFrame(self.piano_frame, fg_color='transparent')
        status.pack(fill='x', padx=10, pady=(8, 4))
        status.grid_columnconfigure(0, weight=1)
        self.audio_position = ctk.CTkLabel(status,
            text='음높이 확인 · 박자 없음 · 건반 A0~C8', height=26,
            font=ctk.CTkFont(size=11), anchor='w', width=1)
        self.audio_position.grid(row=0, column=0, sticky='ew')
        self.listen_btn = ctk.CTkButton(status, text='▶ 듣기', width=84, height=30,
            fg_color=UI_COLORS['primary'], hover_color=UI_COLORS['primary_hover'],
            text_color='#FFFFFF', text_color_disabled=UI_COLORS['primary_disabled_text'],
            border_width=0, command=self._listen_labels)
        self.listen_btn.grid(row=0, column=1, padx=(8, 4))
        self.stop_btn = ctk.CTkButton(status, text='■ 중지', width=72, height=30,
                                     command=self._stop_listening)
        self.stop_btn.grid(row=0, column=2)
        self.piano_keyboard = PianoKeyboard(self.piano_frame, on_key_click=self._on_piano_key)
        self.piano_keyboard.pack(fill='x', padx=10)
        self.practice_bar = ctk.CTkFrame(self.piano_frame, fg_color='transparent')
        self.practice_bar.pack(fill='x', padx=8, pady=(4, 8))
        self.practice_bar.grid_columnconfigure(0, weight=1)
        range_row = ctk.CTkFrame(self.practice_bar, fg_color='transparent')
        range_row.grid(row=0, column=0, sticky='ew')
        range_row.grid_columnconfigure(3, weight=1)
        for column, (text, command) in enumerate((('시작 음', lambda: self._set_practice_boundary('start')),
                ('끝 음', lambda: self._set_practice_boundary('end')), ('구간 지우기', self._clear_practice_range))):
            ctk.CTkButton(range_row, text=text, width=68, height=26,
                font=ctk.CTkFont(size=11), command=command).grid(row=0, column=column, padx=2, pady=2)
        self.practice_range_label = ctk.CTkLabel(range_row, text='구간: 전체',
                                               font=ctk.CTkFont(size=11), width=1, anchor='w')
        self.practice_range_label.grid(row=0, column=3, padx=8, sticky='ew')
        self.practice_repeat = ctk.CTkCheckBox(range_row, text='구간 반복', width=90)
        self.practice_repeat.grid(row=0, column=4, padx=4, sticky='e')
        timing_row = ctk.CTkFrame(self.practice_bar, fg_color='transparent')
        timing_row.grid(row=1, column=0, sticky='ew')
        timing_row.grid_columnconfigure((1, 3), weight=1)
        self.practice_speed_label = ctk.CTkLabel(timing_row,
            text='빠르기 1.0x', font=ctk.CTkFont(size=10), wraplength=120, width=120)
        self.practice_speed_label.grid(row=0, column=0, padx=3, sticky='w')
        self.practice_speed = ctk.CTkSlider(timing_row, from_=.5, to=1.5,
            number_of_steps=10, width=80, command=lambda _value: self._update_practice_controls())
        self.practice_speed.grid(row=0, column=1, padx=(2, 12), pady=6, sticky='ew')
        self.practice_speed.set(1.)
        self.practice_speed.bind('<MouseWheel>', lambda _event: 'break')
        self.audio_delay_label = ctk.CTkLabel(timing_row, text='', font=ctk.CTkFont(size=10))
        self.audio_delay_label.grid(row=0, column=2, padx=4, sticky='w')
        self.audio_delay_slider = ctk.CTkSlider(timing_row, from_=0, to=_AUDIO_DELAY_MAX_MS,
            number_of_steps=_AUDIO_DELAY_MAX_MS // _AUDIO_DELAY_STEP_MS,
            width=80, command=self._set_audio_highlight_delay)
        self.audio_delay_slider.grid(row=0, column=3, padx=4, pady=6, sticky='ew')
        self.audio_delay_slider.bind('<MouseWheel>', lambda _event: 'break')
        ctk.CTkButton(timing_row, text='초기화', width=54, height=26,
            font=ctk.CTkFont(size=11),
            command=lambda: self._set_audio_highlight_delay(AUDIO_HIGHLIGHT_DELAY_MS)).grid(
                row=0, column=4, padx=3)
        self.piano_frame.grid_remove()
        self._preview_placeholder_text = (
            "악보 이미지를 선택하거나\nCtrl+V로 캡처를 붙여넣으세요"
        )
        self._draw_placeholder()

        # 마우스 휠 확대/축소 (커서 위치를 기준점으로 유지)
        self.preview_canvas.bind("<Button-1>", self._on_label_click)
        self.preview_canvas.bind("<Double-Button-1>", lambda event: self._on_label_click(event, edit=True))
        self.preview_canvas.bind("<B1-Motion>", self._drag_region)
        self.preview_canvas.bind("<ButtonRelease-1>", self._finish_region)
        self.preview_canvas.bind("<MouseWheel>", self._on_mousewheel)
        # 리눅스/일부 트랙패드 호환 (Button-4/5)
        self.preview_canvas.bind("<Button-4>", lambda e: self._on_mousewheel(e, delta=120))
        self.preview_canvas.bind("<Button-5>", lambda e: self._on_mousewheel(e, delta=-120))

    def _section(self, parent, row: int, text: str):
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=1)
        card.grid(row=row, column=0, padx=(0, 4), pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=text, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(10, 6), sticky="w")
        return card

    def _caption(self, parent, row: int, text: str, grid: bool = True):
        lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11),
                           text_color=UI_COLORS["muted"])
        if grid:
            lbl.grid(row=row, column=0, padx=12, pady=(0, 2), sticky="w")
        return lbl

    def _apply_settings_to_widgets(self) -> None:
        delay = self.settings["audio_highlight_delay_ms"]
        self.audio_delay_slider.set(delay)
        self.audio_delay_label.configure(text=f'화면 강조 지연 {delay}ms')
        self.clef_menu.set(self.settings["clef"])
        self.notation_menu.set(self.settings["notation"])
        self.placement_menu.set(next(k for k,v in PLACEMENT_LABELS.items() if v==self.settings["placement_mode"]))
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, self.settings.get("key", ""))
        if self.settings.get("minor"):
            self.minor_check.select()
        else:
            self.minor_check.deselect()
        if self.settings.get("photo"):
            self.photo_check.select()
        else:
            self.photo_check.deselect()
        if self.settings.get("legend", True):
            self.legend_check.select()
        else:
            self.legend_check.deselect()
        self._update_key_feedback()
        if self.settings["font"] == "custom":
            self.font_menu.set(os.path.basename(self.settings["custom_font_path"]))
        else:
            self.font_menu.set(self.settings["font"])
        self.size_slider.set(self.settings["font_size"])
        self.size_value_label.configure(text=f"{round(self.settings['font_size'] / 18 * 100)}%")
        self.color_swatch.configure(fg_color=self.settings["text_color"])
        self.theme_btn.configure(text="☾" if self.settings["appearance"] == "light" else "☀")

    # ------------------------------------------------------------------
    # 설정 이벤트
    # ------------------------------------------------------------------
    def _on_setting_changed(self) -> None:
        previous_style = self.settings["placement_mode"], self.settings.get("legend", False)
        previous_notation = (self.settings.get("notation", DEFAULT_SETTINGS["notation"]),
                             self.settings.get("key", ""), self.settings.get("minor", False))
        self.settings["clef"] = self.clef_menu.get()
        self.settings["placement_mode"] = PLACEMENT_LABELS.get(self.placement_menu.get(),"near")
        key_override, valid, _message = self._validated_key_entry()
        notation_changed = False
        if valid:
            notation = self.notation_menu.get()
            minor = bool(self.minor_check.get())
            self.settings.update(notation=notation, key=key_override, minor=minor)
            notation_changed = previous_notation != (notation, key_override, minor)
            if notation_changed:
                self._notation_request = (NOTATION_LABELS.get(notation, 'solfege-fixed'), key_override, minor)
        self.settings["photo"] = bool(self.photo_check.get())
        self.settings["legend"] = bool(self.legend_check.get())
        self._update_key_feedback()
        self._save_settings()
        self._update_placement_notice()
        if notation_changed or previous_style != (self.settings["placement_mode"], self.settings["legend"]):
            self._schedule_style_refresh(immediate=True)

    def _validated_key_entry(self) -> tuple[str, bool, str]:
        raw = self.key_entry.get()
        try:
            return normalize_key_override(raw, bool(self.minor_check.get())), True, ""
        except UnknownNoteNameError as e:
            return "", False, str(e)

    def _update_key_feedback(self) -> bool:
        """조성 오타를 입력 단계에서 표시한다. 빈 값은 조표 자동 판단이라 정상이다."""
        _key_override, valid, message = self._validated_key_entry()
        self.key_entry.configure(
            border_color=self._key_border_color if valid else ("#b3261e", "#ff766f")
        )
        self.key_feedback.configure(
            text=message
        )
        return valid

    def _on_font_selected(self, value: str) -> None:
        if value == CUSTOM_FONT_OPTION:
            path = filedialog.askopenfilename(
                title="글꼴 파일 선택",
                filetypes=[("글꼴 파일", "*.ttf *.otf *.ttc"), ("모든 파일", "*.*")],
            )
            if path:
                self.settings["font"] = "custom"
                self.settings["custom_font_path"] = path
                self.font_menu.set(os.path.basename(path))
                self.log(f"글꼴 변경: {os.path.basename(path)}")
            else:
                # 취소하면 이전 설정으로 되돌림
                self._apply_settings_to_widgets()
                return
        else:
            self.settings["font"] = value
        self._save_settings()
        self._schedule_style_refresh(immediate=True)

    def _current_font_path(self) -> str:
        if self.settings["font"] == "custom" and os.path.isfile(self.settings["custom_font_path"]):
            return self.settings["custom_font_path"]
        return FONT_LABELS.get(self.settings["font"], FONT_LABELS["맑은 고딕"])

    def _on_size_slide(self, value: float) -> None:
        size = int(round(value))
        if size == self.settings["font_size"]:
            return
        self.settings["font_size"] = size
        self.size_value_label.configure(text=f"{round(size / 18 * 100)}%")
        self._save_settings()
        self._schedule_style_refresh()

    def pick_color(self) -> None:
        rgb, hex_color = colorchooser.askcolor(
            color=self.settings["text_color"], title="계이름 글자 색 선택", parent=self
        )
        if hex_color:
            self.settings["text_color"] = hex_color
            self.color_swatch.configure(fg_color=hex_color)
            self._save_settings()
            self._schedule_style_refresh(immediate=True)

    def _cancel_style_refresh(self) -> None:
        if self._style_refresh_timer is not None:
            self.after_cancel(self._style_refresh_timer)
            self._style_refresh_timer = None

    def _schedule_style_refresh(self, *, immediate=False) -> None:
        session = self._edit_session
        if self._converting or session is None:
            return
        self._sync_page_style = True
        self._cancel_style_refresh()
        if immediate:
            self._refresh_page_style(session)
        else:
            self._style_refresh_timer = self.after(180, self._refresh_page_style, session)

    def _style_for_render(self) -> dict:
        return dict(font_path=self._current_font_path(), font_size=self.settings['font_size'],
                    text_color=_hex_to_rgb(self.settings['text_color']),
                    placement_mode=self.settings['placement_mode'], legend=self.settings['legend'],
                    notation_state=getattr(self, '_notation_request', None))

    def _restyle_page(self, session: dict) -> Image.Image | None:
        if self._page_cache is None:
            self._page_cache = tempfile.TemporaryDirectory(prefix='.쪽편집-', dir=self.output_dir)
        updated = _restyle_edit_session(session, self._page_cache.name, **self._style_for_render())
        if updated is None:
            return None
        try:
            with Image.open(updated['png']) as opened:
                image = opened.copy()
        except (ValueError, OSError):
            shutil.rmtree(updated['_style_folder'], ignore_errors=True)
            raise
        updated['report_settings'] = {
            **session.get('report_settings', {}),
            **{key: self.settings[key] for key in
               ('font', 'font_size', 'text_color', 'custom_font_path', 'placement_mode', 'legend')},
        }
        if updated['doc'] is not session['doc']:
            updated['report_settings'].update(
                {key: self.settings[key] for key in ('notation', 'key', 'minor')})
        previous = session.get('_style_folder')
        session.update(updated)
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
        return image

    def _refresh_page_style(self, session: dict) -> bool:
        self._style_refresh_timer = None
        if self._converting or self._edit_session is not session:
            return False
        previous_doc = session['doc']
        try:
            image = self._restyle_page(session)
        except (ValueError, OSError, RendererError) as error:
            self.log(f'표기를 다시 그리지 못했습니다 — 이전 결과 유지: {error}')
            return False
        if image is not None:
            if session['doc'] is not previous_doc:
                self._stop_listening()
                self._close_label_editor()
            self.result_path, self.labels_path = session['png'], session['json']
            self._preview_source = image
            self._update_page_controls()
            self._redraw_preview()
        return True

    def _flush_style_refresh(self) -> bool:
        if self._style_refresh_timer is None:
            return True
        self._cancel_style_refresh()
        return self._refresh_page_style(self._edit_session)

    def toggle_theme(self) -> None:
        mode = "dark" if self.settings["appearance"] == "light" else "light"
        self.settings["appearance"] = mode
        ctk.set_appearance_mode(mode)
        self.theme_btn.configure(text="☾" if mode == "light" else "☀")
        self.preview_canvas.configure(bg=self._apply_appearance_mode(UI_COLORS["canvas"]))
        if self._preview_source is None:
            self._draw_placeholder(getattr(self, "_preview_placeholder_message", None))
        self._update_editor_colors()
        self._save_settings()

    # ------------------------------------------------------------------
    # 파일/변환
    # ------------------------------------------------------------------
    def select_file(self) -> None:
        path = filedialog.askopenfilename(title="악보 파일 선택", filetypes=_filetypes_for_runtime(),
            initialdir=self.settings["last_input_dir"] if os.path.isdir(self.settings["last_input_dir"]) else None)
        if path:
            self._set_input(path)

    def select_images(self) -> None:
        paths = filedialog.askopenfilenames(title="처리할 악보 이미지 선택", filetypes=IMAGE_FILETYPES,
            initialdir=self.settings["last_input_dir"] if os.path.isdir(self.settings["last_input_dir"]) else None)
        if paths and not self._converting:
            self._set_input_files(paths)

    def _set_input_files(self, paths, *, keep_result=False):
        self._set_input(paths[0], keep_result=keep_result)
        self.input_paths = tuple(paths)
        if len(paths) > 1:
            self.file_label.configure(text=f"{os.path.basename(paths[0])} 외 {len(paths) - 1}장")
            self.log(f"이미지 {len(paths)}장 선택 — 선택한 순서대로 처리합니다.")

    @staticmethod
    def _existing_recent_files(paths):
        result, seen = [], set()
        for path in paths:
            if not isinstance(path, str) or not os.path.isabs(path) or not os.path.isfile(path):
                continue
            key = os.path.normcase(os.path.normpath(path))
            if key in seen:
                continue
            result.append(path)
            seen.add(key)
            if len(result) == 5:
                break
        return result

    def _load_recent_files(self):
        try:
            with open(self._recent_path, encoding="utf-8-sig") as file:
                paths = json.load(file)
        except (OSError, ValueError):
            return []
        return SheetHelperApp._existing_recent_files(paths) if isinstance(paths, list) else []

    def _remember_recent_files(self, paths):
        updated = self._load_recent_files()
        successful = [os.path.abspath(path) for path in paths if os.path.isfile(path)]
        if not successful:
            return
        updated = SheetHelperApp._existing_recent_files(successful + updated)
        staged = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=os.path.dirname(self._recent_path),
                    prefix=".recent-", delete=False) as file:
                staged = file.name
                json.dump(updated, file, ensure_ascii=False, indent=2)
            os.replace(staged, self._recent_path)
        except OSError as error:
            if staged is not None:
                try:
                    os.remove(staged)
                except OSError:
                    pass
            self.log(f"최근 악보 목록을 저장할 수 없습니다: {error}")

    def _show_recent_files(self):
        if self._converting:
            self.log("변환이 끝난 뒤 최근 악보를 열어 주세요.")
            return
        menu = self._recent_menu
        menu.delete(0, "end")
        paths = self._load_recent_files()
        if not paths:
            menu.add_command(label="최근 변환한 악보가 없습니다", state="disabled")
        else:
            for path in paths:
                name = os.path.basename(path)
                if sum(os.path.basename(p) == name for p in paths) > 1:
                    name = f"{name} — {os.path.basename(os.path.dirname(path))}"
                menu.add_command(label=name, command=lambda path=path: self._open_recent_file(path))
        try:
            menu.tk_popup(self.recent_btn.winfo_rootx(),
                          self.recent_btn.winfo_rooty() + self.recent_btn.winfo_height())
        finally:
            menu.grab_release()

    def _open_recent_file(self, path):
        if self._converting:
            self.log("변환이 끝난 뒤 최근 악보를 열어 주세요.")
        elif not os.path.isfile(path):
            self.log(f"최근 악보 파일을 찾을 수 없습니다: {os.path.basename(path)}")
        else:
            self.start_convert(dropped_paths=(path,))

    def _enable_file_drop(self, event):
        if event.widget is not self or self._windows_drop is not None or self._closing:
            return
        try:
            self._windows_drop = _WindowsFileDrop(self.winfo_id(), self._queue_dropped_files)
        except (OSError, AttributeError, TclError):
            return
        self._preview_placeholder_text = "악보 이미지를 끌어다 놓거나\nCtrl+V로 캡처를 붙여넣으세요"
        if self._preview_source is None:
            self._draw_placeholder(getattr(self, "_preview_placeholder_message", None))

    def _queue_dropped_files(self, paths):
        if self._closing:
            return
        self._pending_drops.append((paths, self._converting))
        if self._drop_timer is None:
            self._drop_timer = self.after_idle(self._process_dropped_files)

    def _process_dropped_files(self):
        self._drop_timer = None
        pending, self._pending_drops = self._pending_drops, []
        for paths, busy in pending:
            self._handle_dropped_files(paths, busy)

    def _handle_dropped_files(self, paths, busy=False):
        if self._closing:
            return
        if busy or self._converting:
            self.log("변환이 끝난 뒤 악보 파일을 끌어다 놓으세요.")
            return
        if paths is None:
            self.log("끌어다 놓은 파일의 경로를 읽지 못했습니다.")
            return
        if not paths:
            self.log("끌어다 놓은 파일이 없습니다.")
            return
        for path in paths:
            if os.path.isdir(path):
                self.log("폴더는 열 수 없습니다. 폴더 안의 악보 파일을 끌어다 놓으세요.")
                return
            if not os.path.isfile(path):
                self.log(f"파일을 찾을 수 없습니다: {os.path.basename(path)}")
                return
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf":
                if getattr(sys, "frozen", False):
                    self.log(_PDF_EXE_MESSAGE)
                    return
                if len(paths) > 1:
                    self.log("여러 파일을 한꺼번에 열 때는 악보 이미지만 끌어다 놓으세요.")
                    return
            elif ext not in _IMAGE_EXTENSIONS:
                self.log(f"지원하지 않는 파일 형식입니다: {os.path.basename(path)}")
                return
        self.start_convert(dropped_paths=tuple(paths))

    def _paste_clipboard_image(self, event=None):
        if event is not None and self._typing_input(event):
            return
        if self._converting:
            self.log('변환이 끝나면 클립보드 이미지를 붙여넣을 수 있습니다.')
            return 'break'
        path = None
        try:
            captured = ImageGrab.grabclipboard()
            if not isinstance(captured, Image.Image):
                self.log('클립보드에 이미지가 없습니다. 악보를 캡처한 뒤 다시 붙여넣으세요.')
                return 'break'
            with captured:
                folder = os.path.join(self.output_dir, '붙여넣은 악보')
                os.makedirs(folder, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=folder, prefix='캡처-', suffix='.png', delete=False) as handle:
                    path = handle.name
                    if 'A' in captured.getbands() or 'transparency' in captured.info:
                        with captured.convert('RGBA') as rgba, Image.new('RGB', captured.size, 'white') as white:
                            white.paste(rgba, mask=rgba.getchannel('A'))
                            white.save(handle, format='PNG')
                    elif captured.mode == 'RGB':
                        captured.save(handle, format='PNG')
                    else:
                        with captured.convert('RGB') as image:
                            image.save(handle, format='PNG')
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            if path is not None:
                try:
                    os.remove(path)
                except OSError:
                    pass
            self.log(f'클립보드 이미지를 붙여넣지 못했습니다 — {error}')
            return 'break'
        self._set_input(path, remember_directory=False)
        self.start_convert()
        return 'break'

    def _set_input(self, path: str, *, remember_directory=True, keep_result=False) -> None:
        if self._converting:
            return
        if remember_directory and os.path.isfile(path):
            self.settings["last_input_dir"] = os.path.dirname(os.path.abspath(path))
            self._save_settings()
        if not keep_result:
            self._stop_listening()
            self._close_label_editor()
            self._edit_session = None
            self._clear_result_pages()
            self._region_start = None
            if getattr(self, 'region_check', None) is not None:
                self.region_check.deselect()
            self.edit_btn.configure(state="disabled")
        self.input_path = path
        self.input_paths = (path,)
        self.file_label.configure(text=os.path.basename(path), text_color=("gray15", "gray85"))
        self.log(f"파일 선택: {os.path.basename(path)}")
        if keep_result:
            return

        # 결과가 아직 없는 원본 상태이므로 크게보기/저장 버튼은 다시 비활성화
        self.result_path = None
        self.labels_path = None
        self._review_index = None
        self._update_review_controls()
        self.open_result_btn.configure(state="disabled")
        self.save_as_btn.configure(state="disabled")
        self.report_btn.configure(state="disabled")

        if os.path.splitext(path)[1].lower() == ".pdf":
            # PDF는 PIL로 직접 미리보기가 안 되므로 안내만 표시
            self._preview_source = None
            self._draw_placeholder("PDF 파일이 선택되었습니다\n\n[계이름 달기]를 누르면 변환 결과가 여기에 표시돼요")
            return

        self._load_preview_image(path)

    def _retry_photo(self) -> None:
        if self._converting:
            return
        self.photo_check.select()
        self._on_setting_changed()
        self.start_convert()

    def start_convert(self, *, dropped_paths=()) -> None:
        if self._converting:
            return
        input_path = dropped_paths[0] if dropped_paths else self.input_path
        if not input_path:
            self.log("⚠ 먼저 악보 파일을 선택해주세요.")
            return
        if getattr(sys, "frozen", False) and input_path.lower().endswith(".pdf"):
            self.log(_PDF_EXE_MESSAGE)
            return

        self._run_key_override, key_valid, message = self._validated_key_entry()
        if not key_valid:
            self._update_key_feedback()
            self.log(f"⚠ {message}")
            return
        previous = None
        output_dir = self.output_dir
        if dropped_paths:
            if self.result_path is not None or self._edit_session is not None:
                # 같은 이름의 PNG·JSON도 실패한 변환에서 덮어쓰지 않는다.
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    output_dir = tempfile.mkdtemp(prefix="드롭-", dir=output_dir)
                except OSError as error:
                    self.log(f"❌ 드롭 결과 폴더를 만들 수 없습니다: {error}")
                    return
                names = ("input_path", "input_paths", "result_path", "labels_path",
                         "_edit_session", "_page_sessions", "_page_index", "_page_cache",
                         "_review_index", "_region_start")
                region = getattr(self, 'region_check', None)
                previous = _PreviousDropResult({name: getattr(self, name) for name in names},
                                               self.file_label.cget("text"), bool(region and region.get()))
            self._set_input_files(dropped_paths, keep_result=previous is not None)

        self._run_minor = bool(self.minor_check.get())
        self._run_photo = bool(self.photo_check.get())
        self._run_legend = bool(self.legend_check.get())
        self._run_all_pages = (bool(self.all_pages_check.get())
                               and self.input_path.lower().endswith(".pdf"))
        self._run_input_paths = getattr(self, "input_paths", (self.input_path,))

        try:
            page = max(0, int(self.page_entry.get().strip() or "1") - 1)
        except ValueError:
            page = 0
        saved_settings = dict(self.settings, clef=self.clef_menu.get(),
            notation=self.notation_menu.get(), key=self._run_key_override,
            placement_mode=PLACEMENT_LABELS.get(self.placement_menu.get(),"near"),
            minor=self._run_minor, photo=self._run_photo, legend=self._run_legend)
        self._run_request = _ConversionRequest(
            tuple(self._run_input_paths), output_dir, page, self._run_all_pages,
            CLEF_LABELS.get(saved_settings['clef'], 'auto'),
            NOTATION_LABELS.get(saved_settings['notation'], 'solfege-fixed'),
            self._run_key_override, self._run_minor, self._run_photo, self._run_legend,
            self._current_font_path(), int(self.settings['font_size']),
            _hex_to_rgb(self.settings['text_color']), tuple(saved_settings.items()), previous)
        self._stop_listening()
        self._close_label_editor()
        if previous is not None:
            self._page_cache = None
        self._clear_result_pages()
        self._edit_session = None
        self._region_start = None
        if getattr(self, 'region_check', None) is not None:
            self.region_check.deselect()
        self.edit_btn.configure(state="disabled")
        self._converting = True
        self.convert_btn.configure(state="disabled", text="변환 중...")
        if self._run_all_pages:
            self._set_conversion_progress(0, 0, "쪽 수 확인 중…")
        else:
            self._set_conversion_progress(1, len(self._run_input_paths))
        try:
            threading.Thread(target=self._convert_worker, daemon=True).start()
        except RuntimeError as exc:
            self._converting = False
            if previous is not None:
                self._finish_drop_result(self._run_request, False)
            self._run_request = None
            self.convert_btn.configure(state="normal", text="✨ 계이름 달기")
            self._conversion_status = None
            self._update_page_controls()
            self.log(f"❌ 변환 시작 실패: {exc}")

    def _finish_drop_result(self, request, published):
        previous = request.previous_drop
        if published:
            cache = previous.state["_page_cache"]
            if cache is not None:
                cache.cleanup()
            return
        self._clear_result_pages()
        shutil.rmtree(request.output_dir, ignore_errors=True)
        vars(self).update(previous.state)
        self.file_label.configure(text=previous.file_text)
        if previous.region_selected:
            self.region_check.select()
        self.edit_btn.configure(state="normal" if self._edit_session else "disabled")
        self.log("새 악보 변환을 완료하지 못해 이전 결과를 유지했습니다.")

    def _convert_worker(self) -> None:
        request = getattr(self, '_run_request', None)
        input_path = request.input_paths[0] if request else self.input_path
        output_dir = request.output_dir if request else self.output_dir
        published = False
        recent_paths = (input_path,)
        photo_retry = False
        photo = request.photo if request else getattr(self, '_run_photo', False)
        try:
            input_paths = request.input_paths if request else getattr(self, "_run_input_paths", (input_path,))
            if len(input_paths) > 1:
                done, failed = [], []
                for number, path in enumerate(input_paths, 1):
                    self.after(0, lambda n=number, t=len(input_paths): self._set_conversion_progress(n, t))
                    self.log(f"이미지 {number}/{len(input_paths)}장 처리 중: {os.path.basename(path)}")
                    try:
                        out_path = self._convert_page(0, f"_p{number}", source_path=path)
                        done.append((path, out_path, self.labels_path))
                    except Exception as e:
                        failed.append(number)
                        message = conversion_failure_message(e, path) or f"{type(e).__name__}: {e}"
                        self.log(f"❌ {number}번째 이미지 실패: {message}")
                        photo_retry |= not photo and isinstance(e, StaffNotFoundError) and not isinstance(e, PhotoRejectedError)
                if done:
                    self.after(0, lambda t=len(input_paths): self._set_conversion_progress(t, t, "결과 합치는 중…"))
                    base = os.path.splitext(os.path.basename(input_paths[0]))[0]
                    pdf_path = os.path.join(output_dir, f"{base}_계이름_전체.pdf")
                    _save_image_pages_pdf((path for _, path, _ in done), pdf_path)
                    input_path, self.result_path, self.labels_path = done[0]
                    recent_paths = tuple(path for path, _, _ in done)
                    published = True
                    self.log(f"✅ 합친 PDF: {pdf_path}")
                self.log(f"전체 {len(input_paths)}장: 성공 {len(done)} · 실패 {len(failed)}"
                         + (f" (실패한 순서: {', '.join(map(str, failed))})" if failed else ""))
            elif (request.all_pages if request else self._run_all_pages):
                import fitz
                with fitz.open(input_path) as source:
                    total = len(source)
                done, failed = [], []
                for page in range(total):
                    self.after(0, lambda n=page+1, t=total: self._set_conversion_progress(n, t))
                    self.log(f"PDF {page + 1}/{total}쪽 처리 중...")
                    try:
                        out_path = self._convert_page(page, f"_p{page + 1}")
                        done.append((page, out_path, self.labels_path))
                    except Exception as e:
                        failed.append(page + 1)
                        message = conversion_failure_message(e, input_path) or f"{type(e).__name__}: {e}"
                        self.log(f"❌ {page + 1}쪽 실패: {message}")
                        photo_retry |= not photo and isinstance(e, StaffNotFoundError) and not isinstance(e, PhotoRejectedError)
                if done:
                    self.after(0, lambda t=total: self._set_conversion_progress(t, t, "결과 합치는 중…"))
                    base = os.path.splitext(os.path.basename(input_path))[0]
                    pdf_path = os.path.join(output_dir, f"{base}_계이름_전체.pdf")
                    with fitz.open(input_path) as source, fitz.open() as output:
                        for page, path, _ in done:
                            rect = source[page].rect
                            output_page = output.new_page(width=rect.width, height=rect.height)
                            output_page.insert_image(output_page.rect, filename=path)
                        output.save(pdf_path)
                    self.result_path, self.labels_path = done[0][1:]
                    published = True
                    self.log(f"✅ 합친 PDF: {pdf_path}")
                self.log(f"전체 {total}쪽: 성공 {len(done)} · 실패 {len(failed)}"
                         + (f" (실패한 쪽: {', '.join(map(str, failed))})" if failed else ""))
            else:
                if request:
                    page = request.page
                else:
                    try:
                        page = max(0, int(self.page_entry.get().strip() or "1") - 1)
                    except ValueError:
                        page = 0
                out_path = self._convert_page(page, "")
                self.result_path = out_path
                published = True
                self.log(f"✅ 완료! 저장 위치: {out_path}")

        except PhotoRejectedError as e:
            self.log("❌ " + conversion_failure_message(e, input_path))
        except (
            SheetMusicImageError, StaffNotFoundError, NoteheadDetectionError,
            UnsupportedClefError, UnknownNoteNameError, RendererError,
        ) as e:
            from main import _user_text
            self.log(f"❌ 오류: {conversion_failure_message(e, input_path) or _user_text(e)}")
            photo_retry = not photo and isinstance(e, StaffNotFoundError)
        except Exception as e:
            message = conversion_failure_message(e, input_path)
            if message:
                self.log("❌ " + message)
            else:
                self.log("❌ 예상치 못한 오류가 발생했습니다:")
                self.log(traceback.format_exc(limit=3))
        finally:
            def finished():
                # 실패 중 공개된 JSON을 이전 PNG와 섞지 않는다. 저장한 파일은 남긴다.
                previous_drop = getattr(request, 'previous_drop', None)
                if previous_drop is not None:
                    self._finish_drop_result(request, published)
                elif not published:
                    self.result_path = self.labels_path = None
                    self._edit_session = None
                    self._clear_result_pages()
                    for button in (self.open_result_btn, self.save_as_btn, self.report_btn, self.edit_btn):
                        button.configure(state="disabled")
                    self._preview_source = None
                    self._draw_placeholder("완료된 결과가 없습니다. 오류를 확인한 뒤 다시 변환해 주세요.")
                self._converting = False
                self._run_request = None
                self._conversion_status = None
                self.convert_btn.configure(state="normal", text="✨ 계이름 달기")
                if getattr(self, 'photo_retry_btn', None) is not None:
                    if photo_retry and previous_drop is None:
                        self.photo_retry_btn.grid()
                    else:
                        self.photo_retry_btn.grid_remove()
                if published:
                    # 완료 결과를 공개하는 순간에는 쪽 넘기기/편집 잠금이 이미 풀려 있다.
                    self._show_result()
                    if getattr(self, '_recent_path', None) is not None:
                        self._remember_recent_files(recent_paths)
                elif getattr(self, 'page_nav', None) is not None:
                    self._update_page_controls()
            self.after(0, finished)

    @with_mask_cache
    def _convert_page(self, page: int, suffix: str, source_path: str | None = None) -> str:
        request = getattr(self, '_run_request', None)
        input_path = source_path or (request.input_paths[0] if request else self.input_path)
        # 쪽마다 헤더만 검사한다. 큰 이미지 한 장이 실패해도 나머지 쪽은 계속 처리한다.
        if not input_path.lower().endswith('.pdf'):
            try:
                with Image.open(input_path):
                    pass
            except OSError:
                pass  # 읽기 실패 안내는 기존 전처리 경로가 담당한다.
        output_dir = request.output_dir if request else self.output_dir
        clef = request.clef if request else CLEF_LABELS.get(self.clef_menu.get(), "auto")
        font_path = request.font_path if request else self._current_font_path()
        font_size = request.font_size if request else int(self.settings["font_size"])
        text_color = request.text_color if request else _hex_to_rgb(self.settings["text_color"])
        photo = request.photo if request else self._run_photo
        legend = request.legend if request else getattr(self, '_run_legend', False)
        os.makedirs(output_dir, exist_ok=True)

        self.log("─" * 30)
        self.log("1/5 오선 검출 중...")
        if photo:
            result = preprocess(input_path, pdf_page=page, photo=True)
        else:
            result = preprocess(input_path, pdf_page=page)
        self.log(f"    {staff_count_confirmation(len(result.staves))}")

        contexts = analyze_staves(result)
        found = [c for c in contexts.values() if c.clef_found]
        if found:
            n_treble = sum(1 for c in contexts.values() if c.clef == "treble")
            n_bass = len(contexts) - n_treble
            self.log(f"    음자리표: 높은 {n_treble}개 / 낮은 {n_bass}개")
            if found[0].key_count > 0:
                self.log(f"    조표: {found[0].key_symbol} {found[0].key_count}개")

        self.log("2/5 음표 검출 중...")
        noteheads = detect_noteheads(result, contexts=contexts)
        from main import _filter_noteheads, _filter_accidentals, _diagnose_named_notes, _build_result_document, _confidence_values
        noteheads, beam_ghosts, glyph_ghosts = _filter_noteheads(result, noteheads)
        self.log(f"    음표 {len(noteheads)}개 검출"
                 + (f" (빔에서 온 유령 {len(beam_ghosts)}개 제외)" if beam_ghosts else "")
                 + (f" (덧줄 없는 글리프 {len(glyph_ghosts)}개 제외)" if glyph_ghosts else ""))

        self.log("3/5 음 높이 계산 중...")
        if clef == "auto":
            clef_arg = {idx: c.clef for idx, c in contexts.items()}
        else:
            clef_arg = clef
        pitched = calculate_pitches(noteheads, result.staves, clef=clef_arg)

        self.log("4/5 계이름 변환 중...")
        before_accidentals = len(pitched)
        pitched, accidentals, accidental_candidates = _filter_accidentals(result, contexts, pitched, noteheads)
        accidental_removed = before_accidentals - len(pitched)
        n_acc = sum(1 for a in accidentals if a)
        if n_acc:
            self.log(f"    임시표 {n_acc}개 반영")
        key_letters, key_symbol = (), ""
        if found:
            key_letters, key_symbol = found[0].key_letters, found[0].key_symbol
        notation = (request.notation if request else NOTATION_LABELS.get(self.notation_menu.get(), "solfege-fixed"))
        tonic = ""
        key_override = (request.key if request else getattr(self, "_run_key_override", ""))
        minor = bool((request.minor if request else self._run_minor) and key_override)
        if notation == "solfege-movable":
            from modules.note_namer import resolve_tonic, UnknownNoteNameError as _KeyError
            try:
                tonic = resolve_tonic(key_symbol, len(key_letters), key_override, minor)
            except _KeyError:
                self.log(f"    ⚠ 조성 '{key_override}'을 알 수 없어 조표대로 읽습니다.")
                tonic = resolve_tonic(key_symbol, len(key_letters))
                key_override = ""
            if key_override:
                self.log(f"    이동도: 으뜸음 '도' = {tonic}"
                         f" (지정 {key_override}{'단조' if minor else '장조'})")
            else:
                self.log(f"    이동도: 으뜸음 '도' = {tonic}"
                         f" (조표 {key_symbol or '없음'}{len(key_letters)}개)")
        rare_warnings: list = []
        named = to_solfege_batch(pitched, key_letters, key_symbol, accidentals,
                                 notation, rare_warnings, tonic)
        # CLI와 같은 진단 결과를 화면 스타일과 JSON이 함께 쓴다.
        pitched, accidentals, named, diag_rows, label_keys, chord_removed = _diagnose_named_notes(
            result, contexts, clef_arg, noteheads, pitched, accidentals, named,
            accidental_candidates, key_letters, key_symbol, notation, tonic, rare_warnings,
            photo=photo, keep_tonic=bool(key_override),
            report_rescue=lambda added, deleted: self.log(f"    붙은 화음: 라벨 {added}개 추가 · 가운데 유령 {deleted}개 제외"))
        for w in rare_warnings:
            self.log(f"    [확인 필요] {w['note_name']}{w['octave']}{w['accidental']}"
                     f" -> '{w['text']}' (x={w['x']}, y={w['y']})")
        confidences = _confidence_values(diag_rows, named)

        self.log("5/5 결과 이미지 생성 중...")
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_path = os.path.join(output_dir, f"{base}{suffix}_계이름.png")
        mode=(dict(request.report_settings) if request else self.settings).get('placement_mode','near')
        layout_status={}
        placement_options=({'placement_mode':'lanes','layout_status':layout_status} if mode=='lanes' else {})
        from modules.labels_io import save_labels
        labels_path = os.path.join(output_dir, f"{base}{suffix}_라벨.json")
        doc = _build_result_document(
            input_path, page, result.staves, named,
            result.original_bgr.shape,
            accidentals=accidentals,
            diag_rows=diag_rows,
            contexts=contexts,
            key_symbol=key_symbol, key_letters=tuple(key_letters),
            tonic=tonic, minor=minor, notation=notation,
            label_keys=label_keys,
        )
        from modules.result_legend import annotation_writer, clef_warnings, legend_font_size
        spacings = [s.spacing for s in result.staves]
        header_options = dict(symbol=key_symbol, count=len(key_letters), font_path=font_path,
            spacings=spacings, setting_size=font_size,
            user_key=(key_override if notation == 'solfege-movable' else ''),
            first_staff_top=min((s.top for s in result.staves), default=None))
        legend_options = (dict(font_path=font_path, font_size=legend_font_size(spacings, font_size))
                          if legend and not photo else None)
        writer, annotations = annotation_writer(
            out_path, header=dict(header_options, labels=doc['labels']), legend=legend_options)
        clear_mask_cache()
        placements = render_solfege_on_image(
            result.original_bgr, named, out_path,
            font_path=font_path, font_size=font_size, text_color=text_color,
            text_offset_y=max(14, font_size + 4),
            staff_spacings={s.index: s.spacing for s in result.staves},
            staves=result.staves,
            confidences=confidences, image_writer=writer, **placement_options,
        )
        for warning in clef_warnings(doc["labels"]):
            self.log("    " + warning)
        if not annotations["header"]:
            self.log("    조표 표시를 넣을 빈 상단 여백이 없습니다.")
        if legend and photo:
            self.log("    사진 입력에서는 표시 안내를 생략했습니다.")
        elif legend and not annotations["legend"]:
            self.log("    표시 안내를 넣을 밝은 여백이 없어 생략했습니다.")

        # 결과와 수정 가능한 라벨 목록을 항상 한 쌍으로 남긴다.
        save_labels(labels_path, doc)
        self.labels_path = labels_path
        session = dict(
            original_doc=doc, doc=doc, changes=[], image=result.original_bgr,
            source_path=input_path,
            report_settings=(dict(request.report_settings) if request else dict(self.settings)),
            original_png=out_path, original_json=labels_path,
            original_placements=placements, placements=placements,
            render_options=dict(font_path=font_path, font_size=font_size,
                text_color=text_color, text_offset_y=max(14, font_size + 4),
                staff_spacings={s.index: s.spacing for s in result.staves}, staves=result.staves),
            header_options=header_options, legend_options=legend_options,
            recognition_exclusions=dict(beam=len(beam_ghosts), offstaff=len(glyph_ghosts),
                                        accidental=accidental_removed, chord=chord_removed),
        )
        if mode=='lanes':session['render_options']['placement_mode']='lanes'
        notice=layout_status.get('message','')
        session.update(png=out_path, json=labels_path,placement_notice=notice,original_placement_notice=notice)
        if notice:self.log(notice)
        sessions = getattr(self, '_page_sessions', [])
        batch = ((len(request.input_paths) > 1 or request.all_pages) if request else
                 (len(getattr(self, '_run_input_paths', (input_path,))) > 1 or getattr(self, '_run_all_pages', False)))
        if batch:
            # 쪽마다 큰 배열을 메모리에 남기지 않고 무손실 프레임을 임시 폴더에 둔다.
            if getattr(self, '_page_cache', None) is None:
                self._page_cache = tempfile.TemporaryDirectory(prefix='.쪽편집-', dir=output_dir)
            session['frame_path'] = os.path.join(self._page_cache.name, f'{len(sessions)}.png')
            Image.fromarray(result.original_bgr[:, :, ::-1]).save(session['frame_path'])
        if getattr(self, '_edit_session', None) is None:
            self._edit_session = session
        else:
            session['image'] = None
        sessions.append(session)
        self._page_sessions = sessions
        self.log(f"    라벨 JSON 저장: {labels_path}")
        self.log(f"    {_recognition_summary(session)}")

        return out_path

    # ------------------------------------------------------------------
    # 결과 표시 / 미리보기(원본·결과 공용, 캔버스 기반 확대·축소)
    # ------------------------------------------------------------------
    def _clear_result_pages(self) -> None:
        if getattr(self, 'photo_retry_btn', None) is not None:
            self.photo_retry_btn.grid_remove()
        self._page_sessions = []
        self._page_index = 0
        cache = getattr(self, '_page_cache', None)
        if cache is not None:
            cache.cleanup()
        self._page_cache = None
        self._sync_page_style = False
        self._notation_request = None
        if getattr(self, '_style_refresh_timer', None) is not None:
            self._cancel_style_refresh()
        self._update_page_controls()

    def _set_conversion_progress(self, number: int, total: int, phase: str = "") -> None:
        """작업 스레드가 after로 전달한 진행 상태만 GUI 스레드에서 표시한다."""
        self._conversion_status = (number, total, phase)
        self._update_page_controls()

    def _update_placement_notice(self) -> None:
        if getattr(self,'placement_notice',None) is not None:
            session=self._edit_session or {}
            requested=self.settings.get('placement_mode','near')
            rendered=session.get('render_options',{}).get('placement_mode','near')
            notice=session.get('placement_notice','') if requested==rendered=='lanes' else ''
            self.placement_notice.configure(text=notice)
            self.placement_notice.grid() if notice else self.placement_notice.grid_remove()

    def _update_style_save_notice(self) -> None:
        session = self._edit_session or {}
        saved = session.get('_style_saved_png')
        png = self.result_path
        show = (not self._converting and self._page_cache is not None and png
                and os.path.dirname(png) == session.get('_style_folder'))
        if show and saved and os.path.isfile(saved):
            try:
                show = not filecmp.cmp(png, saved, shallow=False)
            except OSError:
                pass
        self.style_save_notice.grid() if show else self.style_save_notice.grid_remove()

    def _update_page_controls(self) -> None:
        if getattr(self,'placement_notice',None) is not None:
            self._update_placement_notice()
        if getattr(self, 'style_save_notice', None) is not None:
            self._update_style_save_notice()
        if getattr(self, 'review_nav', None) is not None:
            self._update_review_controls()
        count = len(self._page_sessions)
        if getattr(self, 'export_pages_btn', None) is not None:
            self.export_pages_btn.configure(state='normal' if count > 1 and not self._converting else 'disabled')
        normal_color = ctk.ThemeManager.theme['CTkButton']['fg_color']
        for button, available in ((self.prev_page_btn, self._page_index > 0),
                                  (self.next_page_btn, self._page_index < count - 1)):
            enabled = not self._converting and count > 0 and available
            button.configure(state='normal' if enabled else 'disabled',
                             fg_color=normal_color if enabled else ('gray75', 'gray30'))
            button.grid() if count > 1 and not self._converting else button.grid_remove()
        progress = getattr(self, 'page_progress', None)
        if self._converting:
            number, total, phase = getattr(self, '_conversion_status', None) or (1, 1, '')
            self.page_nav.grid()
            message = phase or f'{number}쪽 처리 중…'
            self.page_label.configure(text=message + (f' · {number} / {total} 처리 중' if total else ''))
            if progress is not None:
                progress.pack(fill='x', padx=8, pady=(0, 6))
                progress.configure(mode='indeterminate')
                progress.start()  # 비율을 추측하지 않고 무거운 쪽 안에서도 활동을 표시한다.
            return
        if progress is not None:
            progress.stop()
            progress.configure(mode='determinate')
            progress.set(1 if count else 0)
            progress.pack_forget()
        if count:
            self.file_label.configure(text=os.path.basename(self._page_sessions[self._page_index]['source_path']))
        session = self._page_sessions[self._page_index] if count else getattr(self, '_edit_session', None)
        if session is None or (not count and not session.get('source_path')):
            self.page_nav.grid_remove()
            return
        self.page_nav.grid()
        position = f'{self._page_index + 1} / {count} · ' if count else ''
        source = session.get('original_doc', {}).get('source', {})
        name = os.path.basename(session.get('source_path') or source.get('file') or '악보')
        page = source.get('page', 0) + 1
        self.page_label.configure(text=f"{position}{name} · {page}쪽\n{_recognition_summary(session)}")

    def _select_result_page(self, index: int) -> bool:
        if self._converting or not 0 <= index < len(self._page_sessions) or index == self._page_index:
            return False
        current = self._edit_session
        target = self._page_sessions[index]
        previous_frame = target['image']
        styled = None
        try:
            if not os.path.isfile(target['json']):
                raise ValueError('라벨 JSON이 없습니다.')
            with Image.open(target['png']) as preview:
                preview.load()
            if previous_frame is None:
                target['image'] = _read_page_frame(target['frame_path'])
            if getattr(self, '_sync_page_style', False):
                styled = self._restyle_page(target)
        except (OSError, ValueError, KeyError, RendererError) as exc:
            target['image'] = previous_frame
            self.log(f'쪽을 열지 않았습니다 — 이전 결과 유지: {exc}')
            return False
        if getattr(self, '_style_refresh_timer', None) is not None:
            self._cancel_style_refresh()
        self._stop_listening()
        self._close_label_editor()
        current.update(png=self.result_path, json=self.labels_path)
        if current.get('frame_path'):
            current['image'] = None
        self._page_index = index
        self._edit_session = target
        self.result_path, self.labels_path = target['png'], target['json']
        self._region_start = None
        if getattr(self, 'region_check', None) is not None:
            self.region_check.select() if target.get('region') else self.region_check.deselect()
        if styled is None:
            self._show_result()
        else:
            self._show_result(styled)
        return True

    def _show_result(self, preview: Image.Image | None = None) -> None:
        self._update_page_controls()
        self.open_result_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self.save_as_btn.configure(state="normal")
        self.report_btn.configure(state="normal" if self.labels_path else "disabled")
        self.edit_btn.configure(state="normal" if self._edit_session else "disabled")
        self._load_preview_image(self.result_path, preview)

    def _load_preview_image(self, path: str, img: Image.Image | None = None) -> None:
        self._preview_original = False
        self._review_index = None
        try:
            if img is None:
                with Image.open(path) as opened:
                    img = opened.copy()
        except (OSError, Image.DecompressionBombError) as error:
            self._preview_source = None
            self._update_review_controls()
            self._draw_placeholder(conversion_failure_message(error, path) or "이미지를 불러오지 못했습니다")
            return
        self._preview_source = img
        self._update_review_controls()
        self.after(0, self._fit_zoom)

    def _preview_resized(self, _event=None):
        if self._preview_source is None:
            self._draw_placeholder(getattr(self, "_preview_placeholder_message", None))
        else:
            self._schedule_preview_tile()

    def _draw_placeholder(self, text: str | None = None) -> None:
        self._preview_original = False
        self._cancel_preview_tile()
        self.preview_canvas.delete("all")
        self._preview_photo = None
        canvas = self.preview_canvas
        canvas.configure(scrollregion=(0, 0, 0, 0))
        self._preview_placeholder_message = text
        cx, cy = canvas.winfo_width() / 2, canvas.winfo_height() / 2
        half_width = min(270, max(80, cx - 24))
        half_height = min(125, max(70, cy - 24))
        x0, x1, y0, y1 = cx - half_width, cx + half_width, cy - half_height, cy + half_height
        radius = 18
        canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, fill=self._apply_appearance_mode(UI_COLORS["surface"]),
            outline=self._apply_appearance_mode(UI_COLORS["button_border"]), dash=(5, 5),
            tags="preview-placeholder")
        canvas.create_text(cx, cy-66, text="♫", font=("맑은 고딕", 36),
            fill=self._apply_appearance_mode(UI_COLORS["muted"]), tags="preview-placeholder")
        canvas.create_text(cx, cy, text=text or self._preview_placeholder_text, justify="center",
            width=max(120, 2*half_width-40), font=("맑은 고딕", 14),
            fill=self._apply_appearance_mode(UI_COLORS["text"]), tags="preview-placeholder")
        canvas.create_text(cx, cy+77, text="Ctrl+V · V 원본 비교 · F1 단축키", font=("맑은 고딕", 10),
            fill=self._apply_appearance_mode(UI_COLORS["muted"]), tags="preview-placeholder")

    def _fit_zoom(self) -> None:
        if self._preview_source is None:
            return
        self.preview_canvas.update_idletasks()
        cw = max(50, self.preview_canvas.winfo_width())
        ch = max(50, self.preview_canvas.winfo_height())
        iw, ih = self._preview_source.size
        fit_w, fit_h = cw / iw, ch / ih

        if fit_w >= 1.0 and fit_h >= 1.0:
            # 이미지가 원본 크기로도 패널에 다 들어가면 확대하지 않고 100%로 표시
            # (작은 이미지를 억지로 키우면 화질이 떨어지고, 어차피 여백이 정상이다)
            zoom = 1.0
        else:
            # 세로로 긴 악보(대부분의 스캔본)가 정사각형에 가까운 패널에 들어가면
            # min()으로 맞추면 좌우에 큰 여백이 남는다. 두 축 중 '더 꽉 채우는'
            # 쪽 비율(max)로 맞춰 여백을 없애고, 넘치는 축은 스크롤로 본다
            # (PDF 뷰어의 '폭에 맞춤'과 동일한 방식).
            zoom = max(fit_w, fit_h)

        self._preview_zoom = max(0.02, zoom)
        self._redraw_preview()

    def _preview_view_changed(self, scrollbar, first, last):
        scrollbar.set(first, last)
        self._schedule_preview_tile()

    def _cancel_preview_tile(self):
        timer = self._preview_tile_after
        if timer is not None:
            self.after_cancel(timer)
            self._preview_tile_after = None

    def _schedule_preview_tile(self):
        if self._preview_source is not None and not self._closing:
            self._cancel_preview_tile()
            self._preview_tile_after = self.after(_PREVIEW_REDRAW_MS, self._draw_preview_tile)

    def _preview_extent(self):
        return tuple(max(1, int(length * self._preview_zoom)) for length in self._preview_source.size)

    def _clear_preview_tile(self):
        self.preview_canvas.delete("preview-tile")
        self._preview_photo = None

    def _preview_original_frame(self):
        if self._edit_session is None or self._preview_source is None:
            return None
        frame = self._edit_session.get('image')
        if frame is not None and (frame.shape[1], frame.shape[0]) == self._preview_source.size:
            return frame
        return None

    def _toggle_preview_original(self):
        if self._converting or self._preview_original_frame() is None:
            return
        self._region_start = None
        self._preview_original = not self._preview_original
        self._update_review_controls()
        self._redraw_preview()

    def _draw_preview_tile(self):
        self._preview_tile_after = None
        source = self._preview_source
        if source is None:
            return
        canvas = self.preview_canvas
        width, height = self._preview_extent()
        x, y = canvas.canvasx(0), canvas.canvasy(0)
        left = max(0, floor(x) - _PREVIEW_MARGIN)
        top = max(0, floor(y) - _PREVIEW_MARGIN)
        right = min(width, ceil(x + canvas.winfo_width()) + _PREVIEW_MARGIN)
        bottom = min(height, ceil(y + canvas.winfo_height()) + _PREVIEW_MARGIN)
        self._clear_preview_tile()
        if right <= left or bottom <= top:
            return
        resample = Image.Resampling.LANCZOS if self._preview_zoom <= 2.0 else Image.Resampling.NEAREST
        original = self._preview_original_frame() if self._preview_original else None
        with _resize_preview_tile(source, (width, height), (left, top, right, bottom), resample,
                                  original_bgr=original) as tile:
            self._preview_photo = ImageTk.PhotoImage(tile, master=canvas)
        item = canvas.create_image(left, top, anchor="nw", image=self._preview_photo, tags="preview-tile")
        canvas.tag_lower(item)

    def _redraw_preview(self, *, deferred=False) -> None:
        if self._preview_source is None:
            self._draw_placeholder()
            return
        self._cancel_preview_tile()
        canvas = self.preview_canvas
        canvas.delete("preview-placeholder", "label-selection", "region")
        canvas.configure(scrollregion=(0, 0, *self._preview_extent()))
        if deferred:
            self._clear_preview_tile()
            self._schedule_preview_tile()
        else:
            self._draw_preview_tile()
        z = self._preview_zoom
        box = None if self._preview_original else self._selected_preview_box()
        if box is not None:
            self.preview_canvas.create_rectangle(
                (box['x'] - 3) * z, (box['y'] - 3) * z,
                (box['x'] + box['w'] + 3) * z, (box['y'] + box['h'] + 3) * z,
                outline='#0066cc', width=2, tags='label-selection')

        region = self._edit_session.get('region') if self._edit_session and not self._preview_original else None
        if region is not None:
            self.preview_canvas.create_rectangle(
                *(v * z for v in region), outline='#1676c4', width=2, tags='region')

        self._draw_audio_overlay()
        self._update_piano_keys()

    def _review_indices(self) -> list:
        if not self._edit_session:
            return []
        labels = self._edit_session['doc']['labels']
        # 사용자가 수정한 라벨은 진하게 그려지므로 다시 확인할 목록에서 제외한다.
        return sorted((i for i, label in enumerate(labels)
                       if label['confidence'] in ('check', 'caution') and not label.get('edited')),
                      key=lambda i: (labels[i]['staff'], labels[i]['x'], labels[i]['y'], i))

    def _update_review_controls(self) -> None:
        indices = self._review_indices()
        selected = self._review_index
        position = indices.index(selected) if selected in indices else None
        self.review_label.configure(text=(f"확인 필요·주의 {position + 1 if position is not None else 0} / {len(indices)}"
                                          if indices else "확인 필요 없음"))
        color = ctk.ThemeManager.theme['CTkButton']['fg_color']
        ready = not self._converting and self._preview_source is not None
        if getattr(self, 'preview_compare_btn', None) is not None:
            compare_ready = ready and self._preview_original_frame() is not None
            self.preview_compare_btn.configure(
                text='결과 보기' if self._preview_original else '원본 보기',
                state='normal' if compare_ready else 'disabled',
                fg_color=UI_COLORS['compare_active'] if self._preview_original else color,
                text_color=UI_COLORS['compare_text'] if self._preview_original else UI_COLORS['text'])
        for button, available in ((self.prev_review_btn, position is None or position > 0),
                                  (self.next_review_btn, position is None or position < len(indices) - 1)):
            enabled = bool(indices) and available and ready
            button.configure(state='normal' if enabled else 'disabled',
                             fg_color=color if enabled else ('gray75', 'gray30'))
        if getattr(self, 'review_confirm_btn', None) is not None:
            confirm_ready = ready and not self._preview_original and position is not None
            self.review_confirm_btn.configure(state='normal' if confirm_ready else 'disabled')
        if self._edit_session and not self._converting:
            self.review_nav.grid()
        else:
            self.review_nav.grid_remove()
        self._update_piano_keys()
        if hasattr(self,'practice_bar'):self._update_practice_controls()

    def _selected_preview_box(self):
        return self._preview_box_for_label(self._review_index)

    def _preview_box_for_label(self, index):
        if not self._edit_session or index is None:
            return None
        labels = self._edit_session['doc']['labels']
        if not 0 <= index < len(labels):
            return None
        label = labels[index]
        # 같은 위치의 별도 라벨은 안정된 렌더링 순서의 같은 출현 번호에 대응시킨다.
        occurrence = sum(all(other[k] == label[k] for k in ('staff', 'x', 'y', 'pitch', 'text'))
                         for other in labels[:index])
        for box in self._edit_session['placements']:
            note = box['note']
            if (note.staff_index, note.x, note.y, f'{note.note_name}{note.octave}', box['text']) == (
                    label['staff'], label['x'], label['y'], label['pitch'], label['text']):
                if occurrence:
                    occurrence -= 1
                    continue
                return box
        # 배치가 없는 라벨도 음표 위치로 이동한다. 저장된 결과에는 이 강조를 그리지 않는다.
        return dict(x=label['x'] - 8, y=label['y'] - 8, w=16, h=16)

    def _typing_input(self, event) -> bool:
        focus = self.focus_get() or event.widget
        return focus.winfo_class() in ('Entry', 'TEntry', 'Text', 'Spinbox', 'TSpinbox', 'Combobox', 'TCombobox')

    def _help_shortcut(self, event):
        # Windows Tk의 0x8은 NumLock이다. 실제 Alt 마스크는 0x20000이다.
        if event.state & (0x4 | (0x20000 if sys.platform == 'win32' else 0x8)):
            return
        if event.keysym != 'F1' and (event.keysym != 'question' or self._typing_input(event)):
            return
        return self._show_shortcuts()

    def _show_shortcuts(self):
        window = getattr(self, '_help_window', None)
        if window is None or not window.winfo_exists():
            window = self._help_window = ctk.CTkToplevel(self)
            window.title('단축키 도움말')
            window.geometry('520x510')
            window.transient(self)
            ctk.CTkLabel(window, text=(
                'N : 현재 쪽의 다음 확인 필요·주의\n'
                'P : 현재 쪽의 이전 확인 필요·주의\n'
                '1~7 : 라벨 수정 창에서 계이름·음이름 변경\n'
                '# · b : 반음 설정 · 같은 키로 해제\n'
                'Space · Ctrl+L : 수정 창에서 이 음만 듣기\n'
                'Delete : 선택한 라벨 삭제 · Ctrl+Z로 되돌리기\n'
                '라벨 한 번 클릭 : 선택 · 두 번 클릭 : 수정\n'
                '악보의 빈 곳 두 번 클릭 : 라벨 추가\n'
                '88건반 클릭 : 누른 음을 들어보기\n'
                'Ctrl++ / Ctrl+- / Ctrl+0 : 미리보기 확대 / 축소 / 100%\n'
                'PageUp / PageDown : 이전 / 다음 쪽\n'
                'V : 같은 위치에서 원본 / 결과 비교\n'
                '탐색기에서 끌어다 놓기 : 악보 파일 변환\n'
                'Ctrl+V : 클립보드 이미지 붙여넣고 변환\n'
                'Ctrl+Z : 미리보기·수정 창에서 되돌리기\n'
                'F1 또는 ? : 단축키 도움말\n\n'
                '입력칸에서는 N/P/?와 Space를 입력하고 Delete로 글자를 지웁니다.\n'
                '이동만으로 라벨을 수정하거나 저장하지 않습니다.'
            ), justify='left').pack(padx=20, pady=20)
            ctk.CTkButton(window, text='닫기', command=window.destroy).pack(pady=(0, 12))
            window.bind('<Escape>', lambda _e: window.destroy())
            window.bind('<KeyPress>', self._help_shortcut, add='+')
        window.lift()
        return 'break'

    def _review_shortcut(self, event):
        if event.state & (0x4 | (0x20000 if sys.platform == 'win32' else 0x8)) or self._typing_input(event):
            return
        if sys.platform == 'win32':
            code = event.keycode
            if code == 229:  # 한글 조합 중 PROCESSKEY: 비동기 상태가 아닌 이 이벤트의 입력 큐를 읽는다.
                import ctypes
                state = (ctypes.c_ubyte * 256)()
                if not ctypes.windll.user32.GetKeyboardState(state):
                    return
                # 다른 키와 함께 눌린 모호한 PROCESSKEY를 N/P로 오인하지 않는다.
                down = [vk for vk in range(8, 256) if vk not in (16, 160, 161, 229) and state[vk] & 0x80]
                code = down[0] if len(down) == 1 else 0
            key = {78: 'n', 80: 'p'}.get(code)
        else:
            key = event.keysym.lower()
        # 조합 완료 문자는 원래 물리 키와 중복되므로 Windows에서 다시 순회하지 않는다.
        if key not in ('n', 'p'):
            return
        if self._move_review_label(1 if key == 'n' else -1):
            return 'break'

    def _move_review_label(self, step: int) -> bool:
        indices = self._review_indices()
        if self._converting or not indices or self._preview_source is None:
            return False
        if self._review_index in indices:
            position = indices.index(self._review_index) + step
        else:
            position = 0 if step > 0 else len(indices) - 1
        if not 0 <= position < len(indices):
            return False
        self._review_index = indices[position]
        if self._edit_window is not None:
            self._refresh_label_editor(self._review_index)
        else:
            self._update_review_controls()
            self._redraw_preview()
        box = self._selected_preview_box()
        canvas = self.preview_canvas
        canvas.update_idletasks()
        z = self._preview_zoom
        canvas.xview_moveto(max(0, ((box['x'] + box['w'] / 2) * z - canvas.winfo_width() / 2)
                               / (self._preview_source.width * z)))
        canvas.yview_moveto(max(0, ((box['y'] + box['h'] / 2) * z - canvas.winfo_height() / 2)
                               / (self._preview_source.height * z)))
        return True

    def _preview_shortcut(self, event):
        alt = 0x20000 if sys.platform == 'win32' else 0x8
        if self._converting or event.state & alt or self._typing_input(event):
            return
        key = event.keysym.lower()
        if event.state & 0x4:
            key = key.removeprefix('kp_')
            if key == 'z':
                if self._edit_session and self._edit_session['changes']:
                    self._undo_label_edit()
                    return 'break'
                return
            if self._preview_source is None or key not in ('plus', 'equal', 'add', 'minus', 'subtract', '0'):
                return
            if key == '0':
                zoom = 1.
            else:
                factor = 1 / 1.15 if key in ('minus', 'subtract') else 1.15
                zoom = self._preview_zoom * factor
            canvas = self.preview_canvas
            self._set_preview_zoom(zoom, canvas.winfo_width() // 2, canvas.winfo_height() // 2)
            return 'break'
        if key in ('prior', 'next'):
            if self._select_result_page(self._page_index + (-1 if key == 'prior' else 1)):
                return 'break'
        elif key == 'v' and self._preview_original_frame() is not None:
            self._toggle_preview_original()
            return 'break'

    def _on_mousewheel(self, event, delta: int | None = None) -> None:
        if self._preview_source is None:
            return
        d = delta if delta is not None else event.delta
        factor = 1.15 if d > 0 else (1 / 1.15)
        self._set_preview_zoom(self._preview_zoom * factor, event.x, event.y)

    def _set_preview_zoom(self, zoom: float, x: int, y: int) -> None:
        old_zoom = self._preview_zoom
        new_zoom = max(0.02, min(zoom, 8.0))
        if abs(new_zoom - old_zoom) < 1e-6:
            return

        # 커서 아래 지점이 확대/축소 후에도 같은 화면 위치에 남도록 스크롤을 보정한다
        cx = self.preview_canvas.canvasx(x)
        cy = self.preview_canvas.canvasy(y)
        img_x, img_y = cx / old_zoom, cy / old_zoom

        self._preview_zoom = new_zoom
        self._redraw_preview(deferred=True)

        total_w, total_h = self._preview_extent()
        new_cx, new_cy = img_x * new_zoom, img_y * new_zoom
        if total_w > 0:
            self.preview_canvas.xview_moveto(max(0.0, (new_cx - x) / total_w))
        if total_h > 0:
            self.preview_canvas.yview_moveto(max(0.0, (new_cy - y) / total_h))

    # 인식을 다시 하지 않고 현재 미리보기 쪽의 표기만 바꾼다.
    def _region_point(self, event):
        source = self._edit_session['original_doc']['source']
        return (max(0, min(source['width'], self.preview_canvas.canvasx(event.x) / self._preview_zoom)),
                max(0, min(source['height'], self.preview_canvas.canvasy(event.y) / self._preview_zoom)))

    def _drag_region(self, event):
        if self._region_start is None or self._converting:
            return
        end = self._region_point(event)
        self.preview_canvas.delete('region')
        self.preview_canvas.create_rectangle(
            *(v * self._preview_zoom for v in (*self._region_start, *end)),
            outline='#1676c4', width=2, tags='region')

    def _finish_region(self, event):
        if self._region_start is None or self._converting:
            return
        start, self._region_start = self._region_start, None
        end = self._region_point(event)
        self._select_region((min(start[0],end[0]),min(start[1],end[1]),
                             max(start[0],end[0]),max(start[1],end[1])))
        self.region_check.deselect()

    def _select_region(self, region):
        if self._converting or not self._edit_session:
            return
        from modules.label_region import filter_region
        if region is not None:
            try:
                filter_region(self._edit_session['original_doc'], *region)
            except ValueError as exc:
                self.log(f'영역 선택 실패: {exc}')
                self._redraw_preview()
                return
        self._close_label_editor()
        previous = self._edit_session.get('region')
        self._edit_session['region'] = region
        if not self._apply_label_changes(self._edit_session['changes']):
            self._edit_session['region'] = previous
            self._redraw_preview()
            return
        self.log(f"표시·저장 라벨 {len(self._edit_session['doc']['labels'])}개 "
                 f"(인식 원본 {len(self._edit_session['original_doc']['labels'])}개 보존)")

    def _close_label_editor(self) -> None:
        if getattr(self, '_add_window', None) is not None:
            self._add_window.destroy()
            self._add_window = None
        if self._edit_window is not None:
            self._edit_window.destroy()
            self._edit_window = None
            self._redraw_preview()

    def _on_label_click(self, event, *, edit=False) -> None:
        if self._converting or not self._edit_session or getattr(self, '_preview_original', False):
            return
        if getattr(self, 'region_check', None) is not None and self.region_check.get():
            if not edit:
                self._close_label_editor()
                self._region_start = self._region_point(event)
            return
        self.preview_canvas.focus_set()
        x = self.preview_canvas.canvasx(event.x) / self._preview_zoom
        y = self.preview_canvas.canvasy(event.y) / self._preview_zoom
        indices = []
        for box in self._edit_session['placements']:
            if box['x'] <= x <= box['x'] + box['w'] and box['y'] <= y <= box['y'] + box['h']:
                note = box['note']
                indices.extend(i for i, label in enumerate(self._edit_session['doc']['labels'])
                    if (label['staff'], label['x'], label['y'], label['pitch'], label['text']) ==
                    (note.staff_index, note.x, note.y, f'{note.note_name}{note.octave}', box['text']))
        if indices:
            if edit:
                self._open_label_editor(sorted(set(indices)))
            else:
                self._review_index = indices[0]
                if self._edit_window is not None:
                    self._refresh_label_editor(self._review_index)
                else:
                    self._update_review_controls()
                    self._redraw_preview()
        elif edit and 0 <= x < self._edit_session['doc']['source']['width'] and 0 <= y < self._edit_session['doc']['source']['height']:
            self._open_label_add(int(x), int(y))

    def _open_label_add(self, x: int, y: int) -> None:
        if self._converting or not self._edit_session:
            return
        self._close_label_editor()
        session = self._edit_session
        window = self._add_window = ctk.CTkToplevel(self)
        window.title('라벨 추가')
        window.geometry('440x320')
        window.transient(self)
        window.grab_set()
        ctk.CTkLabel(window, text='클릭한 위치에 추가합니다. 보표와 음고를 직접 확인해 주세요.', wraplength=400).pack(padx=12, pady=12)
        self._add_staff = ctk.CTkOptionMenu(window, values=[str(s['id'] + 1) for s in session['doc']['staves']])
        self._add_staff.set('보표 선택')
        self._add_staff.pack(padx=12, pady=4)
        self._add_pitch = ctk.CTkEntry(window, placeholder_text='음고 (예: C4, B3)')
        self._add_pitch.pack(padx=12, pady=4, fill='x')
        self._add_text = ctk.CTkEntry(window, placeholder_text='표시할 계이름 (예: 도, 시b)')
        self._add_text.pack(padx=12, pady=4, fill='x')
        status = ctk.CTkLabel(window, text='', wraplength=410)
        status.pack(padx=12, pady=4)

        def confirm():
            if self._edit_session is not session:
                status.configure(text='결과가 바뀌었습니다. 창을 닫고 다시 선택해 주세요.')
            elif self._add_user_label(x, y, self._add_staff.get(), self._add_pitch.get(), self._add_text.get()):
                self._close_label_editor()
            else:
                status.configure(text='추가하지 못했습니다. 보표·음고·계이름과 처리 로그를 확인해 주세요.')

        self._add_confirm = ctk.CTkButton(window, text='라벨 추가', command=confirm)
        self._add_confirm.pack(padx=12, pady=4)
        window.bind('<Return>', lambda _e: confirm())
        window.bind('<Escape>', lambda _e: self._close_label_editor())
        window.bind('<KeyPress>', self._help_shortcut, add='+')
        window.protocol('WM_DELETE_WINDOW', self._close_label_editor)
        window.after(100, window.lift)

    def _add_user_label(self, x: int, y: int, staff: str, pitch: str, text: str) -> bool:
        if self._converting or not self._edit_session:
            return False
        try:
            staff_id = int(staff) - 1
        except ValueError:
            self.log('추가할 보표 번호를 선택해 주세요.')
            return False
        change = dict(action='add', after=dict(staff=staff_id, x=x, y=y,
                                              pitch=pitch.strip(), text=text.strip()))
        return self._apply_label_changes(self._edit_session['changes'] + [change])

    def _update_editor_colors(self):
        if self._edit_window is not None and self._edit_window.winfo_exists():
            self._edit_list.configure(
                bg=self._apply_appearance_mode(UI_COLORS["surface"]),
                fg=self._apply_appearance_mode(UI_COLORS["text"]),
                selectbackground=self._apply_appearance_mode(UI_COLORS["compare_active"]),
                selectforeground=self._apply_appearance_mode(UI_COLORS["compare_text"]),
                highlightbackground=self._apply_appearance_mode(UI_COLORS["border"]))

    def _open_label_editor(self, indices=None) -> None:
        if self._converting or not self._edit_session:
            return
        self._close_label_editor()
        window = self._edit_window = ctk.CTkToplevel(self)
        window.title('라벨 수정 / 삭제')
        window.geometry('520x560')
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(window, text='표시 글씨만 수정합니다. 음고·조표 인식은 바뀌지 않습니다.\n악보의 빈 곳을 두 번 클릭하면 라벨을 추가할 수 있습니다').grid(
            row=0, column=0, padx=12, pady=8)
        self._edit_list = Listbox(window, font=('맑은 고딕', 12), exportselection=False,
                                 relief='flat', highlightthickness=1)
        self._update_editor_colors()
        self._edit_list.grid(row=1, column=0, padx=12, pady=4, sticky='nsew')
        scroll = ctk.CTkScrollbar(window, command=self._edit_list.yview)
        scroll.grid(row=1, column=1, sticky='ns')
        self._edit_list.configure(yscrollcommand=scroll.set)
        self._edit_list.bind('<<ListboxSelect>>', self._select_edit_label)
        self._edit_list.bind('<Return>', lambda _e: self._edit_text.focus_set())
        # 목록의 기본 Space 동작 전에 현재 선택 음을 그대로 듣는다.
        self._edit_list.bind('<space>', self._quick_edit_shortcut)
        self._edit_list.bind('<Delete>', self._quick_edit_shortcut)
        self._edit_reason = ctk.CTkLabel(window, text='라벨을 선택하면 확인 이유를 볼 수 있어요.',
                                       wraplength=470, justify='left', anchor='w')
        self._edit_reason.grid(row=2, column=0, columnspan=2, padx=12, pady=4, sticky='ew')
        palette = ctk.CTkFrame(window, fg_color='transparent')
        palette.grid(row=3, column=0, padx=12, pady=4)
        for value in (*self._quick_edit_notes(), '#', 'b'):
            ctk.CTkButton(palette, text=value, width=38, height=34,
                fg_color=UI_COLORS['compare_active'] if value in ('#', 'b') else UI_COLORS['secondary'],
                text_color=UI_COLORS['compare_text'] if value in ('#', 'b') else UI_COLORS['text'],
                command=lambda value=value: self._quick_edit_label(value)).pack(side='left', padx=2)
        self._edit_text = ctk.CTkEntry(window, placeholder_text='표시할 계이름 (예: 도#, 레b)')
        self._edit_text.grid(row=4, column=0, padx=12, pady=8, sticky='ew')
        self._edit_text.bind('<Return>', lambda _e: self._change_label('set_text'))
        buttons = ctk.CTkFrame(window, fg_color='transparent')
        buttons.grid(row=5, column=0, padx=12, pady=4)
        ctk.CTkButton(buttons, text='글씨 수정', width=100,
                      command=lambda: self._change_label('set_text')).pack(side='left', padx=4)
        ctk.CTkButton(buttons, text='라벨 삭제', width=100,
                      fg_color=UI_COLORS['danger'], hover_color=UI_COLORS['danger_hover'],
                      text_color=UI_COLORS['danger_text'], border_width=0,
                      command=lambda: self._change_label('delete')).pack(side='left', padx=4)
        self._undo_edit_btn = ctk.CTkButton(buttons, text='되돌리기', width=100,
                                          command=self._undo_label_edit)
        self._undo_edit_btn.pack(side='left', padx=4)
        ctk.CTkButton(buttons, text='이 음만 듣기', width=100, command=self._listen_edit_note).pack(
            side='left', padx=4)
        ctk.CTkLabel(window, text='수정할 때 PNG·라벨 JSON·사용자 수정 기록을 함께 저장합니다.').grid(
            row=6, column=0, padx=12, pady=4)
        ctk.CTkButton(window, text='수정본 폴더를 다른 곳에 저장...',
                      command=self._export_label_edits).grid(row=7, column=0, padx=12, pady=8)
        window.bind('<Control-z>', lambda _e: self._undo_label_edit())
        window.bind('<Control-l>', self._listen_edit_note)
        window.bind('<KeyPress>', self._review_shortcut, add='+')
        window.bind('<KeyPress>', self._help_shortcut, add='+')
        window.bind('<KeyPress>', self._quick_edit_shortcut, add='+')
        window.protocol('WM_DELETE_WINDOW', self._close_label_editor)
        # 겹친 글씨는 후보를 보여주되 임의로 한 라벨을 고르지 않는다.
        preferred = self._review_index if self._review_index is not None else 0
        if indices is not None:
            preferred = indices[0] if len(indices) == 1 else None
        if preferred is None:
            self._review_index = None
        self._refresh_label_editor(preferred)
        if indices and len(indices) > 1:
            self.log('겹친 라벨 후보: ' + ', '.join(str(i + 1) for i in indices)
                     + ' — 목록에서 직접 골라 주세요.')
            self._edit_list.see(indices[0])
        window.after(100, window.lift)
        self._edit_list.focus_set()

    def _refresh_label_editor(self, preferred=0) -> None:
        self._edit_reason.configure(text='라벨을 선택하면 확인 이유를 볼 수 있어요.')
        self._edit_list.delete(0, 'end')
        for label in self._edit_session['doc']['labels']:
            self._edit_list.insert('end', f"보표 {label['staff'] + 1} · {label['text']} ({label['pitch']})"
                                   + (' · 사용자 수정' if label.get('edited') else ''))
        self._edit_text.delete(0, 'end')
        if preferred is not None and self._edit_list.size():
            index = min(preferred, self._edit_list.size() - 1)
            self._edit_list.selection_set(index)
            self._edit_list.activate(index)
            self._edit_list.selection_anchor(index)
            self._edit_list.see(index)
            self._select_edit_label()
        self._undo_edit_btn.configure(state='normal' if self._edit_session['changes'] else 'disabled')

    def _select_edit_label(self, _event=None) -> None:
        selected = self._edit_list.curselection()
        if selected:
            label = self._edit_session['doc']['labels'][selected[0]]
            self._edit_reason.configure(text=label_review_reason(label))
            self._edit_text.delete(0, 'end')
            self._edit_text.insert(0, label['text'])
            self._review_index = selected[0]
            self._update_review_controls()
            self._redraw_preview()
        else:
            self._edit_reason.configure(text='라벨을 선택하면 확인 이유를 볼 수 있어요.')

    def _quick_edit_notes(self) -> str:
        notation = self._edit_session['doc'].get('music', {}).get('notation')
        return QUICK_LETTERS if notation == 'letter' else QUICK_SOLFEGE

    def _quick_edit_shortcut(self, event):
        if event.state & (0x4 | (0x20000 if sys.platform == 'win32' else 0x8)) or self._typing_input(event):
            return
        key = event.keysym.lower().removeprefix('kp_')
        if key in ('1', '2', '3', '4', '5', '6', '7'):
            self._quick_edit_label(self._quick_edit_notes()[int(key) - 1])
        elif key in ('numbersign', 'b'):
            self._quick_edit_label('#' if key == 'numbersign' else 'b')
        elif key == 'space':
            self._listen_edit_note()
        elif key == 'delete':
            self._change_label('delete')
        else:
            return
        return 'break'

    def _quick_edit_label(self, value: str) -> None:
        selected = self._edit_list.curselection()
        if not selected or self._converting:
            return
        if value in ('#', 'b'):
            label = self._edit_session['doc']['labels'][selected[0]]
            base = label['text'].rstrip('#b♯♭♮x𝄪𝄫')
            if len(base) != 1 or base not in QUICK_SOLFEGE + QUICK_LETTERS:
                return
            suffix = label['text'][len(base):]
            same = ('#', '♯') if value == '#' else ('b', '♭')
            value = base if suffix in same else base + value
        self._change_label('set_text', text=value)

    def _change_label(self, action: str, *, text=None) -> None:
        selected = self._edit_list.curselection()
        if not selected or self._converting:
            return
        label = self._edit_session['doc']['labels'][selected[0]]
        change = dict(action=action, before={k: label[k] for k in ('staff', 'x', 'y', 'pitch', 'text')})
        if action == 'set_text':
            if text is None:
                text = self._edit_text.get().strip()
            if text == label['text']:
                return
            change['after'] = dict(text=text)
        self._apply_label_changes(self._edit_session['changes'] + [change], selected[0])

    def _confirm_review_label(self) -> None:
        index = self._review_index
        if self._converting or self._preview_original or index not in self._review_indices():
            return
        label = self._edit_session['doc']['labels'][index]
        # 글씨를 유지하는 사용자 수정으로 기록해 기존 저장·재열기·되돌리기를 공유한다.
        change = dict(action='set_text', before={k: label[k] for k in ('staff', 'x', 'y', 'pitch', 'text')},
                      after=dict(text=label['text']))
        self._apply_label_changes(self._edit_session['changes'] + [change], index)

    def _undo_label_edit(self) -> None:
        if self._edit_session and self._edit_session['changes'] and not self._converting:
            # 복원된 이전 라벨을 저장 결과에서 찾는다. 추가 취소는 대상이 사라져 선택을 해제한다.
            target = self._edit_session['changes'][-1].get('before')
            self._apply_label_changes(self._edit_session['changes'][:-1], target)

    def _apply_label_changes(self, changes: list, selected=0) -> bool:
        if getattr(self, '_style_refresh_timer', None) is not None and not self._flush_style_refresh():
            return False
        self._stop_listening()
        from modules.label_edits import EditError
        try:
            saved = _save_edit_version(self._edit_session, changes, self.output_dir)
            with Image.open(saved['png']) as opened:
                image = opened.copy()
        except (ValueError, OSError, RendererError) as exc:
            self.log(f'❌ 수정 저장 실패 — 이전 결과를 유지합니다: {exc}')
            return False
        session = self._edit_session
        session.update(changes=changes, doc=saved['doc'], placements=saved['placements'],
                       placement_notice=saved.get('placement_notice',''), png=saved['png'], json=saved['json'])
        self.result_path, self.labels_path = saved['png'], saved['json']
        if os.path.dirname(self.result_path) != session.get('_style_folder'):
            session['_style_saved_png'] = self.result_path
        self._preview_source = image
        self._review_index = None
        if self._edit_window is not None:
            if isinstance(selected, dict):
                matches = [i for i, label in enumerate(saved['doc']['labels'])
                           if all(label[k] == selected[k] for k in ('staff', 'x', 'y', 'pitch', 'text'))]
                selected = matches[0] if len(matches) == 1 else None
            self._refresh_label_editor(selected)
        if getattr(self, 'review_nav', None) is not None:
            self._update_page_controls()
        self._redraw_preview()
        self.log(f"사용자 수정 {len(changes)}건: {self.result_path}")
        return True

    def _open_saved_edits(self) -> None:
        if self._converting:
            self.log('변환 중에는 수정본을 열 수 없습니다.')
            return
        folder = filedialog.askdirectory(title='저장한 수정본 폴더 선택')
        if not folder:
            return
        source = filedialog.askopenfilename(title='이 수정본의 원본 악보 선택 (해시 확인)', filetypes=_filetypes_for_runtime())
        if not source:
            self.log('원본 악보 선택을 취소해 수정본을 열지 않았습니다.')
            return
        try:
            session = _load_edit_version(folder, source, self.output_dir)
        except (ValueError, OSError, RendererError) as exc:
            self.log(f'수정본을 열지 않았습니다 — 이전 결과 유지: {exc}')
            return
        self._stop_listening()
        self._set_input(source)
        self._edit_session = session
        self.result_path, self.labels_path = session['png'], session['json']
        self._show_result()
        self.log(f"수정본 재열기: 사용자 수정 {len(session['changes'])}건 — 수정·되돌리기를 이어갈 수 있습니다.")

    def _export_label_edits(self) -> None:
        if not self._edit_session or not self._edit_session['changes']:
            self.log('아직 사용자 수정이 없습니다.')
            return
        parent = filedialog.askdirectory(title='수정본 파일을 저장할 폴더 선택')
        if parent:
            try:
                saved = _save_edit_version(self._edit_session, self._edit_session['changes'], parent)
                self.log(f"💾 수정본 파일 저장: {os.path.dirname(saved['png'])}")
            except (ValueError, OSError, RendererError) as exc:
                self.log(f'❌ 수정본 저장 실패: {exc}')

    def _update_practice_controls(self):
        doc=self._edit_session['doc'] if self._edit_session else None
        if self._practice_doc is not doc or self._practice_session is not self._edit_session:
            self._practice_start=self._practice_end=None
            self.practice_repeat.deselect();self._practice_doc=doc;self._practice_session=self._edit_session
        labels=doc['labels'] if doc else []
        def name(index):
            return labels[index]['text'] if index is not None and 0<=index<len(labels) else '미지정'
        text=('구간: 전체' if self._practice_start is None and self._practice_end is None
              else f'시작: {name(self._practice_start)} / 끝: {name(self._practice_end)}')
        self.practice_range_label.configure(text=text)
        self.practice_speed_label.configure(text=f'빠르기 {self.practice_speed.get():.1f}x')

    def _set_practice_boundary(self, boundary):
        if boundary not in ('start','end'):raise ValueError('시작/끝 선택을 확인해 주세요.')
        self._update_practice_controls();index=self._review_index
        if not self._edit_session or type(index) is not int or not 0<=index<len(self._edit_session['doc']['labels']):
            self.log('계이름을 먼저 선택해 주세요.');return False
        self._stop_listening();setattr(self,'_practice_'+boundary,index)
        self._update_practice_controls();return True

    def _clear_practice_range(self):
        self._stop_listening();self._practice_start=self._practice_end=None
        self.practice_repeat.deselect();self._update_practice_controls()

    def _practice_options(self):
        self._update_practice_controls()
        start,end=self._practice_start,self._practice_end
        repeat=bool(self.practice_repeat.get());speed=self.practice_speed.get()
        if (start is None)!=(end is None) or repeat and start is None:
            raise ValueError('반복 시작 음과 끝 음을 모두 골라 주세요.')
        if speed==1. and start is None and end is None and not repeat:return None
        return dict(speed=speed,start=start,end=end,repeat=repeat)

    def _set_audio_highlight_delay(self, value: float) -> None:
        delay = _valid_audio_delay(round(value))
        self.audio_delay_slider.set(delay)
        self.audio_delay_label.configure(text=f'화면 강조 지연 {delay}ms')
        if delay == self.settings['audio_highlight_delay_ms']:
            return
        self.settings['audio_highlight_delay_ms'] = delay
        events = tuple(self._audio_delayed.values())
        for timer in self._audio_delayed:
            self.after_cancel(timer)
        self._audio_delayed.clear()
        for event in events:
            self._schedule_audio_event(*event)
        if self._audio_delay_save_timer is not None:
            self.after_cancel(self._audio_delay_save_timer)
        self._audio_delay_save_timer = self.after(250, self._persist_audio_delay)

    def _persist_audio_delay(self) -> None:
        self._audio_delay_save_timer = None
        self._save_settings()

    def _listen_edit_note(self, _event=None):
        if self._converting or self._edit_session is None or self._edit_window is None:
            return
        selected = self._edit_list.curselection()
        if not selected:
            return
        if self._audio_thread and self._audio_thread.is_alive():
            self.log('재생 중입니다. 듣기를 멈춘 뒤 다시 눌러 주세요.')
            return 'break'
        from modules.label_audio import pitch_to_midi

        doc = self._edit_session['doc']
        try:
            midi = pitch_to_midi(doc['labels'][selected[0]], doc.get('music', {}))
        except (ValueError, TypeError, KeyError) as error:
            self.log(f'선택한 음을 재생할 수 없습니다 — {error}')
            return 'break'
        self._stop_listening()
        self._audio_cancel = threading.Event()
        self._audio_thread = threading.Thread(target=self._play_edit_note,
            args=(midi, self._audio_cancel, self._playback.token), daemon=True)
        try:
            self._audio_thread.start()
            self._wake_audio_events()
        except RuntimeError as error:
            self._audio_thread = None
            self.log(f'듣기 시작 실패 — {error}')
        return 'break'

    def _play_edit_note(self, midi, cancel, token):
        from modules.label_audio import play_piano

        try:
            play_piano([[midi]], cancel, duration=.65)
        except (OSError, ValueError, RuntimeError) as error:
            self._audio_events.put((token, 'log', f'듣기 실패: {error}'))

    def _on_piano_key(self, midi):
        if self._converting or self._closing:
            return
        previous = self._audio_thread
        if previous is not None and previous.is_alive() and self._keyboard_note is None:
            return
        self._stop_listening()
        self._keyboard_note = midi
        self._audio_cancel = threading.Event()
        self._audio_thread = threading.Thread(target=self._play_keyboard_note,
            args=(midi, self._audio_cancel, self._playback.token, previous), daemon=True)
        try:
            self._audio_thread.start()
            self._update_piano_keys()
            self._wake_audio_events()
        except RuntimeError as error:
            self._audio_thread = previous
            self._stop_listening()
            self.log(f'건반 듣기를 시작하지 못했습니다: {error}')

    def _play_keyboard_note(self, midi, cancel, token, previous):
        from modules.label_audio import play_piano

        try:
            # 이전 장치가 닫히기를 작업 스레드에서 기다린다. 교체된 음은 건너뛴다.
            if previous is not None and previous.is_alive():
                previous.join()
            if not cancel.is_set():
                play_piano([[midi]], cancel, duration=.55)
        except (OSError, ValueError, RuntimeError) as error:
            self._audio_events.put((token, 'log', f'건반 듣기 실패: {error}'))
        finally:
            self._audio_events.put((token, 'keyboard_finished', None))

    def _listen_labels(self) -> None:
        if self._converting or not self._edit_session:
            self.log("변환 결과를 먼저 만들어 주세요.")
            return
        if self._audio_thread and self._audio_thread.is_alive():
            self.log("재생 중입니다. 듣기 중지 후 다시 눌러 주세요.")
            return
        try:
            practice=self._practice_options() if hasattr(self,'practice_bar') else None
        except ValueError as exc:
            self.log(f'듣기 실패: {exc}');return
        import copy
        doc = copy.deepcopy(self._edit_session['doc'])
        skip_check = bool(self.audio_check.get())
        self._stop_listening()
        token = self._playback.token
        self._audio_cancel = threading.Event()
        self._audio_thread = threading.Thread(target=self._audio_worker,
            args=((doc, skip_check, self._audio_cancel, token) if practice is None
                  else (doc, skip_check, self._audio_cancel, token, practice)), daemon=True)
        try:
            self._audio_thread.start()
            self._wake_audio_events()
        except RuntimeError as exc:
            self._audio_thread = None
            self.log(f"듣기 시작 실패: {exc}")

    def _audio_worker(self, doc, skip_check, cancel, token=None, practice=None) -> None:
        from modules.label_audio import audio_plan, play_piano, practice_plan
        report = self.log if token is None else lambda text: self._audio_events.put((token,'log',text))
        try:
            plan, skipped = audio_plan(doc, skip_check)
            durations=None
            if practice is not None:
                if practice.get('repeat') and (practice.get('start') is None or practice.get('end') is None):
                    raise ValueError('반복 시작 음과 끝 음을 모두 골라 주세요.')
                plan,durations=practice_plan(plan,speed=practice.get('speed',1.),start=practice.get('start'),end=practice.get('end'))
            groups = [row['notes'] for row in plan]
            if token is not None:self._audio_events.put((token,'plan',plan))
            report(f"피아노 음높이 듣기: {len(groups)}묶음, 제외 {len(skipped)}개 (박자 없음)")
            for row in skipped:
                if row['reason'] != '확인 필요 제외':
                    label = row['label']
                    report(f"듣기 제외 ({label.get('x')},{label.get('y')}): {row['reason']}")
            if not groups:return
            options={} if token is None else dict(on_group=lambda kind,index:self._audio_events.put((token,kind,index,time.perf_counter())))
            if practice is not None:options.update(durations=durations,repeat=practice.get('repeat',False))
            play_piano(groups, cancel, **options)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            try:report(f"듣기 실패: {exc}")
            except RuntimeError:pass
        finally:
            if token is not None:self._audio_events.put((token,'finished',None))

    def _apply_audio_event(self,token,kind,value=None):
        if token!=self._playback.token:return
        if kind=='log':
            self.log(value);return
        if kind == 'keyboard_finished':
            self._keyboard_note = None
            self._update_piano_keys()
            return
        if not self._playback.apply(token,kind,value):return
        self._draw_audio_overlay()
        if kind=='start':
            self.audio_position.configure(text=f'음높이 묶음 {value+1} / {len(self._playback.plan)} · 박자 없음')
        elif kind=='finished':
            self.audio_position.configure(text='음높이 듣기 종료 · 라벨을 선택하면 건반을 볼 수 있어요')
        self._update_piano_keys()

    def _schedule_audio_event(self, token, kind, value=None, issued_at=None):
        if token != self._playback.token:
            return
        if kind not in ('start', 'end', 'finished'):
            self._apply_audio_event(token, kind, value)
            return
        def present():
            if self._audio_delayed.pop(timer, None) is not None:
                self._apply_audio_event(token, kind, value)
        now = time.perf_counter()
        issued_at = now if issued_at is None else issued_at
        delay = _valid_audio_delay(getattr(self, 'settings', {}).get('audio_highlight_delay_ms'))
        due = issued_at + delay / 1000
        timer = self.after(max(0, round((due - now) * 1000)), present)
        self._audio_delayed[timer] = (token, kind, value, issued_at)

    def _wake_audio_events(self):
        if self._audio_timer is not None:
            self.after_cancel(self._audio_timer)
        self._audio_timer = self.after(0, self._drain_audio_events)

    def _drain_audio_events(self):
        if self._closing:return
        try:
            while True:self._schedule_audio_event(*self._audio_events.get_nowait())
        except queue.Empty:pass
        worker = self._audio_thread
        active = self._audio_delayed or (worker is not None and worker.is_alive())
        interval = _AUDIO_ACTIVE_POLL_MS if active else _AUDIO_IDLE_POLL_MS
        self._audio_timer = self.after(interval, self._drain_audio_events)

    def _draw_audio_overlay(self):
        canvas=getattr(self,'preview_canvas',None)
        if canvas is None:return
        canvas.delete('audio-playing')
        if not self._edit_session or self._preview_original:
            return
        z=self._preview_zoom
        for index in self._playback.indices:
            box=self._preview_box_for_label(index)
            if box is not None:
                canvas.create_rectangle((box['x']-4)*z,(box['y']-4)*z,
                    (box['x']+box['w']+4)*z,(box['y']+box['h']+4)*z,
                    outline='#e58b2f',width=3,tags='audio-playing')

    def _update_piano_keys(self):
        if not hasattr(self,'piano_keyboard'):return
        if not self._edit_session:
            self.piano_frame.grid_remove();return
        self.piano_frame.grid()
        from modules.label_audio import pitch_to_midi
        selected=[];label=None
        labels=self._edit_session['doc']['labels'];index=self._review_index
        if index is not None and 0<=index<len(labels):
            label=labels[index]
            try:selected=[pitch_to_midi(label,self._edit_session['doc'].get('music',{}))]
            except (ValueError,TypeError,KeyError):pass
        keyboard_note = getattr(self, '_keyboard_note', None)
        if keyboard_note is not None:
            from modules.note_namer import FIXED_DO_MAP
            from modules.piano_keyboard import NAMES

            name = NAMES[keyboard_note % 12]
            solfege = FIXED_DO_MAP[name[0]] + name[1:]
            self.piano_keyboard.set_notes(selected, [keyboard_note])
            self.audio_position.configure(
                text=f'건반 미리듣기: {name}{keyboard_note // 12 - 1} ({solfege} · MIDI {keyboard_note})')
            return
        self.piano_keyboard.set_notes(selected,self._playback.notes)
        if self._playback.group_index is None:
            outside=[n for n in selected if not 21<=n<=108]
            text = '라벨을 선택하면 건반을 볼 수 있어요 · 박자 없음'
            if label is not None:
                text = f"표기: {label['text']} · 음높이 해석 불가"
                if selected:
                    midi = selected[0]
                    name = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')[midi % 12]
                    text = f"표기: {label['text']} · 건반: {name}{midi // 12 - 1} (MIDI {midi})"
            if outside:text+=' · 표시 음역 밖(A0~C8)'
            self.audio_position.configure(text=text)
        elif any(not 21<=n<=108 for n in self._playback.notes):
            self.audio_position.configure(text='재생 음 일부가 표시 음역 밖(A0~C8)입니다 · 소리는 그대로 재생')

    def _stop_listening(self) -> None:
        self._audio_cancel.set()
        self._keyboard_note = None
        for timer in getattr(self, '_audio_delayed', ()):
            self.after_cancel(timer)
        if hasattr(self, '_audio_delayed'):
            self._audio_delayed.clear()
        if getattr(self,'_playback',None) is not None:
            self._playback.reset()
            self._draw_audio_overlay();self._update_piano_keys()

    def destroy(self) -> None:
        timer = getattr(self, '_drop_timer', None)
        if timer is not None:
            self.after_cancel(timer)
            self._drop_timer = None
            self._pending_drops.clear()
        hook = getattr(self, '_windows_drop', None)
        if hook is not None:
            hook.close()
        # 복원이 실패해도 HWND가 소멸할 때까지 ctypes 콜백을 붙잡는다.
        super().destroy()
        self._windows_drop = None

    def _close_app(self) -> None:
        self._stop_listening()
        save_timer = getattr(self, '_audio_delay_save_timer', None)
        if save_timer is not None:
            self.after_cancel(save_timer)
            self._persist_audio_delay()
        self._closing=True
        if getattr(self, '_style_refresh_timer', None) is not None:
            self._cancel_style_refresh()
        if getattr(self, '_preview_tile_after', None) is not None:
            self._cancel_preview_tile()
        timer=getattr(self,'_audio_timer',None)
        if timer is not None:
            self.after_cancel(timer);self._audio_timer=None
        self.destroy()

    def open_result(self) -> None:
        if self.result_path and os.path.isfile(self.result_path):
            os.startfile(self.result_path)

    def open_folder(self) -> None:
        if os.path.isdir(self.output_dir):
            os.startfile(self.output_dir)

    def save_as(self) -> None:
        if self._converting or not (self.result_path and os.path.isfile(self.result_path)):
            return
        if not self._flush_style_refresh():
            return
        default_name = os.path.basename(self.result_path)
        path = filedialog.asksaveasfilename(
            title="계이름 악보 저장",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG 이미지", "*.png"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        try:
            shutil.copyfile(self.result_path, path)
            if self._edit_session is not None:
                self._edit_session['_style_saved_png'] = path
                self._update_style_save_notice()
            self.log(f"💾 저장됨: {path}")
        except OSError as e:
            self.log(f"❌ 저장 실패: {e}")

    def export_all_pages(self) -> None:
        if self._converting or len(self._page_sessions) < 2 or not self._flush_style_refresh():
            return
        parent = filedialog.askdirectory(title='현재 표기로 전체 쪽을 저장할 폴더 선택')
        if not parent:
            return
        style = self._style_for_render()
        pages = tuple(self._page_sessions)
        shown = self._edit_session
        self._stop_listening()
        self._close_label_editor()
        # 일괄 변환의 모든 프레임은 기존 쪽 캐시에서 다시 읽을 수 있다.
        if shown.get('frame_path'):
            shown['image'] = None
        self._converting = True
        self._set_conversion_progress(0, len(pages), '전체 쪽 내보내는 중…')
        threading.Thread(target=self._export_pages_worker,
                         args=(pages, shown, parent, style), daemon=True).start()

    def _export_pages_worker(self, pages, shown, parent, style):
        def progress(number, total):
            self.after(0, self._set_conversion_progress, number, total, '전체 쪽 내보내는 중…')
        try:
            folder = _export_styled_batch(pages, parent, style, progress)
            self.log(f'전체 쪽 PNG와 PDF 저장: {folder}')
        except (OSError, ValueError, RendererError) as error:
            self.log(f'전체 쪽 저장 실패 — {error}')
        finally:
            try:
                if shown['image'] is None:
                    shown['image'] = _read_page_frame(shown['frame_path'])
            except (OSError, ValueError) as error:
                self.log(f'현재 쪽 원본을 다시 읽지 못했습니다 — {error}')
            self.after(0, self._finish_pages_export)

    def _finish_pages_export(self):
        self._converting = False
        self._conversion_status = None
        self._update_page_controls()

    def save_feedback(self) -> None:
        if self._converting or not (self.input_path and self.result_path and self.labels_path):
            return
        path = filedialog.asksaveasfilename(
            title="문제 신고용 ZIP 저장", initialfile="악보헬퍼_문제신고.zip",
            defaultextension=".zip", filetypes=[("ZIP 파일", "*.zip")],
        )
        if not path:
            return
        try:
            from modules.feedback_bundle import save_feedback_bundle
            session = self._edit_session or {}
            save_feedback_bundle(session.get('source_path', self.input_path),
                                 self.result_path, self.labels_path,
                                 session.get('report_settings', self.settings), path, base_dir())
            self.log(f"💾 문제 신고용 ZIP 저장: {path}")
        except (OSError, ValueError, KeyError) as e:
            self.log(f"❌ 문제 신고용 저장 실패: {e}")

    # ------------------------------------------------------------------
    # 로그
    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        def _append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)


def main() -> None:
    app = SheetHelperApp()
    app.mainloop()


def _use_cli(argv=None) -> bool:
    """exe에 CLI 옵션이 있으면 GUI 대신 main.py의 검증된 경로를 사용한다."""
    args = list(sys.argv[1:] if argv is None else argv)
    return any(arg.startswith("--") for arg in args)


def _prepare_cli_streams() -> None:
    """창 없는 exe의 출력 스트림도 ♯·♭을 쓸 수 있게 UTF-8로 맞춘다."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        if len(sys.argv) != 4:
            raise SystemExit("사용법: 악보헬퍼.exe --selftest <입력> <출력폴더>")
        sys.argv[1:] = [sys.argv[2], "--output-dir", sys.argv[3], "--no-debug"]
        sys.stdin = None  # 창 없는 점검 모드는 대화형 종료 대기를 하지 않는다.
    if _use_cli():
        _prepare_cli_streams()
        from main import main as cli_main
        cli_main()
    else:
        main()
