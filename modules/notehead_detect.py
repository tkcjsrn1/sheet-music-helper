# -*- coding: utf-8 -*-
"""
2단계: 음표 머리(Notehead) 검출 모듈

역할: preprocess.py가 만든 이진화 이미지에서 오선을 제거한 뒤,
      남은 도형 중 음표 머리(타원/원형 blob)의 중심 좌표(x, y)를 찾아낸다.

처리 흐름:
  1) 가로로 긴 모폴로지 오프닝으로 오선 성분만 추출한 뒤 원본에서 빼서 오선 제거
     (음표 머리와 오선이 겹치는 지점에서 생기는 구멍은 이후 closing으로 메움)
  2) 보표 간격(spacing)에 비례한 타원 커널로 모폴로지 클로징 -> 끊긴 음표 머리를 하나의 덩어리로 복원
  3) 보표별로 검색 영역(오선 위아래 레저선 여유 포함)을 잘라 contour 검출
  4) 면적/종횡비/크기(보표 간격 대비)로 필터링해 음표 머리가 아닌 잡음(가사, 셈여림 기호 등) 제거
  5) 내부 채움 비율(fill ratio)로 채워진 음표(4분음표 이하) vs 빈 음표(2분/온음표) 구분
"""

import math
import os
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np
from scipy.ndimage import maximum_filter1d

from .engine_mask_cache import cache_mask
from .preprocess import PreprocessResult, Staff


class NoteheadDetectionError(Exception):
    """음표 머리 검출 과정에서 발생하는 오류"""


# 오선 위/아래로 음표를 찾아볼 여유 (spacing 배수).
# 레저선은 오선 밖으로 1sp 간격이라 N sp면 레저선 N개까지 닿는다.
# BASE는 이웃 보표가 가까울 때 쓰는 기본값이고, LEDGER까지는 이웃이 멀리
# 떨어진 쪽으로만 넓힌다(레저선 4개 위 칸=4.5sp에 놓인 머리의 위쪽 끝이
# 실측 4.94sp라 5.5sp가 필요했다 — 이 곡 최고음 A6가 그래서 누락됐다).
#
# BASE가 3.5면 '머리 자체는 들어오는데 바로 옆 레저선이 잘리는' 구간이 생긴다.
# 빈 음표는 링의 아래(위) 호가 레저선과 붙어 있어 레저선이 잘리면 링이 닫히지
# 않고, 구멍 검출이 통째로 실패한다 (실측: 3페이지 87·89마디 베이스 A4가
# 두 보표 사이 3.47sp 자리에 있어 양쪽 밴드 모두에서 잘려 누락됐다).
# 머리 반높이(0.45sp)에 레저선 두께를 더한 만큼 여유를 둬 3.8로 잡는다.
# 화음 분할 분기에 들어가는 높이(오선 간격 단위).
# **양쪽 끝에서 유도한 값이다. 그 사이는 완전히 비어 있다.**
#
#   아래 — 정상 음표 머리 높이의 봉우리가 1.09~1.21sp에 있고 꼬리가 ~1.30sp에서 끝난다
#          (덩어리 3232개 실측). 사람이 판정한 표본 60개에서 이 구간의 화음은 **0개**였다
#          (1.12~1.15: 단일머리 27·비음표 2·애매 1 / 1.15~1.18: 단일머리 25·비음표 3·애매 2)
#   위   — 실제로 분할되는 덩어리 29개의 최소값이 **1.643sp**다(전수 사람 판정, 비음표 0개)
#
# 1.15~1.50에서는 347개가 분기에 들어가 **실제 분할이 0건**이었다 — 순수한 헛걸음이다.
# 1.40은 봉우리 끝에서 0.10sp, 화음 최소에서 0.24sp 떨어져 있다.
# 문턱을 올려 새로 통과하는 덩어리는 **0개**다(1.15~1.40에서 분기 안 판정에 걸리던 것이 없다).
#
# 예전 값 1.15는 봉우리 한가운데였다 — 문턱 바로 아래 1.09~1.15 구간에만 813개가 몰려
# `sp`가 0.1px 흔들릴 때 152개가 뒤집혔다. 1.40에서는 2개다.
# 근거는 `WORKLOG.md` 2026-08-29 · `docs/TASKS.md` A-4.
CHORD_SPLIT_SP = 1.40

# 3음 덩어리(3도로 쌓인 두 머리 + 2도로 기둥 반대편에 비켜 붙은 한 머리, 음역 4도) — 「가로로 긴 덩어리」에서 살리는 높이 창(DECISIONS §1-48).
# 음악 규칙: 머리 중심 폭 1.5sp + 머리 높이 ~1.0sp = 2.5sp. 다음 모양은 2음(≤ 1.8, §1-33 창) · 2도 + 4도 3음(3.0) · 4음(3.5).
# 실측(제품 경로 거절 기록 49쪽, `tools/measure_wide3.py`): 폭 ≤ 2.65에서 정답 3음 51 높이 2.50~2.63 · 잡음(겹빔 · 트레몰로 · 2음 쌍) 최대 2.28, 2.28~3.2 사이 잡음 0
WIDE_TRIPLE_H_SP = (2.4, 2.8)

BASE_MARGIN_SP = 3.8
LEDGER_MARGIN_SP = 5.5
# 덧줄 사다리 판정: 가로 잉크 연속 ≥ 1.2sp — 머리 폭(실측 봉우리 1.2sp)보다 넓은 가로선. 덧줄은 머리보다 양옆으로 길다
LEDGER_LADDER_RUN_SP = 1.2

# 빈 음표 구멍으로 인정하려면 그 둘레가 이 비율 이상 잉크여야 한다.
# 진짜 링은 벽이 사방을 두르지만, '기둥과 음표 머리 사이의 빈칸'이나 '기둥과
# 8분음표 깃발 사이'처럼 오선 제거가 남긴 1px 잔여 획에 우연히 위아래가 막혀
# 닫힌 틈은 귀퉁이가 비어 비율이 낮다(실측: 진짜 링 0.73~0.90, 유령 0.51~0.58).
RIM_INK_MIN = 0.70

# 세로 closing 이전 잉크 덩어리가 이 높이(spacing 배수) 미만이면 이음줄/타이의 호 조각이다.
# 실측: 악보 7종의 진짜 채워진 머리 1187개는 전부 1.02sp 이상, 타이 호는 0.51sp.
ARC_MIN_HEIGHT_SP = 0.75

# 구멍의 좌우 벽이 '양쪽 다' 이만큼 세로로 길면 링이 아니라 세로줄 사이의 빈틈이다.
# 보표 높이가 4sp이므로 5sp를 넘는다는 것은 보표를 관통하는 선이라는 뜻이다.
HOLE_WALL_MAX_SP = 5.0


# 덧줄 지나는 빈 머리(§1-50 초안) — 구멍 중심이 가린 덩어리 중심에서 이 안(sp). 근거는 사용 자리 주석
LEDGER_HOLLOW_CENTER_SP = 0.15


@dataclass
class Notehead:
    """검출된 음표 머리 하나를 표현"""

    x: int
    y: int
    staff_index: int   # 어느 보표에 속하는 음표인지
    filled: bool = True  # True=채워진 음표(4분음표 이하), False=빈 음표(2분/온음표)
    ring_kept: bool = False  # 링 벽 예외(§1-29)로 남은 꽉 찬 머리 — 같은 높이 옆 중복 판정이 빈 머리와의 쌍을 건드리지 않는다
    wide_triple: bool = False  # 3음 덩어리 분할(§1-48)로 나온 머리 — 라벨은 check(보류 세트에서 홑머리 + 짧은 3겹 빔 조각 덩어리가 같은 창에 들었다)


def _ledger_ladder(no_staff: np.ndarray, staff: Staff, direction: int) -> float:
    """오선 밖으로 1sp 간격마다 덧줄이 이어지는 마지막 줄 + 1sp(px). 덧줄 = 그 행 ±1 안 가로 잉크 연속 ≥ LEDGER_LADDER_RUN_SP."""
    sp = staff.spacing
    H = no_staff.shape[0]
    k = 0
    while True:
        y = int(round((staff.top - (k + 1) * sp) if direction < 0 else (staff.bottom + (k + 1) * sp)))
        if not (0 <= y < H):
            break
        found = False
        for r in no_staff[max(0, y - 1):y + 2, :] > 0:
            d = np.diff(np.concatenate(([0], r.astype(np.int8), [0])))
            st, en = np.where(d == 1)[0], np.where(d == -1)[0]
            if len(st) and (en - st).max() >= LEDGER_LADDER_RUN_SP * sp:
                found = True
                break
        if not found:
            break
        k += 1
    return (k + 1) * sp


def _band_margins(staff: Staff, staves: List[Staff], no_staff: "np.ndarray | None" = None) -> Tuple[float, float]:
    """
    이 보표에서 위/아래로 음표를 찾아볼 거리(px)를 (위, 아래)로 정한다.

    기본은 BASE_MARGIN_SP이고, 이웃 보표의 기본 탐색 범위에 닿지 않는 쪽으로만
    LEDGER_MARGIN_SP까지 넓힌다. 이웃 쪽으로 밀고 들어가면 그쪽 기호를 '밴드
    가장자리에서 잘린' 형태로 주워 유령이 생긴다 — 실측 두 가지:
      - 4분쉼표는 잘리면 세로 길이가 짧아져 쉼표 판정을 빠져나간다(유령 14개)
      - 이웃 보표의 빈 음표 화음은 아래 구멍이 잘려 하나만 보이는 바람에,
        두 구멍을 다 봐야 작동하는 이음매(seam) 제거가 무력화된다(유령 1개)
    그래서 여유를 이웃 보표의 기본 범위(BASE_MARGIN_SP)만큼 띄워 잡는다.
    """
    sp = staff.spacing
    base, ext = sp * BASE_MARGIN_SP, sp * LEDGER_MARGIN_SP
    prev = max((s for s in staves if s.bottom < staff.top),
               key=lambda s: s.bottom, default=None)
    nxt = min((s for s in staves if s.top > staff.bottom),
              key=lambda s: s.top, default=None)

    up = ext if prev is None else min(
        ext, max(base, staff.top - (prev.bottom + prev.spacing * BASE_MARGIN_SP)))
    down = ext if nxt is None else min(
        ext, max(base, (nxt.top - nxt.spacing * BASE_MARGIN_SP) - staff.bottom))
    if no_staff is not None:
        # 덧줄 사다리 끝까지(2026-10-04, 사용자 구현 승인 · DECISIONS §1-19, `MISSING_VEROVIO.md` §5 · §6):
        # 고정 5.5sp 밖의 아주 높은 · 낮은 음(덧줄 5~6개, Clara 폴로네즈)은 검색 띠에서 잘려 Verovio 덧줄 구역 누락 115 중 78이었다.
        # 이웃 보표 기본 범위를 침범하지 않는 위 제한은 그대로 둔다. 머리 검출에서만 — 오선 제거(`remove_staff_lines`)는 예전 범위
        cap_u = float("inf") if prev is None else max(base, staff.top - (prev.bottom + prev.spacing * BASE_MARGIN_SP))
        cap_d = float("inf") if nxt is None else max(base, (nxt.top - nxt.spacing * BASE_MARGIN_SP) - staff.bottom)
        up = max(up, min(_ledger_ladder(no_staff, staff, -1), cap_u))
        down = max(down, min(_ledger_ladder(no_staff, staff, 1), cap_d))
    return up, down


