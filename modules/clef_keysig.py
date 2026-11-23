# -*- coding: utf-8 -*-
"""
보표 헤더 분석 모듈: 음자리표(clef) 자동 판별 + 조표(key signature) 인식

각 보표의 왼쪽 헤더 영역(음자리표 + 조표 + 박자표)을 분석해서:
  1. 음자리표 종류 판별 — 높은음자리표는 보표 맨 아래 줄보다 아래로 '꼬리'가 내려오지만
     낮은음자리표는 보표 안에 들어간다. 이 '보표 아래 잉크 비율'로 구분한다.
  2. 헤더 끝 x좌표 계산 — 음표 탐색에서 음자리표/조표/박자표 영역을 제외하기 위함.
     (조표 ♯과 박자표 숫자가 음표로 오검출되는 것을 막는다)
  3. 조표 인식 — 음자리표 뒤 조표 영역의 글리프 개수를 세어 몇 개의 ♯/♭인지 판단.
     ♯은 글리프 오른쪽 위 모서리에 잉크가 있고(십자형), ♭은 비어 있는 점(b형)으로 구분.

악보에 음자리표가 없으면(합성 테스트 이미지 등) 헤더가 없다고 판단하고
기본값(treble, header_end=0, 조표 없음)을 반환한다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import cv2
import numpy as np

from .preprocess import PreprocessResult, Staff
from .notehead_detect import remove_staff_lines

# 조표가 붙는 음이름 순서 (샤프: 파도솔레라미시 / 플랫: 시미라레솔도파)
SHARP_ORDER = "FCGDAEB"
FLAT_ORDER = "BEADGCF"

# 음자리표 끝 — 「오선 행 밖에 잉크가 없는 열」이 이만큼(sp) 이어지면 음자리표가 끝난 것이다 (A-8, 2026-09-27).
# 기존 조건(열 잉크 < 0.5sp가 max_g 넘게)은 오선 제거 잔여물을 잉크로 세어 재표본화 한 번에 무너진다
# (틈 잔여 잉크 원본 최대 0.47sp → 보간 뒤 중앙 ~0.5 · 최대 1.04sp, docs/KEYSIG_CLEF_GAP.md §3).
# 오선 행을 빼고 보면 음자리표-조표 틈은 최소 0.82sp(재표본화 7가지 포함), 음자리표 안 최대 0.27 ·
# 조표 안 최대 0.36sp다 → 기하평균 0.54. 여유 0.28 / 0.18sp. LilyPond 규정(음자리표→조표 extra-space 0.82,
# 조표 안 padding 0 · ♮ 최대 0.3)과 맞지만 **같은 조판 계열이라 독립 근거가 아니다** — 비-LilyPond 조판 미검증(§7).
CLEF_GAP_SP = 0.54
# 오선 행 = 선 y ±2px. 선 두께 3px(세 악보 실측, docs/PORTABILITY.md)을 덮는다.
CLEF_GAP_LINE_PAD = 2
# 음자리표 끝 하한(xe). 1단계(2026-09-27)에서는 빈 틈 규칙도 이 폭 뒤에서만 켰으나(괄호·세로줄 조각 오인 방지),
# RE:Aoharu 높은음자리표(1.74sp)에서 규칙이 꺼져 2단계(2026-09-28)에서 뗐다 — 조각 오인은 아래 시작점 조건이 막는다.
CLEF_MIN_WIDTH_SP = 2.2


@dataclass
class StaffContext:
    """보표 하나의 헤더 분석 결과"""

    clef: str = "treble"           # "treble" | "bass"
    clef_found: bool = False        # 음자리표 글리프를 실제로 찾았는지
    header_end: int = 0             # 음표 탐색 시작 x좌표 (이보다 왼쪽은 헤더로 무시)
    key_count: int = 0              # 조표 갯수
    key_symbol: str = ""            # "♯" | "♭" | ""
    key_letters: Tuple[str, ...] = field(default_factory=tuple)  # 조표 적용 음이름들
    # 조표 후보 세로 막대 (절대 x, step). step은 맨 아랫줄 기준 반칸 수 —
    # 조표 쌍 판정이 "한 글리프의 두 세로획인가"를 y로 확인하는 데 쓴다.
    bars: Tuple[Tuple[float, float], ...] = field(default_factory=tuple)
    holes: int = 0                  # 조표 영역 구멍 수 (♭ 판별용)
    spacing: float = 0.0            # 보표 오선 간격 (조표 교차 투표용)
    clef_end: int = 0               # 음자리표 글리프 끝 x좌표 (헤더 재계산용)
    clef_start: int = 0             # 음자리표 글리프 시작 x좌표 (바뀐 음자리표 검출의 본, `clef_change_suspects`)
    header_reopened: int = 0        # §1-51 전 규칙의 헤더 끝(지금 header_end보다 컸을 때만) — 그 사이 라벨은 check(`header_reopened_suspects`)


def _analyze_one(no_staff: np.ndarray, staff: Staff, img_h: int,
                 single_system: bool = False) -> StaffContext:
    sp = staff.spacing
    top = max(0, int(staff.top - sp * 3))
    bottom = min(img_h, int(staff.bottom + sp * 3))
    band = no_staff[top:bottom, :]
    H, W = band.shape
    top_line_local = staff.top - top
    bot_line_local = staff.bottom - top

    # 각 열의 잉크 세로 범위 (브레이스/세로줄 판별용)
    ink_rows = band > 0
    any_ink = ink_rows.any(axis=0)
    first = ink_rows.argmax(axis=0)
    last = H - 1 - ink_rows[::-1, :].argmax(axis=0)
    extent = np.where(any_ink, last - first, -1)
    tall_thin = extent > sp * 8.5  # 브레이스/시스템 세로줄

    # 헤더 스캔용: 보표 ±1.5sp 행만 (이음줄, 레저 음표의 간섭 배제)
    r0 = max(0, int(top_line_local - sp * 1.5))
    r1 = min(H, int(bot_line_local + sp * 1.5) + 1)
    ink_cnt = (band[r0:r1, :] > 0).sum(axis=0)
    # 오선 행을 뺀 열 잉크 — 음자리표 끝의 「빈 틈」 판정용(CLEF_GAP_SP)
    keep = np.ones(r1 - r0, bool)
    for ly in staff.line_ys:
        a = max(0, ly - top - r0 - CLEF_GAP_LINE_PAD)
        b = min(r1 - r0, ly - top - r0 + CLEF_GAP_LINE_PAD + 1)
        if b > a:
            keep[a:b] = False
    off_cnt = (band[r0:r1, :][keep] > 0).sum(axis=0)

    # 1) 음자리표 글리프 탐색: 폭 0.8sp 이상의 잉크 '클러스터'를 찾는다.
    #    시스템 세로 바라인은 높이 ~7sp라 브레이스 필터(8.5sp)에 안 걸리지만
    #    폭이 2~3px에 불과하므로 클러스터 폭 조건으로 건너뛴다.
    xc = -1
    cluster_end = -1
    cx = 0
    while cx < W:
        if tall_thin[cx] or ink_cnt[cx] < sp * 0.5:
            cx += 1
            continue
        c2 = cx
        g = 0
        e = 0                          # 오선 행 밖 잉크 0인 열의 연속 길이
        gap_hit = False
        max_g = max(3, int(sp * 0.5))  # 글리프 내부의 짧은 공백/옅은 열은 이어붙인다
        while c2 < W and not tall_thin[c2]:
            if off_cnt[c2] == 0:
                e += 1
                # 넓은 빈 틈 — 기존 조건과 OR
                if e >= sp * CLEF_GAP_SP:
                    gap_hit = True
                    break
            else:
                e = 0
            if ink_cnt[c2] >= sp * 0.5:
                g = 0
            else:
                g += 1
                if g > max_g:
                    break
            c2 += 1
        c2 = c2 - e + 1 if gap_hit else c2 - g
        width = c2 - cx
        # 음자리표 본체는 폭 1.5sp 이상이다. 브레이스/바라인 조각(~1sp)은 걸러낸다.
        # 폭은 덩어리 전체가 아니라 **오선 행 밖 잉크가 끊김 없이 이어진 가장 넓은 조각**으로도 본다 (A-8 2단계).
        # 괄호(0.87sp)와 시스템 세로줄(0.26sp)이 짧은 빈칸(0.43sp, max_g 안)을 사이에 두고 한 덩어리 1.48sp로
        # 붙어 이 조건을 1px 차이로 통과했고, 그 조각이 음자리표가 되어 음자리표 끝이 진짜 음자리표 앞에서
        # 정해졌다(RE:Aoharu 괄호 시작 보표 · 들여쓴 첫 시스템, 음자리표 끝 상한 5sp가 가려 왔다).
        # 음자리표 몸통은 조각 하나로 1.57sp 이상(20쪽 실측, docs/KEYSIG_CLEF_GAP.md §9). 단 PDF 피아노 괄호는 조각이 2.08sp까지 돼 못 거른다. 새 상수 없이 같은 1.4sp를 쓴다
        run = seg_w = 0
        for v in off_cnt[cx:c2] > 0:
            run = run + 1 if v else 0
            seg_w = max(seg_w, run)
        if width >= sp * 1.4 and seg_w >= sp * 1.4 and float(ink_cnt[cx:c2].max()) > sp * 0.8:
            xc, cluster_end = cx, c2
            break
        cx = max(c2, cx + 1)
    if xc < 0:
        return StaffContext()

    # 음자리표 끝 = 클러스터 끝 (최소 2.2sp). 최대 5sp 상한은 2026-09-28 뗐다 — 근거 없는 상수였고(§1-3),
    # 음자리표 시작점 결함을 가려 왔다(상한만 떼면 골든 p1 조표 소실). 시작점 수정(A-8 2단계) 뒤에는 상한 없이 골든 변화 0
    xe = min(W, max(cluster_end, xc + int(sp * CLEF_MIN_WIDTH_SP)))
    clef_win = band[:, xc:xe]
    total = int((clef_win > 0).sum())
    win_rows = np.where(clef_win.any(axis=1))[0]
    win_extent = (win_rows[-1] - win_rows[0]) if len(win_rows) else 0
    if total == 0 or win_extent < sp * 2.9:
        # 음자리표라기엔 너무 작은 글리프 -> 헤더 없는 악보(합성 이미지 등)로 판단
        # (낮은음자리표는 ~3.2sp, 높은음자리표는 ~7sp. 임시표+음표 뭉치는 ~2.6sp라 배제)
        return StaffContext()

    # 2) treble/bass 판별: 보표 아래 꼬리 잉크 비율
    b0 = int(bot_line_local + sp * 0.4)
    b1 = min(H, int(bot_line_local + sp * 2.5))
    below = int((clef_win[b0:b1, :] > 0).sum())
    clef = "treble" if below / total > 0.06 else "bass"

    # 3) 조표 영역 스캔:
    #    - 음자리표 끝의 짧은 공백(최대 1.5sp)은 건너뛰고 글리프 시작점을 찾는다
    #    - 조표 글리프들은 서로 겹쳐 있으므로 0.45sp 이상의 공백이 나오면 조표가 끝난 것
    #      (첫 음표까지 침범하지 않도록 공백 허용치를 좁게 잡는다)
    x = xe
    blank_limit = min(W, xe + int(sp * 1.5))
    while x < blank_limit and ink_cnt[x] == 0:
        x += 1
    keysig_start = x
    gap = 0
    limit = min(W, xe + int(sp * 6))
    # 여기서 '잉크 있음'의 문턱을 올리면 안 된다. 오선 제거 뒤 남는 1~4px 잔여
    # 잉크가 신경 쓰이지만, 문턱을 세우면 음자리표와 조표 사이의 정상 간격까지
    # 공백으로 보고 조표 앞에서 끊긴다 (실측: 0.5sp/0.35sp 둘 다 쇼팽 header_end가
    # 514 -> 359로 무너져 ♭ 5개가 유령이 됐다. 쇼팽은 이 간격이 3sp로 넓다).
    while x < limit:
        if ink_cnt[x] > 0:
            gap = 0
        else:
            gap += 1
            if gap >= sp * 0.45:
                break
        x += 1
    keysig_end = x - gap

    # 4) 조표 후보 세로 막대 수집 (개수 판정은 analyze_staves에서 교차 투표로)
    # 막대 수집 창을 6sp로 넉넉히 잡는 것은 교차 투표가 박자표 막대를 걸러준다는
    # 전제 위에서 안전하다. 보표가 한 시스템분(1~2개)뿐이면 투표할 대상이 없어
    # 박자표 숫자의 세로획이 그대로 조표로 세어진다 (실측: 합성 3/4 악보에서
    # ♭2개가 ♭4개로 늘었다). 그런 이미지에서는 공백으로 끊긴 조표 구간까지만 본다.
    if single_system:
        bar_limit = keysig_end
    else:
        bar_limit = _keysig_scan_end(band, sp, keysig_start, r0, r1, W)
    bars, holes = _find_bars(band, sp, keysig_start, max(keysig_start, bar_limit),
                             r0, r1)

    # 헤더가 조표 글리프보다 오른쪽으로 나가지 않게 막는다. 오선 제거 뒤 남는
    # 1~4px 잔여 잉크 때문에 위 공백 판정이 한 번도 성립하지 않으면 스캔이
    # 6sp 한계까지 내달려 첫 음표를 헤더로 삼킨다
    # (실측: RE Aoharu 2페이지 st0가 302 -> 372로 늘어나 39마디 첫 음이 사라졌다).
    if bars:
        keysig_end = min(keysig_end, int(max(bx for bx, _y in bars) + sp * 0.7))

    # 임시 헤더 끝 (조표 확정 후 analyze_staves에서 2차 패스로 다시 계산된다)
    header_end = _extend_over_timesig(ink_cnt, sp, max(keysig_end, xe), W)

    # band 지역 y -> step(맨 아랫줄 기준 반칸). 쌍 판정이 이 단위로 y를 본다.
    bars_step = tuple((bx, (staff.grid_bottom - (top + by)) / (sp / 2.0))
                      for bx, by in bars)

    ctx = StaffContext(
        clef=clef, clef_found=True, header_end=int(header_end),
        bars=bars_step, holes=holes, spacing=sp, clef_end=int(xe), clef_start=int(xc),
    )
    return ctx


def _timesig_span_end(no_staff: np.ndarray, staff: Staff, x_from: int) -> int:
    """
    헤더 뒤에서 박자표 블록을 찾아 그 오른쪽 끝 x를 반환한다. 없으면 x_from 그대로.

    판별 근거(악보 4종 실측): 박자표는 조판 규칙상 오선을 정확히 꽉 채우게 그려져,
    덩어리의 위끝이 맨 윗줄 ±0.05sp, 아래끝이 맨 아랫줄 +0.10~0.15sp에 딱 맞는다.
    반면 같은 자리의 음표·빔은 +0.52 / -0.61 / -1.89sp처럼 제각각이다.
    그래서 '맨 윗줄 근처와 맨 아랫줄 근처에 동시에 잉크가 있는 열'이 숫자 폭만큼
    연속될 때만 인정한다 (음표에서 이 조건을 만족하는 건 기둥 2~3px뿐).

    주의 두 가지:
      - 허용 오차를 넉넉히(1.2sp) 잡으면 빔 아래 음표 머리가 걸린다. 0.2sp로 좁게.
      - 이 판별식만으로는 박자표가 없는 보표에서도 가끔 걸린다(실측: RE Aoharu
        st2/st9/st11에서 1.28sp 구간이 잡혀 19개 손실). 반드시 호출부에서
        '들여쓰기된 첫 시스템'으로 대상을 제한할 것.
    """
    sp = staff.spacing
    H, W = no_staff.shape[:2]
    x_to = min(W, x_from + int(sp * 6))
    if x_to <= x_from:
        return x_from

    tol = max(1, int(round(sp * 0.2)))
    t0, t1 = max(0, int(staff.top) - tol), min(H, int(staff.top) + tol + 1)
    b0, b1 = max(0, int(staff.bottom) - tol), min(H, int(staff.bottom) + tol + 1)
    if t1 <= t0 or b1 <= b0:
        return x_from

    spans = ((no_staff[t0:t1, x_from:x_to] > 0).any(axis=0)
             & (no_staff[b0:b1, x_from:x_to] > 0).any(axis=0))

    lo, hi = int(sp * 0.6), int(sp * 2.6)   # 숫자 한 벌의 폭 범위
    i, n = 0, len(spans)
    while i < n:
        if not spans[i]:
            i += 1
            continue
        j = i
        while j < n and spans[j]:
            j += 1
        if lo <= (j - i) <= hi:
            return x_from + j
        i = j
    return x_from


def _extend_over_timesig(ink_cnt: np.ndarray, sp: float, base: int, W: int, thin: float = 0) -> int:
    """
    base 바로 뒤에 남은 헤더 요소(첫 시스템의 조표 잔여 + 박자표 숫자처럼
    잉크 밀도가 높은 블록)가 이어지면 그 블록 끝까지 확장한다.

    - 밀도 조건(창의 60% 이상이 1.8sp 초과)은 박자표 숫자에서만 만족되고,
      음표 하나(폭 ~1sp)로는 만족되지 않아 첫 음표를 삼키지 않는다.
      이 두 수치를 낮추면 헤더가 첫 음표까지 먹어 각 단 앞부분이 통째로
      누락된다(실측: 0.4sp/40%로 낮췄더니 9개 손실).
    - 시작점도 base 바로 뒤(0.3sp)로 고정한다. 공백을 길게 건너뛰며 잉크를
      찾으면 헤더가 아니라 '첫 음표'에서 조건이 성립해 버린다.
    - 확장 중 공백 허용치는 0.8sp: 조표와 박자표 사이의 작은 틈은 건너뛰되
      박자표와 첫 음표 사이의 더 큰 틈에서는 멈춘다.
    """
    header_end = base
    # 이 세 수치(창 2.2sp / 높이 1.8sp / 비율 0.6)는 모두 건드리면 안 된다.
    # 완화하면 각 단 첫 음표가 헤더에 삼켜진다 — 실측 손실:
    #   높이 0.4sp+비율 0.4 -> 9개, 창 1.2sp -> 6/16/5개, 비율 0.4 -> 6/14/2개
    # 반대로 이 값에서는 폭이 1.4sp인 박자표 블록(쇼팽 6/8)이 최대 45%밖에
    # 안 나와 덮이지 못한다 -> 첫 단 박자표 숫자가 유령 음표가 되는 한계가 남아 있다.
    # 근본 해결은 1차원 잉크량이 아니라 '오선 위/아래 절반에 모두 잉크가 있는
    # 좁은 블록'인지를 2차원으로 보는 것(미착수).
    win = int(sp * 2.2)
    ratio = 0.60
    # 조표와 박자표 사이 간격은 악보마다 다르다(실측: RE Aoharu 0.3sp, 쇼팽 2.0sp).
    # 한 지점만 보지 말고 앞으로 훑으면서 밀도 조건이 처음 성립하는 곳을 찾고,
    # 블록을 하나 넘은 뒤 그 다음 지점부터 다시 훑는다(조표 잔여 -> 빈칸 -> 박자표).
    # 한 번에 훑는 거리는 3sp까지만 — 더 가면 첫 음표까지 넘본다.
    for _ in range(3):
        advanced = False
        for probe in range(header_end + int(sp * 0.3), header_end + int(sp * 3.0)):
            if probe + win >= W:
                break
            dense = sum(1 for c in range(probe, probe + win) if ink_cnt[c] > sp * 1.8)
            if dense <= win * ratio:
                continue
            hx = probe
            gap = 0
            while hx < min(W, probe + int(sp * 6)):
                if ink_cnt[hx] > thin:
                    gap = 0
                else:
                    gap += 1
                    if gap >= sp * 0.8:
                        break
                hx += 1
            if hx - gap > header_end:
                header_end = hx - gap
                advanced = True
            break
        if not advanced:
            break
    return header_end


# 박자표 없는 줄의 헤더 끝 (2026-10-06, 사용자 구현 승인 · DECISIONS §1-28).
# 박자표는 첫 시스템에만 나오는데 `_extend_over_timesig`는 조표 끝 뒤 3sp 안의 진한 블록(첫 화음 등)도 박자표로 보고
# 헤더를 늘려 첫 음을 삼켰다(보지 않은 악보 27 · 헤더 끝이 조표 끝 + 6.0~8.6sp). 그 자리에 박자표 숫자
# (`_timesig_span_end` — 맨 윗줄 · 맨 아랫줄에 동시에 잉크가 있는 숫자 폭 열, 기준 + TIMESIG_LOOK_SP + 숫자 최대 폭 2.6sp 안)가
# 없으면 늘리지 않고 min(지금 값, 기준 + HEADER_MARGIN_SP).
#   HEADER_MARGIN_SP 0.5 — 조표가 있는 보표 348개에서 조표 끝 → 첫 정답 머리 왼끝 최소 0.55sp(1% 1.18 · 중앙 2.85) 아래
#   측정(사본, `NIGHT_CAUSES.md` 후속 ② [2]): 되찾음 33(음고 전부 맞음) · 새 유령 2(check) · 오삭제 0 · 조표 판정 변화 0 · Aoharu 무변화
TIMESIG_LOOK_SP = 2.0
HEADER_MARGIN_SP = 0.5
# 줄 첫 음이 헤더에 삼켜짐 (2026-10-26, 사용자 승인 · DECISIONS §1-51 초안). 49쪽 정답 머리 35개가 조표 · 박자표 뒤인데 헤더 안.
# (가) 첫 시스템이 아닌 줄: 조표 뒤 첫 화음(위 · 아래 줄에 다 걸침)이 박자표 숫자 조건을 채워 헤더가 4 ~ 5sp 늘었다(Chopin bbm 2 ~ 4 · 월광 · Joplin 7번째 보표).
#     박자표는 곡 첫 시스템에만 있다 — Verovio 정답 박자표 48쪽 전부 쪽 맨 위 시스템(나머지 1개는 마디 중간 변경) → 맨 위 시스템(`system_groups`)도
#     들여쓴 줄도 아니면 연장하지 않는다. 들여쓰기만 보면 짧게 들여쓴 첫 시스템(Joplin · Schumann 1.2sp)의 진짜 박자표를 놓친다.
#     음자리표를 셋 이상 못 찾은 쪽(한 시스템 악보)은 비교할 줄이 없어 지금처럼 연장한다.
# (나) 첫 시스템 진짜 박자표 뒤: 연장이 「빈칸 0.8sp」에서 멈춰야 하는데 오선 제거 찌꺼기(열당 몇 px)가 빈칸을 끊어 첫 음까지 갔다(Joplin 2/4 → 470, 첫 음 왼끝 424).
#     연장 중 잉크 TIMESIG_THIN_SP 이하 열은 빈칸으로 센다(시작 판정 · 숫자 열은 그대로). 0.5sp: Joplin 숫자 뒤 찌꺼기 0.33 ~ 0.39sp(열당 6 ~ 7px) 위 ·
#     숫자 블록 열 1.4sp 이상 아래. 빈칸은 0.8sp 연속이어야 하므로 숫자 가장자리의 얇은 열은 끊지 않는다.
TIMESIG_THIN_SP = 0.5


def _header_end_after(no_staff: np.ndarray, staff: Staff, ink_cnt: np.ndarray, base: int, timesig_ok: bool = True) -> Tuple[int, int]:
    """(헤더 끝, §1-51 전 규칙의 헤더 끝)."""
    sp = staff.spacing
    lim = no_staff[:, :min(no_staff.shape[1], base + int(TIMESIG_LOOK_SP * sp) + int(2.6 * sp))]
    ext = int(_extend_over_timesig(ink_cnt, sp, base, len(ink_cnt), thin=TIMESIG_THIN_SP * sp))
    old = int(_extend_over_timesig(ink_cnt, sp, base, len(ink_cnt)))
    if _timesig_span_end(lim, staff, base) == base:
        # 지금 값보다 늘리지는 않는다 — 확장이 없던 보표(Aoharu 등)는 그대로(골든 문맥 헤더 끝 무변화)
        cap = base + int(HEADER_MARGIN_SP * sp)
        return min(ext, cap), min(old, cap)
    if not timesig_ok:
        return min(ext, base + int(HEADER_MARGIN_SP * sp)), old
    return ext, old


def _restricted_profile(no_staff: np.ndarray, staff: Staff, img_h: int) -> np.ndarray:
    """보표 ±1.5sp 행 범위의 열별 잉크 수 프로파일 (헤더 재계산용)"""
    sp = staff.spacing
    top = max(0, int(staff.top - sp * 3))
    bottom = min(img_h, int(staff.bottom + sp * 3))
    band = no_staff[top:bottom, :]
    H = band.shape[0]
    tll = staff.top - top
    bll = staff.bottom - top
    r0 = max(0, int(tll - sp * 1.5))
    r1 = min(H, int(bll + sp * 1.5) + 1)
    return (band[r0:r1, :] > 0).sum(axis=0)


def _split_merged_bars(
    sub_raw: np.ndarray, offset: int, sp: float, x0: int, max_w: float
) -> List[float]:
    """
    세로 closing으로 하나로 뭉친 덩어리에서 개별 세로획의 x좌표를 되찾는다.

    sub_raw는 closing 이전의 열별 최대 세로 run 길이다. ♯의 세로획은 여기서도
    길게 남지만 두 획을 잇는 가로획 부분은 짧으므로, 덩어리 내 최댓값의 절반
    (최소 1.0sp)을 넘는 열만 세로획으로 인정해 연속 구간별로 중심을 낸다.
    """
    peak = float(sub_raw.max()) if len(sub_raw) else 0.0
    if peak <= 0:
        return []
    thr = max(sp * 1.0, peak * 0.5)
    strong = sub_raw >= thr

    found: List[float] = []
    i = 0
    n = len(strong)
    while i < n:
        if not strong[i]:
            i += 1
            continue
        j = i
        while j < n and strong[j]:
            j += 1
        # 분리 후에도 세로획 하나의 폭을 넘으면 조표 글리프가 아니다
        if (j - i) <= max_w:
            found.append(x0 + offset + (i + j - 1) / 2.0)
        i = j
    return found


# 조표 막대 수집을 끊는 간격(오선 간격 단위).
#
# **고정 폭을 쓰지 않는다.** 예전에는 `음자리표 끝 + 6sp`로 잘랐는데, 그 값의
# 근거는 주석의 "넉넉히"뿐이었고 **조표 폭에서 유도된 값이 아니었다.**
# 조표는 ♯이 하나 늘 때마다 약 1.1sp씩 길어지므로 어떤 고정 폭도 언젠가 잘린다 —
# 실측에서 ♯5(B장조)의 마지막 막대가 5.89sp라 6sp 창에 **0.1sp 차이로 잘렸고**,
# 그 결과 조표가 4개로 세어지고 남은 샤프가 음표 후보가 됐다.
#
# 대신 **조표 기호는 서로 붙어 있고 그 뒤에는 빈 공간이 온다**는 성질을 쓴다.
# 막대 간격이 이 값을 넘으면 조표가 끝난 것으로 본다.
#
# **양쪽 끝에서 유도했다** (조표 12종 + 검증 악보 3종, 교차 투표 통과 막대 기준):
#
#   조표 **안쪽** 간격 최대  0.97sp  (♭5 D♭장조. ♯은 0.42~0.65sp)
#   조표 **뒤쪽** 간격 최소  2.76sp  (RE:Aoharu 2쪽. 쇼팽은 3.30sp)
#
#   | 유도 방식 | 값 |
#   |---|---|
#   | 안쪽 최대 × 1.5 | 1.46sp |
#   | 뒤쪽 최소 ÷ 2 | 1.38sp |
#   | 기하평균 √(0.97×2.76) | 1.64sp |
#
# 1.40은 안쪽 최대의 **1.44배 위**, 뒤쪽 최소의 **1.97배 아래**로 여유가 비슷하다.
# 이 방식은 ♯7·♭7처럼 더 긴 조표도 길이 제한 없이 담는다.
KEYSIG_GAP_SP = 1.40


# 한 ♯ 글리프의 두 세로획으로 인정하는 y 차이의 한계(step = 반칸).
#
# **아래 한계는 실측 분포에서, 위 한계는 음악 규칙에서 나온다.** 두 근거가
# 독립적으로 거의 같은 지점을 가리킨다.
#
#   같은 글리프의 두 획  진짜 쌍 **284개**(조표 픽스처 15종 + 검증 악보 7개)
#                        중앙 0.364 · 95% 0.652 · **최대 1.102step**
#   다른 글리프          `SHARP_ORDER`에서 인접한 두 샤프의 step 차이는 -3/+4다.
#                        **다른 글리프면 최소 3step 떨어진다** (음악 규칙)
#   교차 확인            ♯6·♯7에서 겹친 잉크가 만든 가짜 막대(x=343.2)의 실측
#                        **최소 2.754step** — 문턱을 만드는 데는 안 썼다
#
#   | 유도 방식 | 값 |
#   |---|---|
#   | 기하평균 √(1.102 × 3)     (음악 규칙) | 1.818step |
#   | 기하평균 √(1.102 × 2.754) (가짜 실측) | 1.742step |
#
# 1.75는 진짜 최대의 **1.59배 위**, 가짜 최소의 **1.57배 아래**로 여유가 비슷하다
# (`KEYSIG_GAP_SP`를 정한 방식과 같다).
#
# **`0.5step`(반칸의 절반)은 실측이 기각한다** — ♯의 두 세로획은 위아래로 어긋나게
# 조판되므로 중심이 원래 안 맞는다. 진짜 쌍 284개 중 **108개(38%)가 0.5를 넘는다.**
#
# 유도 근거와 재현: `docs/KEYSIG_REDESIGN.md` 부록 2,
# `python tools/measure_keysig_consensus.py`
KEYSIG_PAIR_Y_STEP = 1.75


def _bar_y_centers(band: np.ndarray, sp: float, x0: int, x1: int, r0: int, r1: int,
                   is_bar_col: np.ndarray, bars: List[float]) -> List[float]:
    """막대마다 세로 런의 중심(band 지역 y)을 잰다. **검출 창보다 넓은 창에서.**

    검출 창 `r0 = 맨윗줄 - 1.5sp`는 오선 위로 0.5sp 나가 있는 `G♯`(높은음자리표
    3번째)의 글리프 윗부분을 잘라 중심을 아래로 민다(실측 -0.45step). 검출 조건은
    그대로 두고 **측정 창만** 위아래로 `1.2sp`씩 넓힌다.

    막대 x는 이미 정해졌으므로 그 열에서 이어지는 '막대 열'들의 런 시작·끝
    중앙값을 쓴다. `_split_merged_bars`가 한 덩어리에서 쪼갠 두 막대는 열 범위를
    공유해 **같은 y가 나온다** — 쌍 판정에서 Δ=0이라 통과하는 쪽이므로 안전하다
    (진짜 쌍을 기각하지 않는다).
    """
    m0 = max(0, int(r0 - sp * 1.2))
    m1 = min(band.shape[0], int(r1 + sp * 1.2))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    seg = cv2.morphologyEx(band[m0:m1, x0:x1], cv2.MORPH_CLOSE, vk)
    W = seg.shape[1]

    def _run_span(col: np.ndarray) -> Tuple[int, int, int]:
        best = (0, -1, -1)
        run = 0
        for i, v in enumerate(col):
            if v:
                run += 1
                if run > best[0]:
                    best = (run, i - run + 1, i)
            else:
                run = 0
        return best

    spans = [_run_span(seg[:, c] > 0) for c in range(W)]
    out: List[float] = []
    for bx in bars:
        c = min(max(int(round(bx - x0)), 0), W - 1)
        lo = hi = c
        while lo - 1 >= 0 and is_bar_col[lo - 1]:
            lo -= 1
        while hi + 1 < W and is_bar_col[hi + 1]:
            hi += 1
        cols = [i for i in range(lo, hi + 1) if is_bar_col[i]] or [c]
        top_y = float(np.median([spans[i][1] for i in cols]))
        bot_y = float(np.median([spans[i][2] for i in cols]))
        out.append(m0 + (top_y + bot_y) / 2.0)
    return out


def _keysig_scan_end(
    band: np.ndarray, sp: float, x0: int, r0: int, r1: int, W: int
) -> int:
    """조표가 끝나는 x를 **간격으로** 찾는다. 고정 폭으로 자르지 않는다.

    넉넉한 범위에서 막대를 한 번 훑어 보고, 인접 막대 간격이 `KEYSIG_GAP_SP`를
    넘는 첫 지점에서 끊는다. 막대가 없으면 예전과 같은 보수적인 폭을 돌려준다.
    """
    probe_to = min(W, x0 + int(sp * 12))
    cand, _ = _find_bars(band, sp, x0, probe_to, r0, r1)
    if not cand:
        return min(W, x0 + int(sp * 6))
    last = cand[0][0]
    for b, _y in cand[1:]:
        if b - last > sp * KEYSIG_GAP_SP:
            break
        last = b
    return min(W, int(last + sp * 0.7))


def _find_bars(
    band: np.ndarray, sp: float, x0: int, x1: int, r0: int, r1: int
) -> Tuple[List[Tuple[float, float]], int]:
    """
    조표 후보 영역에서 '얇은 세로 막대'(높이 1.6~3.4sp, 폭 0.45sp 이하)의
    `(절대 x, band 지역 y중심)` 목록과, 영역 내 구멍(♭ 고리 후보) 수를 반환한다.

    ♯은 이런 막대 2개가 0.4~0.9sp 간격으로 붙은 유일한 기호다. 판정 자체는
    analyze_staves에서 모든 보표의 막대를 교차 투표한 뒤 수행한다 (조표는
    페이지 내 모든 보표에서 같은 x 위치에 있으므로, 일부 보표에만 있는
    음표/박자표 막대는 투표에서 걸러진다).
    """
    if x1 - x0 < sp * 0.5:
        return [], 0
    seg_raw = band[r0:r1, x0:x1]
    # 오선 제거로 글리프가 위/아래로 쪼개져 있으므로 세로 closing으로 복원
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    seg = cv2.morphologyEx(seg_raw, cv2.MORPH_CLOSE, vk)
    H, W = seg.shape

    def _max_run(col: np.ndarray) -> int:
        best = run = 0
        for v in col:
            if v:
                run += 1
                best = max(best, run)
            else:
                run = 0
        return best

    runs = np.array([_max_run(seg[:, c] > 0) for c in range(W)])
    runs_raw = np.array([_max_run(seg_raw[:, c] > 0) for c in range(W)])
    is_bar_col = (runs >= sp * 1.6) & (runs <= sp * 3.4)

    max_w = sp * 0.45
    bars: List[float] = []
    c = 0
    while c < W:
        if not is_bar_col[c]:
            c += 1
            continue
        c2 = c
        while c2 < W and is_bar_col[c2]:
            c2 += 1
        if (c2 - c) <= max_w:
            bars.append(x0 + (c + c2 - 1) / 2.0)
        else:
            # 덩어리가 세로획 하나보다 넓다 -> ♯의 두 세로획 사이를 세로 closing이
            # 가로획까지 이어붙인 경우다. closing 이전(raw) 프로파일에서는 세로획만
            # 길게 남으므로, 덩어리 안에서 raw run이 두드러지는 열만 골라 분리한다.
            # (이 분리가 없으면 ♯ 글리프가 통째로 버려져 조표 개수가 모자라게 센다)
            bars.extend(_split_merged_bars(runs_raw[c:c2], c, sp, x0, max_w))
        c = c2

    holes = 0
    # ♭ 고리(오른쪽 배 잉크) 검출: 오선 제거 후 구멍이 뚫릴 수 있으므로 세로막대 오른쪽 잉크 폭으로 판정
    for bx in bars:
        local_x = int(round(bx - x0))
        rx0 = max(0, local_x)
        rx1 = min(W, local_x + int(sp * 0.65))
        if rx1 > rx0:
            right_sub = seg_raw[:, rx0:rx1] > 0
            right_cols = right_sub.any(axis=0)
            if right_cols.sum() >= sp * 0.25:
                holes += 1

    return list(zip(bars, _bar_y_centers(band, sp, x0, x1, r0, r1, is_bar_col, bars))), holes


def _same_glyph(found: "List[StaffContext]", xa: float, xb: float) -> bool:
    """구조 막대 둘이 **한 ♯ 글리프의 두 세로획인가**를 y로 확인한다.

    구조 막대는 x만 남은 합의값이므로 **보표별 막대로 되돌아가 읽어**(±3px, 투표
    클러스터와 같은 폭) y를 얻는다. 보표마다 `|Δstep|`을 재고 **중앙값**으로 판정한다 —
    최댓값을 쓰면 막대가 쪼개진 보표 하나가 전체를 뒤집고, 골든의 여유도 3.0배에서
    1.6배로 준다.

    **두 막대가 함께 있는 보표가 하나도 없으면 판단하지 않는다**(True). 그런 막대는
    애초에 지지 보표가 적어 교차 투표에서 걸러지는 쪽이다.
    """
    diffs = []
    for c in found:
        ya = [s for x, s in c.bars if abs(x - xa) <= 3.0]
        yb = [s for x, s in c.bars if abs(x - xb) <= 3.0]
        if ya and yb:
            diffs.append(abs(ya[0] - yb[0]))
    return not diffs or float(np.median(diffs)) <= KEYSIG_PAIR_Y_STEP


# 조표 ♭의 자리 확인 (2026-10-02, TASKS [2](a) · docs/KEYSIG_VOTE_FIX.md · DECISIONS §1-10).
#
# **음악 규칙**: 조표 ♭은 자리가 정해져 있다 — FLAT_ORDER B E A D G C F =
# 높은음자리표 step 4 · 7 · 3 · 6 · 2 · 5 · 1(맨아랫줄 기준 반칸), 낮은음자리표는 그 −2.
# 쉼표 · 기둥 · 박자표가 모든 시스템 같은 x에 서면(Verovio 조판) 교차 투표를 통과해 ♭1로 읽혔다
# (Verovio 4쪽 · 바흐 0.5px 이동 6건). 그것들은 이 자리에 맬 이유가 없다.
#
#   FLAT_STEM_OFFSET_STEP  ♭ 세로획 중심 − 음 자리. 바르게 읽힌 ♭ 쪽 중앙값
#                          LilyPond 1.13~1.20 · Bravura · Leipzig 1.06~1.39 — 세 조판 공통 1.17
#                          (배가 음 자리에, 세로획이 위로 뻗는 글리프 모양 그대로)
#   FLAT_POS_TOL_STEP      √(진짜 보표별 최대 편차 0.46 × 한 음 차이 1step) = 0.68.
#                          1step 어긋나면 다른 음의 ♭이다. 진짜 ♭ 631 막대 |편차| 중앙 0.06 · 99% 0.49
#   과반(0.5)              막대가 잡힌 보표 중 제자리 비율. **여유가 얇다**: 진짜 최소 0.57
#                          (Beethoven — 지원 밖 알토 음자리표 보표가 섞임, 알토 빼면 0.75) · 가짜 최대 0.40
#                          (바흐 0.5px 이동 2배, 세로 정렬 첫 기둥 중 둘이 우연히 B 자리)
#
# **약점 — ♭을 「없다」고 읽는 쪽으로 틀릴 수 있다.** 이 확인은 ♭을 빼기만 한다. 보표 절반 이상에서
# 세로획 높이가 어긋나면(지원 밖 음자리표 · 심한 왜곡 · 막대 쪼개짐) 진짜 ♭ 조표가 줄거나 없어진다.
FLAT_STEP_TREBLE = (4, 7, 3, 6, 2, 5, 1)
FLAT_STEM_OFFSET_STEP = 1.17
FLAT_POS_TOL_STEP = 0.68


def _flat_at_position(found: "List[StaffContext]", x: float, k: int) -> bool:
    """구조 막대 x가 k번째 조표 ♭ 자리인가 — 막대가 잡힌 보표의 과반이 그 자리(± 허용)에 있을 것."""
    hits = []
    for c in found:
        steps = [s for bx, s in c.bars if abs(bx - x) <= 3.0]     # 투표 클러스터와 같은 ±3px
        if steps:
            want = FLAT_STEP_TREBLE[k] - (2 if c.clef == "bass" else 0) + FLAT_STEM_OFFSET_STEP
            hits.append(abs(steps[0] - want) <= FLAT_POS_TOL_STEP)
    return bool(hits) and sum(hits) * 2 >= len(hits)


def _staff_sharp_pairs(c: "StaffContext", sp: float) -> List[float]:
    """보표 **안에서** ♯ 쌍 중심 — 교차 투표의 쌍 조건(0.3~0.55sp · `KEYSIG_PAIR_Y_STEP`)을 그대로, 떨어지면 한 칸 전진."""
    b = sorted(c.bars)
    out: List[float] = []
    i = 0
    while i < len(b):
        if (i + 1 < len(b) and sp * 0.3 <= b[i + 1][0] - b[i][0] <= sp * 0.55
                and abs(b[i + 1][1] - b[i][1]) <= KEYSIG_PAIR_Y_STEP):
            out.append((b[i][0] + b[i + 1][0]) / 2.0)
            i += 2
        else:
            i += 1
    return out


def _sharp_chain(pairs: List[float], sp: float) -> List[float]:
    """쌍 중심들을 간격 0.9~2.2sp 사슬로 잇고 가장 긴 것(동률이면 오른쪽 — 음자리표 잔여물 배제)."""
    if not pairs:
        return []
    chains: List[List[float]] = []
    cur = [pairs[0]]
    for p in pairs[1:]:
        if sp * 0.9 <= p - cur[-1] <= sp * 2.2:
            cur.append(p)
        else:
            chains.append(cur)
            cur = [p]
    chains.append(cur)
    return max(chains, key=lambda ch: (len(ch), ch[0]))


def _vote_key_signature(contexts: "Dict[int, StaffContext]") -> Tuple[int, str, float]:
    """
    모든 보표의 막대 후보를 교차 투표해 조표를 판정한다.

    1. 과반(최소 2개) 보표에서 ±3px 이내에 나타나는 막대 x만 '구조 막대'로 인정
       (음표 기둥은 보표마다 위치가 달라 걸러지고, 박자표는 첫 시스템에만 있어 걸러짐)
    2. 구조 막대로 쌍을 만든다 — x 간격 0.3~0.55sp **그리고** 두 막대의 y가
       한 글리프 안에 들어올 것(`_same_glyph`). 쌍들을 간격 0.9~2.2sp 사슬로 연결
    3. 가장 긴 사슬의 길이 = ♯ 개수 (동률이면 오른쪽 사슬 = 음자리표 잔여물 배제).
       보표 안 쌍 먼저 투표한 사슬과 비교해 긴 쪽 (시스템 x 어긋남 대응)
    4. 쌍이 전혀 없으면 ♭ 후보: 구조 막대 + 구멍 다수결, 단 조표 ♭ 자리에 있는 막대만
    """
    found = [c for c in contexts.values() if c.clef_found]
    if not found:
        return 0, "", 0.0
    sp = float(np.median([c.spacing for c in found]))
    threshold = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1

    # 막대 x 교차 투표 (±3px 클러스터링)
    all_bars = sorted(x for c in found for x, _y in c.bars)
    consensus: List[float] = []
    i = 0
    while i < len(all_bars):
        j = i
        while j + 1 < len(all_bars) and all_bars[j + 1] - all_bars[i] <= 3.0:
            j += 1
        support = j - i + 1
        if support >= threshold:
            consensus.append(float(np.mean(all_bars[i:j + 1])))
        i = j + 1

    # 쌍 만들기
    pairs: List[float] = []
    singles: List[float] = []
    i = 0
    while i < len(consensus):
        # y 조건이 떨어지면 **한 칸만** 전진한다. 겹친 잉크가 만든 가짜 막대가
        # singles로 빠지고 **뒤가 안 밀린다** — ♯6·♯7이 ♯4로 읽히던 이유가
        # 정확히 "하나 끼면 뒤가 전부 밀린다"였다.
        if (i + 1 < len(consensus)
                and sp * 0.3 <= consensus[i + 1] - consensus[i] <= sp * 0.55
                and _same_glyph(found, consensus[i], consensus[i + 1])):
            pairs.append((consensus[i] + consensus[i + 1]) / 2.0)
            i += 2
        else:
            singles.append(consensus[i])
            i += 1

    # 보표 안 쌍 먼저 → 쌍 중심 교차 투표 (2026-10-02, docs/KEYSIG_VOTE_FIX.md §2).
    # 시스템끼리 조표 x가 어긋나면(Schumann Leipzig 3.5px) ±3px 막대 묶음이 한 ♯의 두 획(6~7px)을
    # 섞어 쌍이 깨진다. 묶음 폭을 넓히는 것은 안 된다 — 0.3sp면 픽스처 ♯6 · ♯7이 깨진다
    # (시스템 어긋남 0.2sp와 두 획 간격 0.33sp가 너무 가깝다). 쌍 중심끼리는 사슬 하한 0.9sp 넘게
    # 떨어지므로 그 절반 0.45sp로 묶어도 다른 ♯과 안 섞인다.
    # 단독으로 쓰지 않는다 — 보표 하나에서 획 하나만 빠져도 그 보표 쌍이 없어져 Aoharu 0.5px 이동
    # 3건이 ♯2 → ♯1. 두 방식 모두 **덜 세는 쪽으로만** 틀렸으므로(정답보다 많이 센 경우 0 / 361 입력)
    # 긴 사슬을 택한다.
    staff_pairs = sorted(x for c in found for x in _staff_sharp_pairs(c, sp))
    voted_pairs: List[float] = []
    i = 0
    while i < len(staff_pairs):
        j = i
        while j + 1 < len(staff_pairs) and staff_pairs[j + 1] - staff_pairs[i] <= sp * 0.45:
            j += 1
        if j - i + 1 >= threshold:
            voted_pairs.append(float(np.mean(staff_pairs[i:j + 1])))
        i = j + 1
    best = max((_sharp_chain(pairs, sp), _sharp_chain(voted_pairs, sp)), key=len)
    if best:
        return min(len(best), 7), "♯", best[-1] + sp * 0.8

    if singles:
        n_holes = int(np.median([c.holes for c in found]))
        # 왼쪽부터 조표 ♭ 자리에 있는 것만 센다 — 처음 어긋나는 데서 멈춘다(위 FLAT_STEM_OFFSET_STEP 주석)
        n_pos = 0
        while n_pos < min(len(singles), 7) and _flat_at_position(found, singles[n_pos], n_pos):
            n_pos += 1
        n_flat = min(len(singles), n_holes, n_pos)
        if n_flat > 0:
            return min(n_flat, 7), "♭", max(singles) + sp * 0.8

    return 0, "", 0.0


# 같은 음자리표끼리 맞춘 조표 투표 (2026-10-14, 사용자 결정 · DECISIONS §1-37, `docs/KEYSIG_PERSPECTIVE.md` (가)).
# 원근으로 보표마다 조표 막대 x가 26~194px 어긋나면 ±3px 교차 투표가 무너져 조표를 0개로 읽는다.
#   옮김 = 같은 종류(`clef`) 보표들의 clef_end 중앙 − 자기 clef_end — 종류를 섞으면 글리프 폭 차(3~6px)가 투표 묶음 ±3px를 넘는다(Aoharu 2 · Clara 1 L)
#   들여쓴 첫 시스템 보표(clef_end ≥ 중앙 + 4sp, 아래 박자표 판정과 같음)는 박자표 시작 x 이후 막대를 뺀다 —
#     옮긴 박자표 숫자 막대가 다른 보표 잡막대와 합의했다(Clara 2 B)
#   박자표 시작 = `_timesig_span_end`와 같은 열 조건 구간의 왼끝(clef_end부터 KEYSIG_TS_LOOK_SP 안)
# 측정(`tools/measure_keysig_sameclef.py`): 깨끗한 160 입력 조표 변화 0 · 열화 세트 틀림 12 중 10 회복 · 망침 0.
# **지금 투표와 조표가 다를 때만** 쓴다 — 같으면 헤더 끝 등 모든 값이 예전 그대로.
# 사진 모드도 켠다(2026-10-14 사용자 결정): 열화 세트 사진 모드 회복 5 · 망침 0으로 검증 — 실제 사진 표본은 아직 없다.
KEYSIG_TS_LOOK_SP = 8.0


def _timesig_start(no_staff: np.ndarray, staff: Staff, x_from: int):
    """`_timesig_span_end`와 같은 열 조건으로 첫 숫자 구간의 **왼끝**. 없으면 None."""
    sp = staff.spacing
    H, W = no_staff.shape[:2]
    x_to = min(W, x_from + int(sp * KEYSIG_TS_LOOK_SP))
    tol = max(1, int(round(sp * 0.2)))
    t0, t1 = max(0, int(staff.top) - tol), min(H, int(staff.top) + tol + 1)
    b0, b1 = max(0, int(staff.bottom) - tol), min(H, int(staff.bottom) + tol + 1)
    if x_to <= x_from or t1 <= t0 or b1 <= b0:
        return None
    spans = (no_staff[t0:t1, x_from:x_to] > 0).any(axis=0) & (no_staff[b0:b1, x_from:x_to] > 0).any(axis=0)
    lo, hi = int(sp * 0.6), int(sp * 2.6)
    i, n = 0, len(spans)
    while i < n:
        if not spans[i]:
            i += 1
            continue
        j = i
        while j < n and spans[j]:
            j += 1
        if lo <= j - i <= hi:
            return x_from + i
        i = j
    return None


def _same_clef_view(result: PreprocessResult, contexts: "Dict[int, StaffContext]", no_staff: np.ndarray):
    """(막대를 옮긴 사본 contexts, 보표별 옮김 px) — 투표 입력만 만든다. 원래 contexts는 건드리지 않는다."""
    import dataclasses
    found = [c for c in contexts.values() if c.clef_found]
    if not found:
        return contexts, {}
    staff_of = {s.index: s for s in result.staves}
    med_all = float(np.median([c.clef_end for c in found]))
    med_kind = {k: float(np.median([c.clef_end for c in found if c.clef == k])) for k in {c.clef for c in found}}
    view, shift = {}, {}
    for k, c in contexts.items():
        if not c.clef_found:
            view[k] = c
            continue
        bars = list(c.bars)
        if len(found) >= 3 and c.clef_end >= med_all + staff_of[k].spacing * 4.0:
            cut = _timesig_start(no_staff, staff_of[k], int(c.clef_end))
            if cut is not None:
                bars = [b for b in bars if b[0] < cut]
        d = med_kind[c.clef] - c.clef_end
        view[k] = dataclasses.replace(c, bars=tuple((x + d, y) for x, y in bars))
        shift[k] = d
    return view, shift


def analyze_staves(result: PreprocessResult) -> Dict[int, StaffContext]:
    """모든 보표의 헤더를 분석하고, 조표는 다수결로 통일해 각 보표에 적용한다."""
    no_staff = remove_staff_lines(result.binary, result.staves)
    img_h = result.binary.shape[0]

    contexts: Dict[int, StaffContext] = {}
    single_system = len(result.staves) <= 2
    for staff in result.staves:
        contexts[staff.index] = _analyze_one(no_staff, staff, img_h, single_system)

    # 조표 판정: 모든 보표의 막대 후보를 교차 투표
    kc, ks, key_right = _vote_key_signature(contexts)
    right_of: Dict[int, float] = {}      # 같은 음자리표 맞춤 투표를 쓸 때 보표별 조표 오른쪽 끝(원래 좌표)
    view, shift = _same_clef_view(result, contexts, no_staff)
    kc2, ks2, r2 = _vote_key_signature(view)
    if (kc2, ks2) != (kc, ks):
        kc, ks, key_right = kc2, ks2, r2
        right_of = {k: r2 - d for k, d in shift.items()}
    order = SHARP_ORDER if ks == "♯" else FLAT_ORDER
    letters = tuple(order[:kc]) if kc > 0 else tuple()
    for ctx in contexts.values():
        ctx.key_count, ctx.key_symbol, ctx.key_letters = kc, ks, letters

    # 2차 패스: 확정된 조표 오른쪽 끝(key_right)을 기준으로 헤더 끝을 다시 계산한다.
    # (개별 보표의 조표 스캔이 첫 음표와 붙어 과확장되는 경우를 바로잡아
    #  시스템 첫 음표가 헤더에 삼켜지는 것을 방지)
    # 단, 들여쓰기된 첫 시스템처럼 조표 x위치가 합의 위치와 다른 보표는
    # 자체 스캔 결과(이미 조표+박자표를 올바르게 포함)를 그대로 유지한다.
    found_ctx0 = [c for c in contexts.values() if c.clef_found]
    med_clef0 = (float(np.median([c.clef_end for c in found_ctx0]))
                 if len(found_ctx0) >= 3 else None)
    groups_all = system_groups(result.binary, result.staves) if result.staves else []
    top_sys = set(groups_all[0]) if groups_all else set()
    # 줄 첫머리 조바꿈(2026-10-26, §1-52 초안): 한 시스템(보표 둘 이상)의 보표가 **하나하나** 같은 조표를 가리키고 그 조표가 쪽 조표보다 수가 적고
    # 기호가 같으면, 그 시스템은 자기 조표 오른쪽 끝을 헤더 기준으로 쓴다. 쪽 합의 끝(4♯ 자리)을 쓰면 1♯ 줄의 첫 음을 덮는다(Schubert 「보리수」 마지막 줄 8).
    # 49쪽 전수에서 이 조건은 Schubert 두 쪽에서만 걸린다(보표 하나씩의 표는 1♯ · 1♭로 흔들리는 일이 잦아 「전부 같음」을 요구).
    # 계이름의 조표는 바꾸지 않는다(줄 중간 조바꿈 확인 `key_change_regions` 몫) — 헤더 경계만.
    sys_kr: Dict[int, float] = {}
    for g in groups_all:
        g = [i for i in g if i in contexts and contexts[i].clef_found]
        own = {_vote_key_signature({i: contexts[i]})[:2] for i in g}
        if len(g) >= 2 and len(own) == 1:
            k1, s1 = next(iter(own))
            if 0 < k1 < kc and s1 == ks:
                r = _vote_key_signature({i: contexts[i] for i in g})[2]
                sys_kr.update({i: r for i in g})

    for staff in result.staves:
        ctx = contexts.get(staff.index)
        if ctx is None or not ctx.clef_found:
            continue
        ink_cnt = _restricted_profile(no_staff, staff, img_h)
        if kc > 0:
            # 들여쓰기되지 않은 보표는 조표가 반드시 합의 위치에 있다. 자체 스캔이
            # 잔여 잉크 탓에 과확장돼도 합의값으로 잘라야 한다 — 안 그러면 자기
            # 스캔이 만든 잘못된 header_end를 그대로 써서 첫 음표를 삼킨다
            # (실측: 2페이지 st0가 352로 남아 39마디 첫 음 C4가 사라졌다.
            #  이 보표의 유일한 '막대' 344는 조표가 아니라 그 음표의 기둥이었다).
            kr = right_of.get(staff.index, key_right)
            indented = (med_clef0 is not None
                        and ctx.clef_end >= med_clef0 + staff.spacing * 4.0)
            aligned = (not indented
                       or not ctx.bars
                       or any(b <= kr + 3 for b, _y in ctx.bars))
            if aligned:
                base = max(ctx.clef_end, int(round(kr)))
                ts_ok = med_clef0 is None or indented or staff.index in top_sys
                if staff.index in sys_kr:
                    old = _header_end_after(no_staff, staff, ink_cnt, base, timesig_ok=ts_ok)[1]
                    ctx.header_end, old2 = _header_end_after(no_staff, staff, ink_cnt, max(ctx.clef_end, int(round(sys_kr[staff.index]))), timesig_ok=ts_ok)
                    old = max(old, old2)
                else:
                    ctx.header_end, old = _header_end_after(no_staff, staff, ink_cnt, base, timesig_ok=ts_ok)
                ctx.header_reopened = old if old > ctx.header_end else 0
            # 정렬되지 않은 보표(들여쓰기된 시스템)는 기존 header_end 유지
        else:
            # 조표가 없는 악보: 음자리표 끝 기준으로만 헤더를 잡는다
            first = med_clef0 is None or ctx.clef_end >= med_clef0 + staff.spacing * 4.0 or staff.index in top_sys
            ctx.header_end, old = _header_end_after(no_staff, staff, ink_cnt, ctx.clef_end, timesig_ok=first)
            ctx.header_reopened = old if old > ctx.header_end else 0

    # 박자표는 곡의 첫 시스템에만 나온다. 그 시스템은 브레이스·곡명 때문에
    # 들여쓰기되어 음자리표가 뚜렷이 오른쪽에서 시작한다
    # (실측 clef_end: 쇼팽 314/361 vs 나머지 136~183, RE Aoharu 324/325 vs 252~272,
    #  바흐 364/365 vs 187). 이어지는 페이지는 들여쓰기가 없어 아무 보표도 안 걸리고,
    # 그게 맞는 동작이다 — 그런 페이지엔 박자표가 없다.
    found_ctx = [c for c in contexts.values() if c.clef_found]
    if found_ctx:
        # 보표가 한 시스템분(1~2개)뿐이면 비교할 대상이 없다. 그런 이미지는
        # 그 자체가 첫 시스템이므로 들여쓰기 판정을 건너뛰고 그냥 적용한다
        # (합성 테스트처럼 보표가 하나뿐인 악보에서 박자표 숫자가 유령이 됐다).
        single_system = len(found_ctx) <= 2
        med_clef = float(np.median([c.clef_end for c in found_ctx]))
        first_system = []
        for staff in result.staves:
            ctx = contexts.get(staff.index)
            if ctx is None or not ctx.clef_found:
                continue
            # 문턱 4sp: 진짜 첫 시스템은 중앙값보다 +4.9sp 이상 들여쓰이지만
            # (실측 RE Aoharu 1p 324 vs 중앙값 268), 이어지는 페이지의 살짝 큰
            # clef_end(302, +3.0sp)는 걸러야 한다. 1.5sp로 두면 그게 통과해
            # 2페이지에서 3개를 잃었다.
            if not single_system and ctx.clef_end < med_clef + staff.spacing * 4.0:
                continue  # 들여쓰기되지 않음 -> 첫 시스템이 아니다
            ts_end = _timesig_span_end(no_staff, staff, ctx.header_end)
            first_system.append((ctx, max(int(ts_end), ctx.header_end)))

        # 박자표는 한 시스템의 모든 보표에 **같은 x 자리**에 세로로 맞춰 그린다.
        # 그러니 한 보표에서만 제대로 찾혀도 나머지 보표의 답을 알 수 있다.
        # 이 규칙이 필요한 이유(바흐 미뉴에트 실측): 위 보표에서는 높은음자리표
        # 꼬리가 먼저 '숫자 폭'(0.6~2.6sp) 조건을 만족해 버려 탐색이 x=401에서
        # 멈췄고, 정작 박자표 3/4(x≈405~425)는 헤더 밖에 남아 숫자 두 개가
        # 유령 음표가 됐다. 아래 보표(낮은음자리표)는 꼬리가 짧아 425를 제대로
        # 찾았다 — 그 값을 위 보표에도 그대로 쓴다.
        if first_system:
            shared = max(end for _c, end in first_system)
            for ctx, _end in first_system:
                ctx.header_end = int(shared)

    # 짧게 들여쓴 첫 시스템도 있다(Verovio 4중주: 1.7sp).
    # 기존 4sp 문턱은 건드리지 않고, 원본의 연속 세로줄로 묶인 보표를 확인한다.
    # 뒤 시스템보다 음자리표 끝이 모두 오른쪽이고, 모든 보표가 같은 숫자 끝을
    # 찾았을 때만 그 끝을 쓴다. 확인 불가·불일치는 기존 경계를 보존한다.
    # 검색은 음자리표 끝부터: 이미 덮은 박자표 뒤에서 다시 찾으면 첫 음표를 잡는다.
    # 음자리표를 못 찾은 보표도 숫자는 직접 검사한다. 같은 끝이면 경계만 공유하고
    # 음자리표 종류·검출 여부는 그대로 둔다(0.5px 이동 시 네 번째 음자리표 미검출).
    if result.staves and contexts[result.staves[0].index].clef_found:
        first = result.staves[0]
        left = contexts[first.index].clef_end
        linked = (result.binary[first.top:first.bottom + 1, :left] > 0).all(axis=0)
        group = [first]
        for staff in result.staves[1:]:
            linked &= (result.binary[first.top:staff.bottom + 1, :left] > 0).all(axis=0)
            if not linked.any():
                break
            group.append(staff)
        group_ctx = [contexts[s.index] for s in group]
        found_group = [c for c in group_ctx if c.clef_found]
        others = [contexts[s.index] for s in result.staves[len(group):]
                  if contexts[s.index].clef_found]
        if (len(found_group) >= 2
                and (not others or min(c.clef_end for c in found_group)
                     > max(c.clef_end for c in others))):
            base = max(c.clef_end for c in found_group)
            ends = [_timesig_span_end(no_staff, s, base) for s in group]
            # 숫자 둘은 두 머리를 잇는 기둥이 아니다. 같은 화음이 모든 성부에
            # 반복돼도 박자표로 자르지 않도록, 위·아래 검사 띠 사이의 연속 기둥을 거부한다.
            stems = []
            for staff, end in zip(group, ends):
                tol = max(1, int(round(staff.spacing * 0.2)))
                block = result.binary[staff.top + tol:staff.bottom - tol + 1,
                                      max(base, end - int(staff.spacing * 2.6)):end]
                stems.append(block.size > 0 and (block > 0).all(axis=0).any())
            if len(set(ends)) == 1 and ends[0] > base and not any(stems):
                for ctx in group_ctx:
                    ctx.header_end = max(ctx.header_end, ends[0])

    return contexts


# ------------------------------------------------------------------
# 보표 중간 음자리표 바뀜 → 「확인 필요」 (2026-10-04, 사용자 승인 · (c) 안 2, docs/CLEF_CHANGE.md · DECISIONS §1-16)
# 음고 계산은 보표 머리 음자리표 하나로 하므로(`pitch_calculator` 동결) 보표 중간에 음자리표가 바뀌면 그 뒤 음은 3도 · 6도씩 틀린다.
# 맞게 읽기(안 1)는 동결 모듈을 풀어야 해서 보류 — 여기서는 **바뀐 뒤 라벨을 check로 표시만** 한다(삭제 · 음고 변경 없음).
# 검출: 그 쪽 머리 음자리표(검출 구간 `clef_start ~ clef_end`, 종류별 첫 보표)를 본으로, 오선 제거 영상에서 배율별 정규화 상관.
#   CLEF_CHANGE_SCORE 0.55 — Verovio 20쪽 맞는 구간 38 → 44 · 헛 구간 0(2026-10-06 사용자 승인, `NIGHT_CAUSES.md` [7]).
#     0.55에서 PDF E단조 1쪽 보표 0 템포 「= 69)」의 9가 낮은음자리표로 걸린 헛 구간 1은 아래 상자-보표 겹침 조건이 막는다
#   배율 0.55~1.0 — 바뀐 음자리표는 머리보다 작게 찍힌다(기보 관례 약 2/3 · 실측 Verovio 0.65~0.75)
#   1.5sp 안 최댓값만 — 한 글리프가 여러 x에서 걸리는 것을 하나로
# 구간: 머리와 **다른 종류**로 검출된 x부터 같은 보표의 다음 검출(또는 보표 끝)까지.
CLEF_CHANGE_SCORE = 0.55
CLEF_CHANGE_SCALES = (0.55, 0.65, 0.75, 0.85, 1.0)
CLEF_BOX_STAFF_OVERLAP = 0.25
CLEF_REPRINT_MAX = 1     # 바뀌기 전 같은 종류 재표기 허용 수(정답 실측 최대) — `clef_change_regions`


def _clef_change_hits(ns: np.ndarray, staff: Staff, ctx: StaffContext, tmpl: Dict[str, np.ndarray]) -> List[Tuple[int, str, int, int, int]]:
    """한 보표 몸통(헤더 뒤)에서 본이 걸린 (x, 종류, 위끝 y, 상자 폭, 상자 높이) — 1.5sp 안 최댓값, 같은 자리 여러 배율 · 종류는 최고 점수 하나.
    상자 = matchTemplate 최고 자리 ~ 본 크기 × 배율(글리프 상자 안 라벨 표시 §1-23이 쓴다)."""
    sp = staff.spacing
    H = ns.shape[0]
    y0 = max(0, int(staff.top - 3 * sp))
    band = ns[y0:min(H, int(staff.bottom + 3 * sp)), :]
    w = max(1, int(1.5 * sp))
    # 검색 시작 = 머리 음자리표 끝 + 조표 끝(2026-10-06 사용자 승인). 헤더 끝(박자표까지)에서 시작하면 머리 바로 뒤에
    # 찍힌 바뀐 음자리표를 놓친다 — 슈만 Bravura 보표 1 x 269(상관 0.67)가 잘려 확실 음고 오류 30(`NIGHT_CAUSES.md` [7]).
    # 조표 끝 = 조표 막대 가장 오른쪽 + 0.5sp(♭ 고리 · ♯ 오른쪽 획). 음자리표를 못 찾은 보표는 지금처럼 헤더 끝.
    x_from = ctx.header_end
    if ctx.clef_found and ctx.clef_end > 0:
        x_from = ctx.clef_end
        if ctx.key_count and ctx.bars:
            x_from = max(x_from, int(max(b for b, _y in ctx.bars) + 0.5 * sp))
        x_from = min(x_from, ctx.header_end)
    best: Dict[int, tuple] = {}
    for kind, tp in tmpl.items():
        for sc in CLEF_CHANGE_SCALES:
            tt = cv2.resize(tp, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            if tt.shape[0] >= band.shape[0] or tt.shape[1] < 3 or tt.std() == 0:
                continue
            m = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED)
            prof = m.max(axis=0)
            for x in np.where(prof >= CLEF_CHANGE_SCORE)[0]:
                if x < x_from or prof[x] < prof[max(0, x - w):x + w + 1].max():
                    continue
                k = int(round(x / w))
                if k not in best or prof[x] > best[k][0]:
                    best[k] = (float(prof[x]), int(x), kind, y0 + int(m[:, x].argmax()), tt.shape[1], tt.shape[0])
    # 상자가 보표 세로 범위(윗줄~아랫줄)와 보표 높이의 CLEF_BOX_STAFF_OVERLAP 이상 겹쳐야 음자리표로 인정(2026-10-06 사용자 승인).
    # 실측 겹침/보표 높이: 정답 글리프 걸림 최소 0.51(PDF 19) · 0.76(Verovio 75), 헛 걸림 0.0(E단조 1쪽 보표 0 템포 「= 69)」의 9) — 그 중간 0.25
    top, h = staff.top, max(1, staff.bottom - staff.top)
    return sorted(t[1:] for t in best.values()
                  if max(0, min(t[3] + t[5], staff.bottom) - max(t[3], top)) >= CLEF_BOX_STAFF_OVERLAP * h)


def _clef_detections(result: PreprocessResult, contexts: Dict[int, StaffContext]):
    """보표 몸통 음자리표 검출 — (보표 목록, 보표별 걸림, 버린 종류, 본). `clef_change_regions` · `clef_glyph_suspects`가 함께 쓴다."""
    ns = remove_staff_lines(result.binary, result.staves).astype(np.float32)
    H = ns.shape[0]
    tmpl: Dict[str, np.ndarray] = {}
    for st in sorted(result.staves, key=lambda s: s.top):
        c = contexts.get(st.index)
        if c is None or not c.clef_found or c.clef in tmpl or c.clef_end <= c.clef_start:
            continue
        # 행은 머리 음자리표 검출과 같은 오선 ±1.5sp — ±3sp로 오리면 음자리표 칸 위아래 다른 잉크가 섞여
        # 낮은음자리표 본이 정답 상자의 두 배 높이(129 대 66행)가 되고 원래 음자리표로 돌아오는 자리를 놓쳤다(Clara 1 보표 9 x 1052, 상관 0.48 대 0.76)
        win = ns[max(0, int(st.top - 1.5 * st.spacing)):min(H, int(st.bottom + 1.5 * st.spacing) + 1), c.clef_start:c.clef_end]
        rows, cols = np.where(win.any(axis=1))[0], np.where(win.any(axis=0))[0]
        if len(rows) and len(cols):
            tmpl[c.clef] = win[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    staves = [st for st in result.staves if st.index in contexts]
    hits = {st.index: _clef_change_hits(ns, st, contexts[st.index], tmpl) for st in staves}
    # 망가진 본 거르기: 같은 음자리표를 바뀐 적 없는 보표 중간에 다시 찍는 일은 드물다 — Verovio 20쪽 정답에서 다른 종류로 바뀌기 전
    # 같은 종류 재표기는 보표당 최대 1번(Clara 3 보표 8 x 669). 머리가 K인 보표에서 다른 종류가 걸리기 전에 K 본이
    # CLEF_REPRINT_MAX(1)번보다 많이 걸리면 그 본은 음자리표가 아닌 것(음표 조각 · 음자리표+조표+박자표 덩어리)을 잡는다 — 머리 검출이 틀린 쪽.
    # 실측: 보지 않은 오르간 2쪽은 머리 검출이 음표 조각 · 폭 9~15sp 덩어리를 본으로 오려 음표마다 걸렸고 한 쪽 161개가 헛표시됐다(`CLEF_CHANGE.md` §4).
    # 그 종류의 본을 버린다 — 그 종류가 머리인 보표는 판정하지 않는다(가를 본이 없다)
    def _same_before_change(si: int) -> int:
        n = 0
        for _x, k, *_box in hits[si]:
            if k != contexts[si].clef:
                break
            n += 1
        return n
    bad = {contexts[si].clef for si in hits if _same_before_change(si) > CLEF_REPRINT_MAX}
    return staves, hits, bad, tmpl


def clef_change_regions(result: PreprocessResult, contexts: Dict[int, StaffContext]) -> Dict[int, List[Tuple[int, int]]]:
    """보표별 (시작 x, 끝 x) — 머리와 다른 종류의 음자리표가 검출된 구간."""
    staves, hits, bad, tmpl = _clef_detections(result, contexts)
    out: Dict[int, List[Tuple[int, int]]] = {}
    for st in staves:
        c = contexts[st.index]
        if c.clef in bad or c.clef not in tmpl:
            continue
        found = [(x, k) for x, k, *_box in hits[st.index] if k not in bad]
        for i, (x, kind) in enumerate(found):
            if kind != c.clef:
                out.setdefault(st.index, []).append((x, found[i + 1][0] if i + 1 < len(found) else 10 ** 9))
    return out


# 보표 중간 음자리표 글리프 상자 안의 라벨 → 「확인 필요」 (2026-10-05, 사용자 구현 승인 · DECISIONS §1-23, `docs/CLEF_GLYPH_LABELS.md`).
# 바뀐 음자리표 · 원래 음자리표로 돌아오는 글리프 모두. 측정(PDF 17 · 보지 않은 8 · Verovio 20): 상자 83 안 라벨 78 = 전부 유령(음자리표 조각), 진짜 머리 0.
# 표시만 — 삭제안은 보류(상자가 본 크기에 묶여 음자리표 바로 뒤에 붙은 음표가 있는 조판에서 진짜 머리를 지울 수 있다). 사진 모드에서는 끈다(미측정)
def header_reopened_suspects(contexts: Dict[int, StaffContext], notes) -> list:
    """§1-51로 헤더에서 풀려난 자리(지금 헤더 끝 ~ 전 규칙 헤더 끝)의 음 → check. 49쪽 되찾음 29 중 유령은 0이었지만
    보류 쪽에서 셈여림 「ppp」 고리 하나가 「확실」 유령이 됐다(bbm3) — 판정을 보류하고 사람이 본다(지시: 유령이 생기면 그 경로는 check)."""
    out = []
    for n in notes:
        c = contexts.get(n.staff_index)
        if c is not None and c.header_end <= n.x < c.header_reopened:
            out.append(n)
    return out


def clef_glyph_suspects(result: PreprocessResult, contexts: Dict[int, StaffContext], notes) -> list:
    if getattr(result, "photo_correction", None) is not None:
        return []
    staves, hits, bad, tmpl = _clef_detections(result, contexts)
    boxes = {}
    for st in staves:
        c = contexts[st.index]
        if c.clef in bad or c.clef not in tmpl:
            continue
        boxes[st.index] = [(x, y, x + bw, y + bh) for x, k, y, bw, bh in hits[st.index] if k not in bad]
    return [n for n in notes if any(a <= n.x <= b and t <= n.y <= u for a, t, b, u in boxes.get(n.staff_index, ()))]


def clef_change_suspects(result: PreprocessResult, contexts: Dict[int, StaffContext], notes) -> list:
    """바뀐 음자리표 뒤 음표(같은 보표). 사진 모드에서는 끈다 — 사진 세트 표시 정밀도를 재기 전(사용자 결정 2026-10-04)."""
    if getattr(result, "photo_correction", None) is not None:
        return []
    reg = clef_change_regions(result, contexts)
    return [n for n in notes if any(a <= n.x < b for a, b in reg.get(n.staff_index, ()))]


# ------------------------------------------------------------------
# 알토(가온) 음자리표 → 그 보표 전체 「확인 필요」 (2026-10-04, 사용자 구현 승인 · DECISIONS §1-17, docs/ALTO_CLEF.md)
# 알토는 지원하지 않는다 — 머리 음자리표 판별(높은음 / 낮은음)이 낮은음으로 읽어 보표 전체 음고가 틀린 채 「확실」로 나왔다(Verovio 확실 음고 오류 164).
# 고치지 않고 **표시만** 한다(삭제 · 음고 변경 없음). 기보: C 음자리표는 윗줄부터 아랫줄까지 오선에 꼭 맞고, 왼쪽 굵은 획이 5줄(4sp) 전체를 관통한다.
#   ALTO_EDGE_SP 0.3 — 음자리표 칸 잉크 위 · 아래 끝과 윗줄 · 아랫줄의 거리. 실측 알토 ±0.06, 높은음 아래끝 ≥ 1.49, 낮은음 아래끝 중앙 −0.91
#   ALTO_BAR_SP 3.6 — 세로로 끊김 없이 이어진 잉크 최장. 오선 높이 4sp의 90%. 실측 알토 4.11, 범위 조건만 맞는 낮은음 16보표 최대 2.14
ALTO_EDGE_SP = 0.3
ALTO_BAR_SP = 3.6


def is_alto(no_staff: np.ndarray, staff: Staff, ctx: StaffContext) -> bool:
    if not ctx.clef_found or ctx.clef_end <= ctx.clef_start:
        return False
    sp = staff.spacing
    y0 = max(0, int(staff.top - 3 * sp))
    win = no_staff[y0:min(no_staff.shape[0], int(staff.bottom + 3 * sp)), ctx.clef_start:ctx.clef_end] > 0
    rows = np.where(win.any(axis=1))[0]
    if not len(rows):
        return False
    if abs(y0 + rows[0] - staff.top) > ALTO_EDGE_SP * sp or abs(y0 + rows[-1] - staff.bottom) > ALTO_EDGE_SP * sp:
        return False
    best = 0
    for col in win.T:
        cur = 0
        for v in col:
            cur = cur + 1 if v else 0
            best = max(best, cur)
    return best >= ALTO_BAR_SP * sp


def alto_suspects(result: PreprocessResult, contexts: Dict[int, StaffContext], notes) -> list:
    """알토 음자리표 보표의 음표 전부. 사진 모드에서는 끈다 — 사진 세트에 알토가 없어 정밀도를 잴 수 없음."""
    if getattr(result, "photo_correction", None) is not None:
        return []
    ns = remove_staff_lines(result.binary, result.staves)
    alto = {st.index for st in result.staves if st.index in contexts and is_alto(ns, st, contexts[st.index])}
    return [n for n in notes if n.staff_index in alto]


# ------------------------------------------------------------------
# 음자리표를 못 찾은 보표 → 그 보표 전체 「확인 필요」 (2026-10-05, 사용자 구현 승인 · DECISIONS §1-22, `docs/CLEF_TAIL.md` [C])
# 머리 음자리표 군집을 못 찾으면(`clef_found` 거짓) 기본값 높은음으로 음고를 계산한다 — 낮은음 보표면 전체가 틀린 채 「확실」.
# 측정: 전 세트 · 조표 픽스처에서 3보표(전부 베토벤 4중주 첼로 — 각괄호와 음자리표가 붙음), 라벨 51 = 음고 틀림 45 · 유령 6 · 헛표시 0. 사진 51장 0보표.
# 사진 모드에서도 켠다: 판단 근거(음자리표를 못 찾았다 = 음고가 추측값)는 사진 보정과 무관하고, 사진 세트에서 걸리는 보표가 0이라 헛표시 위험이 없다.
# 사용자가 음자리표를 직접 지정하면(`clef_arg`가 문자열) 추측이 아니므로 표시하지 않는다.
def unknown_clef_suspects(contexts: Dict[int, StaffContext], notes, clef_arg) -> list:
    if not isinstance(clef_arg, dict):
        return []
    unknown = {i for i, c in contexts.items() if not c.clef_found}
    return [n for n in notes if n.staff_index in unknown]



# ------------------------------------------------------------------
# 곡 중간 조바꿈(줄 중간 조표) — KEY_CHANGE.md §4 · §7, DECISIONS §1-43 초안
# ------------------------------------------------------------------
# 증거 = 마디선 바로 뒤 창(간격으로 끝 찾기 `_keysig_scan_end`)의 막대를 같은 시스템 보표 ≥ 2가 같은 조표로 읽음(§4 — 동의 ≥ 2).
# 확인 = 다음 시스템 머리 조표가 그 값 · 지금 시스템 머리 조표는 그 값이 아님(§7). 조표는 바뀐 뒤 시스템마다 머리에 다시 찍히지만
# 마디 첫 임시표(오검출 대부분)는 다음 시스템 머리에 없다. 측정: Verovio 진짜 조바꿈 6/6 · 오검출 PDF 10 → 0 · 보지 않은 8 → 0 · Verovio 24 → 0(중복 1).
# 쪽 마지막 시스템의 증거는 확인할 수 없어 쓰지 않는다(지금처럼 쪽 조표).
KEY_CHANGE_MIN_STAVES = 2


def system_groups(binary: np.ndarray, staves: List[Staff]) -> List[List[int]]:
    """보표를 시스템(함께 연주하는 큰보표)으로 묶는다 — 위아래 이웃 보표를 **위 보표 맨 윗줄부터 아래 보표 맨 아랫줄까지 꿰뚫는 마디선**이
    보표 안쪽(양 끝 1sp 제외)에 하나라도 있으면 같은 시스템. 열 잉크 95% 이상을 꿰뚫음으로 본다.
    양 끝을 빼는 이유: 아오하루 스크린숏은 쪽 전체를 지나는 세로선이 보표 왼끝 · 오른끝에 있어 시스템 사이도 꿰뚫는다.
    측정(`tools/measure_system_groups.py`, 49쪽 이웃 쌍 439): 같은 시스템 250 중 0개 1(Schumann L — 떨어뜨리는 쪽이라 조바꿈을 못 볼 뿐),
    다른 시스템 189 중 ≥ 1은 organ2 4뿐(3단 오르간이라 정답 「두 개씩」이 틀린 쪽)."""
    st = sorted(staves, key=lambda s: s.top)
    if not st:
        return []
    ink = binary > 0

    def ends(s):
        xs = np.where(np.stack([ink[y] for y in s.line_ys]).sum(axis=0) >= 4)[0]
        return (int(xs[0]), int(xs[-1])) if len(xs) else (0, 0)

    groups = [[st[0].index]]
    for a, b in zip(st, st[1:]):
        sp = a.spacing
        x0 = max(ends(a)[0], ends(b)[0]) + int(sp) + 1
        x1 = min(ends(a)[1], ends(b)[1]) - int(sp)
        through = x1 > x0 and (ink[int(a.top):int(b.bottom) + 1, x0:x1].mean(axis=0) >= 0.95).any()
        if through:
            groups[-1].append(b.index)
        else:
            groups.append([b.index])
    return groups


def key_change_regions(result: PreprocessResult, contexts: Dict[int, StaffContext], notes) -> Dict[int, List[Tuple[float, str, Tuple[str, ...]]]]:
    """확인된 줄 중간 조바꿈 → 보표마다 [(그 x부터, 조표 기호, 조표 음이름들)] (x 오름차순). 없으면 빈 dict. 사진 모드 끔."""
    if not notes or not contexts or getattr(result, "photo_correction", None) is not None:
        return {}
    from .accidental_detect import _propagation_barlines
    staves = {s.index: s for s in result.staves}
    groups = [[i for i in g if i in contexts] for g in system_groups(result.binary, result.staves)]
    if len(groups) < 2:
        return {}

    def vote(cs):
        kc, ks, _r = _vote_key_signature(cs)
        return (kc, ks) if kc else (0, "")

    heads = [vote({i: contexts[i] for i in g}) for g in groups]
    ns = remove_staff_lines(result.binary, result.staves)
    H = ns.shape[0]
    pts_of: Dict[int, list] = {}
    for n in notes:
        pts_of.setdefault(n.staff_index, []).append((n.x, n.y))
    changes = []        # (시스템 번호, 증거 x, (kc, ks))
    for gi, g in enumerate(groups[:-1]):
        win: Dict[int, Dict[int, Tuple[StaffContext, float]]] = {}
        for i in g:
            s = staves[i]
            sp = s.spacing
            pts = sorted(pts_of.get(i, []))
            if len(pts) < 2:
                continue
            for bx in _propagation_barlines(result.binary, ns, s, pts):
                if not any(x > bx for x, _y in pts):
                    continue
                top = max(0, int(s.top - sp * 3))
                band = ns[top:min(H, int(s.bottom + sp * 3)), :]
                r0 = max(0, int(s.top - top - sp * 1.5))
                r1 = min(band.shape[0], int(s.bottom - top + sp * 1.5) + 1)
                x0 = int(bx + 0.3 * sp)
                x1 = _keysig_scan_end(band, sp, x0, r0, r1, band.shape[1])
                if x1 - x0 < sp:
                    continue
                bars, holes = _find_bars(band, sp, x0, x1, r0, r1)
                c = StaffContext(clef=contexts[i].clef, clef_found=True, spacing=sp, holes=holes,
                                 bars=tuple((x, (s.grid_bottom - (top + y)) / (sp / 2.0)) for x, y in bars))
                win.setdefault(round(bx / (2 * sp)), {})[i] = (c, bx)
        for cs in win.values():
            if len(cs) < KEY_CHANGE_MIN_STAVES:
                continue
            key = vote({i: c for i, (c, _b) in cs.items()})
            if key[0] and key == heads[gi + 1] and key != heads[gi]:
                changes.append((gi, min(b for _c, b in cs.values()), key))
    if not changes:
        return {}
    changes.sort()
    named = lambda kc, ks: (ks, tuple((SHARP_ORDER if ks == "♯" else FLAT_ORDER)[:kc]))
    out: Dict[int, List[Tuple[float, str, Tuple[str, ...]]]] = {}
    for gj, g in enumerate(groups):
        before = [k for gi, _x, k in changes if gi < gj]
        here = [(-1.0,) + named(*before[-1])] if before else []      # 앞 시스템에서 바뀐 조가 머리부터
        here += [(x,) + named(*k) for gi, x, k in changes if gi == gj]
        if here:
            for i in g:
                out[i] = here
    return out


def key_at(regions: Dict[int, List[Tuple[float, str, Tuple[str, ...]]]], note) -> "Tuple[str, Tuple[str, ...]] | None":
    """`key_change_regions` 결과에서 이 음표에 적용할 (조표 기호, 음이름들). 바뀐 구간 밖이면 None(쪽 조표 그대로)."""
    hit = None
    for x, ks, letters in regions.get(note.staff_index, ()):
        if note.x >= x:
            hit = (ks, letters)
    return hit


def apply_key_changes(result, contexts, notes, accidentals, named, notation, tonic, keep_tonic=False):
    """확인된 조바꿈 구간의 음만 새 조표로 다시 이름 붙인다(`note_namer.to_solfege` 그대로 — 음고 · 임시표는 그대로, 조 문맥만).
    `named`는 `notes`와 같은 순서의 (음표, 표기). 이동도는 구간 조표의 으뜸음으로(사용자가 조를 지정했으면 그 으뜸음 유지).
    (named, keys) — keys[k]는 바뀐 구간 음의 dict(key_symbol, key_count, key_letters, tonic), 아니면 None. JSON · 재생이 같은 조를 쓰게 라벨에 싣는다."""
    keys = [None] * len(notes)
    regions = key_change_regions(result, contexts, notes)
    if not regions:
        return named, keys
    from .note_namer import to_solfege, resolve_tonic
    out = list(named)
    for k, note in enumerate(notes):
        key = key_at(regions, note)
        if key is None:
            continue
        ks, letters = key
        acc = accidentals[k] if accidentals and k < len(accidentals) else ""
        t = tonic if keep_tonic or notation != "solfege-movable" else resolve_tonic(ks, len(letters))
        out[k] = (out[k][0], to_solfege(note, letters, ks, acc, notation, None, t))
        keys[k] = dict(key_symbol=ks, key_count=len(letters), key_letters=list(letters), tonic=t)
    return out, keys
