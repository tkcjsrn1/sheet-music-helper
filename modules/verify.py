# -*- coding: utf-8 -*-
"""
역방향 검증 모듈

지금까지의 점검(`--audit`)은 "음표마다 라벨이 붙었나"만 봤다. 그 방향만으로는
'라벨은 있는데 그 자리에 음표가 없는' 유령을 영원히 못 잡는다 — 실제로 1페이지
10마디의 유령이 v2부터 여러 판올림 동안 살아남았다. 이 모듈은 반대 방향,
즉 **라벨마다 진짜 음표 머리 잉크가 있나**를 검사한다.

판정 근거: 음표 머리는 채워졌든(온통 잉크) 비었든(링) **중심의 좌우 양쪽**
0.20~0.55sp 자리에 잉크가 있다. 빈 음표는 가운데가 비지만 링의 좌우 벽이
정확히 거기를 지난다. 반면 유령이 앉는 자리 — 마디선과 기둥 사이 빈칸,
기둥·8분음표 깃발, 빔과 빔 사이 틈 — 은 좌우 중 한쪽이 반드시 비어 있다.

오선을 지운 영상(no_staff)에서 재는 것이 핵심이다. 원본 이진화로 재면
오선·덧줄 위에 앉은 유령이 선 잉크만으로 조건을 통과한다.
"""

from typing import Dict, List, Optional, Sequence

import numpy as np

from .notehead_detect import remove_staff_lines
from .engine_mask_cache import cache_mask
from .preprocess import Staff


# 좌우 양쪽 잉크 비율 중 약한 쪽이 이 값 미만이면 유령 후보로 본다.
# 실측(RE Aoharu 3장): 진짜 음표 713개의 최솟값 0.40, 유령 3개는 0.03~0.20.
# 다른 악보(바흐/쇼팽 4종)에서도 진짜 음표는 대부분 0.35 이상이다.
GHOST_SIDE_THRESHOLD = 0.30


def own_center_y(no_staff: np.ndarray, x: int, y: int, spacing: float) -> "float | None":
    """머리 자신의 잉크로 다시 잰 중심 y — 두꺼운 행(폭 ≥ 0.45sp)이 y에서 끊김 없이 이어지는 구간의 중점.

    엔진 중심은 세로 closing 뒤 덩어리에서 잡아, 1px 틈만 둔 이음줄이 붙으면 위로 끌린다
    (B♭m 2쪽 보표 7: 머리 잉크 2510~2531 · 엔진 2516 · 맨윗줄 2520, 2026-11-20 실측).
    빈 행으로 이음줄과 갈라 머리 구간만 본다. 구간이 머리 높이(0.6~1.4sp)가 아니면 None(빔·기둥 덩어리).
    """
    h, w = no_staff.shape[:2]
    half = max(1, int(round(spacing * 0.6)))
    xa, xb = max(0, x - half), min(w, x + half + 1)
    reach = int(round(spacing * 1.2))
    ya, yb = max(0, y - reach), min(h, y + reach + 1)
    if not (ya <= y < yb) or xb <= xa:
        return None
    thick = (no_staff[ya:yb, xa:xb] > 0).sum(axis=1) >= spacing * 0.45
    i = y - ya
    if not thick[i]:
        return None
    lo = hi = i
    while lo > 0 and thick[lo - 1]:
        lo -= 1
    while hi + 1 < len(thick) and thick[hi + 1]:
        hi += 1
    if not (spacing * 0.6 <= hi - lo + 1 <= spacing * 1.4):
        return None
    return ya + (lo + hi) / 2.0


def _side_ink(no_staff: np.ndarray, x: int, y: int, spacing: float) -> tuple:
    """(약한 쪽, 강한 쪽) 잉크 비율. 중심 좌우 0.20~0.55sp 띠에서 잰다."""
    height, width = no_staff.shape[:2]
    dy = max(1, int(round(spacing * 0.25)))
    y0, y1 = max(0, y - dy), min(height, y + dy + 1)
    inner = max(1, int(round(spacing * 0.20)))
    outer = max(2, int(round(spacing * 0.55)))

    ratios = []
    for x0, x1 in ((max(0, x - outer), max(0, x - inner + 1)),
                   (min(width, x + inner), min(width, x + outer + 1))):
        strip = no_staff[y0:y1, x0:x1] > 0
        ratios.append(float(strip.mean()) if strip.size else 0.0)
    return min(ratios), max(ratios)


def barline_positions(binary: np.ndarray, staff: Staff,
                      note_xs: Sequence[int] = ()) -> List[int]:
    """
    마디선의 x좌표 목록.

    '보표를 위아래로 관통하는 세로 잉크'만으로는 부족하다 — 음표 기둥도 머리에서
    보표 반대편까지 뻗으면 같은 조건을 만족해서 마디 번호가 실제보다 크게 나온다.
    '보표 밖으로 안 나가는 것만 인정'하는 방법은 못 쓴다: 피아노 악보의 마디선은
    두 보표를 잇느라 보표 밖(대괄호 사이)으로 지나간다.
    대신 **마디선 자리에는 음표가 없다**는 사실을 쓴다 — note_xs를 주면 그 근처
    기둥을 걸러낸다.
    """
    top, bottom = int(staff.top), int(staff.bottom)
    band = binary[top:bottom + 1] > 0
    need = (bottom - top) * 0.95
    columns = np.where(band.sum(axis=0) >= need)[0]

    near = staff.spacing * 0.9
    groups: List[List[int]] = []
    for x in columns:
        if any(abs(int(x) - nx) <= near for nx in note_xs):
            continue    # 음표 기둥
        if not groups or x - groups[-1][-1] > 3:
            groups.append([int(x)])
        else:
            groups[-1].append(int(x))
    bars = [int(np.mean(g)) for g in groups]

    # 시스템 맨 앞의 브레이스·시작 세로줄과 맨 뒤의 마침줄은 마디 경계가 아니다.
    # 이것들을 세면 첫 마디가 3번째 마디로 나온다.
    if note_xs:
        lo, hi = min(note_xs), max(note_xs)
        bars = [b for b in bars if lo < b < hi]
    return bars


def measure_index(bars: Sequence[int], x: int) -> int:
    """그 보표(시스템) 안에서 몇 번째 마디인지 (1부터)."""
    return 1 + sum(1 for b in bars if b < x)


def reverse_check(
    result,
    notes,
    threshold: float = GHOST_SIDE_THRESHOLD,
    no_staff: Optional[np.ndarray] = None,
) -> List[Dict]:
    """
    라벨(=음고까지 계산된 음표) 하나하나에 대해 실제 음표 잉크가 있는지 확인해
    유령 후보 목록을 돌려준다. 약한 순으로 정렬된다.
    """
    if no_staff is None:
        no_staff = remove_staff_lines(result.binary, result.staves)
    staff_by_index = {s.index: s for s in result.staves}
    notes_by_staff: Dict[int, List[int]] = {}
    for note in notes:
        notes_by_staff.setdefault(note.staff_index, []).append(int(note.x))
    bars_by_staff = {s.index: barline_positions(result.binary, s,
                                                notes_by_staff.get(s.index, ()))
                     for s in result.staves}

    suspects: List[Dict] = []
    for note in notes:
        staff = staff_by_index.get(note.staff_index)
        if staff is None:
            continue
        low, high = _side_ink(no_staff, note.x, note.y, staff.spacing)
        if low < threshold:
            suspects.append(dict(
                staff=note.staff_index,
                measure=measure_index(bars_by_staff[note.staff_index], note.x),
                x=int(note.x), y=int(note.y),
                weak=round(low, 3), strong=round(high, 3),
            ))
    suspects.sort(key=lambda s: s["weak"])
    return suspects


