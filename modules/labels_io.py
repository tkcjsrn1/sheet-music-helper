# -*- coding: utf-8 -*-
"""
라벨 목록 JSON 입출력.

구조와 근거는 `docs/LABELS_SCHEMA.md`에 있다. **이 데이터 구조는 앱으로 그대로
넘어간다.** 그래서 여기 있는 상수는 전부 실측에서 나온 값이고, 바꾸려면 다시 재야 한다.

이 파일이 하는 일은 셋이다.
  1. 인식 결과를 스키마대로 직렬화한다 (`build_document`)
  2. JSON만으로 재렌더링할 수 있게 되돌린다 (`document_staves`, `document_notes`)
  3. 저장된 라벨을 새 인식 결과에 다시 붙인다 (`match_labels`)

**표시 방식은 여기 없다.** JSON에는 `confidence` 값만 있고, 색과 형태는 렌더러가 정한다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Dict, List, Optional, Tuple

from modules.preprocess import Staff
from modules.pitch_calculator import PitchedNote

SCHEMA_VERSION = 2   # 읽을 수 있는 최고 번호. 쓰기는 겹임시표(bb/##)가 실제로 든 문서만 2, 나머지는 1 그대로(기존 출력 바이트 0 · 구버전은 2만 거부)
DOUBLE_ACCIDENTALS = ("bb", "##")
GENERATOR = "악보헬퍼 0.9.0"

# 인식은 300dpi에서만 동작한다. "미검증"이 아니라 **실패한다** —
# 400dpi에서 짝 못 찾은 라벨 58/240, 600dpi는 StaffNotFoundError.
# (`docs/LABELS_SCHEMA.md` 「알려진 한계」 1번)
RECOGNITION_DPI = 300

# 매칭 상한(오선 간격 단위). 위에서 눌린 값이다 — 같은 staff·step 이웃의
# 최소 간격이 1.30sp(= 음표 머리 폭 1.2sp 실측과 일치하는 물리적 바닥)라
# 그 절반 0.65sp가 천장이고, 0.5는 여유 0.15sp다.
# 아래에서 미는 값은 훨씬 작다: 300dpi 고정이라 재실행 시 Δnx는 0이다.
MATCH_DNX_SP = 0.5

# 두 인식 결과의 보표를 **같은 보표로 볼 y 오차**(오선 간격 단위).
# 순번(`staff`)으로 맞추면 보표가 하나만 더/덜 검출돼도 그 아래가 전부 밀린다.
#
# **양쪽 끝에서 유도했고 창이 아주 넓다.**
#   아래 — 같은 페이지를 두 번 인식했을 때 격자 원점 흔들림은 **0.0000sp**였다
#          (7쪽 70개 보표. 300dpi 고정이라 결정적이다)
#   위   — 인접 보표 사이 최소 간격이 **7.67sp**(RE:Aoharu 2쪽)라
#          그 절반 **3.84sp**를 넘으면 옆 보표를 잘못 집는다
#
# `0.0 < 0.5 < 3.84`. 여유가 양쪽으로 충분하다.
MATCH_STAFF_Y_SP = 0.5


class LabelSchemaError(Exception):
    """JSON을 라벨 목록으로 읽을 수 없을 때"""


# ------------------------------------------------------------------
# 확신도
# ------------------------------------------------------------------
# 값은 셋이고, 문자열이다. **불리언이 아닌 이유는 네 번째 값이 생길 수 있어서다.**
# 모르는 값을 만나면 그리는 쪽이 certain처럼 다루고 넘어간다(관대하게).
CONFIDENCE_CERTAIN = "certain"   # 걸린 신호가 없다
CONFIDENCE_CAUTION = "caution"   # 정밀도 낮은 신호만 걸렸다 (실측 11%)
CONFIDENCE_CHECK = "check"       # 정밀도 높은 신호가 걸렸다 (실측 83~100%)

# 등급을 올리는 신호. **정밀도를 재서 고른 것만 들어간다.**
_HIGH_PRECISION = ("weak_side_ink", "beam_adjacent", "beam_sloped", "glyph_shape", "clef_glyph", "narrow_hole", "beam_gap", "text_row", "side_pair", "wide_triple", "chord_column")
# `wide_triple` = 「가로로 긴 덩어리」 중 3음 덩어리 창(폭 ≤ 2.65 · 높이 2.4~2.8sp)을 머리 셋으로 나눈 라벨(`notehead_detect`, 2026-10-19 · §1-48 초안) — 보류 세트 새 유령 9가 이 경로
# `chord_column` = 화음 임시표 먼 열(창 왼끝 밖)에서 새로 읽은 임시표 · 그 마디 안 전파(`accidental_detect.chord_column_suspects`, 2026-10-19 · §1-49 초안)
# `side_pair` = 같은 음 라벨이 가로 0.6~1.2sp에 붙은 쌍의 잉크 얇은 쪽(`verify.side_pair_suspects`, 2026-10-18 · §1-44 초안)
# `text_row` = 오선 밖 1sp 이상 · 같은 높이 글자 크기 덩어리 ≥ 3(나타냄말 · 셈여림 줄, `verify.text_row_suspects`, 2026-10-15 · §1-41 초안) — 측정 「확실」 유령 19 · 헛표시 4
# `beam_gap` = 위 · 아래가 빔 두께의 긴 가로 막대로 막힌 흰 칸(짧은 겹빔 사이, `verify.beam_gap_suspects`, 2026-10-12 · DECISIONS §1-31) — 시뮬레이션 83 중 유령 79
# `narrow_hole` = 오선 밖 · 기둥 없음 · 위 · 아래 테두리가 짧은 좁은 구멍(셈여림 「p」 · 글자 고리, `verify.narrow_hole_suspects`, 2026-10-12 · DECISIONS §1-30) — 시뮬레이션 53 전부 유령
# `clef_glyph` = 보표 중간 음자리표 글리프 상자 안 라벨(`clef_keysig.clef_glyph_suspects`, 2026-10-05 · DECISIONS §1-23) — 측정 78 전부 유령
# `glyph_shape` = ♭형 · ♮형 모양 라벨(임시표 글리프 유령, `verify.glyph_shape_suspects`, 2026-10-04 · DECISIONS §1-20) — 걸림 290 중 유령 283(97.6%)
# `beam_sloped` = 기울어진 빔 마스크(G1, `verify.sloped_beam_suspects`)로 빔 위 · 빔 사이인 빈 머리(2026-10-03) · 세로 두께 < 0.7sp인 채워진 머리(§1-42, 2026-10-16).
# 삭제는 기각(DECISIONS 기각 27 — 진짜 화음 머리 3 오삭제), **표시만** 채택(§1-13): 지워지던 71 중 유령 68 · 진짜 3(정밀도 96%).
# 정밀도 0%인 무관한 신호를 살리는 것이 아니다(원칙 7 비해당) — 기각 사유는 오삭제였고 표시는 지우지 않는다
_LOW_PRECISION = ("vertical_blocked", "chord_rescue_added", "chord_middle_added")
# `chord_middle_added` = 3도 쌓기 화음 가운데 머리 추가 라벨(`chord_rescue.apply_chord_middles`, 2026-10-13 · DECISIONS §1-32) — `chord_rescue_added`와 같은 정책(주의)
# `chord_rescue_added` = 붙은 화음 구제(`modules/chord_rescue.py`)의 두 번째 파이프라인에서만 나온 라벨(2026-09-29).
# 20쪽 305개 중 맞는 음 299(98%) · 유령 5 · 음고 틀림 1 — 정밀도가 낮아서가 아니라, check로 두면 쪽당 check가
# 10.6 → 25.9로 부풀어 check의 뜻(「틀렸을 수 있음」)이 흐려지므로 주의로 둔다(사용자 결정, DECISIONS 1-9)

# 정밀도가 아니라 **판정을 보류했다**는 뜻으로 check를 붙이는 신호.
# `accidental_candidate` = 임시표 글리프 판정에 걸렸지만 채워진 머리라 지우지 않은 음표
# (`accidental_detect.remove_accidental_ghosts`). 실측 21개 중 진짜 음표 18 · 글리프 3이라
# 유령 정밀도는 낮다 — 유령 신호가 아니라 「예전 규칙이면 지워졌을 것, 사람이 볼 것」이다.
_REVIEW_REQUIRED = ("center_split", "ledger_short", "accidental_candidate", "accidental_unstable", "clef_changed", "clef_alto", "clef_unknown", "grace_size", "flat_propagated", "double_acc", "header_reopened")
# `center_split` = 머리 자신의 잉크(빈 행으로 이음줄과 가른 두꺼운 행 구간)로 다시 잰 중심이 엔진 중심과 다른 반칸(`verify.own_center_y`, 2026-11-20 · §1-54 초안)
# `ledger_short` = PDFium 렌더에서 덧줄이 `LEDGER_RUN_SP`보다 짧지만 `LEDGER_RUN_SP_PDFIUM` 이상 · 꽉 찬 머리 · 기둥 ≥ 3.5sp라 남긴 머리(`verify.drop_offstaff_ghosts`, 2026-11-17 B안)
# `header_reopened` = 줄 첫머리 헤더 끝을 줄여(§1-51 초안, 2026-10-26) 새로 음을 찾게 된 자리의 라벨(`clef_keysig.header_reopened_suspects`)
# `double_acc` = 겹임시표 ♭♭ · 𝄪가 붙은 머리와 같은 마디 뒤쪽 같은 음(`accidental_detect.double_acc_suspects`, 2026-10-15 · §1-40 초안) — 제품은 ♭♭ · 𝄪을 표기하지 못한다
# `flat_propagated` = 닫힘 전 영상으로만 읽은 ♭이 마디 안에서 전파된 음(`accidental_detect.c1_flat_suspects`, 2026-10-15 · §1-39 초안) — 원천 뒤 ♮을 못 읽으면 틀린다
# `grace_size` = 꾸밈음 크기(작은 머리) 음표(`verify.grace_size_suspects`, 2026-10-05 · DECISIONS §1-24) — 꾸밈음은 지원하지 않는다
# `clef_unknown` = 음자리표를 못 찾아 기본값(높은음)으로 읽은 보표의 음표 전부(`clef_keysig.unknown_clef_suspects`, 2026-10-05 · DECISIONS §1-22)
# `clef_alto` = 알토(가온) 음자리표 보표의 음표 전부(`clef_keysig.alto_suspects`, 2026-10-04 · DECISIONS §1-17) — 알토는 지원하지 않아 음고가 틀린다
# `clef_changed` = 보표 중간에 머리와 다른 음자리표가 검출된 뒤의 음표(`clef_keysig.clef_change_suspects`, 2026-10-04 · DECISIONS §1-16).
# 음고는 머리 음자리표로 계산되므로 그 뒤 음은 틀렸을 가능성이 높다 — Verovio 표시 733 중 음고 맞음 0(`CLEF_CHANGE.md` §2)
# `accidental_unstable` = 영상을 0.5px 옮겨 다시 판정하면 임시표가 달라지는 음표
# (`accidental_detect.unstable_accidentals`, 2026-09-29). 표기가 표시 없이 바뀌는 경계 글리프를 사람이 보게 한다

# 기록은 하되 등급 산정에 쓰지 않는 신호.
# `snap_residual`은 정밀도 0%로 이미 기각됐다(`docs/DECISIONS.md`).
# **기각된 신호를 '약한 신호'로 재활용하지 않는다** —
# 정밀도 0%는 약한 게 아니라 무관한 것이다.
_RECORDED_ONLY = ("snap_residual", "off_staff", "no_ledger")

WEAK_SIDE_INK = 0.40
SNAP_RESIDUAL = 0.30


def flags_of(row: dict) -> List[str]:
    """diagnose_labels() 한 줄에서 걸린 신호 이름을 전부 뽑는다.

    **등급과 별개로 다 남긴다.** 조건을 하나로 합치지 않는 것이 이 프로젝트의
    원칙이다(`docs/DECISIONS.md` §3-6) — 합치면 어떤 유형이 몇 개인지 셀 수 없다.
    """
    flags = []
    if row.get("weak_ink", 1.0) < WEAK_SIDE_INK:
        flags.append("weak_side_ink")
    if bool(row.get("touch_above")) != bool(row.get("touch_below")):
        flags.append("beam_adjacent")
    if not row.get("vertical_clear", True):
        flags.append("vertical_blocked")
    if row.get("residual", 0.0) > SNAP_RESIDUAL:
        flags.append("snap_residual")
    if row.get("accidental_candidate"):
        flags.append("accidental_candidate")
    if row.get("accidental_unstable"):
        flags.append("accidental_unstable")
    if row.get("chord_rescue_added"):
        flags.append("chord_rescue_added")
    if row.get("chord_middle_added"):
        flags.append("chord_middle_added")
    if row.get("beam_sloped"):
        flags.append("beam_sloped")
    if row.get("glyph_shape"):
        flags.append("glyph_shape")
    if row.get("clef_glyph"):
        flags.append("clef_glyph")
    if row.get("narrow_hole"):
        flags.append("narrow_hole")
    if row.get("beam_gap"):
        flags.append("beam_gap")
    if row.get("text_row"):
        flags.append("text_row")
    if row.get("side_pair"):
        flags.append("side_pair")
    if row.get("ledger_short"):
        flags.append("ledger_short")
    if row.get("center_split"):
        flags.append("center_split")
    if row.get("wide_triple"):
        flags.append("wide_triple")
    if row.get("chord_column"):
        flags.append("chord_column")
    if row.get("grace_size"):
        flags.append("grace_size")
    if row.get("flat_propagated"):
        flags.append("flat_propagated")
    if row.get("double_acc"):
        flags.append("double_acc")
    if row.get("clef_changed"):
        flags.append("clef_changed")
    if row.get("clef_alto"):
        flags.append("clef_alto")
    if row.get("clef_unknown"):
        flags.append("clef_unknown")
    if row.get("header_reopened"):
        flags.append("header_reopened")
    if row.get("outside_staff"):
        flags.append("off_staff")
        if not row.get("ledger_ok", True):
            flags.append("no_ledger")
    return flags


def mark_accidental_candidates(diag_rows: List[dict], flagged, flag: str = "accidental_candidate") -> List[dict]:
    """`remove_accidental_ghosts`가 지우지 않고 넘긴 음표를 진단 행에 표시한다.

    화면(`main._confidence_values`)과 JSON(`build_document`)이 둘 다 진단 행에서 확신도를
    계산하므로 **여기 한 곳에** 표시하면 두 출력이 같아진다. 행이 없는 음표는 새로 만든다."""
    keys = {(int(n.staff_index), int(n.x), int(n.y)) for n in flagged}
    seen = set()
    for row in diag_rows:
        key = (int(row["staff"]), int(row["x"]), int(row["y"]))
        if key in keys:
            row[flag] = True
            seen.add(key)
    diag_rows.extend({"staff": s, "x": x, "y": y, flag: True} for s, x, y in keys - seen)
    return diag_rows


def confidence_of(flags: List[str]) -> str:
    """걸린 신호에서 확신도를 정한다. **값만 정하고 색은 정하지 않는다.**"""
    if any(f in _HIGH_PRECISION or f in _REVIEW_REQUIRED for f in flags):
        return CONFIDENCE_CHECK
    if any(f in _LOW_PRECISION for f in flags):
        return CONFIDENCE_CAUTION
    return CONFIDENCE_CERTAIN


# ------------------------------------------------------------------
# 만들기
# ------------------------------------------------------------------
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _step_of(staff: Staff, y: float) -> int:
    """오선 맨 아랫줄 기준 반칸 단위 정수. 위로 갈수록 +."""
    return int(round((staff.grid_bottom - y) / (staff.spacing / 2.0)))


def label_id(staff_index: int, step: int, nx: float) -> str:
    """사람이 읽는 이름.

    **매칭 키가 아니다** — 해상도가 바뀌면 45~66%만 일치한다(실측).
    """
    return f"s{staff_index}-p{step}-x{round(nx * 2)}"


def build_document(
    input_path: str,
    page: int,
    staves: List[Staff],
    notes_with_names: List[Tuple[PitchedNote, str]],
    image_shape: Tuple[int, int],
    accidentals: Optional[List[str]] = None,
    diag_rows: Optional[List[dict]] = None,
    clefs: Optional[Dict[int, str]] = None,
    key_symbol: str = "",
    key_letters: Tuple[str, ...] = (),
    tonic: str = "",
    minor: bool = False,
    notation: str = "solfege",
    label_keys: Optional[List[Optional[dict]]] = None,
) -> dict:
    """인식 결과를 스키마대로 담는다."""
    by_index = {s.index: s for s in staves}
    h, w = image_shape[:2]

    diag_by_xy = {}
    for r in (diag_rows or []):
        diag_by_xy[(r["staff"], int(r["x"]), int(r["y"]))] = r

    labels = []
    for i, (note, text) in enumerate(notes_with_names):
        staff = by_index.get(note.staff_index)
        if staff is None:
            continue
        nx = note.x / staff.spacing
        step = _step_of(staff, note.y)
        row = diag_by_xy.get((note.staff_index, int(note.x), int(note.y)), {})
        flags = flags_of(row) if row else []
        acc = (accidentals[i] if accidentals and i < len(accidentals) else "") or None
        labels.append(dict(
            id=label_id(note.staff_index, step, nx),
            staff=note.staff_index,
            x=int(note.x),
            y=int(note.y),
            nx=round(nx, 3),
            pitch=f"{note.note_name}{note.octave}",
            step=step,
            accidental=acc,
            text=text,
            confidence=confidence_of(flags),
            flags=flags,
            edited=False,
        ))
        if label_keys and i < len(label_keys) and label_keys[i]:
            labels[-1]["key"] = label_keys[i]   # 조바꿈 구간 조표(§1-43) — 없으면 music의 쪽 조표

    return dict(
        schema=2 if any(l["accidental"] in DOUBLE_ACCIDENTALS for l in labels) else 1,
        generator=GENERATOR,
        source=dict(
            file=os.path.basename(input_path),
            page=int(page),
            width=int(w),
            height=int(h),
            dpi=RECOGNITION_DPI,
            sha256=_sha256(input_path),
        ),
        music=dict(
            key_symbol=key_symbol,
            key_count=len(key_letters),
            key_letters=list(key_letters),
            tonic=tonic,
            minor=bool(minor),
            notation=notation,
        ),
        staves=[dict(
            id=s.index,
            clef=(clefs or {}).get(s.index, "treble"),
            line_ys=[float(v) for v in s.line_ys],
            spacing=float(s.spacing),
            top=float(s.line_ys[0]),
            bottom=float(s.line_ys[-1]),
            # 반칸 격자의 원점. `line_ys`는 행 인덱스라 ±0.5px 양자화돼 있어
            # 음고를 반올림 경계까지 밀어붙인다. 앱도 이 값으로 계산해야 결과가 같다.
            bottom_fit=float(s.grid_bottom),
        ) for s in staves],
        labels=labels,
    )


def save_labels(path: str, doc: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 읽기 — 관대하게. 모르는 필드는 무시하고, 필수가 없으면 명확히 알린다.
# ------------------------------------------------------------------
_REQUIRED_DOC = ("schema", "staves", "labels")
_REQUIRED_STAFF = ("id", "line_ys", "spacing")
_REQUIRED_LABEL = ("staff", "x", "y", "text")


def _validate_number(value, field: str, convert):
    """기존 복원 방식으로 변환 가능한지 확인한다. 저장된 값 자체는 바꾸지 않는다."""
    try:
        number = convert(value)
    except (TypeError, ValueError, OverflowError):
        raise LabelSchemaError(f"{field} 값이 숫자가 아닙니다: {value!r}") from None
    if isinstance(number, float) and not math.isfinite(number):
        raise LabelSchemaError(f"{field} 값이 유한한 숫자가 아닙니다: {value!r}")
    return number


def load_labels(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError, UnicodeError) as e:
        raise LabelSchemaError(f"라벨 파일을 읽지 못했습니다: {path} ({e})") from e

    if not isinstance(doc, dict):
        raise LabelSchemaError("라벨 파일의 최상위가 객체가 아닙니다.")
    missing = [k for k in _REQUIRED_DOC if k not in doc]
    if missing:
        raise LabelSchemaError(f"필수 항목이 없습니다: {', '.join(missing)}")
    schema = _validate_number(doc["schema"], "schema", int)
    if schema > SCHEMA_VERSION:
        raise LabelSchemaError(
            f"이 파일은 schema {schema}인데 이 프로그램은 {SCHEMA_VERSION}까지 압니다. "
            "프로그램을 새로 받으세요."
        )
    # 필드 존재뿐 아니라 실제 복원 함수가 요구하는 구조도 확인한다.
    # 여기서 막아야 CLI의 LabelSchemaError 처리로 사용자에게 원인을 알릴 수 있다.
    for field in ("staves", "labels"):
        if not isinstance(doc[field], list):
            raise LabelSchemaError(f"{field} 값이 배열이 아닙니다: {doc[field]!r}")
    for i, s in enumerate(doc["staves"]):
        field = f"staves[{i}]"
        if not isinstance(s, dict):
            raise LabelSchemaError(f"{field} 값이 객체가 아닙니다: {s!r}")
        m = [k for k in _REQUIRED_STAFF if k not in s]
        if m:
            raise LabelSchemaError(f"{i}번째 보표에 필수 항목이 없습니다: {', '.join(m)}")
        ys = s["line_ys"]
        if not isinstance(ys, list):
            raise LabelSchemaError(f"{field}.line_ys 값이 배열이 아닙니다: {ys!r}")
        if not ys:
            raise LabelSchemaError(f"{field}.line_ys 값이 빈 배열입니다: {ys!r}")
        for j, y in enumerate(ys):
            _validate_number(y, f"{field}.line_ys[{j}]", lambda v: int(round(v)))
        _validate_number(s["id"], f"{field}.id", int)
        spacing = _validate_number(s["spacing"], f"{field}.spacing", float)
        if spacing <= 0:
            raise LabelSchemaError(f"{field}.spacing 값이 양수가 아닙니다: {s['spacing']!r}")
        if s.get("bottom_fit") not in (None, 0, ""):
            # 0/None/빈 문자열/누락은 기존처럼 line_ys[-1]로 복원한다.
            _validate_number(s["bottom_fit"], f"{field}.bottom_fit", float)
    for i, label in enumerate(doc["labels"]):
        field = f"labels[{i}]"
        if not isinstance(label, dict):
            raise LabelSchemaError(f"{field} 값이 객체가 아닙니다: {label!r}")
        m = [k for k in _REQUIRED_LABEL if k not in label]
        if m:
            raise LabelSchemaError(f"{i}번째 라벨에 필수 항목이 없습니다: {', '.join(m)}")
        for key in ("staff", "x", "y"):
            _validate_number(label[key], f"{field}.{key}", int)
        if "nx" in label:
            _validate_number(label["nx"], f"{field}.nx", float)
    if "source" in doc:
        source = doc["source"]
        if not isinstance(source, dict):
            raise LabelSchemaError(f"source 값이 객체가 아닙니다: {source!r}")
        if "page" in source:
            _validate_number(source["page"], "source.page", int)
        if source.get("dpi") is not None:
            _validate_number(source["dpi"], "source.dpi", int)
    return doc


def check_dpi(doc: dict) -> Optional[str]:
    """dpi가 다르면 그 사실을 문장으로 돌려준다(None이면 문제 없음).

    **조용한 warning으로 두지 않는다.** dpi가 다르면 라벨이 통째로 어긋나고
    사용자 수정이 절반쯤 사라진다. 부르는 쪽이 멈추고 사람에게 물어야 한다.

    **예외를 던지지 않는다.** 값이 숫자가 아니어도 traceback 대신 문장을 돌려준다 —
    손으로 고친 JSON에는 무엇이든 들어올 수 있고, 사용자에게 보여줄 것은
    파이썬 스택이 아니라 "무엇이 잘못됐는지"다.
    """
    source = doc.get("source")
    if not isinstance(source, dict):
        return None                     # source가 없으면 dpi를 따질 근거가 없다
    dpi = source.get("dpi")
    if dpi is None:
        return None                     # 옛 파일. 관대하게 넘어간다
    try:
        dpi_val = int(dpi)
    except (TypeError, ValueError, OverflowError):
        return (f"source.dpi 값이 숫자가 아닙니다: {dpi!r}. "
                f"이 프로그램은 {RECOGNITION_DPI}dpi로 인식합니다. "
                f"파일이 손상됐거나 손으로 고치다 잘못된 것 같습니다.")
    if dpi_val == RECOGNITION_DPI:
        return None
    return (f"저장된 라벨은 {dpi_val}dpi인데 이 프로그램은 {RECOGNITION_DPI}dpi로 인식합니다. "
            f"그대로 쓰면 라벨 위치가 어긋나고 고친 내용이 사라질 수 있습니다.")


def check_source(doc: dict, input_path: str,
                 image_shape: Optional[Tuple[int, int]] = None,
                 page: Optional[int] = None) -> Optional[str]:
    """이 라벨 파일이 **이 원본에서 나온 것인가.** 아니면 문장을 돌려준다.

    다른 악보에 남의 라벨을 얹으면 **엉뚱한 자리에 계이름이 찍히는데 오류는 안 난다.**
    스키마에 `sha256`과 `width`/`height`를 넣어 둔 것이 이걸 막기 위해서다
    (`docs/LABELS_SCHEMA.md`). 넣어만 두지 말고 실제로 봐야 한다.

    Args:
        image_shape: 지금 펼친 이미지의 `(높이, 너비, ...)`. 없으면 크기 검사를 건너뛴다.
        page: 지금 그리려는 페이지 번호. 없으면 페이지 검사를 건너뛴다.

    **없는 필드는 검사하지 않는다**(관대하게). 있는데 다르면 막는다.
    """
    source = doc.get("source")
    if not isinstance(source, dict):
        return None

    want = source.get("sha256")
    if isinstance(want, str) and len(want) == 64:
        try:
            got = _sha256(input_path)
        except OSError:
            got = None
        if got and got != want:
            return ("이 라벨 파일은 다른 원본에서 만들어졌습니다. "
                    f"라벨이 가리키는 파일은 {source.get('file', '(이름 없음)')}"
                    f"(sha256 {want[:12]}…)인데, "
                    f"지금 연 것은 {os.path.basename(input_path)}"
                    f"(sha256 {got[:12]}…)입니다.")

    if image_shape is not None:
        w_doc, h_doc = source.get("width"), source.get("height")
        try:
            h_now, w_now = int(image_shape[0]), int(image_shape[1])
        except (TypeError, ValueError, IndexError):
            h_now = w_now = None
        if (h_now is not None and isinstance(w_doc, int) and isinstance(h_doc, int)
                and (w_doc, h_doc) != (w_now, h_now)):
            return (f"이미지 크기가 다릅니다. 라벨은 {w_doc}x{h_doc} 기준인데 "
                    f"지금 펼친 것은 {w_now}x{h_now}입니다. "
                    "같은 파일이라도 페이지나 해상도가 다르면 라벨이 어긋납니다.")

    if page is not None:
        p_doc = source.get("page")
        if isinstance(p_doc, int) and p_doc != int(page):
            return (f"페이지가 다릅니다. 라벨은 {p_doc + 1}쪽 것인데 "
                    f"지금 {int(page) + 1}쪽을 그리려 합니다.")
    return None


def document_staves(doc: dict) -> List[Staff]:
    """JSON에서 보표를 되살린다. **인식을 돌리지 않는다.**"""
    out = []
    for s in doc["staves"]:
        line_ys = [int(round(v)) for v in s["line_ys"]]
        # `bottom_fit`이 없는 옛 파일은 맨 아랫줄로 되돌아간다(관대하게).
        out.append(Staff(line_ys=line_ys, spacing=float(s["spacing"]),
                         index=int(s["id"]),
                         bottom_fit=float(s.get("bottom_fit") or line_ys[-1])))
    return out


def document_notes(doc: dict) -> List[Tuple[PitchedNote, str]]:
    """JSON에서 (음표, 표기) 목록을 되살린다. 렌더러가 그대로 받는다."""
    out = []
    for label in doc["labels"]:
        pitch = str(label.get("pitch") or "")
        name, octave = (pitch[:-1] or "C"), pitch[-1:]
        out.append((PitchedNote(x=int(label["x"]), y=int(label["y"]),
                                note_name=name,
                                octave=int(octave) if octave.isdigit() else 4,
                                staff_index=int(label["staff"])),
                    str(label["text"])))
    return out


# ------------------------------------------------------------------
# 매칭 — id가 아니라 좌표로 붙인다
# ------------------------------------------------------------------
def _staff_bottoms(doc: dict) -> Dict[int, Tuple[float, float]]:
    """`{보표 번호: (격자 원점 y, 오선 간격)}`. 없는 값은 건너뛴다(관대하게)."""
    out: Dict[int, Tuple[float, float]] = {}
    for s in doc.get("staves", []):
        try:
            ys = s["line_ys"]
            bottom = float(s.get("bottom_fit") or ys[-1])
            out[int(s["id"])] = (bottom, float(s["spacing"]))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def match_labels(saved: dict, fresh: dict) -> Tuple[Dict[int, int], List[dict]]:
    """저장된 라벨을 새 인식 결과에 붙인다.

    **같은 보표**(y좌표로 판정) · 같은 `step` · `|Δnx| < MATCH_DNX_SP` 중
    가까운 것부터 그리디 1:1.

    **`step`이 다르면 붙이지 않는다** — 실측에서 그런 짝은 음이 실제로 달랐고
    (`D5→C5`), 사용자가 고친 계이름을 얹으면 틀린 글자가 붙는다.

    Returns:
        ({저장 라벨 인덱스: 새 라벨 인덱스}, 짝을 못 찾은 저장 라벨 목록)

    **못 찾은 것은 조용히 버리지 않는다.** 부르는 쪽이 사람에게 보여야 한다.
    """
    # 보표를 **순번이 아니라 y좌표로** 맞춘다. 순번을 쓰면 보표 하나가 더/덜
    # 검출되는 순간 그 아래가 전부 밀려 라벨이 통째로 어긋난다 — 실측에서
    # 맨 위 보표가 하나 어긋나자 쇼팽 1쪽 240개 중 **4개만** 짝을 찾았고,
    # 그 4개조차 밀린 번호에서 우연히 맞은 것이라 **남의 수정이 얹힐 자리**였다.
    # 고아는 사용자가 "내 수정이 사라졌네"로 알아채지만 잘못 붙은 것은 못 알아챈다.
    sb, fb = _staff_bottoms(saved), _staff_bottoms(fresh)
    A, B = saved["labels"], fresh["labels"]
    cand = []
    for i, a in enumerate(A):
        ya = sb.get(a.get("staff"))
        for j, b in enumerate(B):
            yb = fb.get(b.get("staff"))
            if ya is None or yb is None:
                # 보표 정보가 없는 옛 파일은 예전처럼 순번으로 맞춘다(관대하게)
                if a.get("staff") != b.get("staff"):
                    continue
            elif abs(ya[0] - yb[0]) > yb[1] * MATCH_STAFF_Y_SP:
                continue
            if a.get("step") != b.get("step"):
                continue
            d = abs(float(b.get("nx", 0.0)) - float(a.get("nx", 0.0)))
            if d < MATCH_DNX_SP:
                cand.append((d, i, j))
    cand.sort()
    used_a, used_b, mapping = set(), set(), {}
    for d, i, j in cand:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        mapping[i] = j
    orphans = [A[i] for i in range(len(A)) if i not in mapping]
    return mapping, orphans


def carry_over_edits(saved: dict, fresh: dict) -> Tuple[dict, List[dict]]:
    """사용자가 고친 라벨(`edited: true`)만 새 결과로 옮긴다.

    고치지 않은 라벨은 새 인식 결과가 더 낫다고 본다 — 알고리즘이 좋아졌을 테니.

    Returns:
        (수정을 얹은 새 문서, **잃어버린 사용자 수정 목록**)
    """
    mapping, orphans = match_labels(saved, fresh)
    for i, j in mapping.items():
        if saved["labels"][i].get("edited"):
            fresh["labels"][j]["text"] = saved["labels"][i]["text"]
            fresh["labels"][j]["edited"] = True
    lost = [o for o in orphans if o.get("edited")]
    return fresh, lost
