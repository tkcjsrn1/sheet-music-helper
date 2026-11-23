# -*- coding: utf-8 -*-
"""
4단계: 음이름 -> 계이름(도레미) 변환 모듈

역할: 3단계에서 계산된 영문 음이름(C, D, E...)을 한글 계이름(도, 레, 미...)으로 변환한다.

주의: 이동 도(movable do)는 조표(key signature) 검출이 필요한데 현재 파이프라인에는
      조표 인식 모듈이 없으므로, 우선 다장조(C major) 기준 고정 도(fixed-do) 매핑만 제공한다.
      (조표 인식 모듈이 추가되면 key_signature 인자를 받아 이동 도로 확장 가능하도록 설계)
"""

from typing import Dict, List, Tuple

from .pitch_calculator import PitchedNote

# 다장조(C major) 기준 고정 도(fixed-do) 매핑
FIXED_DO_MAP: Dict[str, str] = {
    "C": "도",
    "D": "레",
    "E": "미",
    "F": "파",
    "G": "솔",
    "A": "라",
    "B": "시",
}


class UnknownNoteNameError(Exception):
    """FIXED_DO_MAP에 없는 음이름이 들어온 경우"""


# ---------------------------------------------------------------------------
# 이동 도(movable do)
#
# 한국 음악과 교육과정의 '계이름'은 이동도다: 으뜸음이 언제나 '도'이고,
# 단조는 나란한 장조를 기준으로 '라'에서 시작한다. 그래서 조표만 알면
# 장·단조 어느 쪽이든 같은 음계 이름표를 쓸 수 있다.
# (예: ♯2개 = 라장조/나단조 — 둘 다 D를 '도'로 읽는 자리표를 쓴다)
# ---------------------------------------------------------------------------

_LETTERS = ("C", "D", "E", "F", "G", "A", "B")
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
_DEGREE_NAMES = ("도", "레", "미", "파", "솔", "라", "시")

