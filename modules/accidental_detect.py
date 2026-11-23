# -*- coding: utf-8 -*-
"""
임시표(accidental: ♯/♭/♮) 검출 모듈

각 음표 머리의 왼쪽(0.55~2.0sp) 영역에서 임시표 글리프를 찾아 분류한다:
  - ♯ / ♮: 얇은 세로 막대 2개. ♯은 두 막대의 위/아래 끝이 거의 나란하지만,
    ♮은 왼쪽 막대가 위로, 오른쪽 막대가 아래로 길게 삐져나온다(0.45sp 이상 어긋남).
  - ♭: 세로 막대 1개 + 오른쪽 아래 고리(구멍).
  - 음표 기둥(stem)은 검사 창(±2sp)을 위아래로 관통하므로 길이 조건에서 배제된다.

악보 규칙대로, 임시표는 같은 마디 안에서 같은 음(음이름+옥타브)에 계속 적용된다.
이를 위해 보표별로 바라인(마디선: 오선 높이를 정확히 관통하는 얇은 세로선)을
검출해 마디 경계에서 임시표 효력을 초기화한다.

반환 값: 각 음표에 대한 임시표 문자열 ("#", "b", "natural", "") 리스트.
"""

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .preprocess import PreprocessResult, Staff
from .notehead_detect import remove_staff_lines
from .pitch_calculator import PitchedNote


# 임시표 글리프의 세로 중심이 음표 중심에서 이만큼(sp 배수) 넘게 벗어나면
# 그 음표의 것이 아니라고 본다. 실측(쇼팽 마단조 녹턴 4쪽, 글리프 223개)에서
# Δy/sp 분포는 0.2 이하(자기 임시표 174개)와 0.45 이상(이웃 음의 것 44개)으로
# 갈라지고 그 사이가 비어 있다. 화음의 3도 이웃은 1.0sp 떨어져 있다.
ACCIDENTAL_Y_TOL_SP = 0.35

# 임시표 글리프 자신이 '음표'로 잘못 잡혔을 때, 그 유령은 글리프 안쪽 칸에 생긴다.
# 그 칸이 음표 중심에서 얼마나 벌어지는지가 이 값이다.
#
# 상수를 눈대중으로 고르면 다음 악보에서 또 깨진다(예전 값 0.8sp는 RE:Aoharu
# sp=11px 기준이었고, sp=19px인 쇼팽에서 dy가 1.0~1.4sp까지 벌어져 놓쳤다).
# 그래서 글리프 크기에서 유도한다: _find_thin_bars가 임시표 세로획으로 인정하는
# 길이는 1.5~3.2sp이고 인쇄 악보의 ♯/♮은 약 2.5sp다. 유령은 글리프 안쪽 칸에
# 생기므로 중심에서 멀어야 '글리프 반높이' 2.5/2 = 1.25sp다. 그 이상은 글리프
# 밖이라는 뜻이므로 여유를 더하지 않는다.
#
# 여유 0.15sp를 더해 1.4sp로 잡아 봤더니 진짜 음표 하나가 지워졌다
# (쇼팽 D♭ 5쪽 x=1897 y=2812 A5, 좌우 잉크 0.70/0.74로 멀쩡한 음표인데
#  오른쪽 1.53sp·아래 1.37sp에 ♭이 붙은 이웃 음표가 있었다). 글리프 반높이를
# 넘어가면 '옆 음표에 붙은 임시표'와 구별되지 않는다.
#
# 실측(쇼팽 D♭장조 6쪽, sp=19px, 글리프 내부 유령 16건): dy/sp 중앙값 1.12,
# 이 값 이하가 11건. 넘는 것 중 1.79/2.00/2.55는 옆 글리프를 기준으로 잰 것이라
# 애초에 이 규칙으로는 잡을 수 없다.
ACCIDENTAL_GHOST_Y_SP = 1.25


# ------------------------------------------------------------------
# 정밀 판정 (2026-10-02, 사용자 승인 — A-17 수락안 c12 + G3 + H3 + ♮ 조건, docs/NATURAL_SHARP.md · DECISIONS §1-12)
# **사진 모드(photo_correction 있음)에서는 끈다** — A-18(회전 사진 오선 잔여로 생긴 가짜 막대)이 안 풀려 기존 판정을 쓴다.
# 다섯 부분 모두 측정 사본(tools/measure_a17_ghost6.py c12g3h3 · tools/measure_natural_sharp.py)과 같은 계산이다.
#
# ♮ 조건 — 두 획 중심의 어긋남: (위끝 차) + (아래끝 차) > NATURAL_OFFSET_SUM_SP.
#   기보 규칙: ♮은 왼쪽 획이 위로 · 오른쪽 획이 아래로 **반대 방향으로** 어긋나고, ♯은 두 획이 같은 높이다.
#   예전 조건 「위 · 아래 **둘 다** > 0.45sp」는 한쪽 끝 하나만 밀려도(Bravura 왼쪽 획 위끝 비스듬 · Leipzig 오른쪽 획 아래끝 ·
#   LilyPond 앞 머리에 붙음) ♯로 떨어졌다(Verovio ♮의 31~40%). 합은 한쪽이 밀려도 버틴다.
#   실측 — 글리프 상자 안 두 획(제품 판정 입력), 세 조판 932 글리프: ♮ 최소 LilyPond 0.51 · Bravura 0.61 · Leipzig 0.50,
#   ♯ 최대 0.00 · −0.11 · 0.06. 부호 있는 값이라 가운데 (0.06 + 0.50) / 2 = 0.28, 양쪽 여유 0.22.
#   **약점**: 고른 쌍이 ♯ 글리프의 두 획이 아니라 「♯ 한 획 + 오른쪽 머리 가장자리 · 기둥」(간격 0.72~0.91sp)이면
#   그 쌍이 위아래로 어긋나 ♮이 된다(보지 않은 악보 단독 4건). 자기 머리 막대 제외(아래 OWN_HEAD_ROWS_SP)와 함께라야
#   1건으로 준다 — 그래서 ♮ 조건만 따로 켜지 않는다.
NATURAL_OFFSET_SUM_SP = 0.28
# 화음 임시표 열(§1-49 초안) — 먼 열까지 보는 띠의 왼끝(머리 − sp). 정답(Verovio 20쪽) 화음 열 창 밖 16의 상자 왼끝 최대 2.66sp ·
# 기보 규칙(원래 창 2.0 + 열 간격 최대 1.06sp = 3.06) → 3.0
CHORD_COLUMN_LEFT_SP = 3.0
# 후보 1 — 판정 창이 보표 밴드(±3.5sp) 경계에서 잘리지 않게 밴드를 위아래로 이만큼 더 넓힌다(A-17 원인 「창 잘림」 9건).
# 마디선 · 오선 제거는 원래 보표 그대로.
WIDE_BAND_SP = 2.0
# 후보 2 — 자기 머리 덩어리를 이만큼 이상 지나가는 막대는 임시표 획이 아니다(머리 · 기둥 가장자리가 막대로 11건).
# 비율로는 안 된다: 머리 + 자기 기둥 막대는 기둥이 얇아 머리 비율이 절반 미만
OWN_HEAD_ROWS_SP = 0.5
# G3 — 빈 머리 후보 자리에 ♯/♮ 모양이 있고 그 주인 음표가 오른쪽(0.5~2.0sp · 세로 1sp)에 있으면 글리프 칸 유령으로 지운다.
# 막대 길이 하한 2.2sp: ♯/♮ 글리프 높이 ≈ 2.5sp와 2도로 쌓인 빈 머리 링 옆면 ≤ 2.0sp(E단조 2쪽 실측 1.81~2.02) 사이.
# 두 막대 사이 잉크 비율 상한 0.7: ♯/♮ 칸(가로획 두 줄, 실측 0.45)과 빽빽한 화음 덩어리(1.00) 사이 — **글리프 표본 1개라 근거 약함**.
# 주인 음표 조건이 없던 판(G2)은 Aoharu 2쪽 골든 C5를 지웠다(오삭제 — 기각). 지운 자리는 측정에서 전부 눈 판정 유령
GLYPH_BAR_SP = 2.2
GLYPH_INNER_INK = 0.7