def draw_reverse_image(result, notes, suspects: List[Dict], path: str) -> None:
    """초록 점 = 라벨 위치, 빨간 원 = 음표 잉크가 없는 유령 후보."""
    import cv2

    img = result.original_bgr.copy()
    for note in notes:
        cv2.circle(img, (int(note.x), int(note.y)), 3, (0, 170, 0), -1)
    for s in suspects:
        cv2.circle(img, (s["x"], s["y"]), 15, (0, 0, 255), 2)
    ok, buf = cv2.imencode(".png", img)
    if ok:
        buf.tofile(path)


# ---------------------------------------------------------------------------
# 라벨 진단 — '유령인가'를 한 가지 기준으로 묻지 않는다
#
# 좌우 잉크만 보던 기존 판정(reverse_check)은 **빈 공간에 앉은 유령**만 잡는다.
# 빔 위에 앉은 유령은 좌우가 잉크로 꽉 차 있어 그대로 통과한다
# (실측: 쇼팽 D♭ 1쪽에서 잔차가 큰 라벨 8개를 확대해 보니 7개가 음표가
#  아니었는데, 그중 5개가 빔 위였다 — 좌우 잉크 검사는 전부 통과했다).
#
# 그래서 조건을 하나로 합치지 않고 **따로따로 기록**한다. 합쳐 버리면 어떤
# 유형이 몇 개인지 셀 수 없고, 유형을 모르면 무엇부터 고쳐야 할지도 모른다.
# ---------------------------------------------------------------------------

# 잔차가 이 값을 넘으면 음표가 줄·칸 사이에 걸쳐 있다는 뜻이다.
# 0.5가 '정확히 중간'이므로 0.35는 한 칸 어긋나기 직전이다.
SNAP_RESIDUAL_LIMIT = 0.35


@cache_mask
def beam_mask(binary: np.ndarray, staves: List[Staff]) -> np.ndarray:
    """
    빔(8분음표 이하를 잇는 굵은 수평 막대)만 남긴 마스크.

    **오선을 먼저 지우고** 긴 수평 구조를 찾는다. 순서가 중요하다.

    예전에는 반대로 했다 — 긴 수평 opening을 먼저 걸어 오선과 빔을 함께 남긴 뒤,
    `staff.line_ys` 좌표의 ±0.22sp를 통째로 0으로 만들어 오선을 지웠다.
    그 방식은 **빔이 오선 줄을 가로지를 때 빔에도 구멍을 뚫는다.** 쇼팽 저음부의
    빠른 음표가 정확히 그렇다. 구멍이 뚫린 빔은 세로로 조각나고, 그 조각이
    아래 두께 opening(0.35sp)을 못 넘겨 마스크에서 사라진다.
    실측(쇼팽 2~6쪽 표본 300개): 남은 유령 20개가 **전부** 이 경로로 새어 나갔고,
    그중 11개가 두께 opening에서, 3개가 오선 지우기에서 탈락했다.
    ±0.22sp(총 9px)는 근거 없이 정한 값이기도 했다 — 오선 두께는 보통 2~3px다.

    지금은 `remove_staff_lines`를 먼저 건다. 그 함수는 오선을 페이지 폭의 1/30짜리
    가로 커널로 찾으므로 **빔은 애초에 후보가 되지 않고**, 음표가 선을 가로지르는
    자리는 세로 두께로 구제한다(그 함수 docstring 참고). 이미 검출 전 과정에서
    쓰이며 RE:Aoharu 711개가 그 위에서 나온 코드다.
    결과적으로 문턱값이 하나 줄었다(±0.22sp가 사라졌다).
    """
    import cv2

    sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
    no_staff = remove_staff_lines(binary, staves)
    wide = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * 2.5)), 1))
    horiz = cv2.morphologyEx(no_staff, cv2.MORPH_OPEN, wide)
    thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
    return cv2.morphologyEx(horiz, cv2.MORPH_OPEN, thick)


def beam_mask_strict(binary: np.ndarray, staves: List[Staff]) -> np.ndarray:
    """
    빔 마스크의 **좁은** 판. '빔에 닿음(한쪽만)' 판정에만 쓴다.

    왜 마스크가 둘인가 — 세 빔 조건의 강도가 다르기 때문이다.

      * '빔 위'와 '빔 사이'는 강하다. 그 자리 자체가 빔이거나 위아래가 모두 빔이면
        빈 머리가 있을 수 없다. 마스크를 넓혀도 안전하다(세 악보에서 오삭제 0).
      * '빔에 닿음(한쪽만)'은 약하다. **다른 성부의 빔이 그 근처를 지나갈 뿐인
        경우**가 있고, 그때 그 빈 음표는 진짜다. A안의 근거("빔은 채워진 머리에만
        붙는다")는 그 빔이 이 음표의 것일 때만 성립한다.

    실제로 마스크를 넓힌 뒤 이 조건이 RE:Aoharu 1쪽 `x=1260 y=822`의 진짜 2분음표를
    지웠다 — 덧줄 위 음표의 1.3sp 안으로 다른 성부의 빔이 지나가는 자리다.
    둘을 가를 값을 찾아봤지만 실패했다: 머리~빔 이음값은 유령 0.09~0.43 / 진짜 0.11,
    머리에 붙었는지는 유령 최소 0.28 / 진짜 0.79로 **분포가 겹친다.**
    진짜 음표 표본이 하나뿐이라 문턱을 유도할 수도 없다.

    그래서 이 조건만 예전의 좁은 마스크로 판정한다. 오선 좌표를 통째로 지우므로
    빔이 조각나 덜 잡히지만, 바로 그 덕에 남의 빔도 덜 잡는다.
    세 악보에서 오삭제 0으로 실증된 동작이다.

    ±0.22sp는 근거가 약한 상수다(오선 두께는 보통 2~3px인데 9px을 지운다).
    없애려다 오삭제가 나와 남겨 뒀다 — 이 조건을 안전하게 넓히는 방법을 찾으면
    이 함수와 상수를 함께 지울 수 있다.
    """
    import cv2

    sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
    wide = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * 2.5)), 1))
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, wide)
    for staff in staves:
        for line_y in staff.line_ys:
            y0 = max(0, int(line_y) - int(sp * 0.22))
            horiz[y0:int(line_y) + int(sp * 0.22) + 1, :] = 0
    thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
    return cv2.morphologyEx(horiz, cv2.MORPH_OPEN, thick)


def _band_ink(img: np.ndarray, x: int, y0: int, y1: int, half_w: int) -> float:
    h, w = img.shape[:2]
    y0, y1 = max(0, y0), min(h, y1)
    x0, x1 = max(0, x - half_w), min(w, x + half_w + 1)
    if y1 <= y0 or x1 <= x0:
        return 0.0
    return float((img[y0:y1, x0:x1] > 0).mean())


