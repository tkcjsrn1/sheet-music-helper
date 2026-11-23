# -*- coding: utf-8 -*-
"""
사진 입력 전처리 M1 — 가장자리 잘라내기 · 전역 기울기 보정 · 안전장치 (2026-09-28).

대상은 **스캐너 · 복사기 · 거치대**로 종이와 평행하게 만든 이미지다(좌우 원근 약 0.2° 이내).
손에 든 휴대폰 촬영은 원근 때문에 이 방식으로 안 된다 — 안전장치가 거부한다(`docs/TASKS.md` P-0).

`preprocess(path, photo=True)`일 때만 쓴다. 기본 경로(photo=False)는 이 모듈을 거치지 않는다.

순서와 근거 (`docs/PHOTO_PREPROCESS.md` §5·§6):

0. 종이 영역 잘라내기(각도 추정 전) — 영상 가장자리 띠가 각도 추정을 끌지 않게
1. 전역 기울기 추정 — 행 투영이 가장 뾰족해지는 각(거친 0.05° → 미세 0.005°). 순수 회전 0.5~20°에서
   추정 오차 ≤ 0.005°(3악보 27회)
2. 회전 보정 — INTER_LINEAR 한 번. A-8 뒤 LINEAR·CUBIC·LANCZOS4는 조표 뒤집힘이 모두 0이다(NEAREST만 1).
   빈 곳은 흰색이 아니라 가장자리를 이어 채운다 — 흰색으로 채우면 새 경계가 생긴다
3. 가장자리 다시 잘라내기(A-12) — 회전으로 축에 맞춰진 종이(밝은 영역)만 남긴다. 오선 문턱은 `0.6 × 가장 긴 가로선`이라
   종이-배경 경계가 가로 전체 폭의 가짜 선이 되면 문턱이 올라가 옅은 보표가 조용히 빠진다
   (RE:Aoharu 합성: 경계 한 줄이 문턱을 18% 올려 보표 하나 소실, 잘라내면 원본과 같음)
4. 안전장치(보정·검출 뒤, `check_photo`) — **둘 다** 통과해야 한다. 하나만으로는 샜다:
   - 가로 띠별 잔여 기울기 × 내용 폭 / sp ≤ 0.21sp (보표 위치를 몰라도 된다)
   - 가로선 봉우리가 sp 간격으로 5개 이어지는데 그 자리를 덮는 보표가 없으면 「못 찾은 보표」
   - 오선이 하나도 없으면 거부 — **못 재면 통과가 아니라 거부**(`docs/MEASUREMENT_PITFALLS.md` B-5)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import cv2
import numpy as np

# 안전장치 문턱: 보표 좌우 끝 y 차이. 합성 회전·원근 실측에서 보표 소실이 시작되는 밀림
# 0.26sp(RE:Aoharu, 가장 낮은 악보)보다 한 단계 아래 — 「보표 소실 없음(최대)」 0.21sp (docs/PORTABILITY.md)
GATE_DRIFT_SP = 0.21
GATE_BANDS = 10              # 가로 띠 수(반씩 겹침). 좌우 원근 ks≈0.02까지 각을 맞춘다(§5-3)
SKEW_RANGE_DEG = 8.0         # 추정 범위 ±8°. 그보다 큰 기울기는 스캐너·거치대 입력에서 안 나온다고 본다

PHOTO_REJECT_MESSAGE = (
    "사진이 비스듬하거나 일부 악보 줄을 찾지 못해 처리를 멈췄습니다. "
    "틀린 계이름을 내놓는 대신 멈춘 것입니다. "
    "스캐너·복사기로 스캔하거나, 거치대를 써서 종이와 정면으로 평행하게 다시 찍어 주세요."
)


@dataclass
class PhotoCorrection:
    """보정 기록 — 원본 사진 좌표를 보정 영상 좌표로 옮기는 2×3 행렬(회전 후 잘라내기)."""
    angle_deg: float = 0.0
    matrix: np.ndarray = field(default_factory=lambda: np.array([[1.0, 0, 0], [0, 1.0, 0]]))
    crop: Tuple[int, int, int, int] = (0, 0, 0, 0)     # 대략의 남긴 영역(기록용). 좌표 변환은 matrix로 한다


def estimate_skew(bgr: np.ndarray, lo: float = -SKEW_RANGE_DEG, hi: float = SKEW_RANGE_DEG) -> float:
    """행 투영이 가장 뾰족해지는 기울기(도) — 영상이 기울어진 각. 바로잡으려면 `getRotationMatrix2D`에 **부호를 바꿔** 넣는다
    (`tools/measure_photo_robustness.py recover`와 같은 약속: back = −estimate_skew).

    회전 대신 전단(y − x·tanθ)으로 근사하고 잉크 좌표의 bincount 제곱합을 최대화한다.
    거친 탐색(1/4 축소, 0.05°) → 원해상도 미세 탐색(±0.1°, 0.005°). `tools/measure_photo_robustness.py`와 같은 식.
    """
    from .preprocess import binarize
    _, binary = binarize(bgr)

    def best(bin_img, angles):
        ys, xs = np.nonzero(bin_img)
        if len(ys) == 0:
            return 0.0
        xs = xs - bin_img.shape[1] / 2
        top = None
        for a in angles:
            yy = np.round(ys - xs * math.tan(math.radians(a))).astype(np.int64)
            yy -= yy.min()
            score = float((np.bincount(yy).astype(np.float64) ** 2).sum())
            if top is None or score > top[0]:
                top = (score, a)
        return top[1]

    small = cv2.resize(binary, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    coarse = best(small > 127, np.arange(lo, hi + 1e-9, 0.05))
    return -best(binary, np.arange(coarse - 0.1, coarse + 0.1 + 1e-9, 0.005))


def _page_box(bgr: np.ndarray) -> Tuple[int, int, int, int]:
    """종이(밝은 영역) 사각형. 배경이 없으면(종이가 영상을 꽉 채움) 영상 전체.

    Otsu로 밝음/어두움을 나누고, 악보 잉크 구멍을 닫기(closing)로 메운 뒤 가장 큰 밝은 덩어리의 외접 사각형.
    배경이 없는 스캔은 Otsu가 잉크/종이를 나누므로 닫기 뒤 덩어리가 영상 전체가 된다.
    """
    h, w = bgr.shape[:2]
    scale = 800.0 / max(h, w)
    small = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    _, bright = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = max(3, int(min(small.shape) * 0.03)) | 1
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bright)
    if n <= 1:
        return 0, 0, w, h
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, bw, bh = stats[i, :4]
    if bw * bh < 0.3 * small.shape[0] * small.shape[1]:      # 종이라기엔 작다 — 자르지 않는다
        return 0, 0, w, h
    # 경계의 번짐 한 줄을 확실히 빼도록 축소 영상 1px 만큼 안쪽으로
    x0, y0 = int((x + 1) / scale), int((y + 1) / scale)
    x1, y1 = int((x + bw - 1) / scale), int((y + bh - 1) / scale)
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def _cuts_content(bgr: np.ndarray, box: Tuple[int, int, int, int]) -> bool:
    """잘라낼 영역(사각형 밖)에 **오선 같은 내용**이 있나 — 긴 가로 런 행 묶음이 5개 이상이면 그렇다고 본다.

    종이-배경 경계나 복사기 테두리는 가로 런 묶음이 한두 개다. 오선은 보표 하나에 다섯 줄이다.
    2026-09-28 합성: 한쪽 그림자(왼쪽이 어두움)를 Otsu가 배경으로 보고 음자리표·조표 쪽을 잘라내
    바흐 133개 소실 · D♭·F 조표 소실 — 안전장치는 잘린 뒤의 영상만 봐서 몰랐다(못 재면 통과).
    """
    from .preprocess import binarize
    _, binary = binarize(bgr)
    h, w = binary.shape
    x0, y0, x1, y1 = box
    if x0 <= 0 and y0 <= 0 and x1 >= w and y1 >= h:
        return False
    long_runs = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 30), 1)))
    outside = np.ones_like(binary, bool)
    outside[y0:y1, x0:x1] = False
    rows = np.flatnonzero(((long_runs > 0) & outside).any(axis=1))
    groups = 0 if len(rows) == 0 else 1 + int((np.diff(rows) > 2).sum())
    return groups >= 5


def correct_photo(bgr: np.ndarray) -> Tuple[np.ndarray, PhotoCorrection]:
    """종이 잘라내기 → 기울기 보정 → 종이 잘라내기. 재표본화는 회전 한 번뿐이다.

    첫 잘라내기는 각도 추정 전에 한다 — 복사기 검은 테두리처럼 영상 가장자리에 붙은 수평 띠가 있으면
    행 투영이 종이 대신 그 띠를 따라 0°를 낸다(2026-09-28 합성: 2° 기울인 바흐·D♭에 검은 테두리를 두자
    추정이 틀려 안전장치가 띠 잔여 5sp로 거부). 둘째 잘라내기는 회전으로 축에 맞춰진 종이의 경계를 뗀다.
    """
    x0, y0, x1, y1 = _page_box(bgr)
    if _cuts_content(bgr, (x0, y0, x1, y1)):        # 내용을 자르게 되면 자르지 않는다
        x0, y0, x1, y1 = 0, 0, bgr.shape[1], bgr.shape[0]
    first = bgr[y0:y1, x0:x1]
    h, w = first.shape[:2]
    angle = -estimate_skew(first)               # 바로잡는 각
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    # 폭 전체에서 밀림이 2px 이하면 돌리지 않는다 — 기울지 않은 PDF 렌더에서도 추정이 0.025° 안팎으로 흔들려
    # (바흐 1쪽 −0.025° = 1.1px) 쓸데없는 재표본화를 한 번 더 하게 된다. 2px는 sp 11.6(검증 최저)의 0.17sp
    if abs(math.tan(math.radians(angle))) * w > 2.0:
        work = cv2.warpAffine(first, rot, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    else:
        work, rot, angle = first, np.array([[1.0, 0, 0], [0, 1.0, 0]]), 0.0
    a0, b0, a1, b1 = _page_box(work)
    if _cuts_content(work, (a0, b0, a1, b1)):
        a0, b0, a1, b1 = 0, 0, work.shape[1], work.shape[0]
    # 원본 → 보정 영상: 첫 잘라내기 이동 → 회전 → 둘째 잘라내기 이동
    t1 = np.array([[1.0, 0, -x0], [0, 1.0, -y0], [0, 0, 1.0]])
    r = np.vstack([rot, [0, 0, 1.0]])
    t2 = np.array([[1.0, 0, -a0], [0, 1.0, -b0], [0, 0, 1.0]])
    m = (t2 @ r @ t1)[:2]
    return work[b0:b1, a0:a1].copy(), PhotoCorrection(angle_deg=angle, matrix=m,
                                                      crop=(x0 + a0, y0 + b0, x0 + a1, y0 + b1))


def check_photo(result) -> Tuple[bool, str]:
    """보정·오선 검출이 끝난 결과를 검사한다. (통과 여부, 거부 사유). 사유는 기록용이다."""
    from scipy.signal import find_peaks
    from .preprocess import staff_line_profile
    staves = result.staves
    if not staves:
        return False, "오선 없음"
    img, binary = result.original_bgr, result.binary
    H = img.shape[0]
    sp = float(np.median([s.spacing for s in staves]))
    cols = np.flatnonzero((binary > 0).sum(axis=0) > H * 0.01)
    width = (cols[-1] - cols[0]) if len(cols) else binary.shape[1]

    # 1) 가로 띠별 잔여 기울기. 긴 가로 런(6sp)이 없는 띠(제목 글자·여백)만 건너뛴다 —
    #    6sp는 잔여 1°에서도 0.1sp만 밀려 오선 런이 끊기지 않는다(못 재서 건너뛰는 일을 막는다)
    h = 2 * H // (GATE_BANDS + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * 6)), 1))
    worst = 0.0
    for i in range(GATE_BANDS):
        y0 = i * h // 2
        band = binary[y0:y0 + h]
        if (cv2.morphologyEx(band, cv2.MORPH_OPEN, kernel) > 0).mean() < 0.002:
            continue
        th = estimate_skew(img[y0:y0 + h], -3.0, 3.0)
        worst = max(worst, abs(math.tan(math.radians(th))) * width / sp)
    if worst > GATE_DRIFT_SP:
        return False, f"띠 잔여 기울기 {worst:.2f}sp"

    # 2) 덮이지 않은 오선 구조 — 봉우리 문턱은 검출된 오선 봉우리 높이 중앙값의 0.3배
    prof = staff_line_profile(binary).astype(float)
    line_h = [prof[y] for s in staves for y in s.line_ys]
    peaks, _ = find_peaks(prof, height=0.3 * float(np.median(line_h)), distance=max(2, int(sp * 0.5)))
    covered = np.zeros(H, bool)
    for s in staves:
        covered[max(0, int(s.top - sp)):int(s.bottom + sp) + 1] = True
    free = [int(y) for y in peaks if not covered[y]]
    run = 1
    for a, b in zip(free, free[1:]):
        if abs((b - a) - sp) <= 0.2 * sp:
            run += 1
            if run == 5:
                return False, f"못 찾은 보표(y≈{a})"
        else:
            run = 1
    return True, f"띠 잔여 {worst:.2f}sp"
