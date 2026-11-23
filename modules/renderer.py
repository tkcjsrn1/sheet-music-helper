# -*- coding: utf-8 -*-
"""
5단계: 결과 렌더링 모듈

역할: 계산된 계이름 텍스트를 각 음표 좌표 바로 위(y - offset)에 합성하여
      최종 결과 이미지를 생성/저장한다.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .pitch_calculator import PitchedNote

_DEFAULT_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",     # 맑은 고딕
    r"C:\Windows\Fonts\malgunbd.ttf",   # 맑은 고딕 Bold
    r"C:\Windows\Fonts\gulim.ttc",      # 굴림
]


# 라벨을 '원칙 방향'(위 보표는 위, 아래 보표는 아래, 화음은 바깥쪽)에 두는 것과
# 오선 위에 얹히지 않게 하는 것 중 무엇을 더 중히 볼지의 저울. 값이 클수록
# 방향을 지킨다. 오선 겹침은 흰 테두리 덕에 읽을 수 있지만, 방향이 어긋난
# 라벨은 옆 보표 음표의 것으로 오해되므로 방향에 조금 더 무게를 둔다.
DIRECTION_WEIGHT = 2

# 제자리에서 허용하는 잉크 배수. 한 줄 내려가면 30~50px 멀어지므로
# 그 전에 조금 지저분한 자리라도 가까이 앉히는 편이 낫다.
# 값의 근거는 실측이다 — 이 값을 넣기 전 gap>30px가 14개, 넣은 뒤는 아래 표.
NEAR_INK_RELIEF = 3


# ------------------------------------------------------------------
# 확신도 표시
# ------------------------------------------------------------------
# **JSON에는 값(`certain`/`caution`/`check`)만 있고 색과 형태는 여기서 정한다**
# (`docs/LABELS_SCHEMA.md`). 앱은 같은 값을 읽어 자기 방식으로 그리면 된다.
#
# **색만으로 구분하지 않는다 — 형태도 함께 준다.** 색약인 사람에게 색은 신호가
# 아니다. `caution`은 옅기로, `check`는 점선 테두리로 갈린다.
#
# `mix`는 기본 글자색과 흰색을 섞는 비율이다. 0.0이면 원래 색 그대로,
# 1.0이면 흰색이다. **흰 테두리는 어느 단계에서도 유지한다** —
# 라벨의 28%가 오선과 겹치는데, 테두리가 없으면 옅은 글자는 그 위에서 읽을 수 없다.
#
# `caution`의 0.25는 눈으로 골랐다. 0.45·0.60도 만들어 오선과 겹친 라벨을 확대해
# 비교했는데, **0.45부터 밀집 구간에서 오선과 섞여 윤곽이 흐려졌다.**
# `caution`의 목적은 눈에 띄는 것이 아니라 `certain`과 다르다는 것만 알리는 것이다 —
# **못 읽으면 의미가 없다.**
LABEL_STYLES = {
    "certain": dict(mix=0.00, dash=None, dash_color=None),
    "caution": dict(mix=0.25, dash=None, dash_color=None),
    # 점선 테두리는 글자 상자 **바깥**에 그린다(아래 `CHECK_BOX_PAD` 참고).
    "check":   dict(mix=0.00, dash=(3, 3), dash_color=(210, 120, 0)),
}

# `check` 점선이 글자 상자에서 얼마나 떨어지는가(px).
# 음표 머리를 가리지 않으려면 이만큼 배치 여유가 더 필요하다. 다만
# **점선이 붙는 라벨에만 더한다** — 셋 다 늘리면 점선도 없는 `certain` 라벨이
# 이유 없이 밀려나 음표에서 멀어진다(실측: gap>30px가 8 → 13으로 늘었다).
# 라벨이 자기 음표에서 멀어지는 것은 미관이 아니라 **오독**이다.
CHECK_BOX_PAD = 2


class RendererError(Exception):
    """렌더링 과정에서 발생하는 오류"""


def _dashed_box(draw, x0: float, y0: float, x1: float, y1: float,
                color, dash) -> None:
    """점선 사각형. `check` 표시가 색 말고도 **형태로** 구분되게 하는 부분이다."""
    on, off = int(dash[0]), int(dash[1])
    step = max(1, on + off)
    for x in range(int(x0), int(x1), step):
        draw.line([(x, y0), (min(x + on, x1), y0)], fill=color, width=1)
        draw.line([(x, y1), (min(x + on, x1), y1)], fill=color, width=1)
    for y in range(int(y0), int(y1), step):
        draw.line([(x0, y), (x0, min(y + on, y1))], fill=color, width=1)
        draw.line([(x1, y), (x1, min(y + on, y1))], fill=color, width=1)


def _find_korean_font() -> str:
    for candidate in _DEFAULT_FONT_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    raise RendererError(
        "한글 폰트를 찾지 못했습니다. font_path 인자로 .ttf/.ttc 경로를 직접 지정해주세요."
    )


def render_solfege_on_image(
    original_bgr: np.ndarray,
    notes_with_names: List[Tuple[PitchedNote, str]],
    output_path: str,
    text_offset_y: int = 22,
    font_path: Optional[str] = None,
    font_size: int = 18,
    text_color: Tuple[int, int, int] = (220, 20, 20),
    staff_spacings: Optional[dict] = None,
    staves: Optional[list] = None,
    confidences: Optional[List[str]] = None,
    styles: Optional[dict] = None,
    placement_mode: str = "near",
    layout_status: Optional[dict] = None,
    image_writer=None,
) -> List[dict]:
    """
    계이름 텍스트를 각 음표 좌표 위에 합성해 output_path에 저장한다.

    배치 결과를 리스트로 돌려준다(점검용). 각 항목은
    {note, text, x, y, w, h, gap} — gap은 음표 머리 중심과 라벨 상자
    사이의 세로 거리(px)다. 이 값이 커질수록 어느 음표의 라벨인지
    알아보기 어려워지므로, 배치 규칙이 지켜졌는지 재는 잣대가 된다.

    Args:
        font_size: 보표 간격이 주어지면 18을 기준(1.1sp)으로 한 상대 크기.
            보표 간격이 없으면 이전과 같이 픽셀 크기.
        confidences: `notes_with_names`와 같은 순서의 확신도 값
            (`certain`/`caution`/`check`). 없으면 전부 `certain`으로 그린다.
            **모르는 값은 `certain`처럼 다룬다** — 나중에 값이 늘어도 옛 코드가
            죽지 않아야 한다(`docs/LABELS_SCHEMA.md`).
        styles: `LABEL_STYLES`를 덮어쓸 표. `settings.json`에서 넘겨 조정한다.
    """
    if placement_mode not in ('near','lanes'):
        raise RendererError('표시 방식은 음표 옆 또는 계이름 줄이어야 합니다.')
    if layout_status is not None:layout_status.clear()
    if placement_mode == 'lanes':
        return render_solfege_in_lanes(original_bgr,notes_with_names,output_path,
            text_offset_y=text_offset_y,font_path=font_path,font_size=font_size,
            text_color=text_color,staff_spacings=staff_spacings,staves=staves,
            confidences=confidences,styles=styles,layout_status=layout_status,image_writer=image_writer)

    if font_path is None:
        font_path = _find_korean_font()

    try:
        fonts = {font_size: ImageFont.truetype(font_path, font_size)}
    except OSError as e:
        raise RendererError(f"폰트를 불러오지 못했습니다: {font_path} ({e})") from e

    img_h, img_w = original_bgr.shape[:2]

    rgb = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil_img)

    # 확신도 표. 모르는 값이 오면 certain으로 떨어진다(관대하게).
    styles = dict(LABEL_STYLES, **(styles or {}))
    conf_of: dict = {}
    if confidences:
        for (note, _t), c in zip(notes_with_names, confidences):
            conf_of[id(note)] = c if c in styles else "certain"
    pad = 2
    # 기본 여유. 점선이 붙는 라벨만 루프 안에서 `CHECK_BOX_PAD`를 더한다
    # (`m`). **전부에 더하면 점선도 없는 라벨이 이유 없이 밀려난다.**
    draw_jobs: list = []
    placed: list = []
    placements: List[dict] = []

    # 악보의 검은 잉크(오선/덧줄/빔/음표) 마스크. 적분영상으로 만들어 두면
    # 임의의 사각형 안 잉크량을 O(1)에 셀 수 있어 후보 위치를 잔뜩 시험해도 싸다.
    gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
    dark = (gray < 128).astype(np.uint8)
    # 이동에서는 회색 윤곽/색 기호도 보호한다. 예산용 이진 마스크와 구분한다.
    protected_ink = np.any(original_bgr != 255, axis=2)
    # 오선 줄이 지나는 행은 장애물에서 뺀다. 라벨에는 흰 테두리가 있어 오선 위에
    # 얹혀도 읽는 데 지장이 없지만, 오선을 장애물로 세면 '보표 안'이 전부 막힌
    # 것처럼 보여 라벨이 보표 밖으로 멀리 밀려난다 — 그 결과 이웃 보표의 음표
    # 머리를 덮었다(실측: 2페이지 39마디 베이스 "레"가 59px 위로 올라감).
    # 마디선 좌표는 **오선 줄을 지우기 전에** 잡는다. 지운 뒤에는 세로선이
    # 끊겨 보표를 관통하지 않는 것으로 보인다.
    barlines: dict = {}
    if staves:
        from modules.verify import barline_positions
        xs_by_staff: dict = {}
        for _n, _t in notes_with_names:
            xs_by_staff.setdefault(_n.staff_index, []).append(int(_n.x))
        for st in staves:
            try:
                barlines[st.index] = barline_positions(
                    dark, st, xs_by_staff.get(st.index, ()))
            except Exception:
                barlines[st.index] = []

    if staves:
        for st in staves:
            for line_y in getattr(st, "line_ys", ()):
                y0 = max(0, int(round(line_y)) - 1)
                dark[y0:min(img_h, y0 + 3), :] = 0
                protected_ink[y0:min(img_h, y0 + 3), :] = False
    integral = cv2.integral(dark)

    # 라벨이 마디선을 넘으면 **다른 마디를 가리키는 것처럼 보인다.** 미관 문제가
    # 아니라 오독이다 — 사용자가 두 번 연속 유령으로 오인했다(실측: RE:Aoharu
    # 1쪽 3개, 2쪽 8개). 앞 마디가 쉼표뿐이라 비어 있으면 특히 그렇게 보인다.
    # 세로로 더 밀거나 오선에 겹치는 것이 이보다 낫다.
    def _crosses_barline(note, tx: int, text_w: int) -> bool:
        bl = barlines.get(note.staff_index)
        if not bl:
            return False
        cx = tx + text_w / 2.0
        lo, hi = (cx, note.x) if cx < note.x else (note.x, cx)
        return any(lo < b < hi for b in bl)

    # 오선·덧줄은 장애물에서 뺐지만(위 참조), 라벨이 줄 위에 얹히면 읽기가
    # 조금 나빠지는 것은 사실이다. 그래서 '잉크가 같다면 줄을 덜 지나가는 자리'를
    # 고르도록 줄 y좌표를 따로 모아 둔다 — 자리를 옮기는 기준이 아니라
    # 동점일 때의 우선순위다.
    line_ys_all: List[int] = []
    if staves:
        for st in staves:
            line_ys_all.extend(int(round(ly)) for ly in getattr(st, "line_ys", ()))

    def _lines_crossed(y0: int, y1: int) -> int:
        return sum(1 for ly in line_ys_all if y0 - 1 <= ly <= y1 + 1)

    def _ink(x0: int, y0: int, x1: int, y1: int) -> int:
        x0, x1 = max(0, min(img_w, int(x0))), max(0, min(img_w, int(x1)))
        y0, y1 = max(0, min(img_h, int(y0))), max(0, min(img_h, int(y1)))
        if x1 <= x0 or y1 <= y0:
            return 0
        return int(integral[y1, x1] - integral[y0, x1]
                   - integral[y1, x0] + integral[y0, x0])

    def _hits_placed(rect, boxes=None) -> bool:
        for r in placed if boxes is None else boxes:
            if not (rect[2] < r[0] or rect[0] > r[2] or rect[3] < r[1] or rect[1] > r[3]):
                return True
        return False

    # 음표 머리는 '넘어가면 안 되는' 장애물이다. 잉크 양으로만 판단하면 오선 세 줄과
    # 머리 하나가 비슷한 화소 수라 구분되지 않아, 라벨이 머리를 통째로 덮는 일이
    # 생긴다 (실측: 1페이지 37마디에서 베이스 "파#"이 트레블 음표 머리를 가렸다).
    head_rects: list = []
    for _n, _t in notes_with_names:
        _sp = (staff_spacings or {}).get(_n.staff_index) or 11.0
        head_rects.append((_n.x - _sp * 0.62, _n.y - _sp * 0.48,
                           _n.x + _sp * 0.62, _n.y + _sp * 0.48))

    def _hits_head(rect) -> bool:
        for r in head_rects:
            if not (rect[2] < r[0] or rect[0] > r[2] or rect[3] < r[1] or rect[1] > r[3]):
                return True
        return False

    # 피아노 악보에서 두 보표 사이 공간은 가장 붐빈다 — 위 보표의 낮은 음과
    # 아래 보표의 높은 음이 그 좁은 틈을 함께 노린다. 먼저 배치된 쪽이 자리를
    # 차지하면 나머지는 갈 곳이 없어 남의 보표까지 밀려 올라간다.
    # 그래서 위 보표는 '위쪽'을, 아래 보표는 '아래쪽'을 먼저 보게 해서
    # 서로 반대편으로 비켜서게 한다(화음 규칙이 있으면 그쪽이 우선한다).
    upper_staff: set = set()
    if staves:
        tops = sorted((s.index, float(s.top), float(s.bottom)) for s in staves)
        for idx, top, bottom in tops:
            sp_i = next((s.spacing for s in staves if s.index == idx), 0) or 1.0
            has_below = any(o_top > bottom and o_top - bottom < sp_i * 12
                            for _o, o_top, _b in tops if _o != idx)
            has_above = any(o_bottom < top and top - o_bottom < sp_i * 12
                            for _o, _t, o_bottom in tops if _o != idx)
            if has_below and not has_above:
                upper_staff.add(idx)

    # 화음은 '윗음 라벨은 위, 아랫음 라벨은 아래'로 갈라 놓아야 읽기 좋다.
    # 그래서 화음 바깥쪽 음표는 한 방향으로만 자리를 찾는다 — 양방향을 허용하면
    # 위쪽이 막혔을 때 아래로 넘어가 두 라벨이 모두 아래에 쌓인다.
    chord_links: dict = {}
    has_note_above: set = set()
    has_note_below: set = set()
    if staff_spacings:
        by_staff: dict = {}
        for note, _t in notes_with_names:
            by_staff.setdefault(note.staff_index, []).append(note)
        for staff_index, group in by_staff.items():
            sp = staff_spacings.get(staff_index)
            if not sp:
                continue
            for note in group:
                near = [o for o in group if o is not note
                        and abs(o.x - note.x) < sp * 0.9]
                chord_links[id(note)] = {id(o) for o in near
                    if 0 < abs(o.y - note.y) <= sp * 3.0}
                if any(0 < note.y - o.y <= sp * 3.0 for o in near):
                    has_note_above.add(id(note))
                if any(0 < o.y - note.y <= sp * 3.0 for o in near):
                    has_note_below.add(id(note))

    # 기존 이웃 범위 안의 좁은 묶음만 공통 열을 선호한다. 음악적 화음 판정은 아니다.
    # 0.9/3sp는 위의 기존 범위, 중앙값은 별도 간격 상수 없이 머리 위치에서 얻는다.
    # 전체 폭도 0.9sp 안이어야 옆 음형을 연쇄로 한 열에 묶지 않는다.
    chord_x: dict = {}
    chord_group: dict = {}
    note_by_id = {id(n): n for n, _t in notes_with_names}
    visited: set = set()
    for start in chord_links:
        if start in visited:
            continue
        component, pending = set(), [start]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(chord_links.get(current, set()) - component)
        visited.update(component)
        if len(component) < 2:
            continue
        xs = [note_by_id[i].x for i in component]
        sp = staff_spacings[note_by_id[start].staff_index]
        if max(xs) - min(xs) < sp * 0.9:
            center = float(np.median(xs))
            chord_x.update((i, center) for i in component)
            chord_group.update((i, start) for i in component)

    # 라벨이 '다른 음표를 넘어가는' 것을 막기 위한 세로 한계.
    # 라벨은 자기 음표 가까이 있어야 읽히는데, 위가 막히면 계속 위로 밀려
    # 위 보표의 음표보다도 높이 올라간다 — 그러면 그 위 음표의 라벨로 읽힌다
    # (실측: 2페이지 39마디 베이스 D3 라벨이 트레블 C4 음표보다 위에 놓였다).
    # 같은 x 근처에서 1.5sp 넘게 떨어진 음표는 '넘어가면 안 되는 선'이다.
    # (화음 이웃은 1sp 안쪽이라 여기서 빠지고, 위/아래 방향 규칙이 따로 맡는다)
    all_notes = [n for n, _t in notes_with_names]

    def _vertical_bounds(note, sp):
        top_limit, bottom_limit = None, None
        for other in all_notes:
            if other is note or abs(other.x - note.x) > sp * 1.2:
                continue
            if other.y < note.y - sp * 1.5:
                edge = other.y + sp * 0.55
                top_limit = edge if top_limit is None else max(top_limit, edge)
            elif other.y > note.y + sp * 1.5:
                edge = other.y - sp * 0.55
                bottom_limit = edge if bottom_limit is None else min(bottom_limit, edge)
        return top_limit, bottom_limit

    # 왼쪽 -> 오른쪽, 같은 x면 위 음표부터. 화음 라벨의 상하 순서를 지키려면
    # 위 음표를 먼저 배치하고 아래 음표는 그보다 아래에만 놓아야 한다.
    ordered = sorted(notes_with_names, key=lambda t: (t[0].staff_index, t[0].x, t[0].y))
    prev_note = None      # 같은 화음에서 바로 위에 배치한 음표
    prev_bottom = None    # 그 음표 라벨의 아래쪽 경계

    for note, text in ordered:
        sp_for_font = (staff_spacings or {}).get(note.staff_index)
        # 18 설정값은 보표 한 칸의 1.1배. 다른 설정값은 이 비율을 함께 조절한다.
        # 작은 보표의 가독성 하한: Aoharu 3쪽 711개 배치 측정(상자·마디선 겹침 0).
        note_font_size = (max(16, round(sp_for_font * 1.1 * font_size / 18))
                          if sp_for_font else font_size)
        if note_font_size not in fonts:
            try:
                fonts[note_font_size] = ImageFont.truetype(font_path, note_font_size)
            except OSError as e:
                raise RendererError(f"폰트를 불러오지 못했습니다: {font_path} ({e})") from e
        font = fonts[note_font_size]
        stroke_w = max(2, int(round(note_font_size * 0.11)))
        margin = stroke_w + pad
        bbox = draw.textbbox((0, 0), text, font=font)
        # bbox[0]/bbox[1]은 글자마다(받침 유무 등) 달라지는 좌/상단 오프셋이다.
        # draw.text 호출 시 이 값을 빼주지 않으면 계산한 상자와 실제로 그려지는
        # 위치가 어긋나, 겹침을 피해 고른 자리가 무의미해진다.
        off_x, off_y = bbox[0], bbox[1]
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # 확신도 표시가 차지하는 자리는 **라벨마다 다르다.** 점선이 붙는 것만
        # 상자가 커진다 — 나머지까지 키우면 멀쩡한 라벨이 음표에서 멀어진다.
        style = styles.get(conf_of.get(id(note), "certain")) or styles["certain"]
        m = margin + (CHECK_BOX_PAD if style.get("dash") else 0)

        target_x = max(0, min(note.x - text_w // 2, img_w - text_w))
        note_offset_y = round(text_offset_y * note_font_size / font_size)
        base_above = note.y - note_offset_y - text_h
        base_below = note.y + note_offset_y

        sp = (staff_spacings or {}).get(note.staff_index) or text_h * 1.5
        # 너무 멀리 밀면 어느 음표의 라벨인지 알 수 없게 되므로 상한을 둔다
        max_shift = int(sp * 3.0)
        # 화음이면 화음 규칙이, 아니면 보표 위치가 방향을 정한다
        below_first = (id(note) in has_note_above
                       or (id(note) not in has_note_below
                           and note.staff_index not in upper_staff))

        # 같은 화음에서 바로 위 음표의 라벨보다 위로 올라가면 상하가 뒤바뀌어
        # 읽는 사람이 음을 반대로 읽는다 (실측: 2페이지 50마디 베이스 F3+B2).
        floor_y = None
        if (prev_note is not None and prev_note.staff_index == note.staff_index
                and abs(prev_note.x - note.x) < sp * 0.9 and prev_note.y < note.y):
            floor_y = prev_bottom

        # 화음 순서를 지키는 하한(floor_y)과, 다른 음표를 넘지 않게 하는 한계는
        # 성격이 다르다. 앞의 것은 절대 어기면 안 되고(어기면 음이 뒤바뀐다),
        # 뒤의 것은 자리가 정 없으면 포기할 수 있다(라벨끼리 포개지는 편이 더 나쁘다).
        top_limit, bottom_limit = _vertical_bounds(note, sp)
        near_floor = floor_y if top_limit is None else (
            top_limit if floor_y is None else max(floor_y, top_limit))
        ceil_y = None if bottom_limit is None else bottom_limit - text_h

        # 위치를 '줄 단위'로만 옮긴다. 2px씩 미세 조정하면 라벨 높이가 제각각이라
        # 읽기 불편하다 — 같은 줄에 놓이면 눈이 한 줄씩 훑을 수 있다.
        row_step = text_h + m * 2 + max(2, int(round(note_font_size * 0.15)))
        offsets = [i * row_step for i in range(0, max(1, max_shift // row_step) + 1)]

        # 화음의 맨 윗음은 위쪽만, 맨 아랫음은 아래쪽만 본다
        top_of_chord = id(note) in has_note_below and id(note) not in has_note_above
        bottom_of_chord = id(note) in has_note_above and id(note) not in has_note_below

        # 라벨이 자기 음표에서 멀어지면 어느 음표의 것인지 알 수 없게 된다.
        # 그래서 '잉크가 가장 적은 자리'가 아니라 '충분히 깨끗한 자리 중 가장
        # 가까운 곳'을 고른다. 예전 코드는 잉크 최소만 보고 두 칸 위까지 올라가
        # 위 보표의 음표 머리를 덮었다(실측: 2페이지 39마디 베이스 D3의 "레"가
        # 59px 위로 올라가 트레블 음표를 가렸다).
        # 허용 잉크는 '얇은 선 하나가 지나가는 정도'다 — 라벨에 흰 테두리가
        # 있어 오선/덧줄 위는 읽는 데 지장이 없지만, 음표 머리(수백 화소)는 안 된다.
        ink_ok = text_w * 2

        # 한 줄 내려가면 라벨이 음표에서 단숨에 50px 넘게 멀어진다(줄 간격이
        # 글자 높이만큼이므로). 그 전에 **가로로 살짝 비켜** 자리를 찾는다 —
        # 세로로 한 칸 멀어지는 것보다 옆으로 반 글자 옮기는 편이 어느 음표의
        # 라벨인지 훨씬 덜 헷갈린다. 다만 이웃 음표 쪽으로 넘어가면 안 되므로
        # 옮기는 폭은 반 글자(0.5 글자폭)까지만 본다.
        # 옆으로 비키는 폭은 오선 간격에도 묶어 둔다. 이웃 음표는 보통
        # 2.5sp 이상 떨어져 있으므로 1.2sp를 넘지 않으면 '누구의 라벨인지'가
        # 뒤집히지 않는다 — 글자폭만 기준으로 삼으면 촘촘한 악보에서 옆
        # 음표 쪽으로 넘어간다.
        x_limit = sp * 1.2
        x_shifts = [0]
        for frac in (0.30, 0.55, 0.85):
            step = int(round(min(text_w * frac, x_limit)))
            if step and step not in x_shifts:
                x_shifts += [-step, step]
        # 두 보표 사이처럼 세로 공간이 아예 없는 자리에서는 이만큼으로도 모자란다.
        # 그때는 옆 음표 쪽으로 조금 더 밀어서라도 라벨끼리 포개지는 것만은 막는다
        # (포개지면 글자를 아예 못 읽지만, 조금 밀린 라벨은 읽을 수 있다).
        wide = int(round(sp * 2.0))
        if wide not in x_shifts:
            x_shifts += [-wide, wide]

        best = None  # (잉크량, 이동거리, y, x)
        for d in offsets:
            if top_of_chord:
                # 화음의 윗음은 위, 아랫음은 아래 — 방향을 섞지 않는다.
                # 윗음에게 아래쪽을 허용해 보면 윗음 하나는 가까워지지만
                # 아랫음이 그보다 더 아래로 밀려(상하 순서 유지) 전체로는
                # 멀어진다(실측: 30px 초과가 12개에서 35개로 늘었다).
                order = (base_above - d,)
            elif bottom_of_chord:
                order = (base_below + d,)
            elif below_first:
                order = (base_below + d, base_above - d)
            else:
                order = (base_above - d, base_below + d)
            # 같은 거리에 후보가 둘(위/아래)이면 잉크가 적은 쪽 —
            # 즉 오선·기둥과 덜 겹치는 쪽 — 을 고른다.
            here = None
            for pref, ty in enumerate(order):
                if ty < 0 or ty > img_h - text_h:
                    continue
                if near_floor is not None and ty < near_floor:
                    continue
                if ceil_y is not None and ty > ceil_y:
                    continue
                for dx in x_shifts:
                    tx = max(0, min(target_x + dx, img_w - text_w))
                    if _crosses_barline(note, tx, text_w):
                        continue
                    rect = (tx - m, ty - m,
                            tx + text_w + m, ty + text_h + m)
                    if _hits_placed(rect) or _hits_head(rect):
                        continue
                    cnt = _ink(tx, ty, tx + text_w, ty + text_h)
                    # 같은 조건이면 오선을 덜 지나가고, 가로로 덜 옮긴 자리를 고른다
                    # '충분히 깨끗한' 자리들끼리는 잉크량을 더 따지지 않는다.
                    # 그래야 방향 원칙(pref)이 판단을 이끌고, 잉크 몇 픽셀 때문에
                    # 라벨이 반대편(붐비는 보표 사이)으로 넘어가지 않는다.
                    lines_here = _lines_crossed(ty, ty + text_h)
                    score = (0 if cnt <= ink_ok else cnt,
                             pref * DIRECTION_WEIGHT + min(lines_here, 3),
                             lines_here, abs(dx))
                    if best is None or score < best[0]:
                        best = (score, d, ty, tx)
                    if here is None or score < here[0]:
                        here = (score, d, ty, tx)
                    if cnt <= ink_ok and dx == 0:
                        break   # 제자리가 깨끗하면 더 볼 것 없다
            # 제자리(d == 0)에서는 잉크를 더 봐준다. 한 줄 내려가면 라벨이 단숨에
            # 30~50px 멀어지는데, **자기 음표에서 멀어지는 것이 오선·기둥에
            # 겹치는 것보다 나쁘다** — 멀어진 라벨은 옆 음표의 것으로 읽힌다.
            # 음표 머리와 다른 라벨은 여기서도 절대 안 덮는다(_hits_head/_hits_placed).
            limit = ink_ok * NEAR_INK_RELIEF if d == 0 else ink_ok
            if here is not None and here[0][0] <= limit:
                # 이 거리에서 쓸 만한 자리를 찾았으면 더 멀리 가지 않는다
                best = here
                break

        if best is None:
            # 이동 상한 안에 자리가 없으면, 겹침만은 피하도록 더 멀리까지 찾는다.
            # (여기서 포기하고 기본 위치에 그리면 라벨끼리 완전히 포개져
            #  판독 불가가 된다 — 2페이지에서 3군데 발생했다)
            # 이때도 화음의 방향 제약은 지킨다. 예전에는 여기서 아래쪽을 먼저
            # 봤기 때문에, 위쪽이 막힌 화음의 윗음 라벨이 아랫음 라벨 밑으로
            # 내려가 상하가 뒤바뀌었다(실측: 2페이지 3군데, 4쌍).
            # 예비 탐색에서도 화음 방향은 지킨다. 윗음에게 아래쪽을 열어 주면
            # 라벨 겹침은 4쌍에서 1쌍으로 줄지만 화음 상하가 3쌍 뒤바뀌고
            # 음표 머리까지 가려진다 — 겹침보다 나쁜 결과다(실측).
            if top_of_chord:
                far_order = lambda d: (base_above - d,)
            elif bottom_of_chord:
                far_order = lambda d: (base_below + d,)
            elif below_first:
                far_order = lambda d: (base_below + d, base_above - d)
            else:
                far_order = lambda d: (base_above - d, base_below + d)
            # 여기서는 가로로도 훨씬 크게 비켜 본다. 세로 자리가 없을 때
            # 제자리만 고집하면 라벨이 그대로 포개져 글자를 못 읽는다
            # (실측: 세로 한계를 넣은 뒤 2페이지에서 4쌍이 포개졌다).
            far_x = [0]
            for mult in (1.0, 1.6, 2.4, 3.2):
                step = int(round(sp * mult))
                if step not in far_x:
                    far_x += [-step, step]
            # 세로로 더 멀어지기 전에, 같은 높이에서 옆으로 비켜 앉을 자리부터
            # 다시 본다 (가로 범위가 1차 탐색보다 훨씬 넓다).
            for d in range(0, int(sp * 8), row_step):
                for ty in far_order(d):
                    if ty < 0 or ty > img_h - text_h:
                        continue
                    if floor_y is not None and ty < floor_y:
                        continue
                    for fdx in far_x:
                        tx = max(0, min(target_x + fdx, img_w - text_w))
                        if _crosses_barline(note, tx, text_w):
                            continue
                        rect = (tx - m, ty - m,
                                tx + text_w + m, ty + text_h + m)
                        if not _hits_placed(rect) and not _hits_head(rect):
                            best = ((_ink(tx, ty, tx + text_w, ty + text_h),
                                     _lines_crossed(ty, ty + text_h), 0), d, ty, tx)
                            break
                    if best is not None:
                        break
                if best is not None:
                    break

        # 라벨은 절대 빠뜨리지 않는다. 그래도 자리가 없으면 기본 위치에 그린다.
        chosen = best[2] if best else max(0, min(base_above if base_above >= 0
                                                 else base_below, img_h - text_h))
        x_shift = 0
        if best:
            x_shift = best[3] - target_x
            target_x = best[3]

        # 라벨은 자기 음표 바로 위/아래에 있어야 한다. x가 크게 벗어나면
        # 어느 음표의 라벨인지 알 수 없으므로 경고를 남긴다(유령 검출 신호이기도 하다).
        # 겹침을 피하려고 일부러 옆으로 비킨 만큼(x_shift)은 정상이므로 빼고 잰다.
        off_center = abs((target_x - x_shift + text_w / 2.0) - note.x)
        if off_center > 10:
            print(f"[경고] 라벨이 음표에서 x로 {off_center:.0f}px 벗어났습니다 "
                  f"(음표 x={note.x}, y={note.y}, 라벨='{text}')")

        placed.append((target_x - m, chosen - m,
                       target_x + text_w + m, chosen + text_h + m))
        gap = (chosen - note.y) if chosen >= note.y else (note.y - (chosen + text_h))
        # 점검용: 라벨이 놓인 쪽과 '원칙상 놓여야 할 쪽'
        side = "below" if chosen >= note.y else "above"
        if top_of_chord:
            want = "above"
        elif bottom_of_chord:
            want = "below"
        else:
            want = "below" if below_first else "above"
        placements.append(dict(note=note, text=text, x=target_x, y=chosen,
                               w=text_w, h=text_h, gap=int(gap),
                               side=side, want=want))
        prev_note, prev_bottom = note, chosen + text_h + m

        # 그리기는 모든 자리와 수평 정돈이 확정된 뒤 한다. 원본 장애물은 그대로다.
        mix = float(style.get("mix", 0.0))
        fill = text_color if mix <= 0 else tuple(
            int(round(c + (255 - c) * mix)) for c in text_color)
        draw_jobs.append((font, off_x, off_y, fill, stroke_w, style.get("dash"),
                          style.get("dash_color") or text_color, m, note_offset_y))

    def _preserves_source_ink(p, tx, ty, job):
        if (tx, ty) == (p['x'], p['y']):
            return True
        font, ox, oy, fill, stroke, dash, dash_color, m, _offset = job
        # 본문뿐 아니라 흰 테두리/점선 여유 안의 잉크도 늘리지 않는다.
        for margin in (0, m):
            if _ink(tx-margin, ty-margin, tx+p['w']+margin, ty+p['h']+margin) > _ink(
                    p['x']-margin, p['y']-margin, p['x']+p['w']+margin, p['y']+p['h']+margin):
                return False
        x0, y0 = max(0, min(tx, p['x'])-m), max(0, min(ty, p['y'])-m)
        x1, y1 = min(img_w, max(tx, p['x'])+p['w']+m+1), min(img_h, max(ty, p['y'])+p['h']+m+1)
        original = rgb[y0:y1, x0:x1]
        differences = []
        for x, y in ((p['x'], p['y']), (tx, ty)):
            sample = Image.fromarray(original.copy())
            painter = ImageDraw.Draw(sample)
            painter.text((x-x0-ox, y-y0-oy), p['text'], font=font, fill=fill,
                         stroke_width=stroke, stroke_fill=(255, 255, 255))
            if dash:
                _dashed_box(painter, x-x0-CHECK_BOX_PAD, y-y0-CHECK_BOX_PAD,
                            x-x0+p['w']+CHECK_BOX_PAD, y-y0+p['h']+CHECK_BOX_PAD,
                            dash_color, dash)
            differences.append(np.abs(np.asarray(sample).astype(np.int16)-original.astype(np.int16)))
        # 같은 합계로 숫자 하나를 가리고 다른 획을 비우는 교환도 허용하지 않는다.
        return not np.any((differences[1] > differences[0]) & protected_ink[y0:y1, x0:x1, None])

    # 먼저 모든 자리를 예약한 뒤 비어 있는 가까운 원칙 자리/공통 열로 정돈한다.
    # 다른 라벨을 밀거나 기존 거리를 늘리지 않는다(초기 순차안 라 1.31→9.23sp 기각).
    groups: dict = {}
    for i, p in enumerate(placements):
        groups.setdefault(chord_group.get(id(p['note']), id(p['note'])), []).append(i)
    def _preserves_order(updates):
        for i, (_tx, ty, _gap, _side) in updates.items():
            p, note = placements[i], placements[i]['note']
            sp = (staff_spacings or {}).get(note.staff_index) or p['h'] * 1.5
            for j, other in enumerate(placements):
                q = other['note']
                if (q.staff_index != note.staff_index or abs(q.x - note.x) >= sp * 0.9
                        or q.y == note.y):
                    continue
                other_y = updates[j][1] if j in updates else other['y']
                old = (p['y'] + p['h'] / 2 - other['y'] - other['h'] / 2) * (note.y - q.y)
                new = (ty + p['h'] / 2 - other_y - other['h'] / 2) * (note.y - q.y)
                if old >= 0 and new < 0:
                    return False
        return True

    for indices in groups.values():
        members = set(indices)
        shared_side = None
        if len(indices) == 1 and 0 < indices[0] < len(placements) - 1:
            i = indices[0]
            left, middle, right = placements[i-1:i+2]
            note = middle['note']
            neighbors = (left['note'], right['note'])
            sp = (staff_spacings or {}).get(note.staff_index)
            bars = barlines.get(note.staff_index, ())
            if (sp and id(note) not in has_note_above and id(note) not in has_note_below
                    and all(n.staff_index == note.staff_index
                            and id(n) not in has_note_above and id(n) not in has_note_below
                            and 0.9*sp < abs(n.x - note.x) <= 3*sp for n in neighbors)
                    and not any(neighbors[0].x < bar < neighbors[1].x for bar in bars)
                    and left['side'] == right['side'] != middle['side']):
                shared_side = left['side']
        obstacles = [r for j, r in enumerate(placed) if j not in members]
        # 가까운 원칙 자리 → 수평 정돈만. 어느 쪽도 다른 글자를 밀어내지 않는다.
        for settle_near in (True, False):
            updates, rectangles = {}, []
            ink_blocked = False
            for i in indices:
                p = placements[i]
                note = p['note']
                center = chord_x.get(id(note), note.x)
                tx = (p['x'] if abs(p['x'] + p['w'] / 2 - center) <= 0.5 else
                      max(0, min(round(center - p['w'] / 2), img_w - p['w'])))
                m, offset = draw_jobs[i][-2:]
                ty, gap, side = p['y'], p['gap'], p['side']
                if settle_near:
                    if offset > gap:
                        break
                    gap, side = offset, shared_side or p['want']
                    ty = note.y + offset if side == 'below' else note.y - offset - p['h']
                    sp = (staff_spacings or {}).get(note.staff_index) or p['h'] * 1.5
                    top, bottom = _vertical_bounds(note, sp)
                    if (ty < 0 or ty > img_h - p['h'] or top is not None and ty < top
                            or bottom is not None and ty + p['h'] > bottom):
                        break
                rect = (tx - m, ty - m, tx + p['w'] + m, ty + p['h'] + m)
                if (_crosses_barline(note, tx, p['w']) or _hits_head(rect)
                        or _hits_placed(rect, obstacles + rectangles)):
                    break
                if not _preserves_source_ink(p, tx, ty, draw_jobs[i]):
                    ink_blocked = True
                    break
                updates[i] = tx, ty, gap, side
                rectangles.append(rect)
            else:
                if settle_near and not _preserves_order(updates):
                    continue
                # 같은 묶음은 원래 자리를 함께 비운 뒤 동시에 옮긴다.
                for (i, (tx, ty, gap, side)), rect in zip(updates.items(), rectangles):
                    placements[i].update(x=tx, y=ty, gap=gap, side=side)
                    placed[i] = rect
                break
            if ink_blocked:
                break  # 한 구성원이라도 기호를 더 가리면 묶음 전체를 원래 자리에 둔다.

    # 같은 머리 묶음의 기존 열 안에서 잉크·충돌이 늘지 않는 정돈만 비교한다.
    for indices in groups.values():
        if len(indices) < 2:
            continue
        current_centers = [placements[i]['x'] + placements[i]['w']/2 for i in indices]
        old_spread = max(current_centers) - min(current_centers)
        if old_spread <= 1:
            continue
        anchors = sorted(set(current_centers +
            [chord_x[id(placements[indices[0]]['note'])]]))
        before_dx = max(abs(placements[i]['x']+placements[i]['w']/2 -
                            placements[i]['note'].x) for i in indices)
        best_layout = None
        for center in anchors:
            updates = {}
            for i in indices:
                p = placements[i]
                tx = max(0, min(round(center-p['w']/2), img_w-p['w']))
                ty, m = p['y'], draw_jobs[i][-2]
                rect = (tx-m, ty-m, tx+p['w']+m, ty+p['h']+m)
                if (_crosses_barline(p['note'], tx, p['w']) or _hits_head(rect)
                        or not _preserves_source_ink(p, tx, ty, draw_jobs[i])):
                    continue
                updates[i] = (tx, rect)
            if True and len(updates) != len(indices):
                continue
            rectangles = [updates[i][1] if i in updates else placed[i] for i in indices]
            if any(_hits_placed(rect, [placed[j] for j in range(len(placed)) if j not in indices] +
                              rectangles[:k] + rectangles[k+1:])
                   for k, rect in enumerate(rectangles)):
                continue
            centers = [updates[i][0]+placements[i]['w']/2 if i in updates
                       else placements[i]['x']+placements[i]['w']/2 for i in indices]
            spread = max(centers) - min(centers)
            dx = max(abs(cx-placements[i]['note'].x) for i,cx in zip(indices,centers))
            if spread >= old_spread or dx > before_dx:
                continue
            score = (spread, dx, sum(abs(cx-placements[i]['note'].x) for i,cx in zip(indices,centers)))
            if best_layout is None or score < best_layout[0]:
                best_layout = score, updates
        if best_layout is not None:
            for i, (tx, rect) in best_layout[1].items():
                placements[i]['x'] = tx
                placed[i] = rect

    for p, job in zip(placements, draw_jobs):
        font, off_x, off_y, fill, stroke_w, dash, dash_color, _m, _offset = job
        draw.text((p['x'] - off_x, p['y'] - off_y), p['text'], font=font, fill=fill,
                  stroke_width=stroke_w, stroke_fill=(255, 255, 255))
        if dash:
            _dashed_box(draw, p['x'] - CHECK_BOX_PAD, p['y'] - CHECK_BOX_PAD,
                        p['x'] + p['w'] + CHECK_BOX_PAD, p['y'] + p['h'] + CHECK_BOX_PAD,
                        dash_color, dash)

    if image_writer is None:
        _save_rendered_image(pil_img, output_path)
    else:
        image_writer(pil_img)
    return placements


def _save_rendered_image(image, output_path):
    result_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    ext = os.path.splitext(output_path)[1] or ".png"
    ok, buf = cv2.imencode(ext, result_bgr)
    if not ok:
        raise RendererError(f"결과 이미지 저장 실패: {output_path}")
    buf.tofile(output_path)


def render_solfege_in_lanes(original_bgr, notes_with_names, output_path, **options):
    """보표마다 잉크 접촉이 적고 읽기 안전한 계이름 줄을 선택한다."""
    status=options.pop('layout_status',None)
    if status is not None:
        status.clear();status.update(applied=False,message='계이름 줄 공간이 부족해 이 쪽 전체를 음표 옆으로 표시했습니다.')
    writer = options.pop('image_writer', None)
    pending = []
    placements = render_solfege_on_image(original_bgr, notes_with_names, output_path,
                                         image_writer=pending.append if writer else None, **options)

    def fallback():
        if writer is not None:
            writer(pending.pop())
        return placements

    staves = sorted(options.get('staves') or [], key=lambda s: s.top)
    if (not staves or not placements or
            not {p['note'].staff_index for p in placements} <= {s.index for s in staves}):
        return fallback()
    h, w = original_bgr.shape[:2]
    font_path = options.get('font_path') or _find_korean_font()
    font_size = options.get('font_size', 18)
    spacings = options.get('staff_spacings') or {}
    styles = dict(LABEL_STYLES, **(options.get('styles') or {}))
    confidences = options.get('confidences') or []
    conf_of = {id(n): c for (n, _), c in zip(notes_with_names, confidences)}
    color = options.get('text_color', (220, 20, 20))
    fonts, jobs, boxes = {}, [], []
    for p in placements:
        sp = spacings.get(p['note'].staff_index)
        size = max(16, round(sp * 1.1 * font_size / 18)) if sp else font_size
        if size not in fonts:
            fonts[size] = ImageFont.truetype(font_path, size)
        font = fonts[size]
        ox, oy, _right, _bottom = font.getbbox(p['text'])
        stroke = max(2, round(size * .11))
        style = styles.get(conf_of.get(id(p['note']), 'certain')) or styles['certain']
        m = stroke + 2 + (CHECK_BOX_PAD if style.get('dash') else 0)
        mix = float(style.get('mix', 0))
        fill = color if mix <= 0 else tuple(int(round(c + (255-c)*mix)) for c in color)
        jobs.append((font, ox, oy, fill, stroke, style.get('dash'), style.get('dash_color') or color, m))
        boxes.append((p['x']-m, p['y']-m, p['x']+p['w']+m, p['y']+p['h']+m))

    dark = (cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY) < 128).astype(np.uint8)
    for staff in staves:
        for y in staff.line_ys:
            y = round(y)
            dark[max(0, y-1):min(h, y+2)] = 0
    ink = cv2.integral(dark)

    def ink_at(rect):
        x0, y0, x1, y1 = rect
        return int(ink[y1+1, x1+1] - ink[y0, x1+1] - ink[y1+1, x0] + ink[y0, x0])

    def overlaps(a, b):
        return not (a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])

    heads = []
    for note, _ in notes_with_names:
        sp = spacings.get(note.staff_index) or 11.0
        heads.append((note.x-.62*sp, note.y-.48*sp, note.x+.62*sp, note.y+.48*sp))
    planned = {}
    failed = []
    for si, staff in enumerate(staves):
        indices = [i for i,p in enumerate(placements) if p['note'].staff_index == staff.index]
        if not indices:
            continue

        # 대보표의 위쪽 보표는 위 여백, 아래쪽과 단독 보표는 아래 여백을 쓴다.
        above = (staff.index % 2 == 0 and si+1 < len(staves)
                 and staves[si+1].index == staff.index+1)
        side = 'above' if above else 'below'
        columns = []
        for i in sorted(indices, key=lambda i: placements[i]['note'].x):
            x = placements[i]['note'].x
            if not columns or x-placements[columns[-1][0]]['note'].x >= staff.spacing*.9:
                columns.append([])
            columns[-1].append(i)
        for col in columns:
            col.sort(key=lambda i: placements[i]['note'].y)
        depth = max(map(len, columns))
        margin = max(jobs[i][-1] for i in indices)
        step = max(placements[i]['h'] for i in indices) + 2*margin + 1
        band_h = depth*step
        scan_extra = round(4.5 * staff.spacing)
        separation = round(.4 * staff.spacing)
        if above:
            hi = int(staff.top) - 1
            lo = max(0, hi - band_h - scan_extra + 1)
            if si > 0:
                previous = staves[si-1]
                lo = max(lo, int(previous.bottom) + 1)
                if previous.index // 2 != staff.index // 2:
                    mid = int((previous.bottom + staff.top) // 2)
                    lo = max(lo, mid + separation)
            starts = range(hi-band_h+1, lo-1, -1)
        else:
            lo = int(staff.bottom) + 1
            hi = min(h-1, lo + band_h + scan_extra - 1)
            if si + 1 < len(staves):
                following = staves[si+1]
                hi = min(hi, int(following.top) - 1)
                if staff.index // 2 != following.index // 2:
                    mid = int((staff.bottom + following.top) // 2)
                    hi = min(hi, mid - separation)
            starts = range(lo, hi-band_h+2)

        members = set(indices)
        # 다른 보표는 줄로 이미 옮겼거나 기존 near 자리에 있다. 둘 다 장애물이다.
        obstacles = [rect for j,rect in enumerate(boxes) if j not in members] + heads
        reach = round(staff.spacing*.5)
        shifts = [0] + [dx for d in range(1,reach+1) for dx in (-d,d)]
        fixed = {}
        for i in indices:
            p, m = placements[i], jobs[i][-1]
            x = round(p['note'].x-p['w']/2)
            width = p['w']
            fixed[i] = (x, [rect for rect in obstacles
                            if rect[0]<=x+reach+width+m and rect[2]>=x-reach-m
                            and rect[1]<=hi and rect[3]>=lo])
        best = None
        for start in starts:
            updates, rects = {}, []
            total_ink = row_shifts = x_shifts = 0
            for col in columns:
                for rank,i in enumerate(col):
                    p, m = placements[i], jobs[i][-1]
                    note = p['note']
                    x, relevant = fixed[i]
                    y = start + (depth-len(col)+rank)*step + margin
                    # 가까운 열끼리 닿으면 옆 줄을 쓴다. 화음의 상하 순서는 아래에서 확인한다.
                    positions = (y, y-step, y+step, y-2*step, y+2*step, y-3*step, y+3*step)
                    choice = None
                    for ty in positions:
                        if ty-m < lo or ty+p['h']+m > hi:
                            continue
                        center = ty+p['h']/2
                        if any(abs(note.x-placements[j]['note'].x) < staff.spacing*.9 and
                               (note.y-placements[j]['note'].y)*(center-yj-placements[j]['h']/2)<0
                               for j, (_xj,yj) in updates.items()):
                            continue
                        for dx in shifts:
                            tx = x+dx
                            rect = (tx-m,ty-m,tx+p['w']+m,ty+p['h']+m)
                            if rect[0] < 0 or rect[2] >= w:
                                continue
                            contact = ink_at(rect)
                            # 가는 기호 가장자리만 허용한다. 간격 조정으로 잉크를 피할 수 있으면 우선한다.
                            if contact > 4 or any(overlaps(rect,other) for other in relevant+rects):
                                continue
                            score = (contact,ty!=y,abs(dx))
                            if choice is None or score<choice[0]:
                                choice = (score,tx,ty,rect)
                            if score == (0,False,0):
                                break
                        if choice is not None and choice[0] == (0,False,0):
                            break
                    if choice is None:
                        break
                    (contact,moved,dx),tx,ty,rect = choice
                    updates[i] = (tx,ty)
                    rects.append(rect)
                    total_ink += contact
                    row_shifts += moved
                    x_shifts += dx
                else:
                    continue
                break
            else:
                score = (total_ink,row_shifts,x_shifts)
                if best is None or score < best[0]:
                    best = (score,updates,rects)
                if score == (0,0,0):
                    break
        if best is None:
            failed.append((indices, staff.spacing))
            continue
        _, updates, rects = best
        for (i,(tx,ty)),rect in zip(updates.items(),rects):
            planned[i] = (tx,ty,side)
            boxes[i] = rect

    if not planned:
        return fallback()

    # 좁은 보표의 옆 표기에서 이미 뒤집힌 화음만 안전한 자리로 미세 조정한다.
    for indices, spacing in failed:
        by_pitch = sorted(indices, key=lambda i: placements[i]['note'].y)

        def center(i):
            p = placements[i]
            return p['y'] + p['h'] / 2

        def close(i, j):
            return abs(placements[i]['note'].x - placements[j]['note'].x) < .9 * spacing

        for pos, upper in enumerate(by_pitch):
            for lower in by_pitch[pos+1:]:
                high, low = placements[upper], placements[lower]
                distance = center(upper) - center(lower)
                if (distance <= 0 or high['note'].y == low['note'].y or
                        high['side'] != low['side'] or not close(upper, lower)):
                    continue
                step = int(distance) + 1
                if step > round(1.5 * spacing):
                    continue
                for rise in (step, 0, *range(1, step)):
                    shifts = {i: dy for i,dy in ((upper,-rise),(lower,step-rise)) if dy}
                    changes = {}
                    for i, dy in shifts.items():
                        p = placements[i]
                        x0, y0, x1, y1 = boxes[i]
                        rect = (x0, y0+dy, x1, y1+dy)
                        gap = p['gap'] + (dy if p['side'] == 'below' else -dy)
                        if not (gap >= 0 and 0 <= x0 <= x1 < w and
                                0 <= min(y0, rect[1]) and max(y1, rect[3]) < h):
                            break
                        ink_delta = ink_at(rect) - ink_at(boxes[i])
                        if ink_delta > 4 or any(overlaps(rect, other) for other in heads):
                            break
                        if any(close(i,j) and (p['note'].y - placements[j]['note'].y) *
                               (center(i) + dy - center(j) - shifts.get(j,0)) < 0
                               for j in indices if j != i):
                            break
                        changes[i] = (rect, gap, ink_delta)
                    else:
                        if sum(change[2] for change in changes.values()) > 0:
                            continue
                        if any(overlaps(rect, changes[j][0] if j in changes else other)
                               for i,(rect,_,_) in changes.items() for j,other in enumerate(boxes) if j != i):
                            continue
                        for i, (rect,gap,_) in changes.items():
                            placements[i].update(y=placements[i]['y']+shifts[i], gap=gap)
                            boxes[i] = rect
                        break

    for i,(tx,ty,side) in planned.items():
        p=placements[i]
        gap=ty-p['note'].y if side=='below' else p['note'].y-ty-p['h']
        p.update(x=tx,y=ty,gap=gap,side=side,lane=True)
    if status is not None:
        status.update(applied=True, message=(
            f'계이름 줄 공간이 부족한 보표 {len(failed)}개는 음표 옆으로 표시했습니다.' if failed else ''))
    pending.clear()
    image = Image.fromarray(cv2.cvtColor(original_bgr,cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    for p,job in zip(placements,jobs):
        font,ox,oy,fill,stroke,dash,dash_color,_m = job
        draw.text((p['x']-ox,p['y']-oy),p['text'],font=font,fill=fill,
                  stroke_width=stroke,stroke_fill=(255,255,255))
        if dash:
            _dashed_box(draw,p['x']-CHECK_BOX_PAD,p['y']-CHECK_BOX_PAD,
                        p['x']+p['w']+CHECK_BOX_PAD,p['y']+p['h']+CHECK_BOX_PAD,dash_color,dash)
    if writer is None:
        _save_rendered_image(image, output_path)
    else:
        writer(image)
    return placements