# 임시표 전파 경계 — 마디선 (2026-10-03, 사용자 승인 · A-25, docs/A25_BARLINE.md §6~7 · DECISIONS §1-14). **사진 모드에서는 끈다**(`_refined`).
# 예전 경계 `_find_barlines`(오선 높이 관통 · 얇음)는 빔으로 묶인 16분음표 · 화음 기둥까지 마디선으로 잡아(Verovio 후보 2,163 중 진짜 772)
# 마디를 쪼갰다 — 「읽었는데 전파 안 됨」 53건 중 52건이 원천 ~ 대상 사이 기둥. 라벨 배치가 쓰는 `verify.barline_positions`와 같은 규칙에
# 흰 틈 보조 규칙을 더한 **전파 전용 사본**을 쓴다(렌더러 경로는 그대로 — 그 함수는 x만 받는다).
#
# BARLINE_NOTE_GAP_SP 0.9 — 「마디선 자리에는 음표가 없다」: 선 0.9sp 안에 음표 x가 있으면 기둥 후보.
#   기둥 → 가장 가까운 음표 중앙 0.56~0.60 · 95% 0.61~0.70(머리 반폭), 진짜 마디선 → 5% 1.06 · 중앙 1.7~2.0(세 조판 + Aoharu).
#   √(0.70 × 1.06) = 0.86 ≈ 0.9(라벨 배치에서 쓰던 값이 이 사이에 있다)
# BARLINE_WHITE_GAP_SP 0.1 — 그래도 **그 음표들 모두와 흰 틈**(음표 y ±0.25sp 행, 선 ~ 머리 사이 빈 열)이 있으면 마디선이다.
#   기보 규칙: 기둥은 자기 머리와 잉크가 이어진다(틈 0), 마디선과 음표 사이에는 흰 틈이 있다.
#   기둥 99% 0.09(Verovio · Aoharu) · 진짜 마디선 최소 0.11 → √(0.09 × 0.11) = 0.10. Verovio 진짜 마디선 20/20을 되찾는다.
#   **한계**: PDF 기둥 꼬리(99% 0.25 — 자기 머리가 아닌 음표가 더 가까운 기둥)와 겹쳐 기둥 약 2%가 다시 마디선이 된다 —
#   틀리면 마디가 쪼개져 전파가 안 되는 쪽(예전 동작)이다. 남은 나쁜 방향(진짜 마디선을 넘어 전파) 1: B♭m 6쪽 (1605,1100) 「파 → 파b」
#   (마디선 옆 머리와의 틈 0.1sp 미만)
BARLINE_NOTE_GAP_SP = 0.9
BARLINE_WHITE_GAP_SP = 0.1


def _propagation_barlines(binary: np.ndarray, no_staff: np.ndarray, staff: Staff, notes) -> List[int]:
    """임시표 전파 경계 마디선 x — `verify.barline_positions` 규칙(오선 행 95% 관통 · 음표 0.9sp 안 제외 · 음표 범위 밖 제외) + 흰 틈 규칙.
    `notes`는 그 보표의 (x, y)."""
    top, bottom = int(staff.top), int(staff.bottom)
    band = binary[top:bottom + 1] > 0
    columns = np.where(band.sum(axis=0) >= (bottom - top) * 0.95)[0]
    sp = staff.spacing
    near = sp * BARLINE_NOTE_GAP_SP

    def gap(x, nx, ny):
        a, b = sorted((int(x), int(nx)))
        y0, y1 = int(ny - 0.25 * sp), int(ny + 0.25 * sp) + 1
        return int((~(no_staff[y0:y1, a:b + 1] > 0).any(axis=0)).sum()) / sp

    groups: List[List[int]] = []
    for x in columns:
        close = [(nx, ny) for nx, ny in notes if abs(int(x) - nx) <= near]
        if close and any(gap(x, nx, ny) < BARLINE_WHITE_GAP_SP for nx, ny in close):
            continue    # 음표 기둥 — 그 머리와 잉크가 이어짐
        if not groups or x - groups[-1][-1] > 3:
            groups.append([int(x)])
        else:
            groups[-1].append(int(x))
    bars = [int(np.mean(g)) for g in groups]
    xs = [x for x, _y in notes]
    if xs:
        lo, hi = min(xs), max(xs)
        bars = [b for b in bars if lo < b < hi]   # 시스템 첫머리선 · 마침줄은 마디 경계가 아니다
    return bars


def _refined(result) -> bool:
    """정밀 판정을 켜는가 — 사진 모드(photo_correct 경로)가 아닐 때만."""
    return getattr(result, "photo_correction", None) is None


def _bars_without_own_head(band: np.ndarray, r0: int, c0: int, patch: np.ndarray, sp: float):
    """창 안 막대 중 **자기 머리 덩어리**를 OWN_HEAD_ROWS_SP 이상 지나가는 것을 뺀 목록(후보 2).

    밴드 전체 8연결 성분은 못 쓴다 — 글리프가 빔 · 덧줄 · 기둥을 거쳐 머리와 한 성분이 된다(D♭ 3쪽 (986,2900)).
    창 + 머리 영역을 열림(타원 0.4sp)으로 얇은 획(글리프 막대 · 기둥 · 이음줄 ≤ 0.3sp)을 지우고 남은 두꺼운 덩어리 중
    머리 자리 것을 자기 머리로 본다(쌓인 화음 머리는 한 덩어리). 가장자리가 열림에 깎이므로 k//2 부풀려 잰다.
    머리 덩어리가 없으면(빈 머리 등) None — 부르는 쪽이 막대를 그대로 쓴다.
    """
    H, W = patch.shape
    hr = int(round(H - 2 * sp)) if r0 == 0 else int(round(2 * sp))      # 창 안 머리 행
    hc = int(round(W + 0.55 * sp))                                        # 창 원점 기준 머리 열
    local = band[r0:r0 + H, c0:min(band.shape[1], c0 + hc + int(0.8 * sp))]
    k = max(3, int(0.4 * sp)) | 1
    ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    thick = cv2.morphologyEx((local > 0).astype(np.uint8), cv2.MORPH_OPEN, ell)
    _n, lab = cv2.connectedComponents(thick, connectivity=8)
    d = max(1, int(0.3 * sp))
    box = lab[max(0, hr - d):hr + d + 1, max(0, hc - d):hc + d + 1]
    ids = box[box > 0]
    if ids.size == 0:
        return None
    head = cv2.dilate((lab == np.bincount(ids).argmax()).astype(np.uint8), ell, iterations=1)
    return [b for b in _find_thin_bars(patch, sp)
            if head[b[1]:b[2] + 1, int(round(b[0]))].sum() < OWN_HEAD_ROWS_SP * sp]


def _max_run_and_extent(col: np.ndarray) -> Tuple[int, int, int]:
    """열 하나에서 최장 연속 잉크 런의 (길이, 시작행, 끝행)을 구한다."""
    best = run = 0
    best_s = best_e = -1
    s = 0
    for i, v in enumerate(col):
        if v:
            if run == 0:
                s = i
            run += 1
            if run > best:
                best, best_s, best_e = run, s, i
        else:
            run = 0
    return best, best_s, best_e