# --- 덧줄 ---------------------------------------------------------------
# 덧줄은 **수평선**이다. 그러니 수평선인지를 재야지, 음표 머리를 기준으로 좌우를
# 나눠 재면 안 된다 — 좌우 띠는 머리 중심 추정에 매달려 있어서 중심이 몇 px만
# 치우쳐도 한쪽 비율이 무너진다. 실제로 그 방식(좌우 각각 0.4 이상)은 쇼팽 5쪽에서
# 덧줄이 멀쩡히 있는데도 왼쪽 0.33 / 오른쪽 0.83으로 갈려 정상 음표 11개를 놓쳤다.
#
# 그래서 덧줄 y에서 **수평 런의 길이**를 잰다. 근거는 덧줄의 정의다 —
# 덧줄은 음표 머리보다 넓게 그린다. 머리보다 긴 수평 런이 있으면 덧줄이 있는 것이다.
#
# 문턱 1.30sp의 유도 (두 악보 전 쪽 실측):
#   - 음표 머리 폭      쇼팽 834개 봉우리 1.2sp(438)·1.3sp(223) / 바흐 124개 봉우리 1.2sp(53)
#   - 덧줄 있는 정상 음표의 런  두 악보 134개 중 **최소 1.40sp**
#   - 덧줄 없는 유령의 런        **최대 1.19sp**
#   1.19와 1.40 사이이면서 '머리 폭보다 넓다'를 만족하는 값이 1.30sp다.
#
# 빈 음표(2분·온음표)가 덧줄 위에 얹히면 링 안쪽이 흰색이라 런이 두 토막 난다.
# 덧줄은 하나의 선인데 머리가 덮고 있을 뿐이므로 closing으로 메운 뒤 잰다.
# 메우는 폭 0.6sp는 머리 폭(1.2sp)에서 링 벽 두께를 뺀 안쪽 흰 부분의 크기다.
# (0.3~0.9sp 사이에서 결과가 거의 안 변한다 — 이 값에 민감하지 않다)
LEDGER_RUN_SP = 1.30        # 덧줄로 인정하는 최소 수평 런 길이
LEDGER_BRIDGE_SP = 0.6      # 머리에 덮여 끊긴 자리를 메우는 폭
LEDGER_SEARCH_SP = 2.5      # 런을 찾는 좌우 범위
LEDGER_ROW_TOL = 2          # 덧줄 y 오차(px)

# 덧줄 자리 허용 오차. 실측(두 악보 전 쪽): 정상 음표에서 '필요한 y'와 '실제 덧줄 y'의
# 차이는 최대 0.30sp까지 벌어진다(중앙 0.18). 0.45sp는 그 위에 반칸(0.5sp)까지
# 못 미치게 둔 값이다 — 반칸을 넘기면 이웃 줄을 자기 줄로 착각한다.
#
# 이 값은 좁힐 수 없다. 이 오차를 유령 쪽에서도 재 보면 최소 0.12sp여서
# 정상(최대 0.30)과 **분포가 겹친다**. 좁히면 유령 몇 개를 더 잡는 대신 오삭제가 난다.
# 그래서 겹치는 구간은 포기하고 넉넉한 쪽을 택했다 — 오삭제 0이 절대 조건이므로.
# 결과: 이웃 음표의 진짜 덧줄이 반칸 안에 있는 글리프 18개는 이 조건으로 못 잡는다.
# 대부분 임시표(♯♭♮)인데, 임시표는 자기가 붙는 음표와 **같은 높이**에 놓이므로
# 그 음표의 덧줄과 세로로 겹치는 것이 조판 규칙상 당연하다 — 원리적 한계다.
LEDGER_MATCH_SP = 0.45


def ledger_run_sp(binary: np.ndarray, x: int, y: int, spacing: float) -> float:
    """(x, y)를 지나는 수평 런의 길이를 sp 단위로. 머리에 덮인 자리는 메운다."""
    import cv2

    h, w = binary.shape[:2]
    half = int(round(spacing * LEDGER_SEARCH_SP))
    x0, x1 = max(0, x - half), min(w, x + half + 1)
    if x1 <= x0:
        return 0.0
    kernel = np.ones((1, max(1, int(round(spacing * LEDGER_BRIDGE_SP)))), np.uint8)
    best = 0.0
    for dy in range(-LEDGER_ROW_TOL, LEDGER_ROW_TOL + 1):
        yy = y + dy
        if not (0 <= yy < h):
            continue
        row = (binary[yy, x0:x1] > 0).astype(np.uint8)
        if not row.any():
            continue
        closed = cv2.morphologyEx(row.reshape(1, -1), cv2.MORPH_CLOSE, kernel).ravel()
        i = x - x0
        if not closed[i]:
            continue
        a = i
        while a > 0 and closed[a - 1]:
            a -= 1
        b = i
        while b + 1 < len(closed) and closed[b + 1]:
            b += 1
        best = max(best, (b - a + 1) / spacing)
    return best


def ledger_ys(binary: np.ndarray, x: int, staff: Staff,
              y_lo: float, y_hi: float, run_sp: float = LEDGER_RUN_SP) -> List[int]:
    """음표 x 자리에서 덧줄의 y좌표들 (머리 폭보다 긴 수평 런이 있는 줄)."""
    sp = staff.spacing
    h = binary.shape[0]
    out: List[int] = []
    for y in range(max(0, int(y_lo)), min(h, int(y_hi))):
        if ledger_run_sp(binary, x, y, sp) >= run_sp:
            if not out or y - out[-1] > sp * 0.5:
                out.append(y)
    return out


def needed_ledger_ys(staff: Staff, y: int) -> Optional[List[float]]:
    """오선 밖 머리 하나에 필요한 덧줄들의 y좌표. 판정 대상이 아니면 None.

    개수는 오선 가장자리에서 잰 거리를 **내림**한 값이다. 줄 위 음표는 거리가
    sp의 정수배(k)라 k개, 칸에 있는 음표는 k+0.5배라 역시 k개로 떨어진다.
    예전 식 `int(dist/sp + 0.25)`는 머리 y가 0.4sp만 위로 치우쳐도 한 개를 더
    요구해서, 있지도 않은 덧줄을 찾다가 정상 음표를 지웠다(쇼팽 5쪽 x=2114 y=3038).
    """
    sp = staff.spacing
    above = y < staff.top - sp * 0.4
    below = y > staff.bottom + sp * 0.4
    if not (above or below):
        return None
    dist = (y - staff.bottom) if below else (staff.top - y)
    k_max = int(dist / sp)
    if k_max < 1:
        return None
    sign = 1 if below else -1
    base = staff.bottom if below else staff.top
    return [base + sign * sp * k for k in range(1, k_max + 1)]


def ledger_check(binary: np.ndarray, staff: Staff, x: int, y: int,
                 run_sp: float = LEDGER_RUN_SP) -> Optional[bool]:
    """오선 밖 머리에 필요한 덧줄이 실제로 그려져 있는가. 대상이 아니면 None. `run_sp` = 덧줄로 인정하는 최소 런."""
    need = needed_ledger_ys(staff, y)
    if need is None:
        return None
    sp = staff.spacing
    if y > staff.bottom:
        got = ledger_ys(binary, x, staff, staff.bottom + sp * 0.5, y + sp * 0.5, run_sp)
    else:
        got = ledger_ys(binary, x, staff, y - sp * 0.5, staff.top - sp * 0.5, run_sp)
    return all(any(abs(w - g) <= sp * LEDGER_MATCH_SP for g in got) for w in need)