@cache_mask
def remove_staff_lines(binary: np.ndarray, staves: List[Staff]) -> np.ndarray:
    """
    이진화 이미지에서 오선(수평선) 성분만 제거하고 나머지(음표, 기호 등)를 남긴다.

    가로로 긴 구조 요소로 모폴로지 오프닝하는 것만으로는, 음표 머리 잉크가 오선과
    같은 행(row)에서 맞닿아 있으면 그 행 전체가 "오선의 일부"로 오판되어(그 행에서
    잉크가 오선 길이만큼 길게 이어져 있으므로) 음표 머리 쪽 잉크까지 함께 지워지는
    문제가 있다. 특히 빈 음표(2분/온음표)가 오선에 바짝 붙으면 링의 위/아래 호가
    잘려나가 구멍(hole) 검출이 실패, 음표 자체가 통째로 누락된다.

    그렇다고 이 판단을 세로 두께만으로(오선 y좌표 근처의 잉크가 얼마나 길게
    이어지는지만으로) 하면 반대 방향 실패가 난다: 빈 음표 링은 속이 비어 있어서,
    오선과 실제로 안 닿아 있어도 위/아래 호의 접선 부근 세로 두께가 오선 굵기와
    거의 같아 오탐이 매우 잦다(실측: 합성 오선 간격 24px에서도 링과 무관한
    정상 음표까지 지워짐). 오선 간격이 좁은 실사 이미지(예: 10~12px)에서는
    이 오탐이 페이지 전역에서 발생해 빈 음표 다수가 통째로 사라졌다.

    그래서 가로 길이 기준(모폴로지 오프닝)을 '1차 후보' 판정으로 그대로 쓰고
    ("이 화소는 오선/레저선처럼 충분히 길게 이어져 있다"는 신뢰할 수 있는 신호),
    Staff.line_ys(및 그 배수 위치의 레저선 후보) 각각을 중심으로 한 좁은 창
    안에서만 그 후보를 세로 두께 검사로 '구제(rescue)'한다: 순수 선 굵기(그
    창 안 후보 열들의 중앙값)보다 뚜렷이 두꺼운 열은 노트헤드가 선을
    가로지르는 것으로 보아 지우지 않는다.

    (오선 자체가 아니라, 후보로 찍힌 행들을 전역적으로 인접한 것끼리 묶어
    처리하는 방식도 시도했으나, 실사 사진은 살짝 기울어져 있어 같은 오선이라도
    x에 따라 y가 1~2px씩 흔들리고, 그 결과 페이지 전혀 다른 위치의 무관한
    긴 구조물(빔, 이음줄 등)이 오선과 같은 행 대역에 우연히 걸려 하나의
    "행 묶음"으로 잘못 합쳐지는 문제가 있었다. Staff.line_ys처럼 이미 알고
    있는 정확한 좌표를 기준으로 창을 고정하는 방식이 이 문제를 피한다.)

    빈 음표 링이 오선 '위/아래 정중앙'(타원의 접선이 수평이 되는 지점)에서
    닿을 때는 그 접점 자체의 세로 두께가 순수 선 굵기와 거의 같아서, 열별
    두께만으로는 여전히 오선으로 오판된다(실측: 링 중심 열은 두께 2~3px로
    순수 선과 구분 불가). 반면 접점에서 링의 좌/우 가장자리로 살짝만 옮겨가면
    (타원의 접선이 세로에 가까워지는 지점) 두께가 급격히 커진다. 그래서
    열별 두께 배열에 슬라이딩 최댓값 필터를 적용해, 바로 옆 열의 '두껍다'는
    정보가 중앙의 얇은 접점 열까지 퍼지도록 한다 — 순수 오선은 필터를
    적용해도 여전히 전 구간이 얇으므로 영향이 없다.

    이 방식은 오프닝이 애초에 후보로 찍지 않는(=페이지 폭에 비해 훨씬 짧은)
    순수 음표 잉크에는 전혀 손대지 않으므로, 오선/레저선과 무관한 음표가
    오탐으로 지워지는 경우가 원천적으로 없다.
    """
    height, width = binary.shape[:2]
    kernel_len = max(15, width // 30)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    staff_only = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    to_remove = (staff_only > 0) & (binary > 0)
    if not to_remove.any():
        return binary.copy()

    binary_bool = binary > 0

    def _rescue_at(center_y: int, radius: int, bridge: int) -> None:
        y0 = max(0, center_y - radius)
        y1 = min(height, center_y + radius + 1)
        center = center_y - y0
        if not (0 <= center < y1 - y0):
            return
        if not to_remove[y0:y1, :].any():
            return

        band = binary_bool[y0:y1, :]
        ink_at_center = band[center]

        up_len = np.zeros(width, dtype=np.int32)
        cur = ink_at_center.copy()
        for r in range(center - 1, -1, -1):
            cur = cur & band[r]
            up_len += cur

        down_len = np.zeros(width, dtype=np.int32)
        cur = ink_at_center.copy()
        for r in range(center + 1, band.shape[0]):
            cur = cur & band[r]
            down_len += cur

        run_len = np.where(ink_at_center, up_len + down_len + 1, 0)
        thick_cols = run_len[run_len > 0]
        if thick_cols.size == 0:
            return

        # 이 창 안에서 후보로 찍힌 잉크는 대부분 순수 오선/레저선이다(음표
        # 하나만으로는 오프닝 커널 길이만큼 길어질 수 없어 애초에 후보가 되지
        # 않는다). 따라서 중앙값은 노트헤드 두께가 아니라 진짜 선 굵기를
        # 안정적으로 대표한다.
        threshold = float(np.median(thick_cols))
        # 링의 접점(중앙) 열이 얇더라도 바로 옆(가장자리)이 두꺼우면 같은
        # 노트헤드로 보아 함께 구제한다.
        bridged = maximum_filter1d(run_len, size=bridge, mode="constant")
        rescue_cols = bridged > threshold
        if rescue_cols.any():
            to_remove[y0:y1, rescue_cols] = False

    for staff in staves:
        spacing = staff.spacing
        radius = max(4, int(round(spacing * 0.55)))
        up_margin, down_margin = _band_margins(staff, staves)  # 탐색 밴드와 동일 범위
        # 너무 넓게 다리를 놓으면(예: 0.5sp 이상) 노트헤드와 무관한 근처의
        # 다른 얇은 세로 구조물(예: ♭ 기호의 막대와 고리 사이의 진짜 빈 틈)
        # 까지 이어붙여 버린다(실측: sp=20에서 폭 7 이상부터 ♭ 기호의 고리가
        # 막대와 잘못 합쳐져 구멍이 사라짐). 5px는 실사 이미지(spacing~11.5)의
        # 접점 구제와 이 합성 이미지(spacing=20)의 오탐 방지 양쪽을 만족하는
        # 상한이라 절대값으로 고정한다.
        bridge = max(3, min(5, int(round(spacing * 0.4)))) | 1

        for line_y in staff.line_ys:
            _rescue_at(line_y, radius, bridge)

        k = 1
        while k * spacing <= max(up_margin, down_margin):
            if k * spacing <= up_margin:
                _rescue_at(int(round(staff.top - k * spacing)), radius, bridge)
            if k * spacing <= down_margin:
                _rescue_at(int(round(staff.bottom + k * spacing)), radius, bridge)
            k += 1

    result = binary.copy()
    result[to_remove] = 0
    return result


def _has_ledger_line(no_staff: np.ndarray, staff: Staff, cx: float, cy: float) -> bool:
    """음표 바로 옆(오선 쪽)에 레저선처럼 긴 가로 잉크가 있는지."""
    sp = staff.spacing
    H, W = no_staff.shape[:2]
    need = sp * 1.5           # 레저선 실측 폭 ~2sp, 글자 획은 이보다 짧다
    half = int(round(sp * 1.2))
    xa, xb = max(0, int(cx) - half), min(W, int(cx) + half + 1)
    if xb <= xa:
        return False
    if cy < staff.top:
        r0, r1 = int(cy - sp * 0.2), int(cy + sp * 0.8)
    else:
        r0, r1 = int(cy - sp * 0.8), int(cy + sp * 0.2)
    r0, r1 = max(0, r0), min(H, r1 + 1)
    for r in range(r0, r1):
        run = best = 0
        for v in (no_staff[r, xa:xb] > 0):
            run = run + 1 if v else 0
            if run > best:
                best = run
        if best >= need:
            return True
    return False


def _has_stem(no_staff: np.ndarray, staff: Staff, cx: float, cy: float) -> bool:
    """
    후보 근처에 기둥(길게 이어진 세로 잉크)이 있는지.

    글자 획은 아무리 길어야 2.1sp인데(실측: 쇼팽 나타냄말 0.72~2.10sp)
    음표 기둥은 3.5sp를 넘는다(실측: 바흐 덧줄 음표 3.52~4.14sp).
    덧줄 길이로는 안 갈린다 — 바흐 덧줄 1.16sp < 쇼팽 글자 가로획 1.33sp라
    순서가 뒤집힌다. 기둥이 유일하게 깨끗한 지표다.
    """
    sp = staff.spacing
    H, W = no_staff.shape[:2]
    xa, xb = max(0, int(cx - sp * 0.9)), min(W, int(cx + sp * 0.9) + 1)
    y0, y1 = max(0, int(cy - sp * 4)), min(H, int(cy + sp * 4))
    if xb <= xa or y1 <= y0:
        return False
    need = sp * 2.5
    sub = no_staff[y0:y1, xa:xb] > 0
    r = int(cy) - y0
    if not (0 <= r < sub.shape[0]):
        return False
    # 반드시 후보 자신의 행을 지나는 연속 잉크여야 한다. 창 안 아무 곳의 긴
    # 세로줄이나 인정하면, 오선 안 음표의 기둥이 창에 걸려 바로 위 글자까지
    # 살려버린다(실측: 쇼팽 나타냄말 유령 8개가 그렇게 살아남았다).
    for c in range(sub.shape[1]):
        col = sub[:, c]
        if not col[r]:
            continue
        up = dn = r
        while up - 1 >= 0 and col[up - 1]:
            up -= 1
        while dn + 1 < len(col) and col[dn + 1]:
            dn += 1
        if (dn - up + 1) >= need:
            return True
    return False


def _detect_noteheads_in_band(
    no_staff_img: np.ndarray,
    staff: Staff,
    img_height: int,
    header_end: int = 0,
    margins: "Tuple[float, float] | None" = None,
    reject_log: "List[dict] | None" = None,
    ring_wall_keep: bool = True,
    second_pair_split: bool = True,
) -> List[Notehead]:
    """
    한 보표에 대해, 레저선 여유를 포함한 검색 영역에서 음표 머리를 검출한다.

    채워진 음표: 오선 제거로 생긴 세로 구멍을 메운 뒤(세로 closing),
      타원 opening으로 얇은 기둥(stem)/빔(beam)을 지우고 남는 덩어리를 찾는다.
      (기존 closing 방식은 머리가 기둥·빔과 한 덩어리로 붙어 크기 필터에서
       통째로 탈락했기 때문에, 빔으로 묶인 8분음표를 거의 검출하지 못했다)
    빈 음표(2분/온음표): 링 안쪽의 '구멍(hole)'을 찾는다.

    Args:
        header_end: 이 x좌표보다 왼쪽은 헤더(음자리표/조표/박자표) 영역으로 보고 무시
        margins: 오선 위/아래로 넓힐 거리(px). 없으면 _band_margins의 기본값
        ring_wall_keep: 링 벽 예외(§1-29)를 쓰는가 — 사진 모드는 끈다
    """
    spacing = staff.spacing
    up_margin, down_margin = margins if margins else (
        spacing * BASE_MARGIN_SP, spacing * BASE_MARGIN_SP)
    top = max(0, staff.top - int(round(up_margin)))
    bottom = min(img_height, staff.bottom + int(round(down_margin)))
    band = no_staff_img[top:bottom, :]

    # 오선 제거가 남긴 가로 방향 구멍(음표를 가로지르던 선 자리)을 세로로 메움
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(spacing * 0.4)) | 1))
    patched = cv2.morphologyEx(band, cv2.MORPH_CLOSE, vk)

    # ---- 채워진 음표: 타원 opening으로 기둥/빔 제거 후 연결 성분 분석 ----
    kw = max(3, int(spacing * 0.65)) | 1
    kh = max(3, int(spacing * 0.5)) | 1
    ek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kw, kh))
    opened = cv2.morphologyEx(patched, cv2.MORPH_OPEN, ek)

    def _refine_y(x: float, y_band: float,
                  y_lo: "int | None" = None, y_hi: "int | None" = None) -> float:
        """
        음표 머리 중심 y를 정밀 보정한다.

        blob 무게중심은 기둥(stem)·이음줄 등 부속 잉크에 끌려 반 칸 경계에서
        오판(한 음 어긋남)을 일으킬 수 있다. 머리 부분 행은 잉크 폭이 넓고(~1sp)
        기둥 행은 얇다(~2px)는 점을 이용해, 머리 주변 창에서 '충분히 두꺼운 행'
        구간의 중점을 중심으로 삼는다. (빈 음표 링도 위/아래 호가 두꺼워 동일하게 동작)
        """
        x0, x1 = int(x - spacing * 0.55), int(x + spacing * 0.55) + 1
        y0, y1 = int(y_band - spacing * 0.8), int(y_band + spacing * 0.8) + 1
        # 창을 이 blob 자신의 세로 범위로 제한한다. patched는 세로 closing을 거쳐
        # 있어서, 바로 위/아래 레저선이 음표와 3px 틈만 두고 있으면 하나로 이어져
        # 무게중심이 그쪽으로 끌려간다 (실측: 2페이지 40마디 A3가 379 -> 376으로
        # 밀려 "라"가 "시"로 나왔다). opening 후 blob의 bbox는 레저선이 이미
        # 지워진 '음표만'이라 이 범위로 자르면 오염이 사라진다.
        if y_lo is not None:
            y0 = max(y0, y_lo)
        if y_hi is not None:
            y1 = min(y1, y_hi + 1)
        if y1 <= y0:
            return y_band
        win = patched[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        # closing이 서로 다른 원본 성분을 잇는 경우에만 중심 잉크를 분리한다.
        # 머리 조각이 bbox 안에 있거나 원본 성분의 세로 범위가 겹치면 그대로 둔다.
        blob = _labels[y_lo:y_hi + 1, stats[i, 0]:stats[i, 0] + stats[i, 2]] == i
        source_ids = np.unique(band_lab[y_lo:y_hi + 1, stats[i, 0]:stats[i, 0] + stats[i, 2]][blob])
        source_ids = source_ids[source_ids > 0]
        if len(source_ids) > 1:
            bx, by, bw, bh = (int(v) for v in stats[i, :4])
            px, py = ek.shape[1], vk.shape[0] + ek.shape[0]
            xa, xb = max(0, bx - px), min(band.shape[1], bx + bw + px)
            ya, yb = max(0, by - py), min(band.shape[0], by + bh + py)
            labels = band_lab[ya:yb, xa:xb]
            supported = []
            for component in source_ids:
                lo = int(band_stats[component, 1])
                hi = lo + int(band_stats[component, 3])
                others = [band_stats[j] for j in source_ids if j != component]
                if any(not (int(s[1]) + int(s[3]) <= lo or int(s[1]) >= hi)
                       or (by <= int(s[1]) and int(s[1]) + int(s[3]) <= by + bh)
                       for s in others):
                    continue
                isolated = cv2.morphologyEx(np.uint8(labels == component) * 255,
                                            cv2.MORPH_CLOSE, vk)
                seeds = cv2.erode(isolated, ek)
                if np.any((seeds[by-ya:by-ya+bh, bx-xa:bx-xa+bw] > 0) & blob):
                    supported.append(isolated)
            if len(supported) == 1:
                win = supported[0][max(0, y0)-ya:max(0, y1)-ya,
                                   max(0, x0)-xa:max(0, x1)-xa]
        if win.size == 0:
            return y_band
        rows = (win > 0).sum(axis=1)
        if rows.max() == 0:
            return y_band
        dense = np.where(rows > rows.max() * 0.55)[0]
        if len(dense) == 0:
            return y_band
        return max(0, y0) + (dense[0] + dense[-1]) / 2.0

    band_h, band_w = patched.shape


    def _vertical_ink_run(cx: float, cy: float) -> float:
        """
        blob 중심을 지나는 세로 잉크의 연속 길이를 spacing 단위로 잰다.

        음표 머리는 링이든 채워졌든 높이가 1sp 남짓이지만, 4분쉼표는 2.5sp 안팎의
        세로로 긴 글리프다. 얇은 기둥(stem)이 길이를 부풀리지 않도록 창 폭의
        1/3 이상이 잉크인 행만 연속으로 인정한다.
        """
        xa = max(0, int(cx - spacing * 0.45))
        xb = min(band_w, int(cx + spacing * 0.45) + 1)
        r = int(round(cy))
        if xb <= xa or not (0 <= r < band_h):
            return 0.0
        need = max(1, (xb - xa) // 3)
        col = (patched[:, xa:xb] > 0).sum(axis=1) >= need
        if not col[r]:
            return 0.0
        up = 0
        while r - up - 1 >= 0 and col[r - up - 1]:
            up += 1
        dn = 0
        while r + dn + 1 < band_h and col[r + dn + 1]:
            dn += 1
        return (up + dn + 1) / spacing

    def _stem_beyond(cx: float, y0: int, y1: int) -> Tuple[float, float]:
        """
        후보 bbox의 위/아래로 기둥(stem)이 얼마나 더 뻗어 있는지 sp 단위로 잰다.

        음표 머리는 기둥의 '끝'에 달리므로 한쪽으로만 뻗는다. 반면 8분음표 꼬리
        (깃발)는 기둥 중간에 붙어 있어 위·아래 양쪽에 기둥이 남는다.
        opening 전 이미지(band)로 재야 기둥이 살아 있다.
        """
        xa = max(0, int(cx - spacing * 0.45))
        xb = min(band_w, int(cx + spacing * 0.45) + 1)
        if xb <= xa:
            return 0.0, 0.0
        col = (band[:, xa:xb] > 0).any(axis=1)
        up = 0
        while y0 - up - 1 >= 0 and col[y0 - up - 1]:
            up += 1
        dn = 0
        while y1 + dn + 1 < band_h and col[y1 + dn + 1]:
            dn += 1
        return up / spacing, dn / spacing

    def _has_ledger_support(cx: float, cy_abs: float) -> bool:
        """
        기본 여유 밖(확장 구역)의 후보가 진짜 레저선 음표인지 확인한다.

        오선에서 3.5sp 넘게 떨어진 음표는 자기 바로 밑(오선 쪽)에 레저선을 달고
        있다. 반면 제목·작곡가 표기 같은 글자에는 레저선이 없다
        (실측: 이 범위를 그냥 넓혔더니 "Piano arr : ..." 글자에서 유령 14개 발생).

        찾는 범위를 '후보 바로 옆'으로 좁히는 게 핵심이다. 오선까지 훑으면
        아래쪽에 있는 다른 음표의 레저선을 자기 근거로 착각한다
        (실측: 글자 유령도 1.7~2.0sp 런을 찾아냈는데 전부 1~2번 레저선,
         즉 1마디 높은음들 것이었다. 바로 밑만 보면 글자는 최대 1.07sp,
         진짜 음표는 2.04sp로 깨끗이 갈린다).
        """
        need = spacing * 1.5   # 레저선 실측 폭 ~2sp, 글자 획은 이보다 짧다
        half = int(round(spacing * 1.2))
        xa, xb = max(0, int(cx) - half), min(band_w, int(cx) + half + 1)
        if xb <= xa:
            return False
        # 음표가 레저선 위에 얹혀 있으면 같은 행, 칸에 있으면 반 칸 아래에 있다
        if cy_abs < staff.top:
            r0 = int(cy_abs - top - spacing * 0.2)
            r1 = int(cy_abs - top + spacing * 0.8)
        else:
            r0 = int(cy_abs - top - spacing * 0.8)
            r1 = int(cy_abs - top + spacing * 0.2)
        r0, r1 = max(0, r0), min(band_h, r1 + 1)
        for r in range(r0, r1):
            row = band[r, xa:xb] > 0
            run = best = 0
            for v in row:
                run = run + 1 if v else 0
                if run > best:
                    best = run
            if best >= need:
                return True
        return False

    base_px = spacing * BASE_MARGIN_SP
    _extended = up_margin > base_px or down_margin > base_px

    def _keep_candidate(cx: float, cy_abs: float) -> bool:
        """
        확장 구역 후보는 레저선이 받쳐줄 때만 인정한다.

        검사 범위를 오선 밖 전체로 넓히면 안 된다. 기보법상으로는 '오선 밖 음표는
        레저선을 단다'가 맞지만, 이 파이프라인은 보표 사이 음표를 이웃 밴드에서도
        일부러 잡아 나중에 정리하는 구조라 그 후보들이 먼저 죽는다. 게다가 손실이
        구멍(빈 음표) 경로를 통해 연쇄로 번진다
        (실측: 문턱 0.75sp -> 쇼팽 Em 396->302, 1.4sp -> 313. 정작 _keep_candidate가
         직접 버린 건 8개뿐이었고 나머지는 전부 연쇄 손실이었다).
        """
        if not _extended:
            return True
        if staff.top - cy_abs <= base_px and cy_abs - staff.bottom <= base_px:
            return True
        return _has_ledger_support(cx, cy_abs)

    def _log_drop(before: list, after: list, reason: str) -> None:
        """
        누락 점검용: 모양·쉼표 판정을 이미 통과한 후보가 뒤 단계에서 지워지면
        기록한다. 여기서 잡히는 것들은 '음표로 보이는데 라벨이 안 붙은' 자리라
        진짜 누락일 가능성이 높다 (쉼표/글자는 앞 단계에서 걸러져 여기 안 온다).
        """
        if reject_log is None:
            return
        kept = {(round(it[0], 1), round(it[1], 1)) for it in after}
        for it in before:
            if (round(it[0], 1), round(it[1], 1)) not in kept:
                reject_log.append(dict(staff=staff.index, x=float(it[0]),
                                       y=float(it[1]), filled=bool(it[2]),
                                       reason=reason))

    # 세로 closing 이전(band)의 연결 성분. 후보가 '원래 얼마나 두꺼웠는지'를 재는 데 쓴다.
    _bn, band_lab, band_stats, _bc = cv2.connectedComponentsWithStats(band, connectivity=8)

    def _band_component_height(cx: float, cy: float) -> float:
        """후보 자리의 원본(closing 이전) 잉크 덩어리 높이를 sp 단위로 잰다.

        이음줄·타이의 호 조각은 얇고 납작한데(실측 0.51sp), 세로 closing과 타원
        opening을 거치면 음표 머리와 비슷한 크기로 부풀어 모양 필터를 통과한다
        (실측: 3페이지 93마디 트레블의 타이 호가 "솔" 유령이 됐다).
        진짜 채워진 머리는 기둥이 붙어 있어 덩어리가 훨씬 높다 —
        악보 7종 전체에서 최솟값 1.02sp.
        0을 돌려주는 경우(성분을 못 찾음)는 판정하지 않는다.
        """
        y, x = int(round(cy)), int(round(cx))
        y0, y1 = max(0, y - 3), min(band.shape[0], y + 4)
        x0, x1 = max(0, x - 3), min(band.shape[1], x + 4)
        ids = band_lab[y0:y1, x0:x1]
        ids = ids[ids > 0]
        if ids.size == 0:
            return 0.0
        return float(band_stats[np.bincount(ids).argmax()][3]) / spacing

    raw: List[tuple] = []  # (x, y, filled, y0_abs, y1_abs)
    triple_xy = set()      # 3음 덩어리 분할(§1-48)로 나온 머리 자리
    n, _labels, stats, cents = cv2.connectedComponentsWithStats(opened)
    expected_area = math.pi * (spacing * 0.6) * (spacing * 0.42)  # 머리 타원 기대 면적
    # 8분음표 꼬리(깃발) 판별용. 깃발은 좁고, 기둥 '중간'에 붙어 위아래 양쪽에
    # 기둥이 남는다. 다만 빈 음표 링이 깎여 남은 조각도 좁고 양쪽 신호가 비슷해
    # (실측: 1페이지 x=1049 링 조각 0.35/3.04 vs 2페이지 깃발 1.11/0.43),
    # '같은 기둥에 제대로 된 머리가 따로 있는가'를 마지막 조건으로 둔다.
    solid_heads: List[tuple] = []
    hook_suspects: List[tuple] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if cents[i][0] < header_end:
            continue
        if area < expected_area * 0.5 or w < spacing * 0.7:
            continue
        wide_pair = False
        wide_triple = False
        if w > spacing * 2.2:
            # 가로로 긴 덩어리(빔 잔여물 등)는 버린다. 단 **2도로 나란한 머리 쌍**(기둥 양옆으로 반 칸 어긋나 붙은 두 머리)은 남겨
            # 아래 화음 분할로 보낸다 — 「각자 x」(2026-10-13 야간 · DECISIONS §1-33 · 병합 전 사용자 승인 대상, `docs/CHORD_MISSING.md`).
            # 창: 폭 2.2~2.65sp · 높이 1.45~1.8sp(머리 2개 덩어리 5~95% 폭 2.26~2.57 · 높이 1.50~1.68, NIGHT_CAUSES ⑤),
            # 위 · 아래 4분의 1 좌우 중심 차 ≥ 0.68sp(머리 2개 5% 0.84 · 머리 없는 같은 크기 덩어리 최대 0.54의 기하평균 — 바흐 BWV 846 짧은 겹빔 조각 41이 여기 걸린다)
            if second_pair_split and w <= spacing * 2.65 and spacing * 1.45 <= h <= spacing * 1.8:
                _sb = patched[y:y + h, x:x + w] > 0
                _q = max(1, h // 4)
                _xs = np.arange(w)

                def _xc(r0, r1):
                    col = _sb[r0:r1].sum(axis=0)
                    return float((_xs * col).sum() / col.sum()) if col.sum() else w / 2.0
                wide_pair = abs(_xc(0, _q) - _xc(h - _q, h)) >= spacing * 0.68
            elif second_pair_split and w <= spacing * 2.65 and spacing * WIDE_TRIPLE_H_SP[0] <= h <= spacing * WIDE_TRIPLE_H_SP[1]:
                wide_pair = wide_triple = True   # 3음 덩어리 — 아래 분할에서 머리 셋으로
            if not wide_pair:
                continue
        if h < spacing * 0.68:
            # 세로로 얇은 조각: 이음줄/타이 호나 빔(beam)의 잔여물.
            # 실측상 진짜 머리는 h >= 0.78sp, 이런 조각들은 h <= 0.61sp로 깨끗이 갈린다.
            continue
        _bh = _band_component_height(float(cents[i][0]), float(cents[i][1]))
        if 0.0 < _bh < ARC_MIN_HEIGHT_SP:
            continue  # 이음줄/타이 호 조각 (closing 전 원본에서 너무 얇다)
        if w > h * 2.1:
            continue  # 납작하고 넓은 조각(이음줄 호) — 머리는 종횡비 ~1.6 이하
        if (
            w < spacing * 1.12
            and w < h * 1.15
            and _vertical_ink_run(float(cents[i][0]), float(cents[i][1])) >= 2.0
        ):
            # 4분쉼표 제거.
            # 채워진 머리는 폰트상 폭이 거의 고정된(~1.2sp 이상) '가로로 긴' 타원이라
            # 쉼표 조각과 폭·종횡비로 갈린다(실측: 쉼표 조각 폭 0.78~1.07sp·종횡비
            # 0.67~1.12, 진짜 머리는 폭 1.19sp 이상). 다만 빈 음표(2분/온음표) 링이
            # 타원 opening에 깎여 남은 좌우 조각도 똑같이 좁고 납작하다 — 이 악보처럼
            # 링 안쪽 구멍이 세로 closing에 메워지면 그 조각이 유일한 검출 경로라
            # 함께 버리면 온음표가 통째로 사라진다.
            # 그래서 '세로로 긴 글리프의 일부인가'를 마지막 조건으로 둔다:
            # 쉼표는 2.5sp 안팎으로 길고(실측 2.35~2.87sp), 링 조각은 1sp 남짓이다
            # (실측 1.04~1.74sp).
            continue

        box = (patched[y:y + h, x:x + w] > 0)
        cw, chh = max(1, int(w * 0.25)), max(1, int(h * 0.25))
        corner_fill = float(np.mean([
            box[:chh, :cw].mean(), box[:chh, -cw:].mean(),
            box[-chh:, :cw].mean(), box[-chh:, -cw:].mean(),
        ]))
        if (box.sum() / max(1, w * h) >= 0.95
                and corner_fill >= 0.90
                and w >= h * 1.6):
            # 온쉼표/2분쉼표 제거: 오선에 얹히거나 매달린 '완전히 채워진 가로 직사각형'.
            # 음표 머리는 기울어진 타원이라 bbox 모서리가 비어 있다
            # (실측: 쉼표는 채움률 1.00·모서리 1.00·종횡비 1.9~2.0,
            #  진짜 머리는 채움률 최대 0.97·모서리 최대 0.92이고 이 종횡비대에서는
            #  채움률이 0.81을 넘지 않는다).
            continue
        if h > spacing * CHORD_SPLIT_SP:
            # 머리 하나 높이(~0.9sp)를 넘는 덩어리: 2도~3도 간격 화음(기둥 좌우로
            # 어긋나 붙은 머리 여러 개)인지, 4분쉼표(대각 지그재그)인지 판별한다.
            #
            # 폭이 아니라 '행별 잉크 밀도(그 행의 잉크 픽셀 수 / 전체 폭)'로 분할한다.
            # 노트헤드가 있는 행은 폭 대부분이 채워져 밀도가 높고(2도 화음처럼 폭이
            # 좁아도 마찬가지), 쉼표의 대각선 획은 bbox 폭에 비해 얇아 밀도가
            # 낮게 유지된다 — 이전에는 폭>=1.5sp를 요구해 2도 화음(폭~1.3sp)이
            # 이 분기를 타지 못하고 단일 음표로 오인되는 문제가 있었다.
            sub = (patched[y:y + h, x:x + w] > 0)
            xs_w = np.arange(w)

            def _xcentroid(r0: int, r1: int) -> float:
                col = sub[r0:r1].sum(axis=0)
                return float((xs_w * col).sum() / col.sum()) if col.sum() else w / 2.0

            rows = sub.sum(axis=1)
            density = rows / max(1, w)
            bands = []
            r = 0
            while r < h:
                if density[r] <= 0.55:
                    r += 1
                    continue
                r2 = r
                while r2 < h and density[r2] > 0.55:
                    r2 += 1
                if (r2 - r) >= spacing * 0.3:
                    bands.append((r, r2))
                r = r2

            # 화음(2도~3도 간격)은 표준 기보법상 기둥 좌우로 노트헤드가 어긋나
            # 배치되므로 좌우 중심(x-centroid)이 실제로 벌어져 있다. 반면 레저선에
            # 걸린 2분/온음표 링이 opening 과정에서 위/아래 호로 쪼개져 생기는
            # '유령 밴드'는 같은 링이므로 좌우 중심이 거의 일치한다(실측 spread<0.04sp,
            # 진짜 2도 화음은 >=0.15sp). 이 오프셋으로 화음과 링 잔여물을 구분한다.
            split_points = None
            preferred_single_cy = None
            if len(bands) >= 2:
                xcents = [_xcentroid(r, r2) for r, r2 in bands]
                if max(xcents) - min(xcents) >= spacing * 0.15:
                    split_points = [y + (r + r2 - 1) / 2.0 for r, r2 in bands]
                else:
                    # 화음이 아니라 링 잔여물로 판정된 경우: 두 밴드 중 더 두꺼운
                    # (진짜 노트헤드에 더 가까운) 쪽의 중심을 단일 음표 위치로 쓴다.
                    # 전체 블록에 대한 _refine_y는 얇은 잔여 밴드 쪽으로 무게중심이
                    # 끌려가 반 칸 오판을 일으키기 때문에 여기서는 쓰지 않는다.
                    r, r2 = max(bands, key=lambda b: b[1] - b[0])
                    preferred_single_cy = y + (r + r2 - 1) / 2.0

            if (
                split_points is None
                and preferred_single_cy is None
                and h >= spacing * 1.5
                and area >= expected_area * 1.7
            ):
                # 2도 간격 화음처럼 두 머리가 거의 완전히 겹쳐 붙으면 밀도 경계가
                # 전혀 생기지 않아(또는 위 좌우 중심 검증에서 탈락해) 위에서 분할되지
                # 않는다 (검증: 실측 h=1.91sp, 밀도가 전 구간 0.67 이상으로 골이 없음).
                # 위/아래 4분의 1 지점의 좌우 중심이 벌어져 있을 때만(진짜 화음일 때만)
                # 기대 머리 반높이(0.42sp) 기준으로 위/아래 두 음으로 분할한다.
                # 3도 화음은 두 머리가 기둥 같은 쪽에 나란히 붙으므로 좌우 중심이
                # 어긋나지 않는다(2도만 어긋난다). 그래서 x중심 검사만으로는
                # 3도 화음이 통째로 한 음으로 병합된다 — 실측: 2페이지 55마디
                # 트레블 E5+C#5가 중간값인 D5 "레" 한 개로 나왔다.
                # 대신 '머리 하나로는 나올 수 없는 높이인가'로 받는다.
                # 단일 머리는 0.9sp, 링은 1.2sp 남짓이라 1.75sp면 두 개뿐이다.
                q = max(1, h // 4)
                quarter_spread = abs(_xcentroid(0, q) - _xcentroid(h - q, h))
                if (quarter_spread >= spacing * 0.15
                        or (h >= spacing * 1.75 and w <= spacing * 1.6)):
                    half_head = spacing * 0.42
                    cy_top, cy_bot = y + half_head, y + h - half_head
                    if cy_bot - cy_top >= spacing * 0.4:
                        split_points = [cy_top, cy_bot]

            mid_x = {}
            if wide_triple:
                # 위 · 아래 끝 머리(반높이 0.42sp 안쪽) + 가운데 머리 하나. 가운데는 끝에서 2도(0.5sp) 떨어져 기둥 반대편 끝 머리와 같은 x(3도 쌍)에 있다 —
                # 위 끝 0.5sp 아래(아래 끝 머리 x)와 아래 끝 0.5sp 위(위 끝 머리 x) 중 잉크가 많은 쪽
                half_head = spacing * 0.42
                cy_top, cy_bot = y + half_head, y + h - half_head

                def _row_x(cy):
                    return _xcentroid(max(0, int(cy - y - spacing * 0.3)), min(h, int(cy - y + spacing * 0.3) + 1))

                def _ink(cx, cy):
                    r, c = max(1, int(spacing * 0.25)), int(round(cx))
                    yy = int(round(cy - y))
                    return float(sub[max(0, yy - r):yy + r + 1, max(0, c - r):c + r + 1].mean())
                xt, xb = _row_x(cy_top), _row_x(cy_bot)
                if _ink(xb, cy_top + spacing * 0.5) >= _ink(xt, cy_bot - spacing * 0.5):
                    cy_mid, mid_x[1] = cy_top + spacing * 0.5, x + xb
                else:
                    cy_mid, mid_x[1] = cy_bot - spacing * 0.5, x + xt
                split_points = [cy_top, cy_mid, cy_bot]
            if split_points is not None:
                for k, cy in enumerate(split_points):
                    cx = float(cents[i][0])
                    if wide_pair:
                        # 「각자 x」: 나란한 쌍은 덩어리 x 중심 하나에 두 머리를 두면 둘 다 0.6sp 넘게 비껴 이웃 라벨 · 빈 머리 구멍과 엉킨다
                        # (측정 ⑤의 오삭제 10 경로). 그 높이 ±0.3sp 행의 좌우 중심을 각 머리 x로 쓴다
                        r0 = max(0, int(cy - y - spacing * 0.3))
                        r1 = min(h, int(cy - y + spacing * 0.3) + 1)
                        cx = x + _xcentroid(r0, r1)
                        cx = mid_x.get(k, cx)
                    raw.append((cx, cy + top, True, y + top, y + h + top))
                    if wide_triple:
                        triple_xy.add((int(round(cx)), int(round(cy + top))))
                continue

            if preferred_single_cy is not None:
                # 링 잔여물로 판정됐다는 건 '음표 1개'라는 뜻이지 '음표 없음'이
                # 아니다. 예전 코드는 여기서 그냥 continue 해서 음표를 통째로
                # 버렸다(실측: 1페이지 마지막 마디 트레블 마지막 음표가 이렇게
                # 사라졌다. 빈 음표는 구멍 경로가 받쳐주지만 채워진 음표는 그대로 누락).
                raw.append((float(cents[i][0]), preferred_single_cy + top, True,
                            y + top, y + h + top))
                continue

            half = h // 2
            xs = np.arange(w)
            top_ink = sub[:half].sum(axis=0)
            bot_ink = sub[half:].sum(axis=0)
            if top_ink.sum() and bot_ink.sum():
                tc = float((xs * top_ink).sum() / top_ink.sum())
                bc = float((xs * bot_ink).sum() / bot_ink.sum())
                if abs(tc - bc) > spacing * 0.32:
                    continue  # 대각 형태 -> 쉼표
        cy = _refine_y(float(cents[i][0]), float(cents[i][1]), y, y + h - 1)
        if w >= spacing * 1.15:
            solid_heads.append((float(cents[i][0]), cy + top))
        elif w < spacing * 1.12:
            up, dn = _stem_beyond(float(cents[i][0]), y, y + h - 1)
            if up >= 0.30 and dn >= 0.30:
                hook_suspects.append((float(cents[i][0]), cy + top))
        raw.append((float(cents[i][0]), cy + top, True, y + top, y + h + top))

    # 확장 구역의 근거 없는 후보(제목·작곡가 글자 등)는 여기서 미리 걷어낸다.
    # 뒤의 blocker/artifact 판정이 raw를 훑기 때문에, 늦게 지우면 글자 blob이
    # 진짜 음표의 구멍을 가리거나 링 조각으로 오인되어 멀쩡한 음표가 사라진다
    # (실측: 늦게 지웠더니 1마디 위 C6가 통째로 없어졌다).
    # 이 단계는 '레저선이 없으면 음표가 아니다'라는 의도적 분류라 점검 목록에
    # 올리지 않는다 (제목·작곡가 글자가 매번 8곳씩 잡혀 목록이 묻힌다).
    raw = [it for it in raw if _keep_candidate(it[0], it[1])]

    # 같은 기둥(x가 거의 같음)에 제대로 된 머리가 1.5~4sp 떨어져 있으면,
    # 그 좁은 덩어리는 머리가 아니라 그 음표의 8분음표 꼬리다.
    if hook_suspects and solid_heads:
        hooks = {
            (hx, hy) for hx, hy in hook_suspects
            if any(abs(sx - hx) < spacing * 0.6 and spacing * 1.5 <= abs(sy - hy) <= spacing * 4.0
                   for sx, sy in solid_heads)
        }
        if hooks:
            _before = list(raw)
            raw = [it for it in raw if (it[0], it[1]) not in hooks]
            _log_drop(_before, raw, "8분음표 꼬리(깃발)로 판정되어 제거")

    # ---- 빈 음표(2분/온음표): 구멍(hole) 기반 검출 ----
    def _rim_ink_ratio(mask: np.ndarray, ya: int, xa: int,
                       ref: np.ndarray) -> float:
        """
        구멍 모양 mask의 둘레가 실제로 잉크로 감싸여 있는 비율.

        진짜 빈 음표라면 링 벽이 사방을 두르므로 둘레의 대부분이 잉크다. 반면
        '기둥과 음표 머리 사이의 빈칸'처럼 우연히 닫힌 틈은 네 귀퉁이가 비어 있어
        비율이 뚜렷이 낮다(실측: 진짜 링 0.73~0.90, 3페이지 유령 0.51).
        """
        pad = max(2, int(round(spacing * 0.45)))
        grown = cv2.dilate(mask, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (pad * 2 + 1, pad * 2 + 1)))
        rim = (grown > 0) & (mask == 0)
        if not rim.any():
            return 0.0
        h_, w_ = mask.shape
        return float((ref[ya:ya + h_, xa:xa + w_][rim] > 0).mean())

    def _wall_span(src: np.ndarray, hx: int, hy: int, hw: int, hh: int) -> float:
        """구멍 좌/우 벽이 세로로 얼마나 길게 이어지는지, 짧은 쪽 값(sp).

        빈 음표 링의 벽은 링 높이(~1sp)에서 끝난다. 기둥이 붙어 한쪽이 길어질 수는
        있어도 양쪽이 동시에 길 수는 없다. 반면 겹세로줄(마지막 마디의 두 줄)
        사이 빈틈은 좌우가 모두 보표를 관통하는 세로줄이라 양쪽 다 아주 길다
        (실측: 3페이지 마지막 마디 유령 3개가 7.8~7.9sp, 악보 7종의 진짜 링은
         최대 4.1sp).
        """
        rows, cols = src.shape
        y = min(max(0, hy + hh // 2), rows - 1)

        def run(x: int) -> int:
            if not (0 <= x < cols) or not src[y, x]:
                return 0
            up = down = 0
            while y - up - 1 >= 0 and src[y - up - 1, x]:
                up += 1
            while y + down + 1 < rows and src[y + down + 1, x]:
                down += 1
            return up + down + 1

        left = max(run(hx - 1), run(hx - 2))
        right = max(run(hx + hw), run(hx + hw + 1))
        return min(left, right) / spacing

    def _hole_rects(src: np.ndarray) -> List[tuple]:
        """
        src에서 빈 음표 구멍 후보의 bbox (x0, y0, w, h)를 밴드 좌표로 모은다.

        여기서는 크기 조건을 느슨하게만 건다. 오선/덧줄이 링 안쪽을 가로지르면
        구멍이 위아래로 쪼개지는데, 최종 크기 판정을 여기서 해버리면 조각이 먼저
        버려져 다시 합칠 기회가 사라진다 (실측: 4마디 베이스 E4의 아래 조각이
        0.52x0.43sp라 탈락하고 위 조각만 남아 중심이 3px 밀려 F4로 오판됐다).
        진짜 크기 판정은 _merge_split_holes로 합친 뒤에 한다.
        """
        # 커널은 반드시 작게(3x3) 유지할 것. 세로로 큰 closing을 걸면 오선에
        # 바짝 붙은 빈 음표의 작은 구멍이 통째로 메워져 2분음표가 사라진다
        # (버그3과 같은 실패. 실측: 세로 5px 커널로 바꿨더니 39개가 누락됐다).
        # 가로 closing으로 '오선 제거가 남긴 1~3px 틈'을 메우는 시도도 실패했다
        # — 전체 적용은 +29개, 오선 행에만 적용해도 지워진 오선 조각을 도로
        # 이어붙여 가짜 구멍이 쏟아졌다(바흐 213->284).
        sc = cv2.morphologyEx(
            src, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        cs, hi = cv2.findContours(sc, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        out: List[tuple] = []
        if hi is None:
            return out
        hi = hi[0]
        for idx, c in enumerate(cs):
            if hi[idx][3] == -1:
                continue  # 바깥 윤곽은 스킵, 구멍만 본다
            hx, hy, hw, hh = cv2.boundingRect(c)
            if not (spacing * 0.30 <= hw <= spacing * 1.6
                    and spacing * 0.22 <= hh <= spacing * 1.15):
                continue
            # 조표 ♯ 글리프 중앙의 작은 구멍이 헤더 경계 직후에 걸리는 경우가 있어
            # 빈 음표 판정은 헤더 끝에서 0.6sp 여유를 더 두고 시작한다
            if hx + hw / 2.0 < header_end + spacing * 0.6:
                continue
            if _wall_span(src, hx, hy, hw, hh) >= HOLE_WALL_MAX_SP:
                continue
            out.append((hx, hy, hw, hh))
        return out

    def _enclosed_rects() -> List[tuple]:
        """
        위/아래가 오선에 먹혀 '닫힌 윤곽'이 안 되는 링을, 사방이 잉크로 둘러싸인
        배경 영역으로 찾아낸다. (x0, y0, w, h) 목록을 밴드 좌표로 반환.

        오선 제거가 링 테두리에 1~3px 틈을 남기면 구멍이 바깥으로 새어 윤곽
        검출이 실패한다 (실측: 1페이지 36마디 E3는 아래로 3px+2px 틈으로,
        37마디 F2는 위로 1px 틈으로 샜다. 온음표 화음의 한 음이 통째로 누락).
        그런 경우에도 링의 좌·우 세로 벽은 멀쩡히 남는다. 그래서 윤곽이 아니라
        '가까운 거리 안에 상하좌우 모두 잉크가 있는 배경 화소'를 모은다.
        모폴로지로 틈을 메우는 방법은 실패했다 — 지워진 오선 조각을 도로
        이어붙여 가짜 구멍이 쏟아졌다(바흐 213->284).
        """
        # 배경을 opening하면 링 안쪽(가로 6~12px)은 남고 누수 통로(1~3px)만
        # 끊긴다. 그러면 링 안쪽이 바깥 배경과 분리되어 '테두리에 닿지 않는
        # 배경 덩어리'로 잡힌다. 잉크 쪽을 건드리지 않으므로 지워진 오선 조각을
        # 되살리는 부작용도 없다.
        bg = (band == 0).astype(np.uint8)
        k = max(3, int(round(spacing * 0.42))) | 1
        bg_open = cv2.morphologyEx(
            bg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        n, lab, stats, _c = cv2.connectedComponentsWithStats(bg_open, connectivity=4)
        outside = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) \
            | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
        out: List[tuple] = []
        for i in range(1, n):
            if i in outside:
                continue
            x, y, w, h, _area = stats[i]
            # 폭 상한을 링 안쪽 크기로 좁게 잡는다. 배경 opening은 마디선·기둥과
            # 음표 머리 사이의 틈도 '갇힌 배경'으로 만들어 내는데, 그런 틈은
            # 폭 1.17~1.53sp로 진짜 링 안쪽(0.6~1.1sp)보다 뚜렷이 넓다.
            if not (spacing * 0.30 <= w <= spacing * 1.10
                    and spacing * 0.22 <= h <= spacing * 1.15):
                continue
            if x + w / 2.0 < header_end + spacing * 0.6:
                continue
            # 둘레가 실제로 잉크로 감싸여 있는지 확인한다. 배경 opening만으로는
            # 빔 아래 삼각형 틈이나 글자 속(Andante, legato)까지 '갇힌 배경'이
            # 되어 유령이 쏟아진다(실측: 쇼팽 Em에서 신규 후보 73개 중 대부분).
            # 진짜 링 안쪽은 링 벽이 사방을 두르므로 둘레의 대부분이 잉크다.
            # 문턱 RIM_INK_MIN — 실측: 진짜 링 0.73/0.76(버그8 두 건), 가짜 틈은
            # 쇼팽 Em 후보 100건이 전부 0.65 이하(중앙 0.48)로 깨끗이 갈린다.
            pad = max(2, int(round(spacing * 0.45)))
            ya, yb = max(0, y - pad), min(bg.shape[0], y + h + pad)
            xa2, xb2 = max(0, x - pad), min(bg.shape[1], x + w + pad)
            comp = (lab[ya:yb, xa2:xb2] == i).astype(np.uint8)
            if _rim_ink_ratio(comp, ya, xa2, band) < RIM_INK_MIN:
                continue
            out.append((x, y, w, h))
        return out

    # 세로 closing(patched)은 오선에 잘려 위/아래 호로 쪼개진 링을 다시 이어붙여
    # 구멍을 '닫힌 윤곽'으로 만들어주는 순기능이 있지만, 반대로 오선에 바짝 붙은
    # 빈 음표의 작은 구멍은 그 closing이 통째로 메워버린다
    # (실측: 이 악보 전체에서 구멍이 115개 -> 68개로 41% 소실, 빈 음표가 많은
    #  베이스 보표는 19개 -> 5개까지 줄어 2분음표가 통째로 누락됐다).
    # 그래서 closing 전(band)과 후(patched) 양쪽에서 찾아 합집합으로 쓴다.
    def _can_merge(a: tuple, b: tuple) -> bool:
        """두 구멍 bbox가 '같은 링에서 나온 조각'인지 판정한다."""
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        if abs((ax + aw / 2.0) - (bx + bw / 2.0)) > spacing * 0.6:
            return False
        a0, a1, b0, b1 = ay, ay + ah, by, by + bh
        overlap = min(a1, b1) - max(a0, b0)
        # 세로로 크게 겹치면 closing 전/후에서 같은 구멍을 두 번 잡은 중복이다
        if overlap > 0 and overlap >= 0.5 * min(ah, bh):
            return True
        # 떨어져 있으면 '선에 잘린 같은 링'일 때만 합친다:
        # 틈이 좁고, 합쳐도 구멍 하나 크기를 넘지 않아야 한다.
        return -overlap <= spacing * 0.3 and (max(a1, b1) - min(a0, b0)) <= spacing * 1.15

    def _merge_split_holes(rects: List[tuple]) -> List[tuple]:
        """
        같은 링에서 나온 구멍 조각들을 union bbox 하나로 합친다.

        오선/덧줄이 링 안쪽을 가로지르면 구멍이 위아래로 쪼개지는데, 조각 하나만
        남으면 중심이 실제 머리 중심에서 밀려 음고가 한 칸 어긋난다
        (실측: 3마디 베이스 E4의 구멍이 y=573~579 / 580~585로 갈렸는데 아래 조각만
         남아 중심 582 -> D4로 오판. 합치면 579 -> E4로 정확해진다).
        closing 전/후에서 중복 검출된 같은 구멍도 여기서 하나로 합쳐진다.
        """
        merged: List[tuple] = []
        for rect in sorted(rects, key=lambda r: (r[0] + r[2] / 2.0, r[1])):
            for k, cur in enumerate(merged):
                if _can_merge(cur, rect):
                    x0 = min(cur[0], rect[0])
                    y0 = min(cur[1], rect[1])
                    merged[k] = (x0, y0,
                                 max(cur[0] + cur[2], rect[0] + rect[2]) - x0,
                                 max(cur[1] + cur[3], rect[1] + rect[3]) - y0)
                    break
            else:
                merged.append(rect)
        return merged

    # 합친 뒤에야 '구멍 하나로서 그럴듯한 크기인가'를 판정한다
    hole_rects: List[tuple] = []
    for hx, hy, hw, hh in _merge_split_holes(
            _hole_rects(patched) + _hole_rects(band) + _enclosed_rects()):
        if not (spacing * 0.35 <= hw <= spacing * 1.6
                and spacing * 0.3 <= hh <= spacing * 1.15):
            continue
        if hw < spacing * 0.55 and hh < spacing * 0.75:
            continue
        if not _keep_candidate(hx + hw / 2.0, hy + hh / 2.0 + top):
            continue
        hole_rects.append((hx + hw / 2.0, hy + hh / 2.0, hy, hh))

    hollow_candidates: List[tuple] = []  # (cx, cy_abs, blocker, y0_abs, y1_abs)
    for cx, cy, hy, hh in hole_rects:
        # 이미 채워진 머리로 검출된 위치와 겹치면 어느 filled 항목이 막는지 기록한다.
        # 세로 판정은 고정 허용치 대신 filled blob의 실제 bbox를 써서,
        # 레저선에 걸친 빈 음표 링 조각이 같은 글리프에서 중복 검출되는 것을 막는다.
        cy_abs = cy + top
        blocker = next(
            (bi for bi, (px, _py, _f, by0, by1) in enumerate(raw)
             if abs(cx - px) < spacing * 0.8
             # 범위를 좁히지 말 것. 이음매(seam) 판정은 '한 filled 항목이 위/아래
             # 구멍 2개를 동시에 가린다'는 사실로 성립하는데, 여기를 좁히면 그
             # 관계가 끊겨 링 좌/우 벽이 유령 라벨로 살아난다(버그5와 같은 실패)
             and by0 - spacing * 2.0 <= cy_abs <= by1 + spacing * 2.0),
            None,
        )
        hollow_candidates.append((cx, cy_abs, blocker, hy + top, hy + hh + top))

    # 3도 간격으로 붙은 빈 음표 화음은 두 링이 겹치는 이음매가 두꺼운 잉크로 남아
    # '채워진 머리'로 오검출되고, 그 오검출이 정확히 두 구멍 사이에 있어 양쪽을
    # 동시에 가리는 특이 패턴이 생긴다. 같은 filled 항목이 서로 다른 방향(위/아래)의
    # 구멍 2개를 막고 있으면 그 filled 항목은 이음매 오탐으로 보고 제거,
    # 두 구멍은 정상적인 빈 음표로 살린다.
    blocked_by: dict = {}
    for cx, cy, blocker, _hy0, _hy1 in hollow_candidates:
        if blocker is not None:
            blocked_by.setdefault(blocker, []).append(cy)
    seam_artifacts = set()
    for bi, ys in blocked_by.items():
        if len(ys) < 2 or (max(ys) - min(ys)) <= spacing * 0.4:
            continue
        # 이음매는 '두 링 사이에 낀 잉크'이므로 두 구멍이 그 blob을 위아래로
        # 사이에 두고 있어야 한다. 두 구멍이 blob의 같은 쪽에만 몰려 있으면
        # 이음매가 아니라 다른 원인이다 — 실측(2페이지 st2 x=390): 8분음표의
        # 기둥과 깃발 사이 빈칸이 오선 잔여 획에 막혀 가짜 구멍 2개가 되었고,
        # 둘 다 머리 '아래'에 있는데도 이음매로 오인되어 진짜 머리가 지워지고
        # 유령 라벨 2개가 그 자리를 대신했다.
        blob_cy = raw[bi][1]
        if min(ys) < blob_cy < max(ys):
            seam_artifacts.add(bi)

    # '링 조각'이라면 그 링의 구멍이 blob 자기 bbox 안에 걸쳐 있어야 한다.
    # 구멍이 하나도 안 걸치는 blob은 속이 찬 진짜 머리이므로 지우면 안 된다
    # (실측: 2페이지 72마디 화음의 윗음이, 아랫음 구멍을 '멀리 있는 자기 구멍'으로
    #  오인당해 링 조각으로 삭제됐다. blocker 탐색 범위가 ±2sp로 넓어서 생긴 오인).
    ring_capable = set()
    for hx, hy, _bk, _h0, _h1 in hollow_candidates:
        for bi, (px, _py, _f, by0, by1) in enumerate(raw):
            if abs(hx - px) < spacing * 0.8 and by0 - spacing * 0.2 <= hy <= by1 + spacing * 0.2:
                ring_capable.add(bi)

    ring_artifacts = set()
    for cx, cy, blocker, _hy0, _hy1 in hollow_candidates:
        if blocker is None or blocker not in ring_capable:
            continue
        _px, _py, _f, by0, by1 = raw[blocker]
        if cy < by0 - spacing * 0.75 or cy > by1 + spacing * 0.75:
            ring_artifacts.add(blocker)

    artifacts = seam_artifacts | ring_artifacts
    raw_pre = list(raw)       # blocker 번호는 이 목록 기준(아래에서 artifacts를 빼면 번호가 밀린다)
    if artifacts:
        _before = list(raw)
        raw = [item for bi, item in enumerate(raw) if bi not in artifacts]
        _log_drop(_before, raw, "이음매/링 조각으로 판정되어 제거")

    accepted_holes: List[tuple] = []
    ring_kept_xy: set = set()
    for cx, cy, blocker, hy0, hy1 in hollow_candidates:
        if blocker is not None and blocker not in artifacts:
            continue  # 정상적으로 채워진 머리에 가려진 구멍 -> 무시
        raw.append((cx, cy, False, hy0, hy1))
        accepted_holes.append((cx, hy0, hy1))

    # 덧줄이 한가운데를 지나는 2분 · 온음표(§1-50 초안): 덧줄이 링 구멍을 위아래 반쪽으로 가르고, 링 + 덧줄이 opening을 견뎌 「꽉 찬 머리」 덩어리가
    # 되어 자기 구멍을 가린다(Verovio 개발 20쪽 빈 → 꽉 엇갈림 31 중 30 — 오선 위 첫 덧줄 C4 · A5). 구멍을 살리지 않는다(기각 20 ~ 23: 구멍 채택은
    # `_inside_ring` 삭제를 부른다) — 가린 덩어리 자신의 `filled`만 바꾼다(머리 수 · 좌표 그대로).
    # 조건: 구멍 중심이 가린 덩어리 중심에서 가로 · 세로 LEDGER_HOLLOW_CENTER_SP 안 + 덩어리 중심 행의 가로 잉크 런 ≥ LEDGER_RUN_SP(덧줄).
    #   런 1.30sp = 덧줄 판정 상수(verify, 정상 최소 1.40 / 유령 최대 1.19)이고, 이 경로 실측도 같은 자리를 가리킨다 — 중심 창 0.2sp 안 가려진 구멍
    #   진짜 31의 런 최소 1.72(덧줄 30, 오선 위 B2 1개만 0.66) · 가짜 32의 런 최대 1.12(`tools/measure_center_blocked.py`)
    #   중심 0.15sp: 진짜 최대 0.06 · 런 ≥ 1.3인 가짜 중 가장 가까운 것 0.24(Schumann L (526,674), 덩어리 높이 1.4)의 사이
    from .verify import LEDGER_RUN_SP
    W = no_staff_img.shape[1]
    for cx, cy, blocker, _hy0, _hy1 in hollow_candidates:
        if blocker is None or blocker in artifacts:
            continue
        it = raw_pre[blocker]
        if not it[2] or abs(cx - it[0]) > spacing * LEDGER_HOLLOW_CENTER_SP or abs(cy - it[1]) > spacing * LEDGER_HOLLOW_CENTER_SP:
            continue
        r = int(round(it[1]))
        if not (0 <= r < no_staff_img.shape[0]):
            continue
        row = no_staff_img[r, max(0, int(it[0] - spacing * 1.5)):min(W, int(it[0] + spacing * 1.5))] > 0
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        if best < spacing * LEDGER_RUN_SP:
            continue
        for k, cur in enumerate(raw):
            if cur is it:
                raw[k] = (it[0], it[1], False, it[3], it[4])

    # 빈 음표로 확정된 링의 좌/우 벽이 타원 opening을 견디고 남으면 '채워진 머리'로도
    # 잡혀 같은 음표에 라벨이 두 번 붙는다 (실측: 3마디 베이스 온음표의 링이
    # x=792/802 두 조각으로 남아 "라"가 두 번 찍혔다).
    # 확정된 구멍의 링 범위 안에 중심이 들어오는 filled 항목은 그 링의 조각으로 본다.
    if accepted_holes:
        def _inside_ring(px: float, py: float) -> bool:
            return any(
                abs(px - hx) <= spacing * 0.95
                and hy0 - spacing * 0.3 <= py <= hy1 + spacing * 0.3
                for hx, hy0, hy1 in accepted_holes
            )

        # 정말 꽉 찬 머리면 지우지 않는다(2026-10-05 야간, DECISIONS §1-29 · `RING_WALL.md` §7): 머리 옆 오선 칸이 가짜 빈 음표 구멍이 되어
        # 그 0.95sp 창이 옆의 진짜 머리를 지웠다(Verovio 112 · PDF 28). 구멍 쪽 성질(경계 · 모양 · 폭 · 연결성)은 모두 기각 — 지워지는 쪽을 본다.
        # 본 = 이 띠의 링 밖 단독 꽉 찬 후보 조각 평균, 상관 ≥ RING_WALL_KEEP_NCC면 진짜 머리로 남긴다.
        #   0.66 = 링 벽 조각 최대 0.54와 잘못 지운 진짜 머리 중앙 0.81의 기하평균(측정: 진짜 117/140 되찾음 · 링 벽 · 유령 되살아남 0/22)
        # 사진 모드는 끈다 — 사진 51장에서 오삭제 1(쇼팽 D♭ 형광등 (1249,2841) 「시b」, 원인 미확인)
        keep_ids = _ring_wall_true_heads(no_staff_img, raw, _inside_ring, spacing) if ring_wall_keep else set()
        _before = list(raw)
        ring_kept_xy = {(int(round(it[0])), int(round(it[1]))) for it in raw if id(it) in keep_ids}
        raw = [it for it in raw if not (it[2] and _inside_ring(it[0], it[1]) and id(it) not in keep_ids)]
        _log_drop(_before, raw, "빈 음표 링의 좌우 벽으로 판정되어 제거")

    # ---- 중복 제거 (가까운 좌표 병합) ----
    raw.sort(key=lambda t: (t[0], t[1]))
    noteheads: List[Notehead] = []
    kept: List[tuple] = []
    # 병합 범위는 '음표 머리 한 개 안'이다. 머리는 가로 약 1.3sp / 세로 약 1.0sp이므로
    # 같은 머리를 두 번 잡으면 중심이 가로로 최대 ~0.65sp 떨어진다 (실측: 빈 음표 링이
    # 좌·우 벽으로 갈라져 각각 잡힌 2단 12마디 베이스, dx=0.61sp dy=0.17sp).
    # 세로는 0.5sp를 넘기면 안 된다 — 2도 화음의 두 머리가 그만큼 어긋나 붙기 때문.
    for x, y, f, _y0, _y1 in raw:
        if any(abs(mx - x) < spacing * 0.7 and abs(my - y) < spacing * 0.5 for mx, my, _ in kept):
            continue
        kept.append((x, y, f))
        noteheads.append(
            Notehead(x=int(round(x)), y=int(round(y)), staff_index=staff.index, filled=f,
                     ring_kept=(int(round(x)), int(round(y))) in ring_kept_xy,
                     wide_triple=(int(round(x)), int(round(y))) in triple_xy)
        )

    _log_drop(raw, kept, "같은 자리 중복으로 제거")
    return noteheads


RING_WALL_KEEP_NCC = 0.66


def _ring_wall_true_heads(no_staff_img: np.ndarray, raw: list, inside_ring, sp: float) -> set:
    """링 벽으로 지워질 꽉 찬 후보 중 단독 꽉 찬 머리 본과 상관 ≥ RING_WALL_KEEP_NCC인 것의 id. 본을 못 만들면(< 5) 빈 집합."""
    ns = (no_staff_img > 0).astype(np.float32)
    hw, hh = int(0.65 * sp), int(0.55 * sp)
    crops = []
    for it in raw:
        if not it[2] or inside_ring(it[0], it[1]):
            continue
        if any(o is not it and abs(o[0] - it[0]) <= 1.2 * sp and abs(o[1] - it[1]) <= 1.2 * sp for o in raw):
            continue
        x, y = int(it[0]), int(it[1])
        c = ns[y - hh:y + hh + 1, x - hw:x + hw + 1]
        if c.shape == (2 * hh + 1, 2 * hw + 1) and c.mean() > 0.4:
            crops.append(c)
        if len(crops) >= 30:
            break
    if len(crops) < 5:
        return set()
    tmpl = np.mean(crops, axis=0).astype(np.float32)
    r = int(0.2 * sp)
    keep = set()
    for it in raw:
        if not (it[2] and inside_ring(it[0], it[1])):
            continue
        x, y = int(it[0]), int(it[1])
        reg = ns[max(0, y - hh - r):y + hh + r + 1, max(0, x - hw - r):x + hw + r + 1]
        if reg.shape[0] > tmpl.shape[0] and reg.shape[1] > tmpl.shape[1] and cv2.matchTemplate(reg, tmpl, cv2.TM_CCOEFF_NORMED).max() >= RING_WALL_KEEP_NCC:
            keep.add(id(it))
    return keep


def detect_noteheads(result: PreprocessResult, contexts=None,
                     reject_log: "List[dict] | None" = None) -> List[Notehead]:
    """
    전체 이미지에 대해 보표별로 음표 머리를 검출한다.

    Args:
        contexts: clef_keysig.analyze_staves()의 결과(dict[staff_index, StaffContext]).
                  주어지면 각 보표의 헤더 영역(음자리표/조표/박자표)을 탐색에서 제외한다.
        reject_log: 리스트를 주면 '모양·쉼표 판정은 통과했는데 뒤 단계에서 지워진'
                  후보를 기록한다(누락 점검용, --audit).

    Raises:
        NoteheadDetectionError: 어떤 보표에서도 음표 머리를 하나도 찾지 못한 경우
    """
    no_staff = remove_staff_lines(result.binary, result.staves)
    img_height = result.binary.shape[0]

    all_noteheads: List[Notehead] = []
    for staff in result.staves:
        header_end = 0
        if contexts is not None and staff.index in contexts:
            header_end = contexts[staff.index].header_end
        found = _detect_noteheads_in_band(
            no_staff, staff, img_height, header_end=header_end,
            margins=_band_margins(staff, result.staves, no_staff),
            reject_log=reject_log,
            ring_wall_keep=getattr(result, "photo_correction", None) is None,
            second_pair_split=getattr(result, "photo_correction", None) is None,   # 사진 모드는 끈다(미측정)
        )
        all_noteheads.extend(found)

    # 보표 사이 영역은 이웃한 두 보표의 탐색 밴드에 모두 걸릴 수 있어
    # 같은 잉크가 두 번(서로 다른 보표 기준으로) 검출된다.
    # 가까운 좌표의 중복은 '자기 보표에서 더 가까운' 쪽만 남긴다.
    staff_by_index = {s.index: s for s in result.staves}

    def _ledger_at(s: Staff, cx: float, ly: float) -> bool:
        """(cx, ly)에 덧줄(가로로 긴 잉크)이 실제로 있는지."""
        sp = s.spacing
        H, W = no_staff.shape[:2]
        xa, xb = max(0, int(cx - sp * 1.2)), min(W, int(cx + sp * 1.2) + 1)
        r0, r1 = max(0, int(ly) - 2), min(H, int(ly) + 3)
        if xb <= xa or r1 <= r0:
            return False
        need = sp * 1.0        # 바흐 실측 1.16sp — 문턱을 이보다 올리면 안 된다
        for r in range(r0, r1):
            run = best = 0
            for v in (no_staff[r, xa:xb] > 0):
                run = run + 1 if v else 0
                if run > best:
                    best = run
            if best >= need:
                return True
        return False

    def _ledger_evidence(si: int, x: int, y: int) -> tuple:
        """
        (적합도 0~1, 실제로 확인된 덧줄 수, 필요한 덧줄 수)를 돌려준다.

        적합도만 보면 '덧줄이 아예 필요 없는 보표'가 물증 0개로 1.0을 받아,
        덧줄 여러 개를 실제로 갖춘 보표를 거리로 이겨버린다
        (실측: 13마디 베이스 라+레 화음의 윗음 A4가 트레블로 넘어가 "도#"이 됐다).
        그래서 확인된 개수도 같이 돌려준다.
        """
        s = staff_by_index[si]
        sp = s.spacing
        if s.top <= y <= s.bottom:
            return 1.0, 0, 0
        # 필요한 덧줄 개수는 반올림이 아니라 int(d + 0.25)다. 오선 바로 바깥 '칸'
        # (0.5sp)은 덧줄이 필요 없는데 반올림하면 1개를 요구해 적합도가 0이 된다
        # (실측: 2페이지 39마디 D4가 0.51sp인데 덧줄을 요구받아 베이스로 넘어갔다).
        # 0.5->0, 1.0->1, 1.5->1, 2.0->2 로 기보법과 맞는다.
        if y < s.top:
            steps = int((s.top - y) / sp + 0.25)
            need = [s.top - k * sp for k in range(1, steps + 1)]
        else:
            steps = int((y - s.bottom) / sp + 0.25)
            need = [s.bottom + k * sp for k in range(1, steps + 1)]
        # 음표 자신의 자리는 덧줄 근거로 치지 않는다(머리 잉크가 가로로 길어 오인됨)
        need = [ly for ly in need if abs(ly - y) > sp * 0.4]
        if not need:
            return 1.0, 0, 0
        hit = sum(1 for ly in need if _ledger_at(s, x, ly))
        return hit / len(need), hit, len(need)

    def _ledger_fit(nh: Notehead) -> float:
        """
        보표 밖 음표가 그 보표의 덧줄로 실제 이어져 있는 비율(0~1).

        보표 사이에 뜬 음표는 '가까운 보표'가 아니라 '덧줄이 이어지는 보표'에
        속한다. 거리만 보면 반대쪽으로 넘어가 음이름이 통째로 틀리고
        (실측: 2페이지 40마디 A3가 베이스로 넘어가 "레"가 됐다),
        반 칸 격자 적합도로 판정하면 두 보표의 sp가 미세하게 달라 엉뚱한 쪽이
        이긴다(실측: 이미 검증된 15마디 베이스 "도#"가 "파#"로 뒤집혔다).
        덧줄은 그 보표에서 뻗어 나온 것이라 소속을 그대로 말해준다.
        """
        return _ledger_evidence(nh.staff_index, nh.x, nh.y)[0]

    def _staff_distance(nh: Notehead) -> float:
        s = staff_by_index[nh.staff_index]
        if s.top <= nh.y <= s.bottom:
            return 0.0
        return min(abs(nh.y - s.top), abs(nh.y - s.bottom)) / s.spacing

    all_noteheads.sort(key=lambda n: (n.x, n.y))
    deduped: List[Notehead] = []
    for nh in all_noteheads:
        sp = staff_by_index[nh.staff_index].spacing
        dup_idx = next(
            (k for k, m in enumerate(deduped)
             if m.staff_index != nh.staff_index
             and abs(m.x - nh.x) < sp * 0.7 and abs(m.y - nh.y) < sp * 0.7),
            None,
        )
        if dup_idx is None:
            deduped.append(nh)
        else:
            cur = deduped[dup_idx]
            # 격자 적합도는 '두 보표 사이에 떠 있는 음표'에만 적용한다. 보표 안에
            # 들어와 있는 음표까지 이 기준으로 뒤집으면 이미 맞던 것이 바뀐다.
            both_outside = _staff_distance(nh) > 0 and _staff_distance(cur) > 0
            lf_new, lf_cur = (_ledger_fit(nh), _ledger_fit(cur)) if both_outside else (0, 0)
            # 덧줄이 '전부' 갖춰진 쪽만 거리를 뒤집을 수 있다. 부분 일치로
            # 비교하면 타이(이음줄) 곡선의 가로 구간이 덧줄로 오인되어 엉뚱한
            # 보표가 이긴다 (실측: 2페이지 39마디 타이 앞 음이 2/3로 이겨 "솔").
            if both_outside and lf_new >= 1.0 and lf_cur < 1.0:
                deduped[dup_idx] = nh
            elif both_outside and lf_cur >= 1.0 and lf_new < 1.0:
                pass
            elif _staff_distance(nh) < _staff_distance(cur):
                deduped[dup_idx] = nh
    if reject_log is not None:
        survived = {(m.x, m.y) for m in deduped}
        for nh in all_noteheads:
            if (nh.x, nh.y) not in survived:
                reject_log.append(dict(staff=nh.staff_index, x=float(nh.x),
                                       y=float(nh.y), filled=nh.filled,
                                       reason="이웃 보표와 중복으로 제거"))
    all_noteheads = deduped

    # ---- 보표 소유권 재검토 ----
    # 위 중복 제거는 '두 보표가 모두 그 음표를 찾았을 때'만 동작한다. 보표 사이에
    # 뜬 음표가 한쪽 밴드에서만 잡히면 경쟁이 없어 그대로 굳어버린다
    # (실측: 13마디 베이스 화음의 윗음 A4는 베이스 밴드가 1px 모자라 놓쳐,
    #  트레블이 덧줄 물증 0개로 가져가 "라"가 "도#"이 됐다).
    # 덧줄은 어느 보표에서 뻗어 나왔는지를 그대로 말해주므로, 이웃 보표가 덧줄을
    # '전부' 갖추고 자기 보표는 물증이 하나도 없으면 소유권을 넘긴다.
    for i, nh in enumerate(all_noteheads):
        s = staff_by_index[nh.staff_index]
        if s.top <= nh.y <= s.bottom:
            continue
        j = nh.staff_index + (1 if nh.y > s.bottom else -1)
        if j not in staff_by_index:
            continue
        o = staff_by_index[j]
        if not (o.top - o.spacing * 6 <= nh.y <= o.bottom + o.spacing * 6):
            continue
        _own_fit, own_hit, _own_need = _ledger_evidence(nh.staff_index, nh.x, nh.y)
        fit, hit, need = _ledger_evidence(j, nh.x, nh.y)
        if own_hit == 0 and fit >= 1.0 and need >= 2 and hit > 0:
            if os.environ.get("AKBO_TRACE"):
                print(f"[소유권] x={nh.x} y={nh.y} 보표{nh.staff_index}->{j} "
                      f"(덧줄 {hit}/{need})")
            all_noteheads[i] = Notehead(x=nh.x, y=nh.y, staff_index=j,
                                        filled=nh.filled, ring_kept=nh.ring_kept, wide_triple=nh.wide_triple)

    # 보표 사이(gap)의 빈 음표는 자기 보표보다 이웃 보표의 밴드 가장자리에서
    # 검출되는 경우가 있다 (예: 베이스 화음의 윗음이 높은음자리표 밴드에서 검출).
    # 그 상태로 두면 엉뚱한 음자리표 기준으로 계이름이 계산되므로,
    # 같은 x 근처에 '보표에 더 가까운' 빈 음표 파트너(화음의 아랫음)가 있으면
    # 그 파트너의 보표로 소속을 옮겨준다.
    hollows = [nh for nh in all_noteheads if not nh.filled]
    for nh in hollows:
        sp = staff_by_index[nh.staff_index].spacing
        d = _staff_distance(nh)
        if d <= 0.3:
            continue  # 보표 안쪽/근처는 정상 음표
        best = None
        for m in hollows:
            if m is nh or m.staff_index == nh.staff_index:
                continue
            if abs(m.x - nh.x) < sp * 0.6 and abs(m.y - nh.y) < sp * 2.8 \
                    and _staff_distance(m) + 0.3 < d:
                if best is None or _staff_distance(m) < _staff_distance(best):
                    best = m
        if best is not None:
            nh.staff_index = best.staff_index

    # ---- 나타냄말·셈여림·손가락번호 같은 '글자'에서 나온 유령 제거 ----
    # 글자는 오선 밖에 같은 높이로 여러 개가 줄지어 늘어서고 레저선이 없다
    # (실측: 쇼팽 "Lento sostenuto" 위에 같은 y로 8개, "dolce" 위에도 발생).
    # 진짜 음표가 오선 밖에 있으면 반드시 레저선을 달고 있으므로 안전하게 갈린다.
    #
    # 이 판정은 반드시 파이프라인 맨 뒤에서 할 것. 검출 앞단에서 오선 밖 후보를
    # 지우면 보표 사이 음표를 이웃 밴드에서 잡아 정리하는 로직이 무력화되어
    # 연쇄 손실이 난다(실측: 앞단 적용 시 쇼팽 Em 396 -> 302).
    by_staff: dict = {}
    for nh in all_noteheads:
        by_staff.setdefault(nh.staff_index, []).append(nh)
    ghosts: set = set()
    for si, group in by_staff.items():
        s = staff_by_index[si]
        sp = s.spacing
        outside = sorted(
            (nh for nh in group
             if max(s.top - nh.y, nh.y - s.bottom) > sp * 0.75),
            key=lambda n: (n.y, n.x),
        )
        i = 0
        while i < len(outside):
            j = i
            while j + 1 < len(outside) and abs(outside[j + 1].y - outside[i].y) <= sp * 0.3:
                j += 1
            row = outside[i:j + 1]
            # 3개 이상 나란히 늘어선 것으로 '글자 줄'임을 인정하되, 제거는
            # 항목별로 판단한다. 그룹 단위로 any()를 쓰면 나타냄말 안에 그려진
            # 음표 그림(♩ = 50) 하나 때문에 줄 전체가 살아남는다(실측 9개).
            # 낱개(줄을 이루지 않은) 후보에도 같은 규칙을 적용해 보았으나
            # 실패했다: 오선 밖 1.5~2.5sp에서 덧줄/기둥 검사가 고해상도 조판에서
            # 자주 실패해 진짜 음표를 지운다(실측: 쇼팽 Em −10~18개, D♭ −12~14개).
            # '줄을 이룬다'는 증거는 여전히 필수 조건이다.
            if len(row) >= 3:
                for n in row:
                    if not (_has_ledger_line(no_staff, s, n.x, n.y)
                            or _has_stem(no_staff, s, n.x, n.y)):
                        ghosts.add(id(n))
            i = j + 1
    if ghosts:
        if reject_log is not None:
            for nh in all_noteheads:
                if id(nh) in ghosts:
                    reject_log.append(dict(staff=nh.staff_index, x=float(nh.x),
                                           y=float(nh.y), filled=nh.filled,
                                           reason="글자에서 나온 유령으로 판정"))
        all_noteheads = [nh for nh in all_noteheads if id(nh) not in ghosts]

    # ---- 잉크가 아예 없는 자리의 유령 제거 ----
    # 음표는 채워졌든 비었든 '중심을 지나는 가로줄'에 반드시 잉크가 있다
    # (빈 음표라도 링의 좌우 벽을 지난다). 잉크가 하나도 없으면 음표가 아니다.
    # 실측: 1페이지 10마디 베이스의 유령(마디선과 기둥 사이 빈칸)과
    # 2페이지 67마디의 "미#" 유령이 모두 여기서 걸린다.
    # 오선이 지워진 no_staff가 아니라 원본 이진화를 봐야 한다.
    bin_img = result.binary
    BH, BW = bin_img.shape[:2]
    solid: List[Notehead] = []
    for nh in all_noteheads:
        sp = staff_by_index[nh.staff_index].spacing
        hw, hh = int(sp * 0.55), int(sp * 0.40)
        y0, y1 = max(0, nh.y - hh), min(BH, nh.y + hh + 1)
        x0, x1 = max(0, nh.x - hw), min(BW, nh.x + hw + 1)
        win = bin_img[y0:y1, x0:x1] > 0
        frac = float(win.mean()) if win.size else 0.0
        run = best = 0
        for v in (bin_img[min(max(0, nh.y), BH - 1), x0:x1] > 0):
            run = run + 1 if v else 0
            best = max(best, run)
        # 빈 음표는 중심이 비어 있어 frac이 낮지만, 중심 행이 링의 좌우 벽을
        # 지나므로 가로런이 생긴다. 둘 다 없으면 잉크가 아예 없는 자리다.
        if frac >= 0.30 or best >= sp * 0.45:
            solid.append(nh)
        elif reject_log is not None:
            reject_log.append(dict(staff=nh.staff_index, x=float(nh.x), y=float(nh.y),
                                   filled=nh.filled,
                                   reason="검출 위치에 잉크가 없음(유령)"))
    all_noteheads = solid

    # ---- 같은 음이 1sp 옆에 또 잡힌 중복 제거 ----
    # 기보법상 한 보표에서 '같은 높이의 머리 두 개'가 1sp 남짓 떨어져 나란히
    # 놓이는 일은 없다. 2도 화음은 기둥 좌우로 어긋나 붙지만 그때는 높이가
    # 반 칸(0.5sp) 다르다. 높이가 같은데 옆으로만 벌어져 있으면 한쪽은 유령이다
    # (실측: 3페이지 st3 x=466/522 — 기둥과 이웃 음표 머리 사이의 빈칸이
    #  오선 잔여 획에 위아래가 막혀 가짜 구멍이 됐다. 진짜 머리는 11px 오른쪽).
    # 어느 쪽을 남길지는 '머리 좌우에 실제로 잉크가 있는가'로 정한다.
    def _head_evidence(nh: Notehead) -> float:
        sp = staff_by_index[nh.staff_index].spacing
        height, width = no_staff.shape[:2]
        dy = max(1, int(round(sp * 0.25)))
        y0, y1 = max(0, nh.y - dy), min(height, nh.y + dy + 1)
        inner, outer = max(1, int(round(sp * 0.20))), max(2, int(round(sp * 0.55)))
        sides = []
        for x0, x1 in ((max(0, nh.x - outer), max(0, nh.x - inner + 1)),
                       (min(width, nh.x + inner), min(width, nh.x + outer + 1))):
            strip = no_staff[y0:y1, x0:x1] > 0
            sides.append(float(strip.mean()) if strip.size else 0.0)
        return min(sides)

    doomed = set()
    for i, a in enumerate(all_noteheads):
        sp = staff_by_index[a.staff_index].spacing
        for b in all_noteheads[i + 1:]:
            if (b.staff_index == a.staff_index
                    and sp * 0.6 <= abs(b.x - a.x) <= sp * 1.3
                    and abs(b.y - a.y) <= sp * 0.35):
                # 링 벽 예외로 살아난 꽉 찬 머리와 빈 머리가 나란히 = 두 성부의 같은 음(Clara 3 Bravura (1642 · 1663, 2518)) — 둘 다 남긴다.
                # 이 예외 없이는 빈 머리가 지워져 오삭제 1이 났다(`NIGHT_CAUSES.md` 후속 [3]). 쌍 전체를 빼면 이 판정이 원래 지우던 유령이 살아날 수 있어 그 경로만
                if a.filled != b.filled and (a.ring_kept or b.ring_kept):
                    continue
                loser = a if _head_evidence(a) < _head_evidence(b) else b
                doomed.add(id(loser))
    if doomed:
        if reject_log is not None:
            for nh in all_noteheads:
                if id(nh) in doomed:
                    reject_log.append(dict(staff=nh.staff_index, x=float(nh.x),
                                           y=float(nh.y), filled=nh.filled,
                                           reason="같은 높이 바로 옆의 중복으로 판정"))
        all_noteheads = [nh for nh in all_noteheads if id(nh) not in doomed]

    if not all_noteheads:
        raise NoteheadDetectionError(
            "음표 머리를 하나도 검출하지 못했습니다. 이미지 해상도나 이진화 파라미터를 확인해주세요."
        )

    # 보표 -> x좌표 순으로 정렬해 왼쪽에서 오른쪽으로 읽는 순서를 보장
    all_noteheads.sort(key=lambda n: (n.staff_index, n.x))
    return all_noteheads