def _find_thin_bars(
    patch: np.ndarray, sp: float
) -> List[Tuple[float, int, int]]:
    """
    영역 안의 '얇은 세로 막대' 목록을 (중심x, 런시작행, 런끝행)으로 반환.
    막대 조건: 최장 런이 1.5~3.2sp (기둥은 창 전체를 관통해 더 길다), 폭 0.45sp 이하.
    """
    H, W = patch.shape
    runs = []
    for c in range(W):
        r, s, e = _max_run_and_extent(patch[:, c] > 0)
        runs.append((r, s, e))

    is_bar = [(sp * 1.5 <= r <= sp * 3.2) for r, _s, _e in runs]
    bars: List[Tuple[float, int, int]] = []
    c = 0
    while c < W:
        if not is_bar[c]:
            c += 1
            continue
        c2 = c
        while c2 < W and is_bar[c2]:
            c2 += 1
        if (c2 - c) <= sp * 0.45:
            mid = (c + c2 - 1) // 2
            _r, s, e = runs[mid]
            bars.append(((c + c2 - 1) / 2.0, s, e))
        c = c2
    return bars


FLAT_BAR_LEFT_SP = (0.05, 0.5)     # ♭ 고리 중심 − 왼쪽 세로획 거리 범위(sp) — `_find_glyphs` ♭ 판정


def _find_glyphs(patch: np.ndarray, sp: float, bars=None, refined: bool = False, hole_patch=None) -> List[Tuple[str, float]]:
    """
    음표 왼쪽 영역 패치 안의 임시표 후보를 **모두** (종류, 세로중심)으로 모은다.

    후보를 하나만 돌려주면 화음에서 잘못된 것을 집는다: 검사 창은 위아래 2sp라
    3도 이웃 음의 임시표까지 들어오는데, 먼저 발견된 것이 이웃의 것이면 자기
    임시표를 영영 못 본다. 그래서 여기서는 고르지 않고, 부르는 쪽이 음표 높이에
    가장 가까운 후보를 고른다.

    세로중심의 기준은 종류마다 다르다 — ♯/♮은 두 세로 막대의 중심, ♭은
    고리(구멍)의 중심이 곧 그 기호가 가리키는 음높이다.

    `bars`를 주면 그 막대 목록을 쓴다(자기 머리 막대를 뺀 목록 — 후보 2). `refined`면 ♮ 조건 ·
    H3(♯ 쌍 안쪽 칸 ♭ 제외)를 쓴다(위 NATURAL_OFFSET_SUM_SP 설명).
    """
    found: List[Tuple[str, float]] = []
    if bars is None:
        bars = _find_thin_bars(patch, sp)

    # 막대 2개: ♯ 또는 ♮
    for i in range(len(bars) - 1):
        (x1, s1, e1), (x2, s2, e2) = bars[i], bars[i + 1]
        if not (sp * 0.3 <= x2 - x1 <= sp * 0.95):
            continue
        center = ((s1 + e1) + (s2 + e2)) / 4.0
        # ♮: 왼쪽 막대가 위로, 오른쪽 막대가 아래로 어긋남
        if refined:
            natural = (s2 - s1) + (e2 - e1) > sp * NATURAL_OFFSET_SUM_SP
        else:
            natural = (s1 + sp * 0.45 < s2) and (e1 + sp * 0.45 < e2)
        if natural:
            found.append(("natural", center))
        else:
            found.append(("#", center))

    # 막대 1개 + 고리(구멍): ♭
    if bars:
        # ♭ 구멍은 hole_patch(세로 닫힘 전 오선 제거 영상, 정밀 판정 — §1-39 초안)가 있으면 거기서 찾는다.
        # 오선이 ♭ 고리를 지나면 오선 제거가 남긴 오선 행이 구멍을 위 · 아래로 가르고, 밴드의 세로 닫힘(1 × 0.4sp)이 둘 다 메운다.
        # 비보류 정답 ♭ 375: 머리가 오선 위인 88 중 37(42%) 놓침(칸 11%) — 그중 22는 원본 · 오선 제거만에선 구멍이 있고 닫힘 뒤에 사라짐.
        small = cv2.morphologyEx(
            patch if hole_patch is None else hole_patch, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        contours, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hier is not None:
            for idx in range(len(contours)):
                if hier[0][idx][3] == -1:
                    continue
                _x, _y, hw, hh = cv2.boundingRect(contours[idx])
                if sp * 0.25 <= hw <= sp * 0.9 and sp * 0.25 <= hh <= sp * 0.9:
                    # ♭의 세로획은 고리 **왼쪽**에 붙는다(기보). 위치를 안 보면 화음 기둥(고리 오른쪽) + 이웃 빈 머리 속이 ♭이 되어
                    # 그 빈 머리를 글리프로 지웠다(슈베르트 보리수 L (606,1522) 오삭제, `docs/SCHUBERT_DROP.md`). 2026-10-04 사용자 구현 승인 · DECISIONS §1-21.
                    # 범위 FLAT_BAR_LEFT_SP: 진짜 ♭ 235의 고리 중심 − 왼쪽 막대 거리 0.14~0.36sp(1~99% 0.15~0.36) → 0.05~0.5
                    if not any(FLAT_BAR_LEFT_SP[0] * sp <= _x + hw / 2 - b[0] <= FLAT_BAR_LEFT_SP[1] * sp for b in bars):
                        continue
                    # H3: ♯ 쌍(간격 0.3~0.95sp · 예전 ♮ 조건 아님)이 된 두 막대 사이 · 겹친 높이 안의 고리는 ♯ 안쪽 칸이다
                    # (E단조 4쪽 (1067,894) · 2쪽 (1736,1314)의 가짜 ♭). 측정 사본과 같게 쌍은 **예전 ♮ 조건**으로 가른다
                    rx, ry = _x + hw / 2, _y + hh / 2
                    if refined and any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95
                                       and not (p_[1] + sp * 0.45 < q[1] and p_[2] + sp * 0.45 < q[2])
                                       and p_[0] < rx < q[0] and max(p_[1], q[1]) <= ry <= min(p_[2], q[2])
                                       for p_, q in zip(bars, bars[1:])):
                        continue
                    found.append(("b", _y + hh / 2.0))
    return found


