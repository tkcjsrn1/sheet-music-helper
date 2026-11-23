# -*- coding: utf-8 -*-
"""
3단계: 음고(Pitch) 계산 모듈

역할: 음표 머리의 y좌표와 해당 보표의 오선 간격(spacing)을 이용해
      음표가 오선의 몇 번째 줄/칸에 위치하는지 계산하고, 음이름(A~G)과 옥타브를 결정한다.

핵심 로직:
  - 오선 한 줄과 다음 줄 사이(spacing)는 음이름 2단계(예: E -> G) 차이이므로,
    반 칸(spacing/2)이 음이름 1단계에 해당한다.
  - "옥타브 내 음이름 번호"를 C=0, D=1, E=2, F=3, G=4, A=5, B=6 으로 고정하고,
    실제 음이름 옥타브 표기(예: C5)와 일치하도록 절대 인덱스를 계산한다.
    absolute_index = octave * 7 + letter_number
    이 방식은 "B4 다음이 C5"가 되는 표준 음악 표기를 자연스럽게 만족시킨다.
  - 보표의 맨 아래 오선(가장 낮은 y가 아니라 가장 큰 y, 즉 시각적으로 아래쪽 줄)을 기준선으로 삼고,
    이 기준선의 절대 인덱스(clef별로 다름)에서 음표까지의 step 수를 더해 최종 절대 인덱스를 구한다.
  - 조표(#, b)와 임시표는 검출 모듈이 없으므로 자연음(natural) 기준으로만 계산한다 (확장 지점으로 남김).
"""

from dataclasses import dataclass
from typing import List

from .notehead_detect import Notehead
from .preprocess import Staff

# 옥타브 내 음이름 번호 (C=0 ~ B=6). 절대 인덱스 계산의 기준.
NOTE_CYCLE = ["C", "D", "E", "F", "G", "A", "B"]

# 각 음자리표(clef)에서 "맨 아래 오선"이 나타내는 음의 절대 인덱스.
# 절대 인덱스 = octave * 7 + NOTE_CYCLE.index(letter)
#   - 높은음자리표(treble) 맨 아래 줄 = E4 -> 4*7 + 2 = 30
#   - 낮은음자리표(bass) 맨 아래 줄   = G2 -> 2*7 + 4 = 18
CLEF_BOTTOM_LINE_ABS_INDEX = {
    "treble": 30,  # E4
    "bass": 18,    # G2
}


class UnsupportedClefError(Exception):
    """지원하지 않는 음자리표를 요청했을 때 발생"""


@dataclass
class PitchedNote:
    """음고가 계산된 음표"""

    x: int
    y: int
    note_name: str    # 영문 음이름, 예: "E"
    octave: int        # 옥타브 번호, 예: 4
    staff_index: int


def calculate_pitch(notehead: Notehead, staff: Staff, clef: str = "treble") -> PitchedNote:
    """
    오선 간격 기준으로 음표 y좌표를 음이름/옥타브로 변환한다.

    Args:
        notehead: 2단계에서 검출된 음표 머리
        staff: 해당 음표가 속한 보표 (오선 y좌표, 간격 정보 포함)
        clef: "treble"(높은음자리표) 또는 "bass"(낮은음자리표)

    Raises:
        UnsupportedClefError: clef 값이 지원 목록에 없는 경우
    """
    if clef not in CLEF_BOTTOM_LINE_ABS_INDEX:
        raise UnsupportedClefError(
            f"지원하지 않는 음자리표입니다: {clef} (지원: {list(CLEF_BOTTOM_LINE_ABS_INDEX)})"
        )

    # 검출된 line_ys는 행 인덱스라 ±0.5px 양자화돼 있다. 반올림 경계까지 밀어붙이는
    # 원인이라, 다섯 줄로 맞춘 격자 원점을 쓴다 (`Staff.grid_bottom`).
    bottom_line_y = staff.grid_bottom          # 반칸 격자의 맨 아래 기준선
    half_step_px = staff.spacing / 2.0          # 반 칸 = 음이름 1단계 간격(px)

    # y가 작을수록(위로 갈수록) 음이 높아지므로 (bottom_line_y - notehead.y)로 부호를 맞춘다.
    raw_steps = (bottom_line_y - notehead.y) / half_step_px
    step = int(round(raw_steps))  # 반올림으로 가장 가까운 줄/칸에 스냅

    base_abs_index = CLEF_BOTTOM_LINE_ABS_INDEX[clef]
    abs_index = base_abs_index + step

    letter_number = abs_index % 7
    octave = abs_index // 7
    note_name = NOTE_CYCLE[letter_number]

    return PitchedNote(
        x=notehead.x,
        y=notehead.y,
        note_name=note_name,
        octave=octave,
        staff_index=notehead.staff_index,
    )


def calculate_pitches(
    noteheads: List[Notehead], staves: List[Staff], clef="treble"
) -> List[PitchedNote]:
    """
    여러 음표에 대해 calculate_pitch를 일괄 적용한다.

    Args:
        clef: 모든 보표에 적용할 음자리표 문자열("treble"/"bass"),
              또는 보표별 지정을 위한 dict[staff_index, str]
              (dict에 없는 보표는 treble로 처리)
    """
    staff_by_index = {s.index: s for s in staves}
    results: List[PitchedNote] = []
    for nh in noteheads:
        staff = staff_by_index.get(nh.staff_index)
        if staff is None:
            continue  # 해당 보표 정보가 없으면 건너뜀 (방어적 처리)
        if isinstance(clef, dict):
            staff_clef = clef.get(nh.staff_index, "treble")
        else:
            staff_clef = clef
        results.append(calculate_pitch(nh, staff, clef=staff_clef))
    return results