def diagnose_labels(result, notes) -> List[Dict]:
    """
    라벨 하나하나에 '음표가 맞는지' 물어보는 조건들을 각각 세워 기록한다.

    돌려주는 항목(라벨당 하나):
        weak_ink      좌우 잉크 중 약한 쪽 비율 (기존 판정 기준)
        on_beam       그 자리 자체가 빔인가
        beam_above/below   위/아래 1.3sp 안에 빔이 있는가 (넓은 마스크)
        touch_above/below  같은 것을 좁은 마스크로 — '한쪽만 닿음' 판정에 쓰는 값
        vertical_clear     머리 위아래가 비어 있는가 (진짜 머리면 비어 있다)
        residual      줄·칸에서 벗어난 정도 (0.5가 정확히 중간)
        outside_staff 오선 밖인가
        ledger_ok     오선 밖일 때 필요한 덧줄이 실제로 있는가

    판정을 내리지 않고 값만 남긴다 — 유형별로 세는 것은 부르는 쪽의 몫이다.
    """
    no_staff = remove_staff_lines(result.binary, result.staves)
    mask = beam_mask(result.binary, result.staves)
    narrow = beam_mask_strict(result.binary, result.staves)
    staff_by_index = {s.index: s for s in result.staves}
    head_filled = getattr(result, "head_filled", {})            # 꽉 찬 머리만 center_split(빈 머리는 고리 안쪽 행이 얇아 구간이 끊긴다 — §1-54)
    short_xy = getattr(result, "ledger_short_xy", set())     # 짧은 덧줄 구제 머리(`drop_offstaff_ghosts`) → 등급 check

    notes_by_staff: Dict[int, List[int]] = {}
    for note in notes:
        notes_by_staff.setdefault(note.staff_index, []).append(int(note.x))
    bars_by_staff = {s.index: barline_positions(result.binary, s,
                                                notes_by_staff.get(s.index, ()))
                     for s in result.staves}

    rows: List[Dict] = []
    for note in notes:
        staff = staff_by_index.get(note.staff_index)
        if staff is None:
            continue
        sp = staff.spacing
        x, y = int(note.x), int(note.y)
        low, high = _side_ink(no_staff, x, y, sp)

        half = max(1, int(sp * 0.5))
        # 문턱값 0.05의 근거 — 사람이 확대해 확인한 쇼팽 D♭ 1쪽 13곳 실측:
        # 진짜 음표 6곳은 자리·위·아래가 모두 정확히 0.00이었고,
        # 빔 위에 앉은 유령 5곳은 위 또는 아래가 0.11~0.40이었다.
        # (채워진 음표는 빔에 직접 붙으므로 이 값이 높은 것이 정상이다 —
        #  그래서 판정하지 않고 값만 남긴다)
        on_beam = _band_ink(mask, x, y - int(sp * 0.2), y + int(sp * 0.2) + 1, half) > 0.05
        beam_above = _band_ink(mask, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        beam_below = _band_ink(mask, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05
        # 판정과 같은 기준으로 남긴다 — '한쪽만'은 좁은 마스크를 본다
        touch_above = _band_ink(narrow, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        touch_below = _band_ink(narrow, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05

        # 진짜 음표 머리는 위아래가 비어 있다(기둥은 폭이 좁아 여기 안 걸린다).
        # 빔 위에 앉은 유령은 위아래도 잉크라 이 값이 높다.
        up_ink = _band_ink(no_staff, x, y - int(sp * 1.1), y - int(sp * 0.6), half)
        dn_ink = _band_ink(no_staff, x, y + int(sp * 0.6), y + int(sp * 1.1), half)
        vertical_clear = max(up_ink, dn_ink) < 0.45

        raw = (staff.grid_bottom - y) / (sp / 2.0)   # 음고 계산과 같은 격자를 봐야 한다
        residual = abs(raw - round(raw))
        # 머리 자신의 잉크로 다시 잰 중심이 다른 반칸이면 음고 판정 보류(§1-54 초안, 원칙 7 비해당 — 잔차가 아니라 독립 재측정의 불일치)
        own = own_center_y(no_staff, x, y, sp) if head_filled.get((note.staff_index, x, y)) is True else None
        center_split = (own is not None and abs(own - y) >= sp * 0.15
                        and round((staff.grid_bottom - own) / (sp / 2.0)) != round(raw))

        above = y < staff.top - sp * 0.4
        below = y > staff.bottom + sp * 0.4
        outside = above or below
        ledger_ok = True
        if outside:
            verdict = ledger_check(result.binary, staff, x, y)
            ledger_ok = True if verdict is None else verdict

        rows.append(dict(
            staff=note.staff_index,
            measure=measure_index(bars_by_staff[note.staff_index], x),
            x=x, y=y, pitch=f"{note.note_name}{note.octave}",
            weak_ink=round(low, 3), strong_ink=round(high, 3),
            on_beam=on_beam, beam_above=beam_above, beam_below=beam_below,
            touch_above=touch_above, touch_below=touch_below,
            vertical_clear=vertical_clear,
            up_ink=round(up_ink, 3), dn_ink=round(dn_ink, 3),
            residual=round(residual, 3),
            outside_staff=outside, ledger_ok=ledger_ok,
            ledger_short=(note.staff_index, x, y) in short_xy,
            center_split=center_split,
        ))
    return rows


def sloped_beam_mask(binary: np.ndarray, staves: List[Staff]) -> np.ndarray:
    """`beam_mask`에 기울어진 빔(±7.5~45°, 7.5° 간격) 선 열림을 합친 마스크 — G1 (A-17 §7, 2026-09-30 측정).

    `beam_mask`는 가로 2.5sp 직선 열림이라 가파른 셋잇단 빔을 못 본다(D♭ 3쪽 빔 위 유령 4: 0).
    **삭제에는 쓰지 않는다** — Verovio에서 진짜 화음 머리 라벨 3개를 지웠다(DECISIONS 기각 27).
    `sloped_beam_suspects`의 확인 필요(check) 표시에만 쓴다(DECISIONS §1-13).
    """
    import cv2

    base = beam_mask(binary, staves)
    sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
    no_staff = remove_staff_lines(binary, staves)
    L = max(3, int(sp * 2.5))
    thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
    out = base.copy()
    for deg in (7.5, 15, 22.5, 30, 37.5, 45, -7.5, -15, -22.5, -30, -37.5, -45):
        t = np.deg2rad(deg)
        dx, dy = L * np.cos(t) / 2, L * np.sin(t) / 2
        size = int(2 * max(abs(dx), abs(dy))) + 3
        k = np.zeros((size, size), np.uint8)
        c = size // 2
        cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        line = cv2.morphologyEx(no_staff, cv2.MORPH_OPEN, k)
        out |= cv2.morphologyEx(line, cv2.MORPH_OPEN, thick)
    return out


def sloped_beam_suspects(result, notes, filled: Sequence[bool]) -> list:
    """기울어진 빔 마스크(G1)로 「빔 위 · 빔 사이」인 **빈 머리** 음표 — 지우지 않고 확인 필요(check)로 표시할 대상.

    조건은 `drop_beam_ghosts`의 강한 두 조건과 같다(넓은 마스크 자리만 기울어진 마스크로).
    측정(2026-10-03, 정밀 판정 위, PDF 20 · 보지 않은 9 · Verovio 20): 이 신호로 지워지던 라벨 71 중 유령 68 · 진짜 3(Verovio 화음 머리).

    **채워진 머리**도 같은 조건 + 라벨 자리 세로 잉크 두께(`_vertical_thickness`) < `FILLED_BEAM_THICK_SP`면 넣는다(§1-42, 사진 모드 끔).
    빔에는 채워진 머리가 붙는 게 정상이라 조건만으로는 Verovio 대각 2도 화음 「확실」 23이 걸린다 — 비스듬히 붙은 두 머리가 기운 막대로 보인다.
    머리는 높이 ≈ 1칸, 빔은 두께 ≈ 0.5칸이라 두께로 가른다(측정: 유령 ≤ 0.52sp · 진짜 ≥ 0.92sp, ERROR_CENSUS_1015 큐 4번).
    """
    if not notes:
        return []
    mask = sloped_beam_mask(result.binary, result.staves)
    staff_by_index = {s.index: s for s in result.staves}
    photo = getattr(result, "photo_correction", None) is not None
    no_staff = remove_staff_lines(result.binary, result.staves) if not photo and any(filled) else None
    out = []
    for n, f in zip(notes, filled):
        staff = staff_by_index.get(n.staff_index)
        if staff is None or (f and no_staff is None):
            continue
        sp = staff.spacing
        x, y = int(n.x), int(n.y)
        half = max(1, int(sp * 0.5))
        on_beam = _band_ink(mask, x, y - int(sp * 0.2), y + int(sp * 0.2) + 1, half) > 0.05
        above = _band_ink(mask, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        below = _band_ink(mask, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05
        if (on_beam or (above and below)) and (not f or _vertical_thickness(no_staff, x, y, sp) < FILLED_BEAM_THICK_SP):
            out.append(n)
    return out


# 빔 위 채워진 머리 → check의 두께 문턱(§1-42). 조판 규칙(빔 ≈ 0.5칸 · 채워진 머리 ≈ 1칸)과
# 실측 틈(유령 최대 0.52 · 진짜 최소 0.84, 0 제외 — 49쪽 + Mutopia 8쪽)의 가운데
FILLED_BEAM_THICK_SP = 0.7


def _vertical_thickness(no_staff: np.ndarray, x: int, y: int, sp: float) -> float:
    """x ± 0.4sp 각 열에서 y를 지나는 세로 연속 잉크 길이의 중앙값(sp). 중앙값이라 기둥 한 열이 값을 끌지 않는다."""
    H, W = no_staff.shape
    if not (0 <= y < H):
        return 0.0
    runs = []
    for cx in range(int(x - 0.4 * sp), int(x + 0.4 * sp) + 1):
        if not (0 <= cx < W) or not no_staff[y, cx]:
            runs.append(0)
            continue
        col = no_staff[:, cx] > 0
        a = b = y
        while a > 0 and col[a - 1]:
            a -= 1
        while b < H - 1 and col[b + 1]:
            b += 1
        runs.append(b - a + 1)
    return float(np.median(runs)) / sp


def _cap_bar(no_staff: np.ndarray, x: int, y: int, sp: float, step: int) -> tuple:
    """중심 ±0.3sp 열마다 위(step=-1) · 아래(+1)로 첫 잉크까지 거리 · 그 잉크의 세로 두께, 그 막대 가운데 행의
    가로 런(x 근처를 지나는) — sp, 열 중앙값. 1sp 안에 잉크가 없으면 거리 None.
    측정 도구 `tools/measure_beamgap_dynamic._bar`와 같은 정의다(값을 바꾸면 측정과 어긋난다)."""
    H, W = no_staff.shape
    lim = int(sp * 1.0)
    cols = range(max(0, int(x - 0.3 * sp)), min(W, int(x + 0.3 * sp) + 1))
    gaps, thicks, mids = [], [], []
    for c in cols:
        r, g = y, 0
        while 0 <= r < H and not no_staff[r, c] and g <= lim:
            r += step
            g += 1
        if g > lim or not (0 <= r < H):
            gaps.append(np.inf)
            continue
        t, r0 = 0, r
        while 0 <= r < H and no_staff[r, c]:
            r += step
            t += 1
        gaps.append(g)
        thicks.append(t)
        mids.append(r0 + step * (t // 2))
    if not thicks or np.median(gaps) == np.inf:
        return None, 0.0, 0.0
    gap, thick = float(np.median(gaps)) / sp, float(np.median(thicks)) / sp
    row = no_staff[int(np.median(mids))]
    a = b = int(x)
    if not row[a]:
        near = [c for c in cols if row[c]]
        if not near:
            return gap, thick, 0.0
        a = b = near[len(near) // 2]
    while a > 0 and row[a - 1]:
        a -= 1
    while b + 1 < W and row[b + 1]:
        b += 1
    return gap, thick, (b - a + 1) / sp


# 좁은 구멍(셈여림 「p」 · 글자 고리) → 「확인 필요」 (2026-10-12, 사용자 구현 승인 · DECISIONS §1-30, `docs/BEAMGAP_DYNAMIC.md`).
# 머리 링이라면 구멍 위 · 아래 테두리가 머리 폭만큼 가로로 이어진다 — 오선 밖 · 기둥 없음 · 흰 중심인 진짜 머리 120개의 max(위 런, 아래 런) 최소 0.82sp.
# 「p」 고리 속은 좁다(셈여림 유령 대부분 ≤ 0.45sp) → 기하평균 √(0.45 × 0.82) = 0.61 → 0.6.
# 기둥 = `notehead_detect._has_stem`(2.5sp). 오선 밖 = 머리 y가 맨 윗줄 위 · 맨 아랫줄 아래.
# 시뮬레이션 49쪽: 걸림 53 = 유령 53(p · pp · mf · Ped. · 글자 · 꼬리) · 진짜 0. 지우지 않고 표시만. 사진 모드는 끈다(미측정)
NARROW_HOLE_MAX_SP = 0.6


def narrow_hole_suspects(result, notes) -> list:
    """오선 밖 · 기둥 없음 · 흰 중심인데 위 · 아래 테두리가 둘 다 짧은(≤ 0.6sp) 라벨."""
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    from .notehead_detect import _has_stem
    ns = remove_staff_lines(result.binary, result.staves) > 0
    H, W = ns.shape
    staff_by_index = {s.index: s for s in result.staves}
    out = []
    for n in notes:
        staff = staff_by_index.get(n.staff_index)
        x, y = int(n.x), int(n.y)
        if staff is None or not (0 <= y < H and 0 <= x < W) or ns[y, x]:
            continue
        if staff.top <= y <= staff.bottom:
            continue
        sp = staff.spacing
        gu, _tu, ru = _cap_bar(ns, x, y, sp, -1)
        gd, _td, rd = _cap_bar(ns, x, y, sp, 1)
        if gu is None or gd is None or max(ru, rd) > NARROW_HOLE_MAX_SP:
            continue
        if _has_stem(ns, staff, x, y):
            continue
        out.append(n)
    return out



# 겹빔 사이 흰 틈 → 「확인 필요」 (2026-10-12, 사용자 구현 승인 · DECISIONS §1-31, `docs/BEAMGAP_DYNAMIC.md`).
# 16분음표 두 개를 잇는 짧은 겹빔(≈2.1sp)은 `beam_mask`의 가로 열림 2.5sp보다 짧아 빔 조건 · G1이 못 본다.
# 흰 중심의 위 · 아래 첫 잉크가 가깝고(≤ 0.5sp) 빔 두께(0.40~0.60sp — 조판 빔 0.5sp: Verovio 0.50 · LilyPond 0.48, ± 0.1)이며
# 머리 폭보다 긴(≥ 1.5sp — 진짜 흰 중심 머리 6,907개의 95% 1.09 · 걸린 유령 최소 1.55) 가로 막대로 양쪽 다 막힌 칸.
# 두께 상한 0.6은 화음 이웃 머리(0.81~0.86)를 뺀다. 기각 12(넓힌 마스크로 「한쪽만」)와 달리 양쪽 다 막힌 칸만.
# 시뮬레이션 49쪽: 걸림 83 = 유령 79 · 진짜 4(2개는 이미 check) — 지우면 오삭제라 표시만. 사진 모드는 끈다(미측정)
BEAM_GAP_MAX_SP = 0.5
BEAM_GAP_THICK_SP = (0.4, 0.6)
BEAM_GAP_RUN_SP = 1.5


def beam_gap_suspects(result, notes) -> list:
    """위 · 아래가 빔 두께의 긴 가로 막대로 막힌 흰 칸에 앉은 라벨."""
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    ns = remove_staff_lines(result.binary, result.staves) > 0
    H, W = ns.shape
    staff_by_index = {s.index: s for s in result.staves}
    lo, hi = BEAM_GAP_THICK_SP
    out = []
    for n in notes:
        staff = staff_by_index.get(n.staff_index)
        x, y = int(n.x), int(n.y)
        if staff is None or not (0 <= y < H and 0 <= x < W) or ns[y, x]:
            continue
        sp = staff.spacing
        gu, tu, ru = _cap_bar(ns, x, y, sp, -1)
        gd, td, rd = _cap_bar(ns, x, y, sp, 1)
        if gu is None or gd is None or max(gu, gd) > BEAM_GAP_MAX_SP:
            continue
        if lo <= min(tu, td) and max(tu, td) <= hi and min(ru, rd) >= BEAM_GAP_RUN_SP:
            out.append(n)
    return out


# 임시표 글리프가 음표로 잡힌 유령 → 「확인 필요」 (2026-10-04, 사용자 구현 승인 · DECISIONS §1-20, `docs/GLYPH_GHOST.md` · `GLYPH_RULE_SIM.md`).
# 라벨 중심 좌(−0.75 ~ −0.2sp) · 우(+0.2 ~ +0.75sp) 칸 열마다 중심 ±0.3sp에서 위 · 아래로 끊김 없이 이어진 잉크 길이(sp) 최댓값 LU · LD · RU · RD.
# 기보: 머리 기둥은 오른쪽 위(RU) · 왼쪽 아래(LD)로 뻗는다. ♭은 왼쪽 위(LU), ♮은 LU · RD.
#   ♭형 LU ≥ 1.3 · LD ≤ 0.6 · RU ≤ 1.0 — 실측 ♭ 유령 LU 5% 1.44 · LD 95% 0.50 · RU 95% 0.88, 진짜 머리 LU 중앙 0.17
#   ♮형 LU ≥ 0.6 · RD ≥ 0.6 · LD ≤ 1.7 · RU ≤ 2.0 — 실측 ♮ 유령 LU 5% 0.60 · RD 5% 0.59, 진짜 머리 RD 중앙 0.22
# 시뮬레이션(전 세트 라벨): 걸림 290 중 유령 283(97.6%), 진짜 머리 7(확실 4). 지우지 않고 표시만 — 이웃 기둥 · 이웃 글리프가 붙은 진짜 머리가 걸린다
GLYPH_SHAPE_FLAT = (1.3, 0.6, 1.0)
GLYPH_SHAPE_NATURAL = (0.6, 0.6, 1.7, 2.0)


def _side_runs(no_staff: np.ndarray, x: float, y: float, sp: float) -> Dict[str, float]:
    H, W = no_staff.shape
    out = {}
    for side, (a, b) in (("L", (-0.75, -0.2)), ("R", (0.2, 0.75))):
        cols = range(max(0, int(x + a * sp)), min(W, int(x + b * sp) + 1))
        for d, step in (("U", -1), ("D", 1)):
            best = 0
            for c in cols:
                r = int(y + step * 0.3 * sp)
                n = 0
                while 0 <= r < H and no_staff[r, c]:
                    n += 1
                    r += step
                best = max(best, n)
            out[side + d] = round(best / sp, 2)
    return out


def glyph_shape_suspects(result, notes) -> list:
    """♭형 · ♮형 모양의 라벨(임시표 글리프 유령 후보). 사진 모드에서는 끈다(미측정)."""
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    ns = remove_staff_lines(result.binary, result.staves) > 0
    staff_by_index = {s.index: s for s in result.staves}
    fl, fn = GLYPH_SHAPE_FLAT, GLYPH_SHAPE_NATURAL
    out = []
    for n in notes:
        staff = staff_by_index.get(n.staff_index)
        if staff is None:
            continue
        g = _side_runs(ns, n.x, n.y, staff.spacing)
        flat = g["LU"] >= fl[0] and g["LD"] <= fl[1] and g["RU"] <= fl[2]
        natural = g["LU"] >= fn[0] and g["RD"] >= fn[1] and g["LD"] <= fn[2] and g["RU"] <= fn[3]
        if flat or natural:
            out.append(n)
    return out


# 꾸밈음(작은 머리) → 「확인 필요」 (2026-10-05, 사용자 구현 승인 · DECISIONS §1-24, `docs/GRACE_SIZE.md`). 꾸밈음은 지원하지 않는다 — 표시만.
# 머리 덩어리 = 오선 제거 → 타원(0.5sp) 열림 → 그 음표 자리 8연결 성분. 크기 비 = 그 성분 폭 · 높이 / 그 쪽 「화음이 아닌」 음표들의 중앙값.
#   GRACE_RATIO 0.66~0.80 — 꾸밈음 실측 중앙 0.73(1% 0.69 · 0.67)과 정상 단독 머리 5%(0.96 · 0.98) 사이, 꾸밈음 중앙 ± 0.07
#   화음이 아님(같은 보표 0.6sp 안 다른 음표 없음) — 화음에 붙은 정상 머리는 열림에 깎여 꾸밈음 크기로 재진다(5% 0.76 · 0.73)
# 시뮬레이션: 걸림 216 = 꾸밈음 175 · 정상 머리 32(확실 25) · 유령 9(정밀도 81%). 사진은 흐림 · 변형이 크기를 흔들어 끈다
GRACE_RATIO = (0.66, 0.80)
# 기준 대체 (2026-10-13, 사용자 승인 · DECISIONS §1-35, `docs/GRACE_SIZE.md` 「기준 대체안」) — 기준이 작거나(라벨 < 50, 바흐 · 월광 · 빗방울 0~10)
# 꾸밈음에 오염되면(기준 폭 < 기대 × 0.85, 악흥의 순간 0.91sp) sp 기대 머리 크기로 바꾼다.
#   50 = 기준 라벨 수 틈(작은 쪽 최대 23 · 큰 쪽 최소 57, 30도 같은 결과) · 기대 1.28 × 1.06sp = 49쪽 중 기준 라벨 ≥ 50인 40쪽 쪽별 기준 중앙(폭 5~95% 1.17~1.32 · 높이 1.00~1.14) · 0.85 = 폭 5%(1.17) 바로 아래 1.09
#   시뮬레이션: Mutopia 꾸밈음 확실 33 중 31 · 49쪽 새로 13 전부 꾸밈음 · 헛표시 0 · check → 확실 1(유령 조각, 감수). 문턱 30 · 0.80도 같은 결과
GRACE_REF_MIN, GRACE_REF_SHRINK, GRACE_EXPECT_SP = 50, 0.85, (1.28, 1.06)


def grace_size_suspects(result, notes) -> list:
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    import cv2
    ns = remove_staff_lines(result.binary, result.staves)
    sp_of = {s.index: s.spacing for s in result.staves}
    sp0 = float(np.median(list(sp_of.values())))
    k = max(3, int(0.5 * sp0)) | 1
    op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    _n, lab, stats, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
    H, W = lab.shape
    sizes, chord = [], []
    for n in notes:
        sp = sp_of.get(n.staff_index, sp0)
        y, x = min(H - 1, max(0, int(n.y))), min(W - 1, max(0, int(n.x)))
        c = lab[y, x]
        if not c:
            win = lab[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
            nz = win[win > 0]
            c = int(np.bincount(nz).argmax()) if nz.size else 0
        sizes.append((stats[c, cv2.CC_STAT_WIDTH] / sp, stats[c, cv2.CC_STAT_HEIGHT] / sp) if c else None)
        chord.append(any(o is not n and o.staff_index == n.staff_index and abs(o.x - n.x) <= 0.6 * sp for o in notes))
    ref = [s for s, ch in zip(sizes, chord) if s is not None and not ch]
    mw, mh = GRACE_EXPECT_SP
    if len(ref) >= GRACE_REF_MIN:
        rw, rh = float(np.median([w for w, _h in ref])), float(np.median([h for _w, h in ref]))
        if rw >= mw * GRACE_REF_SHRINK:
            mw, mh = rw, rh
    lo, hi = GRACE_RATIO
    return [n for n, s, ch in zip(notes, sizes, chord)
            if s is not None and not ch and lo <= s[0] / mw <= hi and lo <= s[1] / mh <= hi]


def drop_beam_ghosts(result, noteheads) -> tuple:
    """
    빔에 얹히거나 끼어 있는 '빈 음표'를 버린다. (음표 머리 목록을 받아 걸러 돌려준다)

    근거는 음악 규칙이다 — 빔은 8분음표 이하에만 붙고, 그 음표들의 머리는 채워져
    있다. 따라서 **속이 빈 머리(온음표·2분음표)가 빔에 닿아 있을 수 없다.**
    그런 자리에서 나온 검출은 빔과 빔 사이의 흰 띠를 링으로 착각한 것이다.

    사람이 확대해 판정한 결과(쇼팽 D♭ 1쪽 320개 + 바흐 미뉴에트 191개)에서
    '빔 위·빔 사이·빔 인접'과 '좌우 잉크 약함'은 네 조건 모두 정밀도 100%였다 —
    걸린 것이 전부 실제 유령이었다. 채워진 머리는 빔에 붙는 것이 정상이므로
    건드리지 않는다.

    Returns:
        (남긴 머리 목록, 버린 항목 목록[진단값 포함])
    """
    if not noteheads:
        return noteheads, []
    no_staff = remove_staff_lines(result.binary, result.staves)
    mask = beam_mask(result.binary, result.staves)
    narrow = beam_mask_strict(result.binary, result.staves)
    staff_by_index = {s.index: s for s in result.staves}

    kept, dropped = [], []
    for head in noteheads:
        staff = staff_by_index.get(head.staff_index)
        if staff is None or head.filled:
            kept.append(head)
            continue
        sp = staff.spacing
        x, y = int(head.x), int(head.y)
        half = max(1, int(sp * 0.5))
        on_beam = _band_ink(mask, x, y - int(sp * 0.2), y + int(sp * 0.2) + 1, half) > 0.05
        above = _band_ink(mask, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        below = _band_ink(mask, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05
        # '한쪽만 닿음'은 남의 빔에 취약해 좁은 마스크로만 본다 (beam_mask_strict 참고)
        n_above = _band_ink(narrow, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        n_below = _band_ink(narrow, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05
        weak, _strong = _side_ink(no_staff, x, y, sp)
        reason = ("빔 위" if on_beam else
                  "빔 사이" if (above and below) else
                  "빔에 닿음" if (n_above or n_below) else
                  "좌우에 잉크 없음" if weak < GHOST_SIDE_THRESHOLD else "")
        if reason:
            dropped.append(dict(x=x, y=y, staff=head.staff_index, reason=reason,
                                weak=round(weak, 3)))
        else:
            kept.append(head)
    return kept, dropped


# PDFium 렌더의 짧은 덧줄(2026-11-17, 사용자 결정 B안 · 렌더 흔들림 ① · docs/RENDER_ROBUSTNESS.md §①) — 지우지 않고 「확인 필요(check)」로 남긴다.
# 렌더 종류가 "pdfium"일 때만 켠다(`drop_offstaff_ghosts(render=)` 또는 `result.raster_source`). 기본값(PyMuPDF · 사진 · 이미지)은 예전 그대로다.
# 원인: 덧줄을 높이 0 사각형 선으로 그린 PDF(바흐 · 쇼팽 D♭)는 PyMuPDF가 양 끝을 선 두께만큼 늘려 그리고 PDFium은 기하대로 그린다
#   (D♭ 5쪽 같은 덧줄 PyMuPDF 26px · PDFium 23px, 회색값이 계단이라 회색조 문턱 · 반픽셀 보정으로 못 되찾음). `LEDGER_RUN_SP` 1.30은 늘린 길이에서 유도됐다.
# LEDGER_STRETCH_SP 0.18 = PyMuPDF 늘림 폭. 근거 둘: ① 실측 — 같은 머리 덧줄 런 PyMuPDF − PDFium, 쪽별 중앙 바흐 0.184 · D♭ 0.137 ~ 0.171
#   (B♭단조 · E단조는 0 근처 — 선으로 그린 파일) ② 기하 — 늘림의 상한은 선 두께, D♭ 덧줄 0.946pt = 300dpi 3.9px ≈ 0.19 ~ 0.21sp
# PDFium 문턱 = 1.30 − 0.18 = 1.12sp. PDFium 진짜 덧줄 음 런 최소 1.158 ≥ 1.12.
# 문턱만으로는 안 된다 — PDFium 300 · 360에서 1.12만 쓰면 빈 머리 유령(✱ 페달 떼기 등)이 13 ~ 15개 더 남는다. 그래서 셋 다 요구한다:
#   ⓐ 꽉 찬 머리 ⓑ 머리 행을 지나는 기둥 ≥ LEDGER_RESCUE_STEM_SP 3.5sp(글자 획 최대 2.10 · 음표 기둥 최소 3.52 — `notehead_detect._has_stem` 실측)
#   ⓒ 필요한 덧줄이 모두 LEDGER_RUN_SP_PDFIUM 이상
# 「확실」로 두지 않는 이유: 빔과 기둥 이음 유령(런 1.18 · 기둥 4.7sp)이 셋을 모두 통과한다. 두께 · 머리 창 잉크 비율로도 못 가른다(DECISIONS 기각 44).
LEDGER_STRETCH_SP = 0.18
LEDGER_RUN_SP_PDFIUM = LEDGER_RUN_SP - LEDGER_STRETCH_SP
LEDGER_RESCUE_STEM_SP = 3.5


def _stem_through(no_staff: np.ndarray, x: int, y: int, sp: float) -> float:
    """머리 행(y)을 지나는 가장 긴 세로 잉크(sp) — 좌우 ±0.9sp 창(`notehead_detect._has_stem`과 같은 창)."""
    H, W = no_staff.shape[:2]
    xa, xb = max(0, int(x - sp * 0.9)), min(W, int(x + sp * 0.9) + 1)
    y0, y1 = max(0, int(y - sp * 5)), min(H, int(y + sp * 5))
    if xb <= xa or not (y0 <= y < y1):
        return 0.0
    sub = no_staff[y0:y1, xa:xb] > 0
    r = y - y0
    best = 0
    for c in range(sub.shape[1]):
        col = sub[:, c]
        if not col[r]:
            continue
        up = dn = r
        while up - 1 >= 0 and col[up - 1]:
            up -= 1
        while dn + 1 < len(col) and col[dn + 1]:
            dn += 1
        best = max(best, dn - up + 1)
    return best / sp


def drop_offstaff_ghosts(result, noteheads, render: Optional[str] = None) -> tuple:
    """
    오선 밖에 있는데 필요한 덧줄이 없는 머리를 버린다.

    근거는 음악 규칙이다 — 오선 밖의 음은 반드시 **덧줄 위나 덧줄 사이 칸**에
    놓인다. 덧줄 없이 오선 밖에 떠 있는 덩어리는 음표가 아니라 글자다.
    실제로 걸리는 것은 셈여림(`pp`, `f`), 페달(`Ped.`), 템포(`♩. = 50`),
    나타냄말(`cresc.`, `dim.`, `sempre legato`), 손가락 번호, 악센트(`>`),
    트릴, 임시표 글리프(♯♭♮), 그리고 보표 밖으로 뻗은 빔 조각이다.

    이 조건은 오래 못 썼다. 덧줄 검출이 좌우 띠 비율에 기대던 동안에는 정상 음표를
    지웠기 때문이다 — 폭 임계값 시절 바흐에서 19개, 좌우 띠 시절 쇼팽 5쪽에서 11개.
    덧줄을 '수평 런 길이'로 재고 필요 덧줄 수를 내림으로 세도록 고친 뒤
    두 악보 **전 쪽**에서 다시 측정해 채택했다:

        쇼팽 D♭ 6쪽 + 바흐 1쪽, 오선 밖 후보 766개 중 108개 제거
        제거한 108개를 전부 확대해 확인 -> 전부 음표가 아님 (정밀도 100%)
        확인된 정상 음표 130개 중 **오삭제 0**

    `render` = 그림을 만든 렌더러("pdfium"이면 짧은 덧줄 구제를 켠다). None이면 `result.raster_source`, 그것도 없으면 예전 동작.

    Returns:
        (남긴 머리 목록, 버린 항목 목록)
    """
    if not noteheads:
        return noteheads, []
    pdfium = (render or getattr(result, "raster_source", None)) == "pdfium"
    kinds = getattr(result, "head_filled", None)     # 머리 유형(검출 그대로) — `diagnose_labels`의 center_split가 읽는다(main.py 무변경)
    if kinds is None:
        kinds = {}
        result.head_filled = kinds
    kinds.update(((h.staff_index, int(h.x), int(h.y)), bool(h.filled)) for h in noteheads)
    staff_by_index = {s.index: s for s in result.staves}
    kept, dropped = [], []
    no_staff = None
    for head in noteheads:
        staff = staff_by_index.get(head.staff_index)
        if staff is None:
            kept.append(head)
            continue
        verdict = ledger_check(result.binary, staff, int(head.x), int(head.y))
        if verdict is False and pdfium and head.filled:
            if no_staff is None:
                no_staff = remove_staff_lines(result.binary, result.staves)
            if (_stem_through(no_staff, int(head.x), int(head.y), staff.spacing) >= LEDGER_RESCUE_STEM_SP
                    and ledger_check(result.binary, staff, int(head.x), int(head.y), LEDGER_RUN_SP_PDFIUM)):
                kept.append(head)
                marks = getattr(result, "ledger_short_xy", None)
                if marks is None:
                    marks = set()
                    result.ledger_short_xy = marks
                marks.add((head.staff_index, int(head.x), int(head.y)))     # 라벨 행 표시는 `diagnose_labels`가 읽는다(main.py 무변경)
                continue
        if verdict is False:
            sp = staff.spacing
            off = ((head.y - staff.bottom) if head.y > staff.bottom
                   else (head.y - staff.top)) / sp
            dropped.append(dict(x=int(head.x), y=int(head.y),
                                staff=head.staff_index,
                                reason="오선 밖인데 덧줄 없음",
                                off_sp=round(float(off), 2)))
        else:
            kept.append(head)
    return kept, dropped


# 오선 밖 글자 줄 → 「확인 필요(check)」 (2026-10-15, 사용자 결정 16시 2 · DECISIONS §1-41 초안, `tools/measure_text_ghost.py`) — 표시만. 사진 모드에서는 끈다.
# 나타냄말(dim. · smorz. · Fine · Trio · Allegro 등)과 셈여림(p · sfz)은 **같은 높이에 글자 크기 덩어리가 가로로 늘어선다**(DECISIONS 표 7 「글자 줄」).
#   오선 밖 거리 ≥ TEXT_ROW_MIN_SP — 오선에서 1sp 넘게 떨어진 진짜 음표는 덧줄이 있어야 한다(첫 덧줄 자리 = 1sp).
#   덩어리 = 오선 제거 영상 8연결 성분, 높이 0.4~2.5sp · 폭 0.2~3sp(덧줄은 높이가 낮아 빠짐), 중심이 라벨 높이 ±0.6sp · 좌우 ±4sp(자신 포함) ≥ 3
# 측정(비보류 53쪽, ``error_census`` 정답): 「확실」 유령 19 → check · 맞는 라벨 헛표시 4(괄호 친 ♭ · 점 · 운지 숫자가 붙은 진짜 머리).
#   오선 밖 「확실」 유령 42 중 글자 18 · 셈여림 5가 대상(깃발 8 · 덧줄 위 4 등은 다른 원인).
TEXT_ROW_MIN_SP = 1.0
TEXT_ROW_BLOBS = 3


# 같은 음 라벨이 가로로 바로 옆에 붙은 쌍 → 잉크가 얇은 쪽 「확인 필요(check)」 (2026-10-18, 사용자 지시 2 · DECISIONS §1-44 초안,
# `tools/measure_side_dup.py` · `measure_thin_label.py` · `docs/ERROR_CENSUS_1015.md` 큐 4번) — 표시만(삭제 금지: 진짜를 고른 1건). 사진 모드 끔.
#   쌍 = 같은 보표 · 같은 음이름 + 옥타브 · 가로 SIDE_PAIR_DX_SP · 세로 ≤ SIDE_PAIR_DY_SP. 이 거리대 쌍 43은 진짜 + 진짜(유니즌) 0 —
#   전부 유령을 품었다(거리 0.62 ~ 1.04sp. 0.6 아래는 기각 32의 세로 중복과 다른 현상이라 뺀다).
#   얇은 쪽 = 세로 두께(`_vertical_thickness`) · 머리 창(± 0.55 × ± 0.40sp) 잉크 비율이 **둘 다** 더 작은 라벨. 둘이 엇갈리면 표시 안 함.
#   측정(flatc1u + Mutopia): 진짜 + 유령 42 중 유령 41(「확실」 26) · 진짜 1(em2 (1018,1825) 빈 머리).
SIDE_PAIR_DX_SP = (0.6, 1.2)
SIDE_PAIR_DY_SP = 0.3


def side_pair_suspects(result, notes) -> list:
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    ns = remove_staff_lines(result.binary, result.staves) > 0
    by = {s.index: s for s in result.staves}

    def ink(n, sp):
        x, y = int(n.x), int(n.y)
        win = ns[max(0, int(y - 0.4 * sp)):int(y + 0.4 * sp) + 1, max(0, int(x - 0.55 * sp)):int(x + 0.55 * sp) + 1]
        return _vertical_thickness(ns, x, y, sp), float(win.mean()) if win.size else 0.0
    out = {}
    for i, a in enumerate(notes):
        s = by.get(a.staff_index)
        if s is None:
            continue
        sp = s.spacing
        for b in notes[i + 1:]:
            if b.staff_index != a.staff_index or (b.note_name, b.octave) != (a.note_name, a.octave)                     or not SIDE_PAIR_DX_SP[0] <= abs(a.x - b.x) / sp <= SIDE_PAIR_DX_SP[1] or abs(a.y - b.y) / sp > SIDE_PAIR_DY_SP:
                continue
            (ta, fa), (tb, fb) = ink(a, sp), ink(b, sp)
            if ta < tb and fa < fb:
                out[id(a)] = a
            elif tb < ta and fb < fa:
                out[id(b)] = b
    return list(out.values())


def text_row_suspects(result, notes) -> list:
    if not notes or getattr(result, "photo_correction", None) is not None:
        return []
    import cv2
    ns = (remove_staff_lines(result.binary, result.staves) > 0).astype(np.uint8)
    n, _lab, st, cen = cv2.connectedComponentsWithStats(ns, connectivity=8)
    by = {s.index: s for s in result.staves}
    out = []
    for note in notes:
        s = by.get(note.staff_index)
        if s is None:
            continue
        sp = s.spacing
        if max((s.top - note.y) / sp, (note.y - s.bottom) / sp) < TEXT_ROW_MIN_SP:
            continue
        k = sum(1 for i in range(1, n) if abs(cen[i][1] - note.y) <= 0.6 * sp and abs(cen[i][0] - note.x) <= 4 * sp
                and 0.4 * sp <= st[i][3] <= 2.5 * sp and 0.2 * sp <= st[i][2] <= 3.0 * sp)
        if k >= TEXT_ROW_BLOBS:
            out.append(note)
    return out