def _find_barlines(no_staff: np.ndarray, staff: Staff, img_h: int) -> List[int]:
    """
    보표의 바라인(마디선) x좌표들을 찾는다.
    조건: 오선 맨 윗줄~맨 아랫줄(4sp)을 거의 정확히 관통하는 얇은 세로 런.
    (음표 기둥은 대부분 3.5sp 이하이거나 위치가 오선 경계와 어긋난다)
    """
    sp = staff.spacing
    y0 = max(0, int(staff.top - sp * 0.35))
    y1 = min(img_h, int(staff.bottom + sp * 0.35) + 1)
    band = no_staff[y0:y1, :]
    # 오선 제거로 끊긴 세로선 복원
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    band = cv2.morphologyEx(band, cv2.MORPH_CLOSE, vk)
    H, W = band.shape

    col_run = np.zeros(W, dtype=int)
    for c in range(W):
        r, _s, _e = _max_run_and_extent(band[:, c] > 0)
        col_run[c] = r

    need = (staff.bottom - staff.top) - sp * 0.3  # 거의 오선 전체 높이
    is_line = col_run >= need
    barlines: List[int] = []
    c = 0
    while c < W:
        if not is_line[c]:
            c += 1
            continue
        c2 = c
        while c2 < W and is_line[c2]:
            c2 += 1
        if (c2 - c) <= sp * 0.4:  # 얇은 선만 (빔/굵은 덩어리 배제)
            barlines.append((c + c2 - 1) // 2)
        c = c2
    return barlines


def annotate_accidentals(
    result: PreprocessResult,
    contexts,
    pitched_notes: List[PitchedNote],
    c1: bool = True,
) -> List[str]:
    """
    각 음표에 적용되는 임시표를 판별한다 (마디 내 지속 규칙 포함).

    Args:
        result: 전처리 결과
        contexts: clef_keysig.analyze_staves() 결과 (헤더 영역 침범 방지용, None 허용)
        pitched_notes: 음고 계산이 끝난 음표 리스트

    Returns:
        pitched_notes와 같은 순서의 임시표 리스트 ("#", "b", "natural", "")
    """
    no_staff = remove_staff_lines(result.binary, result.staves)
    img_h, img_w = result.binary.shape
    staff_by_index: Dict[int, Staff] = {s.index: s for s in result.staves}
    refined = _refined(result)
    wide = WIDE_BAND_SP if refined else 0.0

    # 보표별 전처리(밴드 patched, 바라인) 캐시
    band_cache: Dict[int, Tuple[np.ndarray, int]] = {}
    barline_cache: Dict[int, List[int]] = {}

    def _get_band(staff: Staff) -> Tuple[np.ndarray, int]:
        if staff.index not in band_cache:
            sp = staff.spacing
            # 후보 1: 보표 위아래를 WIDE_BAND_SP 넓힌 뒤 ±3.5sp(측정 사본과 같은 정수 내림 순서)
            top = max(0, int(int(staff.top - wide * sp) - sp * 3.5))
            bottom = min(img_h, int(int(staff.bottom + wide * sp) + sp * 3.5))
            band = no_staff[top:bottom, :]
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            band_cache[staff.index] = (cv2.morphologyEx(band, cv2.MORPH_CLOSE, vk), top)
        return band_cache[staff.index]

    # 1) 음표별 원시(raw) 임시표 검출
    raw: List[str] = []
    c1_only = set()      # raw 번호
    for note in pitched_notes:
        staff = staff_by_index.get(note.staff_index)
        if staff is None:
            raw.append("")
            continue
        sp = staff.spacing
        band, top = _get_band(staff)

        x1 = int(note.x - sp * 0.55)
        x0 = int(note.x - sp * 2.0)
        if contexts is not None and note.staff_index in contexts:
            x0 = max(x0, contexts[note.staff_index].header_end + int(sp * 0.2))
        y0 = int(note.y - top - sp * 2.0)
        y1 = int(note.y - top + sp * 2.0)
        if x1 - x0 < sp * 0.6:
            raw.append("")
            continue
        py0 = max(0, y0)
        patch = band[py0:min(band.shape[0], y1), max(0, x0):min(band.shape[1], x1)]
        if patch.size == 0:
            raw.append("")
            continue
        bars = _bars_without_own_head(band, py0, max(0, x0), patch, sp) if refined else None
        hole_patch = no_staff[top + py0:top + py0 + patch.shape[0], max(0, x0):max(0, x0) + patch.shape[1]] if refined and c1 else None
        glyphs = _find_glyphs(patch, sp, bars=bars, refined=refined, hole_patch=hole_patch)
        # 후보 중 음표 높이에 가장 가까운 것만 자기 임시표로 인정한다.
        # 다른 높이의 글리프는 화음의 다른 성부(3도=1.0sp 이웃)의 것이다.
        # 종류 사이에는 우선순위가 있다: ♯/♮은 세로 막대 2개라는 뚜렷한 근거로
        # 잡히지만, ♭은 '구멍이 있다'는 약한 근거라 ♮의 안쪽 칸도 후보가 된다.
        # 그래서 막대쌍 후보가 높이에 맞으면 그쪽을 먼저 쓴다.
        best = ""
        for group in (("#", "natural"), ("b",)):
            cands = [(abs((top + py0 + gy) - note.y), kind)
                     for kind, gy in glyphs if kind in group]
            if cands:
                dy, kind = min(cands)
                if dy <= sp * ACCIDENTAL_Y_TOL_SP:
                    best = kind
                    break
        raw.append(best)
        # C1로만 찾은 ♭(닫힌 밴드에서는 못 찾음) — 그 ♭이 마디 안에서 전파된 음은 check(c1_flat_suspects, §1-39 초안)
        if best == "b" and hole_patch is not None and "b" not in [
                k for k, gy in _find_glyphs(patch, sp, bars=bars, refined=refined)
                if abs((top + py0 + gy) - note.y) <= sp * ACCIDENTAL_Y_TOL_SP]:
            c1_only.add(len(raw) - 1)

    # 화음 임시표 열(§1-49 초안): 화음의 임시표는 엇갈린 열로 쌓여(위 음 = 머리 가까운 열이 기본) 먼 열이 창 왼끝(머리 − 2sp) 밖으로 나간다
    # (Verovio 정답 인쇄 임시표 558 중 창 밖 38 · 그중 화음 열 16 — Schumann B (1075,689) E4♮ · Clara 3 F3♯).
    # 창을 넓히는 기각 33 · 36 · 37 · 39와 달리 **화음 머리이고 · 같은 화음 다른 머리가 이미 임시표를 읽었고(옆 열이 있다는 근거) ·
    # 넓힌 띠에 다른 음 머리가 없을 때만**(기각 39의 실패 = 넓힌 쪽에 앞 음 임시표) 읽는다. 새로 읽은 것과 그 전파는 check(`chord_column`).
    col_only = set()
    if refined:
        for i, note in enumerate(pitched_notes):
            if raw[i]:
                continue
            staff = staff_by_index.get(note.staff_index)
            if staff is None:
                continue
            sp = staff.spacing
            mates = [j for j, m in enumerate(pitched_notes) if j != i and m.staff_index == note.staff_index
                     and abs(m.x - note.x) <= sp * 0.3 and 0 < abs(m.y - note.y) <= sp * 3.0]
            if not any(raw[j] for j in mates):
                continue
            x0w = int(note.x - sp * 2.0)
            if contexts is not None and note.staff_index in contexts:
                x0w = max(x0w, contexts[note.staff_index].header_end + int(sp * 0.2))
            xl = int(note.x - sp * CHORD_COLUMN_LEFT_SP)
            if contexts is not None and note.staff_index in contexts:
                xl = max(xl, contexts[note.staff_index].header_end + int(sp * 0.2))
            if xl >= x0w:
                continue
            band, top = _get_band(staff)
            py0 = max(0, int(note.y - top - sp * 2.0))
            patch = band[py0:min(band.shape[0], int(note.y - top + sp * 2.0)), max(0, xl):int(note.x - sp * 0.55)]
            if patch.size == 0:
                continue
            bars = _bars_without_own_head(band, py0, max(0, xl), patch, sp)
            bars = _find_thin_bars(patch, sp) if bars is None else bars
            best = None
            same = lambda p, q: sp * 0.3 <= q[0] - p[0] <= sp * 0.95 and min(p[2], q[2]) - max(p[1], q[1]) >= 0.5 * min(p[2] - p[1], q[2] - q[1])
            # 같은 화음 다른 머리 높이(0.35sp 안)에 중심이 오는 쌍의 획은 그 머리의 글리프 — 다시 쓰지 않는다
            # (획 하나는 글리프 하나에만 속한다. Clara 4 L (1854,1427) · (1955,1428): 앞 화음 기둥 + C4 ♯ · ♮ 왼획이 가짜 ♯이 됐다)
            claimed = set()
            for k in range(len(bars) - 1):
                if same(bars[k], bars[k + 1]) and any(
                        abs(top + py0 + (bars[k][1] + bars[k][2] + bars[k + 1][1] + bars[k + 1][2]) / 4.0 - pitched_notes[j].y) <= sp * ACCIDENTAL_Y_TOL_SP
                        for j in mates):
                    claimed |= {k, k + 1}
            for k, ((x1, s1, e1), (x2, s2, e2)) in enumerate(zip(bars, bars[1:])):
                # 같은 글리프의 두 획 — 간격 0.3~0.95sp(`_find_glyphs`와 같음) · 세로로 짧은 획 길이의 절반 이상 겹침(남의 획끼리 쌍 배제, 기각 38)
                if not same(bars[k], bars[k + 1]) or {k, k + 1} & claimed:
                    continue
                if max(0, xl) + x1 >= x0w:
                    continue       # 왼쪽 획이 원래 창 안 — 원래 판정이 이미 본 쌍
                # 다른 음 머리(같은 화음 제외, 세로 2sp 안)의 오른끝(+0.7sp)이 왼획보다 오른쪽이면 그 획은 그 머리의 가장자리 · 기둥이다
                # (Clara 4 L (1854,1427): 앞 화음 머리 1799.6의 가장자리 1803.5 + 기둥 1809.5가 가짜 ♯). 두 획 사이에 놓인 머리는
                # 글리프 자신이 머리로 잡힌 유령이라 세지 않는다(Clara 3 B (616,1972) — ♯ 획 610 · 620 사이)
                ax1, ax2 = max(0, xl) + x1, max(0, xl) + x2
                if any(m.staff_index == note.staff_index and j not in mates and j != i and abs(m.y - note.y) <= sp * 2.0
                       and m.x < note.x - sp * 0.3 and not (ax1 < m.x < ax2) and m.x + sp * 0.7 > ax1
                       for j, m in enumerate(pitched_notes)):
                    continue
                dy = abs(top + py0 + ((s1 + e1) + (s2 + e2)) / 4.0 - note.y)
                if dy <= sp * ACCIDENTAL_Y_TOL_SP and (best is None or dy < best[0]):
                    best = (dy, "natural" if (s2 - s1) + (e2 - e1) > sp * NATURAL_OFFSET_SUM_SP else "#", max(0, xl) + x2)
            # 글리프와 화음 사이에 다른 음 머리가 있으면 그 음의 임시표일 수 있다(기각 39의 실패 경로) — 읽지 않는다
            # (위 조건이 글리프 왼쪽 머리를, 이 조건이 오른쪽 머리를 본다)
            if best and any(m.staff_index == note.staff_index and j not in mates and j != i
                            and best[2] < m.x < note.x - sp * 0.3 and abs(m.y - note.y) <= sp * 2.0
                            for j, m in enumerate(pitched_notes)):
                best = None
            if best:
                raw[i] = best[1]
                col_only.add(i)

    # 직접 적힌 임시표(전파 전) — `double_acc_kinds`의 같은 마디 취소 규칙이 읽는다. 출력은 안 바꾼다.
    # 여러 번 불린다(제품 첫 호출 → 붙은 화음 추가분 · c1=False 재판정) — 첫 값을 지키고 새 좌표만 더한다
    direct = getattr(result, "direct_accidentals", None)
    if direct is None:
        direct = result.direct_accidentals = {}
    for n, r in zip(pitched_notes, raw):
        if r:
            direct.setdefault((n.staff_index, int(n.x), int(n.y)), r)

    if not refined:
        # 사진 모드: 임시표 유령 제거가 **원시(인쇄)** 임시표로 판단하도록 남긴다(DECISIONS §1-18). 사진 아닌 입력은 남기지 않는다(동작 그대로)
        raw_map = getattr(result, "raw_accidentals", None)
        if raw_map is None:
            raw_map = {}
            result.raw_accidentals = raw_map
        raw_map.update({id(n): r for n, r in zip(pitched_notes, raw)})

    # 2) 마디 내 지속 규칙 적용
    effective = list(raw)
    pts_by_staff: Dict[int, List[Tuple[int, int]]] = {}
    for n in pitched_notes:
        pts_by_staff.setdefault(n.staff_index, []).append((int(n.x), int(n.y)))
    order = sorted(range(len(pitched_notes)), key=lambda i: (pitched_notes[i].staff_index, pitched_notes[i].x))
    active: Dict[Tuple[str, int], str] = {}
    active_c1: Dict[Tuple[str, int], bool] = {}
    active_col: Dict[Tuple[str, int], bool] = {}
    col_now = set()
    col_marked = getattr(result, "chord_column_read", None)
    if col_marked is None:
        col_marked = set()
        result.chord_column_read = col_marked
    c1_prop = getattr(result, "c1_flat_propagated", None)
    if c1_prop is None:
        c1_prop = set()
        result.c1_flat_propagated = c1_prop
    cur_staff = None
    barline_pos: List[int] = []
    next_bar = 0

    for i in order:
        note = pitched_notes[i]
        if note.staff_index != cur_staff:
            cur_staff = note.staff_index
            staff = staff_by_index.get(cur_staff)
            if staff is None:
                barline_pos = []
            else:
                # 전파 경계(§1-14)는 사진 모드에서도 켠다(2026-10-04 사용자 사전 승인 · DECISIONS §1-17): 사진 51장 표기 틀림 137 → 88, 오삭제 0
                # (경계는 지우지 않는다). ♮ · ♯ · G3 · H3(`refined`)는 사진에서 계속 끈다 — 함께 켜면 G3가 진짜 머리 1개를 지웠다(`PHOTO_TRUTH.md` §3)
                barline_pos = _propagation_barlines(result.binary, no_staff, staff, pts_by_staff.get(cur_staff, []))
            next_bar = 0
            active = {}
        # 음표가 다음 바라인을 지났으면 마디가 바뀐 것 -> 임시표 효력 초기화
        while next_bar < len(barline_pos) and note.x > barline_pos[next_bar]:
            active = {}
            next_bar += 1

        key = (note.note_name, note.octave)
        if raw[i]:
            active[key] = raw[i]
            active_c1[key] = i in c1_only
            active_col[key] = i in col_only
            if i in col_only:
                col_now.add(i)
        elif key in active:
            effective[i] = active[key]
            if active_c1.get(key):
                c1_prop.add((note.staff_index, int(note.x), int(note.y)))
            if active_col.get(key):
                col_now.add(i)

    # 여러 번 불린다(제품 첫 호출 → 붙은 화음 추가분 · 재판정) — 이번 호출이 다룬 음은 이번 결과로 표시를 다시 정한다(앞 호출의 전파가 남지 않게)
    # 예전 판정 비교용 재호출(`unstable_accidentals`의 c1=False — 같은 result)은 표시를 건드리지 않는다
    if c1:
        for i, n in enumerate(pitched_notes):
            (col_marked.add if i in col_now else col_marked.discard)((n.staff_index, int(n.x), int(n.y)))
    return effective


def filled_flags(pitched_notes: List[PitchedNote], noteheads) -> List[bool]:
    """음표마다 '채워진 머리인가'. PitchedNote에는 filled가 없어 머리 검출 결과를 좌표로 잇는다."""
    by_pos = {(h.staff_index, h.x, h.y): bool(h.filled) for h in noteheads}
    return [by_pos.get((n.staff_index, n.x, n.y), False) for n in pitched_notes]


def remove_accidental_ghosts(
    pitched_notes: List[PitchedNote],
    accidentals: List[str],
    staves: List[Staff],
    filled: Optional[List[bool]] = None,
    flagged: Optional[list] = None,
    result: Optional[PreprocessResult] = None,
) -> Tuple[List[PitchedNote], List[str]]:
    """
    임시표 글리프가 음표로 오검출된 '고스트'를 제거한다.

    특히 ♭의 고리(구멍)는 빈 음표(2분음표) 검출과 형태가 같아서 음표로 잡히기 쉽다.
    ♯/♮처럼 세로 막대 2개 + 가로 획 2개로 된 글리프는 안쪽에 칸이 2개 생겨,
    가로 획(크로스바) 위치가 음표 중심(note_y)에서 위/아래로 갈라진 두 개의
    유령으로 검출되기도 한다. 임시표가 직접 검출된 음표의 왼쪽 0.5~1.6sp,
    세로 ±ACCIDENTAL_GHOST_Y_SP 안에 있는 다른 '음표'는 사실 그 임시표
    글리프 자신이므로 제거한다(세로 범위의 근거는 그 상수 옆 설명 참조).

    **채워진 후보는 지우지 않는다**(`filled`를 주면). 지울 후보 중 채워진 머리는 남기고
    `flagged`에 담아 '사람이 확인할 것'(check)으로 넘긴다. 빈 후보는 그대로 지운다.
    근거(2026-09-22, 검증 악보 20쪽 사본 측정 `docs/ACCIDENTAL_GHOST_MEASURE.md` §15-5):
    삭제 후보 556개 중 빈 535개는 표본 40/40이 임시표 글리프였고, 채워진 21개는
    진짜 음표 18 · 글리프 3이었다(§8). 채워진 후보를 지우면 진짜 음표 18개가 오삭제되고,
    남기면 글리프 3개가 점선 붙은 유령이 된다 — 오삭제는 사용자가 알아챌 수 없으므로
    남긴다. `filled`는 확정 판별자가 아니지만(§8·§10) 여기서는 지우지 않고 표시만 하므로
    틀려도 오삭제가 생기지 않는다. `filled`를 안 주면 예전처럼 전부 지운다.

    `result`와 `filled`를 함께 주고 사진 모드가 아니면 G3(♯/♮ 글리프 칸 유령 — 위 GLYPH_BAR_SP 설명)를 더 지운다.
    """
    spacing_by_staff = {s.index: s.spacing for s in staves}
    # 사진 모드는 원시(인쇄) 임시표가 있는 음표만 기준으로 삼는다(DECISIONS §1-18, `docs/PROPAGATED_DROP.md`): 전파된 임시표만 가진 음표 왼쪽에는
    # 글리프가 없을 수 있다 — 사진(A-25 경계 켬)에서 2도 화음의 유일한 머리를 지웠다(쇼팽 blackframe). 사진 아닌 입력은 실효 기준 그대로 —
    # 거기서는 이 경로가 원시 판정이 놓친 실제 글리프 유령 29를 지우고 오삭제 0이었다
    raw_map = getattr(result, "raw_accidentals", None) if (result is not None and not _refined(result)) else None
    trigger = accidentals if raw_map is None else [a if raw_map.get(id(n)) else "" for n, a in zip(pitched_notes, accidentals)]
    drop = set()
    for j, nj in enumerate(pitched_notes):
        if not trigger[j]:
            continue
        sp = spacing_by_staff.get(nj.staff_index, 12.0)
        for i, ni in enumerate(pitched_notes):
            if i == j or ni.staff_index != nj.staff_index:
                continue
            if (sp * 0.5 <= nj.x - ni.x <= sp * 1.6
                    and abs(ni.y - nj.y) <= sp * ACCIDENTAL_GHOST_Y_SP):
                drop.add(i)

    if filled is not None:
        spared = {i for i in drop if filled[i]}
        if flagged is not None:
            flagged.extend(pitched_notes[i] for i in sorted(spared))
        drop -= spared

    kept_notes = [n for i, n in enumerate(pitched_notes) if i not in drop]
    kept_accs = [a for i, a in enumerate(accidentals) if i not in drop]
    if result is not None and filled is not None and _refined(result):
        kept_notes, kept_accs = _drop_glyph_cell_ghosts(result, staves, pitched_notes, filled, kept_notes, kept_accs)
    return kept_notes, kept_accs


def _drop_glyph_cell_ghosts(result, staves, pitched_notes, filled, kept, kaccs):
    """G3: 빈 머리 후보 자리(±0.8sp × ±2sp)에 ♯/♮ 모양(막대 둘 ≥ GLYPH_BAR_SP · 간격 0.3~0.95sp · 쌍 중심 0.5sp 안 ·
    후보가 두 막대 사이 · 사이 잉크 ≤ GLYPH_INNER_INK)이 있고 오른쪽에 주인 음표가 있으면 지운다. 채워진 후보는 건드리지 않는다."""
    no_staff = remove_staff_lines(result.binary, result.staves)
    sp_of = {s.index: s.spacing for s in staves}
    fl = {id(n): f for n, f in zip(pitched_notes, filled)}
    out_n, out_a = [], []
    for n, a in zip(kept, kaccs):
        sp = sp_of.get(n.staff_index, 12.0)
        if not fl.get(id(n), True):
            y0, x0 = max(0, int(n.y - 2 * sp)), max(0, int(n.x - 0.8 * sp))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            band = cv2.morphologyEx(no_staff[y0:int(n.y + 2 * sp), :], cv2.MORPH_CLOSE, vk)
            patch = band[:, x0:int(n.x + 0.8 * sp)]
            bars = _find_thin_bars(patch, sp)
            cx = n.x - x0

            def inner_ink(p_, q):
                r0_, r1_ = max(p_[1], q[1]), min(p_[2], q[2])
                c0_, c1_ = int(p_[0] + 0.15 * sp), int(q[0] - 0.15 * sp)
                return (patch[r0_:r1_ + 1, c0_:c1_ + 1] > 0).mean() if c1_ >= c0_ and r1_ >= r0_ else 1.0
            shape = any(sp * 0.3 <= q[0] - p_[0] <= sp * 0.95
                        and min(p_[2] - p_[1], q[2] - q[1]) + 1 >= GLYPH_BAR_SP * sp
                        and abs(y0 + (p_[1] + p_[2] + q[1] + q[2]) / 4 - n.y) <= 0.5 * sp
                        and p_[0] - 0.1 * sp <= cx <= q[0] + 0.1 * sp
                        and inner_ink(p_, q) <= GLYPH_INNER_INK
                        for p_, q in zip(bars, bars[1:]))
            owner = shape and any(o is not n and o.staff_index == n.staff_index and 0.5 * sp <= o.x - n.x <= 2.0 * sp
                                  and abs(o.y - n.y) <= 1.0 * sp for o in kept)
            if owner:
                continue
        out_n.append(n)
        out_a.append(a)
    return out_n, out_a


def unstable_accidentals(result: PreprocessResult, contexts, pitched_notes: List[PitchedNote],
                         accidentals: List[str]) -> List[PitchedNote]:
    """영상을 (0.5, 0.5)px 옮겨 **음표 검출부터 다시** 했을 때 임시표가 달라지는 음표 (2026-09-29, 사용자 승인).

    재표본화(회전 보정 등) 뒤 임시표 표기가 표시 없이 바뀌는 곳은 무작위가 아니라 **경계에 걸린 글리프 몇 곳**이었다
    (♮을 ♯으로, 붙임줄 곡선을 ♭으로 — `docs/PHOTO_PREPROCESS.md` §5-7). 그런 곳은 0.5px만 옮겨도 판정이 넘어간다.

    음표를 고정하고 임시표만 다시 판정하면 +24%로 싸지만 바흐 17건 중 14건만 잡는다 — 나머지 3건은
    **전파 원천 음표가 머리째 사라져** ♯ 전파가 끊긴 경우라 음표를 다시 찾아야 보인다. 그래서 음표 검출부터 다시 한다
    (17/17, 처리 시간 +130%, `docs/PHOTO_PREPROCESS.md` §7).

    잡지 못하는 것: 흔들리지 않고 **늘 같게 틀리는** 분류 오류(B♭m ♮/♯ — `docs/TASKS.md` A-11).
    """
    # 순환 import를 피해 안에서 부른다(verify · notehead_detect는 이 모듈을 쓰지 않지만 파이프라인 순서를 한곳에 둔다)
    from .preprocess import binarize
    from .notehead_detect import detect_noteheads
    from .verify import drop_beam_ghosts, drop_offstaff_ghosts
    from .pitch_calculator import calculate_pitches
    if not pitched_notes:
        return []
    bgr = result.original_bgr
    shift = np.array([[1.0, 0, 0.5], [0, 1.0, 0.5]])
    moved_bgr = cv2.warpAffine(bgr, shift, (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)
    gray, binary = binarize(moved_bgr)
    moved = PreprocessResult(original_bgr=moved_bgr, gray=gray, binary=binary, staves=result.staves)
    moved.photo_correction = result.photo_correction      # 같은 판정 규칙(사진 모드면 정밀 판정 끔)으로 다시 잰다
    heads = detect_noteheads(moved, contexts=contexts)
    heads, _ = drop_beam_ghosts(moved, heads)
    heads, _ = drop_offstaff_ghosts(moved, heads)
    notes2 = calculate_pitches(heads, moved.staves, clef={i: c.clef for i, c in contexts.items()})
    accs2 = annotate_accidentals(moved, contexts, notes2)
    # C1(§1-39 초안)이 흔들림을 없애 check → 확실로 오르는 틀린 라벨을 막으려고, C1 없는 예전 판정의 흔들림도 함께 본다(둘 중 하나라도 흔들리면 표시)
    old_a = annotate_accidentals(result, contexts, pitched_notes, c1=False)
    old_2 = annotate_accidentals(moved, contexts, notes2, c1=False)
    out = []
    for n, a, oa in zip(pitched_notes, accidentals, old_a):
        best, bd = None, None
        for m, b, ob in zip(notes2, accs2, old_2):
            d = abs(m.x - n.x - 0.5) + abs(m.y - n.y - 0.5)
            if m.staff_index == n.staff_index and d <= 12 and (bd is None or d < bd):
                best, bd = (b, ob), d
        if best is not None and (best[0] != a or best[1] != oa):
            out.append(n)
    return out


# C1(♭ 구멍을 닫힘 전 영상에서 찾음)으로만 읽은 ♭이 마디 안에서 전파된 음 → 「확인 필요」 (2026-10-15, 사용자 지시 3 · §1-39 초안).
# 49쪽에서 「확실」로 남은 새로 틀림 2(Bach PDF (333,2142) · (441,2142))가 이 경로: 원천 ♭은 맞게 새로 읽혔는데 뒤 음 앞의 ♮을 원래 못 읽어 전파가 넘어간다.
# 원천 음 자신(♭ 글리프가 바로 앞에 있음)은 표시하지 않는다.
def chord_column_suspects(result: PreprocessResult, notes: List[PitchedNote]) -> List[PitchedNote]:
    """화음 임시표 열(§1-49 초안)로 새로 읽은 임시표 · 그 전파를 받은 음 → check."""
    marked = getattr(result, "chord_column_read", set())
    return [n for n in notes if (n.staff_index, int(n.x), int(n.y)) in marked]


def c1_flat_suspects(result: PreprocessResult, notes: List[PitchedNote]) -> List[PitchedNote]:
    keys = getattr(result, "c1_flat_propagated", None) or set()
    return [n for n in notes if (n.staff_index, int(n.x), int(n.y)) in keys]

# 겹임시표 ♭♭ · 𝄪 → 「확인 필요」 (2026-10-15, 사용자 결정 16시 1 · DECISIONS §1-40 초안, `tools/measure_double_acc.py`) — 표시만. 사진 모드에서는 끈다.
# 제품은 ♭♭ · 𝄪을 표기하지 못한다(♭ · ♯ 하나로 읽음 — 「확실」 오류 59, `docs/ERROR_CENSUS_1015.md`). 그 머리와 같은 마디 뒤쪽 같은 음을 check로.
# 검출은 표시 전용 넓은 패치(왼쪽 DOUBLE_ACC_LEFT_SP — ♭♭ 상자 최대 2.57 · 𝄪 중심 최대 2.84sp + 여유)에서 한다. 읽기(임시표 판정)는 바꾸지 않는다.
#   ♭♭ = ♭ 구멍(세로 닫힘 전 영상 · 왼쪽 세로획, §1-39와 같은 조건) 두 개가 머리 높이 0.35sp 안에서 가로 0.35~1.2sp, 오른쪽 것은 원래 창(−2sp) 안
#   𝄪 = 세로 닫힘 전 영상을 타원(0.25sp)으로 열어 덧줄 · 기둥을 지운 뒤, 0.8~1.2sp 덩어리의 네 귀퉁이 · 가운데 잉크 ≥ 0.5 · 네 변 가운데 ≤ 0.25(✕),
#       또는 0.2~0.6sp 덩어리 4개가 2 × 2. 중심은 머리와 높이 0.35sp 안 · 머리 왼쪽 0.8~3.0sp
# 측정(비보류 45쪽, 정답 = PDF 글리프 flatflat · doublesharp): ♭♭ 정밀도 88% · 재현율 97%, 𝄪 81% · 72%.
#   표시하면 「확실」 오류 60 → check · 맞는 라벨 헛표시 9.
DOUBLE_ACC_LEFT_SP = 2.9
# 종류 확정(`double_acc_kinds`, bb/## 표기 · 재생)에만 거는 두 조건 (2026-10-18 · §1-46 초안, `tools/measure_double_acc_fp.py`) — check 표시(`double_acc_suspects`)는 그대로.
#   ♭♭: 짝이 된 두 ♭ 구멍의 **오른쪽 벽** 세로 런 < DOUBLE_FLAT_WALL_SP. ♭ 고리 오른쪽은 짧은 곡선(둥근 배)이고 ♮은 곧은 긴 획이다.
#       실측(직접 검출 ♭♭ 43): 진짜 35 최대 0.92sp · 헛검출 3(Clara 3 B · L — 16분음표 꼬리 + ♮ 고리) 최소 2.11sp → 그 사이 1.2
#   𝄪: 「덩어리 4개 2 × 2」 경로의 네 덩어리 면적 최대/최소 < DOUBLE_SHARP_AREA_RATIO. 𝄪은 꽃잎 넷이 같은 크기(대칭 글리프)다.
#       실측(직접 검출 𝄪 16): 진짜 11(이 경로) 1.01 ~ 1.29 · 헛검출 2(D♭ 1 · 6 — 셋잇단 숫자 「3」이 열림에 조각남) 2.82 → 기하평균 1.91 부근 2.0
DOUBLE_FLAT_WALL_SP = 1.2
DOUBLE_SHARP_AREA_RATIO = 2.0


def _double_sharp_at(img: np.ndarray, sp: float, ny: float, nx: float, strict: bool = False) -> bool:
    if img.size == 0:
        return False
    k = max(3, int(0.25 * sp)) | 1
    op = cv2.morphologyEx((img > 0).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, st, cen = cv2.connectedComponentsWithStats(op, connectivity=8)
    for i in range(1, n):
        x, y, w, h, _a = st[i]
        if not (0.8 * sp <= w <= 1.2 * sp and 0.8 * sp <= h <= 1.2 * sp) or abs(cen[i][1] - ny) > 0.35 * sp \
                or not (0.8 * sp <= nx - cen[i][0] <= 3.0 * sp):
            continue
        comp = lab[y:y + h, x:x + w] == i
        q = lambda r0, r1, c0, c1: comp[int(r0 * h):max(int(r0 * h) + 1, int(r1 * h)), int(c0 * w):max(int(c0 * w) + 1, int(c1 * w))].mean()
        corners = min(q(0, .3, 0, .3), q(0, .3, .7, 1), q(.7, 1, 0, .3), q(.7, 1, .7, 1))
        edges = max(q(0, .2, .4, .6), q(.8, 1, .4, .6), q(.4, .6, 0, .2), q(.4, .6, .8, 1))
        if corners >= 0.5 and q(.4, .6, .4, .6) >= 0.5 and edges <= 0.25:
            return True
    blobs = [(cen[i][0], cen[i][1], st[i][4]) for i in range(1, n) if 0.2 * sp <= st[i][2] <= 0.6 * sp and 0.2 * sp <= st[i][3] <= 0.6 * sp]
    for a in blobs:
        for b in blobs:
            if not (0.45 * sp <= b[0] - a[0] <= 0.9 * sp and abs(b[1] - a[1]) <= 0.15 * sp):
                continue
            for c in blobs:
                if not (abs(c[0] - a[0]) <= 0.15 * sp and 0.45 * sp <= c[1] - a[1] <= 0.9 * sp):
                    continue
                for d in blobs:
                    if abs(d[0] - b[0]) <= 0.15 * sp and abs(d[1] - c[1]) <= 0.15 * sp \
                            and abs((a[1] + c[1]) / 2 - ny) <= 0.35 * sp and 0.8 * sp <= nx - (a[0] + b[0]) / 2 <= 3.0 * sp:
                        areas = (a[2], b[2], c[2], d[2])
                        if not strict or max(areas) < DOUBLE_SHARP_AREA_RATIO * min(areas):
                            return True
    return False


def _right_wall_sp(img: np.ndarray, hx: float, hy: float, sp: float) -> float:
    """♭ 구멍 중심 행에서 오른쪽 첫 잉크(오른쪽 벽)의 세로 연속 길이(sp, 3열 중 최대)."""
    H, W = img.shape
    x, y = int(hx), int(hy)
    if not (0 <= y < H):
        return 0.0
    while x < W - 1 and not img[y, x]:
        x += 1
    best = 0
    for cx in range(x, min(W, x + 3)):
        if not img[y, cx]:
            continue
        top = bot = y
        while top > 0 and img[top - 1, cx]:
            top -= 1
        while bot < H - 1 and img[bot + 1, cx]:
            bot += 1
        best = max(best, bot - top + 1)
    return best / sp


def _flat_holes_xy(img: np.ndarray, sp: float, bars) -> List[Tuple[float, float]]:
    """♭ 구멍 (x, y) — `_find_glyphs`의 ♭ 크기 · 왼쪽 세로획 조건과 같다(H3 제외)."""
    if not bars or img.size == 0:
        return []
    small = cv2.morphologyEx(img, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    cs, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is None:
        return out
    for i, c in enumerate(cs):
        if hier[0][i][3] == -1:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if sp * 0.25 <= w <= sp * 0.9 and sp * 0.25 <= h <= sp * 0.9 and \
                any(FLAT_BAR_LEFT_SP[0] * sp <= x + w / 2 - b[0] <= FLAT_BAR_LEFT_SP[1] * sp for b in bars):
            out.append((x + w / 2, y + h / 2))
    return out


def _double_acc_hits(result: PreprocessResult, contexts, notes: List[PitchedNote], strict: bool = False) -> Dict[int, str]:
    """겹임시표가 바로 앞에 적힌 음표 {번호: "bb" | "##" | "?"(둘 다 걸림)}. 사진 모드는 빈 dict.
    strict = 종류 확정용 — ♭♭ 오른쪽 벽 · 𝄪 꽃잎 대칭 조건을 더한다(DOUBLE_FLAT_WALL_SP · DOUBLE_SHARP_AREA_RATIO)."""
    if not notes or not _refined(result):
        return {}
    no_staff = remove_staff_lines(result.binary, result.staves)
    img_h = result.binary.shape[0]
    staff_by_index: Dict[int, Staff] = {s.index: s for s in result.staves}
    bands: Dict[int, Tuple[np.ndarray, int]] = {}
    hit: Dict[int, str] = {}
    for i, n in enumerate(notes):
        staff = staff_by_index.get(n.staff_index)
        if staff is None:
            continue
        sp = staff.spacing
        if staff.index not in bands:
            top = max(0, int(int(staff.top - WIDE_BAND_SP * sp) - sp * 3.5))
            bottom = min(img_h, int(int(staff.bottom + WIDE_BAND_SP * sp) + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            bands[staff.index] = (cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk), top)
        band, top = bands[staff.index]
        x1, x0 = int(n.x - sp * 0.55), int(n.x - sp * 2.0)
        xe = int(n.x - sp * DOUBLE_ACC_LEFT_SP)
        if contexts is not None and n.staff_index in contexts:
            x0 = max(x0, contexts[n.staff_index].header_end + int(sp * 0.2))
            xe = max(xe, contexts[n.staff_index].header_end + int(sp * 0.2))
        xe = min(max(0, xe), max(0, x0))
        if x1 - x0 < sp * 0.6:
            continue
        py0 = max(0, int(n.y - top - sp * 2.0))
        py1 = min(band.shape[0], int(n.y - top + sp * 2.0))
        ep = band[py0:py1, xe:x1]
        ehp = no_staff[top + py0:top + py1, xe:x1]
        if ep.size == 0 or ehp.size == 0 or x1 <= xe:
            continue
        ny = n.y - top - py0
        hs = [(hx + xe, hy) for hx, hy in _flat_holes_xy(ehp, sp, _find_thin_bars(ep, sp)) if abs(hy - ny) <= 0.35 * sp]
        raw = ehp > 0
        kinds = ("bb" if any(0.35 * sp <= abs(a[0] - b[0]) <= 1.2 * sp and max(a[0], b[0]) >= x0
                             and (not strict or max(_right_wall_sp(raw, a[0] - xe, a[1], sp),
                                                    _right_wall_sp(raw, b[0] - xe, b[1], sp)) < DOUBLE_FLAT_WALL_SP)
                             for k, a in enumerate(hs) for b in hs[k + 1:]) else "") + \
                ("##" if _double_sharp_at(ehp, sp, ny, n.x - xe, strict) else "")
        if kinds:
            hit[i] = kinds if len(kinds) == 2 else "?"
    return hit


def double_acc_kinds(result: PreprocessResult, contexts, notes: List[PitchedNote]) -> Dict[int, Tuple[str, str]]:
    """겹임시표 종류 {음표 번호: ("bb" | "##", "직접" | "전파")} — 표기 · 재생층이 `annotate_accidentals` 배열에 덮어 쓸 값. 측정 단계 · 제품 미연결.
    전파 = 같은 보표 · 같은 음이름 + 옥타브 · 다음 전파 마디선 전까지(`annotate_accidentals`와 같은 규칙). 그 사이 같은 음에 새 임시표가
    직접 적히면(♭ · ♯ · ♮ · 다른 겹임시표) 거기서 끊는다. 종류를 못 가른 머리("?")는 넣지 않고 그 음의 전파도 끊는다(설계안: 강제 승격 금지)."""
    hit = _double_acc_hits(result, contexts, notes, strict=True)
    if not hit:
        return {}
    direct = getattr(result, "direct_accidentals", None) or {}
    no_staff = remove_staff_lines(result.binary, result.staves)
    out: Dict[int, Tuple[str, str]] = {}
    for staff in result.staves:
        idx = sorted((i for i, n in enumerate(notes) if n.staff_index == staff.index), key=lambda i: notes[i].x)
        if not any(i in hit for i in idx):
            continue
        bx = _propagation_barlines(result.binary, no_staff, staff, [(int(notes[i].x), int(notes[i].y)) for i in idx])
        active: Dict[Tuple[str, int], str] = {}
        nb = 0
        for i in idx:
            n = notes[i]
            while nb < len(bx) and n.x > bx[nb]:
                active, nb = {}, nb + 1
            key = (n.note_name, n.octave)
            if i in hit:
                if hit[i] == "?":
                    active.pop(key, None)
                else:
                    active[key] = hit[i]
                    out[i] = (hit[i], "직접")
            elif direct.get((n.staff_index, int(n.x), int(n.y))):
                active.pop(key, None)
            elif key in active:
                out[i] = (active[key], "전파")
    return out


def double_acc_suspects(result: PreprocessResult, contexts, notes: List[PitchedNote]) -> List[PitchedNote]:
    hit = _double_acc_hits(result, contexts, notes)
    if not hit:
        return []
    no_staff = remove_staff_lines(result.binary, result.staves)
    staff_by_index: Dict[int, Staff] = {s.index: s for s in result.staves}
    flagged = set(hit)
    for si, staff in staff_by_index.items():
        idx = sorted((i for i, n in enumerate(notes) if n.staff_index == si), key=lambda i: notes[i].x)
        bx = _propagation_barlines(result.binary, no_staff, staff, [(int(notes[i].x), int(notes[i].y)) for i in idx])
        for i in idx:
            if i in hit:
                nxt = min([b for b in bx if b > notes[i].x] or [10 ** 9])
                key = (notes[i].note_name, notes[i].octave)
                flagged |= {j for j in idx if notes[i].x < notes[j].x < nxt and (notes[j].note_name, notes[j].octave) == key}
    return [notes[i] for i in sorted(flagged)]