# 조표 개수 -> 장조 으뜸음
_MAJOR_BY_SHARPS = ("C", "G", "D", "A", "E", "B", "F#", "C#")
_MAJOR_BY_FLATS = ("C", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb")
_MAJOR_KEYS = set(_MAJOR_BY_SHARPS) | set(_MAJOR_BY_FLATS)
_MINOR_KEYS = {"A", "E", "B", "F#", "C#", "G#", "D#", "A#",
               "D", "G", "C", "F", "Bb", "Eb", "Ab"}


def normalize_key_override(value: str, minor: bool = False) -> str:
    """사용자 조성을 지원하는 장·단조 목록으로 검사한다. 빈칸은 조표 자동 판단."""
    if not value.strip():
        return ""
    normalized = value.replace("♯", "#").replace("♭", "b")
    if value != value.strip() or normalized not in (
        _MINOR_KEYS if minor else _MAJOR_KEYS
    ):
        raise UnknownNoteNameError(
            f"알 수 없는 조성입니다: {value} — 대문자로 입력하고 단조는 단조 옵션을 선택하세요 "
            "(예: D, Bb, F#; B♭, F♯도 가능)"
        )
    return normalized


def major_tonic_from_signature(key_symbol: str, key_count: int) -> str:
    """조표(기호, 개수)로 장조 으뜸음을 정한다. 조표가 없으면 다장조."""
    table = _MAJOR_BY_FLATS if key_symbol == "♭" else _MAJOR_BY_SHARPS
    return table[key_count] if 0 <= key_count < len(table) else "C"


def relative_major(tonic: str) -> str:
    """단조 으뜸음 -> 나란한 장조 으뜸음 (단3도 위). 예: D단조 -> F장조."""
    letter, alter = _split_tonic(tonic)
    idx = (_LETTERS.index(letter) + 2) % 7
    new_letter = _LETTERS[idx]
    target_pc = (_LETTER_PC[letter] + alter + 3) % 12
    new_alter = (target_pc - _LETTER_PC[new_letter] + 6) % 12 - 6
    return new_letter + ("#" * new_alter if new_alter > 0 else "b" * -new_alter)


def _split_tonic(tonic: str) -> Tuple[str, int]:
    """'Bb' -> ('B', -1), 'F#' -> ('F', +1)"""
    letter = (tonic[:1] or "C").upper()
    if letter not in _LETTER_PC:
        raise UnknownNoteNameError(f"알 수 없는 조성입니다: {tonic}")
    alter = tonic[1:].count("#") - tonic[1:].count("b")
    return letter, alter


def to_movable(note_name: str, alteration: int, tonic: str) -> str:
    """
    이동도 계이름을 만든다.

    도수는 **실제 음높이**로 정한다. 그 음이 조의 음계에 있으면 그 자리의
    이름을 그대로 쓰고, 없으면 반음 옆 음계 음의 이름에 #/b를 붙인다 —
    이것이 "조표 밖 음은 가장 가까운 음계 도수에 #/b를 붙인다"는 규칙이다.

    음이름의 **글자**로 도수를 정하면 실제로 쓰지 않는 이름이 나온다:
    사장조에서 F♭은 소리로는 음계의 '라'(E)인데 글자만 따지면 7도가 되어
    '시bb'가 된다(실측: 쇼팽 마단조 녹턴에서 2번 나왔다). 소리를 기준으로
    삼으면 그냥 '라'다.

    올림/내림 중 어느 쪽 이름을 쓸지는 그 음에 실제로 걸린 변화의 방향을
    따른다. 올린 음이면 아래 음계 음에 #을, 내린 음이면 위 음계 음에 b를
    붙인다 — 악보에 ♯이 붙은 음을 'b가 붙은 이름'으로 읽지 않도록.

    Args:
        note_name: 영문 음이름 한 글자 (C~B)
        alteration: 그 음에 실제로 적용된 반음 수 (조표 + 임시표 합산)
        tonic: 장조 으뜸음 ('D', 'Bb', ...)
    """
    tonic_letter, tonic_alter = _split_tonic(tonic)
    tonic_pc = (_LETTER_PC[tonic_letter] + tonic_alter) % 12
    actual = (_LETTER_PC[note_name] + alteration) % 12

    scale = [(tonic_pc + step) % 12 for step in _MAJOR_STEPS]
    if actual in scale:
        return _DEGREE_NAMES[scale.index(actual)]

    # 음계 밖의 음: 올린 음이면 반음 아래 자리에 #, 내린 음이면 반음 위 자리에 b.
    # 방향을 알 수 없으면(변화표 없이 음계 밖) 글자 기준 도수로 판정한다.
    if alteration > 0:
        direction = 1
    elif alteration < 0:
        direction = -1
    else:
        letter_degree = (_LETTERS.index(note_name) - _LETTERS.index(tonic_letter)) % 7
        expected = (tonic_pc + _MAJOR_STEPS[letter_degree]) % 12
        direction = 1 if (actual - expected + 6) % 12 - 6 > 0 else -1

    neighbour = (actual - direction) % 12
    if neighbour in scale:
        return _DEGREE_NAMES[scale.index(neighbour)] + ("#" if direction > 0 else "b")

    # 반대쪽도 본다 (온음 간격 자리에서 방향이 어긋난 경우)
    other = (actual + direction) % 12
    if other in scale:
        return _DEGREE_NAMES[scale.index(other)] + ("b" if direction > 0 else "#")

    # 여기까지 오면 겹올림/겹내림 — 글자 기준으로 표기한다
    degree = (_LETTERS.index(note_name) - _LETTERS.index(tonic_letter)) % 7
    diff = (actual - (tonic_pc + _MAJOR_STEPS[degree]) % 12 + 6) % 12 - 6
    return _DEGREE_NAMES[degree] + ("#" * diff if diff > 0 else "b" * -diff)


def to_solfege(
    note: PitchedNote,
    key_letters: Tuple[str, ...] = (),
    key_symbol: str = "",
    accidental: str = "",
    notation: str = "solfege",
    warnings: "List[dict] | None" = None,
    tonic: str = "",
) -> str:
    """
    음이름을 표기용 문자열로 변환한다.

    - notation="solfege"/"solfege-fixed": 고정 도 계이름 (C=도)
    - notation="solfege-movable": 이동 도 계이름 (으뜸음=도, tonic 필요)
    - notation="letter": 영문 음이름 (C, D, E...)
    - 조표가 인식된 경우(key_letters), 조표가 적용되는 음이름에는 #/b를 붙인다
      (예: 라장조에서 F -> "파#").
    - 임시표(accidental)가 있으면 조표보다 우선한다:
      "#"/"b"/"##"/"bb" -> 기호를 그대로 붙임, "natural" -> 기호 없음(조표 취소)
    - 이미지 합성용 폰트(맑은 고딕)에 ♯/♭ 글리프가 없어 □로 깨지므로 #/b로 표기한다.

    warnings: 리스트를 주면 '드문 이름(E♯/B♯/C♭/F♭)' 항목을 기록한다.
      **값은 바꾸지 않는다.** 값을 고쳐버리면 "미#"처럼 눈에 띄던 오류 신호가
      "미"라는 그럴듯한 오답으로 바뀌어 오히려 발견이 어려워지고, ♭계 조성
      (예: D♭장조)에서는 F♭·C♭이 정상적으로 등장하므로 정답을 망가뜨린다.
    """
    if note.note_name not in FIXED_DO_MAP:
        raise UnknownNoteNameError(f"알 수 없는 음이름입니다: {note.note_name}")
    base = note.note_name if notation == "letter" else FIXED_DO_MAP[note.note_name]

    if accidental in ("#", "b"):
        # 임시표 검출이 틀리면 악보에 존재할 수 없는 이름이 나올 수 있다
        # (실측: 라장조 곡의 D3에 ♯이 잘못 붙어 "미#"이 출력됐다 — 그 근본
        #  원인은 '잉크 없는 자리의 유령'이었고 검출 단계에서 해결됐다).
        # E♯/B♯/C♭/F♭은 드물지만 ♭계 조성에서는 정상적으로 나온다.
        # 표기 방식과 무관한 '검출 품질' 신호이므로 이동도에서도 똑같이 남긴다.
        rare = (accidental == "#" and note.note_name in ("E", "B")) or \
               (accidental == "b" and note.note_name in ("C", "F"))
        if rare and note.note_name not in key_letters and warnings is not None:
            warnings.append(dict(
                note_name=note.note_name, octave=note.octave,
                accidental=accidental, x=int(note.x), y=int(note.y),
                staff=note.staff_index, text=base + accidental,
                key=f"{key_symbol or '없음'}{len(key_letters) or ''}",
            ))

    if notation == "solfege-movable":
        # 실제로 적용된 반음 수를 구한다: 임시표가 있으면 그것이, 없으면 조표가 결정한다.
        if accidental in ("#", "b", "##", "bb"):
            alteration = accidental.count("#") - accidental.count("b")
        elif accidental == "natural":
            alteration = 0
        elif key_letters and note.note_name in key_letters:
            alteration = 1 if key_symbol == "♯" else -1
        else:
            alteration = 0
        return to_movable(note.note_name, alteration, tonic or "C")

    if accidental in ("#", "b", "##", "bb"):
        return base + accidental
    if accidental == "natural":
        return base

    if key_letters and note.note_name in key_letters:
        base += {"♯": "#", "♭": "b"}.get(key_symbol, key_symbol)
    return base


def to_solfege_batch(
    notes: List[PitchedNote],
    key_letters: Tuple[str, ...] = (),
    key_symbol: str = "",
    accidentals: "List[str] | None" = None,
    notation: str = "solfege",
    warnings: "List[dict] | None" = None,
    tonic: str = "",
) -> List[Tuple[PitchedNote, str]]:
    """여러 음표에 대해 to_solfege를 일괄 적용해 (음표, 표기) 튜플 리스트로 반환한다."""
    result = []
    for i, note in enumerate(notes):
        acc = accidentals[i] if accidentals and i < len(accidentals) else ""
        result.append((note, to_solfege(note, key_letters, key_symbol, acc,
                                        notation, warnings, tonic)))
    return result


def apply_double_accidentals(notes, accidentals, named, kinds,
                             key_letters=(), key_symbol="", notation="solfege", tonic=""):
    """CLI가 확정한 최종 음표 번호만 다시 표기한다. 전파·취소는 CLI의 값을 그대로 따른다."""
    if not kinds:
        return accidentals, named
    if len(notes) != len(accidentals) or len(notes) != len(named):
        raise ValueError("겹임시표의 음표·임시표·표기 목록 길이가 맞지 않습니다.")
    out_acc, out_named = list(accidentals), list(named)
    for index, (kind, _source) in kinds.items():
        if type(index) is not int or not 0 <= index < len(notes) or kind not in ("bb", "##"):
            raise ValueError("겹임시표의 음표 번호나 종류가 올바르지 않습니다.")
        if named[index][0] != notes[index]:
            raise ValueError("겹임시표의 음표·표기 순서가 맞지 않습니다.")
        out_acc[index] = kind
        out_named[index] = (notes[index], to_solfege(notes[index], key_letters, key_symbol,
                                                   kind, notation, None, tonic))
    return out_acc, out_named

def resolve_tonic(key_symbol: str, key_count: int,
                  key_override: str = "", minor: bool = False) -> str:
    """
    이동도 기준이 될 **장조 으뜸음**을 정한다.

    조표만으로는 장조인지 나란한 단조인지 알 수 없지만, 한국 교육과정의
    이동도는 단조를 '라'에서 시작하므로 **어느 쪽이든 자리표가 같다**.
    그래서 조표만 보고 장조로 읽으면 단조 곡도 그대로 맞는다.
    `--key`로 으뜸음을 직접 준 경우에만 `--minor` 여부가 의미를 갖는다
    (예: --key D --minor -> 라단조 -> 나란한 장조는 바장조).
    """
    key_override = normalize_key_override(key_override, minor)
    if key_override:
        return relative_major(key_override) if minor else key_override
    return major_tonic_from_signature(key_symbol, key_count)


def display_octaves(named: list, enabled: bool = False, edited: list | None = None) -> list:
    """그리기용 글씨만 만든다. 기본값과 사용자 수정 글씨는 그대로 둔다."""
    if type(enabled) is not bool:
        raise ValueError("옥타브 표시 여부는 참/거짓이어야 합니다.")
    if edited is not None and (len(edited) != len(named) or any(type(v) is not bool for v in edited)):
        raise ValueError("사용자 수정 표시가 라벨 목록과 맞지 않습니다.")
    if not enabled:
        return named
    return [(note, text if edited is not None and edited[i] else f"{text}{note.octave}")
            for i, (note, text) in enumerate(named)]
