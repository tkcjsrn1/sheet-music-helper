# -*- coding: utf-8 -*-
"""
1단계: 이미지 전처리 및 오선지(Staff Lines) 검출 모듈

입력된 악보 이미지(png/jpg/pdf)를 불러와 그레이스케일 -> 이진화 처리하고,
가로 방향 픽셀 투영(horizontal projection profile)을 이용해 오선 위치를 검출한다.
검출된 오선들은 5줄 단위로 그룹핑되어 '보표(Staff)' 단위로 정리된다.
"""

from __future__ import annotations

import itertools
import os
from dataclasses import dataclass, field
from typing import List, Tuple

import cv2
import numpy as np
from scipy.signal import find_peaks


# ------------------------------------------------------------------
# 예외 클래스 정의
# ------------------------------------------------------------------
class SheetMusicImageError(Exception):
    """이미지 로드 관련 오류 (파일 없음, 지원하지 않는 포맷 등)"""


class StaffNotFoundError(Exception):
    """오선지를 하나도 검출하지 못했을 때 발생시키는 예외"""


class PhotoRejectedError(StaffNotFoundError):
    """사진 입력(photo=True)의 안전장치가 처리를 거부했다. 메시지가 그대로 사용자 안내가 된다.

    StaffNotFoundError를 이어받아 CLI·GUI의 기존 1단계 오류 경로로 안내가 나간다.
    """

    def __init__(self, reason: str = ""):
        from .photo_correct import PHOTO_REJECT_MESSAGE
        super().__init__(PHOTO_REJECT_MESSAGE)
        self.reason = reason            # 기록용(거부 사유). 화면에는 안내 문구만


# ------------------------------------------------------------------
# 데이터 구조 정의
# ------------------------------------------------------------------
@dataclass
class Staff:
    """하나의 보표(5개 오선)를 표현하는 데이터 클래스"""

    line_ys: List[int]              # 오선 5개의 y좌표 (위에서 아래 순서). 행 인덱스라 정수다
    spacing: float                  # 오선 간 간격(px) - 음고 계산의 기준 단위.
                                    # **최소제곱 직선의 기울기다**(아래 group_into_staves 참고)
    index: int                      # 악보 내 몇 번째 보표인지 (0부터 시작)
    bottom_fit: float = 0.0         # 최소제곱 직선이 말하는 맨 아랫줄 y. 반칸 격자의 원점

    @property
    def top(self) -> int:
        return self.line_ys[0]

    @property
    def bottom(self) -> int:
        return self.line_ys[-1]

    @property
    def grid_bottom(self) -> float:
        """반칸 격자의 원점.

        `line_ys`는 `find_peaks`가 준 **행 인덱스**라 ±0.5px 양자화돼 있다.
        음고는 반칸(=spacing/2) 단위로 반올림하므로 이 오차가 그대로 경계까지 밀어붙인다
        (실측: 여유 0.12px짜리가 있었다). 그래서 격자 계산에는 다섯 줄 전부로 맞춘
        직선 값을 쓴다. 이미지에서 오려내는 좌표에는 `top`/`bottom`(정수)을 그대로 쓴다.
        """
        return self.bottom_fit or float(self.line_ys[-1])


@dataclass
class PreprocessResult:
    """전처리 단계의 최종 산출물을 담는 컨테이너"""

    original_bgr: np.ndarray            # 원본 컬러 이미지 (합성 결과 저장용)
    gray: np.ndarray                    # 그레이스케일 이미지
    binary: np.ndarray                  # 이진화 이미지 (흰 글자=255, 배경=0)
    staves: List[Staff] = field(default_factory=list)  # 검출된 보표 목록
    photo_correction: object = None     # photo=True일 때 보정 기록(photo_correct.PhotoCorrection), 아니면 None
    deskew_deg: float = 0.0             # 일반 모드 작은 기울기 보정으로 돌린 각(바로잡는 각, 도). 0이면 안 돌림 — `_small_deskew`


# ------------------------------------------------------------------
# 1. 이미지 로드 (png / jpg / pdf 지원)
# ------------------------------------------------------------------
def pdf_page_count(path: str) -> int:
    """PDF의 전체 페이지 수. PDF가 아니거나 PyMuPDF가 없으면 1."""
    if not path.lower().endswith(".pdf"):
        return 1
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return 1
    try:
        with fitz.open(path) as doc:
            return len(doc)
    except Exception:
        return 1


def load_image(path: str, pdf_page: int = 0, pdf_dpi: int = 300) -> np.ndarray:
    """
    악보 파일을 불러와 OpenCV BGR numpy 배열로 반환한다.

    Args:
        path: 이미지(.png/.jpg/.jpeg) 또는 PDF(.pdf) 파일 경로
        pdf_page: PDF일 경우 렌더링할 페이지 번호 (0부터 시작)
        pdf_dpi: PDF를 이미지로 변환할 때의 해상도 (높을수록 음표 검출이 정밀해짐)

    Raises:
        SheetMusicImageError: 파일이 없거나, 지원하지 않는 확장자거나, 디코딩에 실패한 경우
    """
    if not os.path.isfile(path):
        raise SheetMusicImageError(f"파일을 찾을 수 없습니다: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        # PDF는 PyMuPDF(fitz)로 렌더링한다. Poppler 같은 외부 바이너리 설치가 필요 없어
        # Windows 환경에서 의존성 관리가 간단하다.
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            import sys
            if getattr(sys, "frozen", False):
                # 배포용 exe에는 라이선스(AGPL) 문제로 PyMuPDF를 포함하지 않는다
                raise SheetMusicImageError(
                    "배포판 exe는 PDF 입력을 지원하지 않습니다. "
                    "악보를 PNG/JPG 이미지로 캡처해서 사용해주세요."
                ) from e
            raise SheetMusicImageError(
                "PDF를 처리하려면 PyMuPDF가 필요합니다. `pip install PyMuPDF`로 설치해주세요."
            ) from e

        doc = fitz.open(path)
        if pdf_page >= len(doc):
            raise SheetMusicImageError(
                f"PDF 페이지 범위 초과: 요청={pdf_page}, 전체 페이지 수={len(doc)}"
            )
        zoom = pdf_dpi / 72.0  # PDF 기본 해상도(72dpi) 대비 확대 배율 계산
        matrix = fitz.Matrix(zoom, zoom)
        pix = doc[pdf_page].get_pixmap(matrix=matrix)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        # RGB(A) -> BGR 변환 (OpenCV 표준 채널 순서로 맞춤)
        if pix.n == 4:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        doc.close()
        return bgr

    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        # 한글 경로(예: 바탕화면\악보헬퍼) 대응을 위해 np.fromfile + imdecode 사용.
        # cv2.imread는 비-ASCII 경로에서 실패하는 경우가 있기 때문.
        try:
            data = np.fromfile(path, dtype=np.uint8)
            bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception as e:
            raise SheetMusicImageError(f"이미지 디코딩 실패: {path} ({e})") from e

        if bgr is None:
            raise SheetMusicImageError(f"이미지 디코딩 실패(손상된 파일 가능성): {path}")
        return bgr

    else:
        raise SheetMusicImageError(f"지원하지 않는 파일 확장자입니다: {ext}")


# ------------------------------------------------------------------
# 2. 그레이스케일 변환 + 이진화
# ------------------------------------------------------------------
def binarize(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    컬러 이미지를 그레이스케일로 변환한 뒤, 적응형 이진화(adaptive threshold)를 적용한다.
    악보는 인쇄 스캔본마다 밝기 편차가 크기 때문에 전역 임계값보다 적응형 임계값이 안정적이다.

    Returns:
        (gray, binary): gray는 8bit 그레이스케일, binary는 배경=0/전경(음표,오선)=255
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 가우시안 블러로 스캔 노이즈를 살짝 제거 (오선 검출 시 잡음 피크 방지)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 적응형 이진화: THRESH_BINARY_INV로 어두운 잉크 부분을 흰색(255) 전경으로 만든다.
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=25,   # 지역 임계값 계산 윈도우 크기 (홀수 필수)
        C=10,           # 임계값에서 뺄 상수 (값이 클수록 더 어두운 픽셀만 전경으로 인정)
    )
    return gray, binary


# ------------------------------------------------------------------
# 3. 오선(Staff Lines) 검출
# ------------------------------------------------------------------
def staff_line_profile(binary: np.ndarray) -> np.ndarray:
    """
    행별 '수평선 픽셀 수' 프로파일을 계산한다.
    가로로 긴 구조 요소로 모폴로지 오프닝을 적용해 음표 머리 같은 짧은 도형은
    제거하고, 오선처럼 길게 이어진 수평 성분만 남긴 뒤 행 단위로 합산한다.
    """
    width = binary.shape[1]
    kernel_len = max(15, width // 30)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))
    staff_only = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    return staff_only.sum(axis=1) / 255.0


def detect_staff_lines(
    binary: np.ndarray,
    min_line_ratio: float = 0.5,
) -> List[int]:
    """
    이진화 이미지의 가로 방향 픽셀 투영(row-wise sum)을 이용해 오선의 y좌표를 검출한다.
    오선은 이미지 폭에 가깝게 길게 이어진 수평선이므로, 각 행(row)의 흰 픽셀 합이
    이미지 폭의 일정 비율(min_line_ratio) 이상인 행을 오선 후보로 간주한다.

    Args:
        binary: binarize()의 결과 (전경=255)
        min_line_ratio: 오선으로 판단할 최소 픽셀 비율 (이미지 폭 대비)

    Raises:
        StaffNotFoundError: 오선 후보가 하나도 검출되지 않은 경우
    """
    height, width = binary.shape
    row_sum = staff_line_profile(binary)

    # 임계값은 이미지 폭이 아니라 '가장 긴 수평선(=실제 오선 길이)' 기준으로 잡는다.
    # 스크린샷처럼 악보 양옆에 여백/검은 배경이 넓게 있으면 오선이 이미지 폭의
    # 절반에 못 미쳐 검출을 통째로 놓치기 때문. 단, 최소한 폭의 25%는 되어야
    # 짧은 낙서 수준의 선을 오선으로 오인하지 않는다.
    ref = float(row_sum.max())
    if ref < width * 0.25:
        raise StaffNotFoundError(
            "오선으로 볼 만한 긴 수평선이 없습니다. 악보 이미지가 맞는지 확인해주세요."
        )
    threshold = max(ref * 0.6, width * min_line_ratio * 0.5)
    # scipy의 find_peaks로 지역 최댓값(오선 중심)을 찾는다.
    # distance=2로 인접 행이 중복 검출되는 것을 방지한다.
    peaks, _ = find_peaks(row_sum, height=threshold, distance=2)
    peaks = _merge_plateau_peaks(sorted(int(p) for p in peaks), row_sum)

    if len(peaks) == 0:
        raise StaffNotFoundError(
            "오선을 검출하지 못했습니다. 이미지 해상도가 낮거나, "
            "스캔 상태(기울어짐/저대비)를 확인해주세요."
        )

    return sorted(int(p) for p in peaks)


# 굵은 오선 한 줄의 평평한 꼭대기 (2026-10-04, 사용자 승인 · A-24, docs/STAFF_PEAKS.md · DECISIONS §1-15).
# 고해상도(≈ 400dpi 이상)에서 오선 한 줄이 3행 두께가 되면 가운데 행이 양옆보다 1~2화소 적어 `find_peaks(distance=2)`가
# 봉우리 둘을 받는다(D♭ 5쪽 행 투영 2966 · 2964 · 2966) → 그 보표가 선 6개 → 5줄 묶기에서 빠짐. 600dpi PDF 17쪽 중 7쪽.
# 이웃 봉우리가 PLATEAU_GAP_ROWS 행 이내이고 그 사이 골이 낮은 봉우리의 PLATEAU_VALLEY 이상이면 한 줄(가운데)로 본다.
#   3행: 굵은 줄의 두 봉우리 간격 실측 2행 · 진짜 이웃 오선은 오선 간격만큼(측정 세트 최소 sp 11.5px) 떨어진다
#   0.9: 굵은 줄 골 실측 99.96% · 진짜 이웃 오선 사이 골은 잉크 0에 가깝다 — 그 사이 어디든 갈리며 보수적으로 0.9
# 측정: 300dpi PDF · Aoharu · Verovio · 픽스처 · 보지 않은 악보는 봉우리 목록 변화 0, 600dpi 보표 수 10 → 17/17 쪽
PLATEAU_GAP_ROWS = 3
PLATEAU_VALLEY = 0.9


def _merge_plateau_peaks(peaks: List[int], row_sum: np.ndarray) -> List[int]:
    out: List[int] = []
    for p in peaks:
        if (out and p - out[-1] <= PLATEAU_GAP_ROWS
                and row_sum[out[-1]:p + 1].min() >= PLATEAU_VALLEY * min(row_sum[out[-1]], row_sum[p])):
            out[-1] = (out[-1] + p) // 2
        else:
            out.append(p)
    return out


# ------------------------------------------------------------------
# 4. 검출된 오선을 5줄 단위 보표(Staff)로 그룹핑
# ------------------------------------------------------------------
def group_into_staves(line_ys: List[int], row_sum: "np.ndarray | None" = None) -> List[Staff]:
    """
    검출된 오선 y좌표 리스트를 5개씩 묶어 보표(Staff) 객체로 변환한다.

    실사 악보(스크린샷/사진)에서는 UI 요소가 가짜 수평선으로 끼어들거나,
    한 줄이 약하게 찍혀 4줄만 검출되는 경우가 흔하다. 이를 견디도록:
      1. '5줄 이상 모여야 분리'라는 조건 없이 간격(2.5x 기준)만으로 순수 분리한다
         (기존 방식은 4줄짜리 보표가 다음 보표를 삼켜 9줄 그룹이 되는 문제가 있었다)
      2. 4줄 그룹은 빠진 줄을 보간/탐색으로 복구, 6줄 그룹은 잡음 줄 하나 제거,
         8줄 이상 그룹은 가장 큰 간격에서 쪼개 재처리한다
      3. 1~3줄 그룹(화면 UI, 제목 밑줄 등 잡음)은 폐기한다

    Args:
        line_ys: 검출된 오선 y좌표 (정렬됨)
        row_sum: 행별 수평선 픽셀 프로파일. 4줄 그룹 복구 시 빠진 줄이
                 위/아래 어느 쪽인지 판단하는 데 사용 (없으면 위쪽 우선)

    Raises:
        StaffNotFoundError: 복구 후에도 유효한 5줄 보표가 하나도 없는 경우
    """
    n = len(line_ys)
    if n < 4:
        raise StaffNotFoundError(
            f"검출된 오선이 {n}개뿐입니다(최소 4개 필요). 오선 검출 파라미터를 조정해주세요."
        )

    gaps = [line_ys[i + 1] - line_ys[i] for i in range(n - 1)]
    small = [g for g in gaps if g < 40]
    space = float(np.median(small)) if small else float(np.median(gaps))

    # 1) 간격 기준 순수 분리
    groups: List[List[int]] = []
    cur = [line_ys[0]]
    for i in range(1, n):
        if line_ys[i] - line_ys[i - 1] > space * 2.5:
            groups.append(cur)
            cur = [line_ys[i]]
        else:
            cur.append(line_ys[i])
    groups.append(cur)

    # 2) 그룹 수리
    fixed: List[List[int]] = []
    queue = list(groups)
    while queue:
        g = queue.pop(0)
        if len(g) == 5:
            fixed.append(g)
        elif len(g) == 4:
            gg = [g[i + 1] - g[i] for i in range(3)]
            doubled = [i for i, x in enumerate(gg) if x > space * 1.6]
            if len(doubled) == 1:
                # 중간 줄이 빠진 경우: 2배 간격 한가운데에 보간
                i = doubled[0]
                fixed.append(sorted(g + [int(round((g[i] + g[i + 1]) / 2))]))
            else:
                # 맨 위/아래 줄이 빠진 경우: 프로파일 값이 큰 쪽(실제 선이 있는 쪽)을 선택
                up = int(round(g[0] - space))
                dn = int(round(g[-1] + space))
                if row_sum is not None and 0 <= up and dn < len(row_sum):
                    up_v = float(row_sum[max(0, up - 1):up + 2].max())
                    dn_v = float(row_sum[max(0, dn - 1):dn + 2].max())
                    fixed.append(sorted(g + [up if up_v >= dn_v else dn]))
                elif up >= 0:
                    fixed.append(sorted(g + [up]))
                else:
                    fixed.append(sorted(g + [dn]))
        elif len(g) in (6, 7):
            # 줄이 남는 그룹: 오선이 아닌 것이 섞여 들어온 경우다. 굵은 빔이
            # 오선만큼 길게 이어지면 수평선 프로파일에서 오선과 구별되지 않아
            # 바로 아래 보표에 달라붙는다 (실측: 쇼팽 D♭ 5쪽에서 오선 5줄 뒤에
            # 32분음표 빔 2줄이 붙어 7줄 그룹이 됐다).
            # 그래서 '남는 줄을 골라 버리는' 대신 **등간격 5줄을 골라 남긴다**.
            # 판정 기준은 아래 3)단계의 검증과 같은 것을 쓴다 — 새 문턱값을
            # 만들면 두 곳이 따로 놀아 나중에 어긋난다.
            best = None
            for combo in itertools.combinations(g, 5):
                d = [combo[i + 1] - combo[i] for i in range(4)]
                sp = float(np.mean(d))
                if float(np.std(d)) > sp * 0.25 or not (space * 0.6 <= sp <= space * 1.6):
                    continue
                score = float(np.std(d)) / sp
                if best is None or score < best[0]:
                    best = (score, list(combo))
            if best is not None:
                fixed.append(best[1])
            elif len(g) == 6:
                # 어느 5줄도 조건을 못 넘기면 예전처럼 끝 줄 하나만 떼어 본다
                # (3)단계 검증이 한 번 더 거르므로 잘못 통과해도 걸린다)
                def _unif(x: List[int]) -> float:
                    d = [x[i + 1] - x[i] for i in range(len(x) - 1)]
                    return float(np.std(d))
                g1, g2 = g[1:], g[:-1]
                fixed.append(g1 if _unif(g1) < _unif(g2) else g2)
        elif len(g) >= 8:
            # 두 보표가 붙어버린 경우: 가장 큰 간격에서 쪼개 재처리
            gg = [g[i + 1] - g[i] for i in range(len(g) - 1)]
            k = int(np.argmax(gg))
            queue.append(g[:k + 1])
            queue.append(g[k + 1:])
        # 1~3줄 그룹(화면 UI, 제목 밑줄 등)은 잡음으로 폐기

    # 3) 간격 균일성 검증
    valid: List[List[int]] = []
    for g in fixed:
        if len(g) != 5:
            continue
        d = [g[i + 1] - g[i] for i in range(4)]
        sp = float(np.mean(d))
        if np.std(d) > sp * 0.25 or not (space * 0.6 <= sp <= space * 1.6):
            continue
        valid.append(g)
    valid.sort(key=lambda g: g[0])

    if not valid:
        raise StaffNotFoundError(
            "오선 후보는 검출되었지만 5줄 단위 보표로 그룹핑하지 못했습니다. "
            "min_line_ratio 값을 낮추거나 이미지 회전(기울기)을 보정해보세요."
        )

    return [_fit_staff(g, idx) for idx, g in enumerate(valid)]


# 짧은 시스템 추가 검출 (2026-10-02, TASKS [2](b) · docs/SHORT_LAST_SYSTEM.md · DECISIONS §1-11).
#
# 오선 문턱 `max(0.6 × ref, 0.25 × 폭)`은 양끝 맞춤하지 않은 짧은 마지막 시스템을 통째로 놓친다
# (Verovio Mozart L 오선 행합 1,046 < 1,201 · Schumann L 243 < 폭 항 525 — 경고 없이 그 줄 음표 전부 누락).
# 문턱을 내리는 대신 **이미 찾은 보표 위아래 1sp 바깥(빈 구간)에서만** 열림 커널 길이(이 파일의
# 「가로선」 정의) 이상인 봉우리로 5줄을 더 찾는다 — 기존 보표 · 그 선은 바뀔 수 없다.
#
# SHORT_STAFF_OVERLAP: 5줄 공통 x 구간 / 전체 x 구간. **기보 규칙 「보표 5줄은 같은 x 범위를 덮는다」.**
#   진짜  제품이 찾은 보표 3,662(사진 · 압박 입력 포함) 1백분위 0.84 · 짧은 시스템 4개 1.00
#   가짜  D♭ 6쪽 페달 괄호선 −0.72 · 보정 없는 회전 0.5° 사진의 오선 조각(한 오선이 여러 행에 걸침) 최대 0.33
#   √(0.84 × 0.33) = 0.53. 462 입력에서 더한 7개 전부 진짜 · 오검출 0
# 길이비(최소 / 최대 행합)는 쓰지 않는다 — 회전 조각 묶음이 0.99까지 나와 못 가른다.
# **못 살리는 것**: 휜 오래된 스캔(Satie)의 진짜 보표 0.47 · 0.52 — 지금도 놓치던 것.
# **못 거르는 것**: 표처럼 같은 길이 · 등간격인 5줄(측정 입력에서 0건).
SHORT_STAFF_OVERLAP = 0.53


def _add_short_staves(binary: np.ndarray, staves: List[Staff]) -> List[Staff]:
    """기존 보표 밖 빈 구간에서 짧은 보표를 더 찾아 y 순서로 합친다(번호는 다시 매긴다)."""
    if not staves:
        return staves
    width = binary.shape[1]
    kernel_len = max(15, width // 30)                   # staff_line_profile과 같은 열림
    staff_only = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1)))
    row_sum = staff_only.sum(axis=1) / 255.0
    sp = float(np.median([s.spacing for s in staves]))
    taken = [(s.top - sp, s.bottom + sp) for s in staves]
    peaks, _ = find_peaks(row_sum, height=kernel_len, distance=2)
    free = [int(y) for y in peaks if not any(a <= y <= b for a, b in taken)]

    def extent(y: int) -> Tuple[int, int]:
        cols = np.flatnonzero(staff_only[y])
        return int(cols[0]), int(cols[-1])

    added: List[List[int]] = []
    i = 0
    while i + 5 <= len(free):
        g = free[i:i + 5]
        d = np.diff(g)
        m = float(np.mean(d))
        # 간격은 group_into_staves 3)단계 검증과 같은 조건
        if np.std(d) <= m * 0.25 and sp * 0.6 <= m <= sp * 1.6:
            ext = [extent(y) for y in g]
            common = min(e[1] for e in ext) - max(e[0] for e in ext)
            span = max(e[1] for e in ext) - min(e[0] for e in ext)
            if common / max(1, span) >= SHORT_STAFF_OVERLAP:
                added.append(g)
                i += 5
                continue
        i += 1
    if not added:
        return staves
    groups = sorted([list(s.line_ys) for s in staves] + added, key=lambda g: g[0])
    return [_fit_staff(g, idx) for idx, g in enumerate(groups)]


def _fit_staff(g: List[int], idx: int) -> Staff:
    """검출된 오선 5줄에 직선을 맞춰 간격과 격자 원점을 정한다.

    **인접 차분의 평균을 쓰면 안 된다.** `mean([g1-g0, g2-g1, g3-g2, g4-g3])`은
    망원 합이라 `(g4 - g0) / 4`와 **항등**이다 — 양 끝 두 줄만 쓰고 가운데 세 줄을
    통째로 버린다. 오선은 최소제곱 직선 대비 최대 0.70px로 거의 완벽한 직선인데
    (보표 70개 실측), 추정기가 그 정보를 버리고 있었다.

    다섯 줄 전부로 맞추면 반칸 격자의 잔차가 0.45 이상인 라벨이
    **15개에서 4개로** 준다(라벨 1767개 실측). 자세한 근거는 `WORKLOG.md` 2026-08-29.
    """
    ys = [float(v) for v in g]
    # 등간격 인덱스 0..4에 대한 최소제곱 기울기의 닫힌 형태.
    # 분모 sum((i-2)^2) = 4+1+0+1+4 = 10
    slope = (-2 * ys[0] - ys[1] + ys[3] + 2 * ys[4]) / 10.0
    mean_y = sum(ys) / 5.0
    return Staff(
        line_ys=g,
        spacing=slope,
        index=idx,
        bottom_fit=mean_y + 2.0 * slope,   # i=4에서의 직선 값
    )


# ------------------------------------------------------------------
# 5. 전체 파이프라인 진입점
# ------------------------------------------------------------------
# 일반 모드 작은 기울기 보정 (2026-10-13 · DECISIONS §1-34 · 병합 전 사용자 승인 대상, `docs/INPUTS_REVIEW.md` §5 · §6)
# 일반 모드는 1°만 기울어도 오선 행 합 봉우리가 퍼져 오선을 못 찾고 거부한다(열화 세트 9/24). 사진 모드와 **같은 추정**
# (`photo_correct.estimate_skew`)으로 각을 재고, 아래 두 조건이면 그만큼 돌린 영상으로 처리한다. 잘라내기 · 안전장치는 하지 않는다.
#   DESKEW_MAX_DEG 3.005° = 지원 목표 3°(열화 세트 rot3) + 추정 격자 한 칸 0.005° — 격자에 안 맞는 각 100개의 추정 오차 최대 0.0047°
#     (`tools/measure_skew_error.py`). 3.0 정확히로 두면 격자 누적 부동소수(3.00000000000002°) 때문에 3° 입력이 돌지 않았다
#   DESKEW_MIN_DRIFT_PX 2 = 폭 전체 밀림 — 사진 모드 `correct_photo`와 같은 문턱(깨끗한 PDF 렌더도 추정이 0.035° 안팎으로 흔들림)
# 측정: 깨끗한 20쪽(Aoharu 3 · PDF 17) 회전 0(추정 최대 0.035° · 밀림 최대 1.08px), 거부 9장 전부 회복(누락 2.0%).
DESKEW_MAX_DEG = 3.005
DESKEW_MIN_DRIFT_PX = 2.0


def _small_deskew(bgr: np.ndarray) -> Tuple[np.ndarray, float]:
    """(영상, 돌린 각). 조건이 안 되면 원본 그대로 · 0."""
    import math
    from .photo_correct import estimate_skew
    angle = -estimate_skew(bgr)
    h, w = bgr.shape[:2]
    if abs(angle) > DESKEW_MAX_DEG or abs(math.tan(math.radians(angle))) * w <= DESKEW_MIN_DRIFT_PX:
        return bgr, 0.0
    # 돌려서 실제로 나아질 때만 — 원해상도 행 투영(전단 근사, `estimate_skew`와 같은 점수)이 0°보다 뾰족해야 한다.
    # 작은 영상은 1/4 축소 거친 탐색이 틀린다: 수평인 900 × 300px 합성 픽스처(`tests/test_accidentals.py`)가 −0.15°로 추정돼
    # 밀림 2.36px > 2px로 돌았고 ♭ 하나를 놓쳤다. 미세 탐색은 ±0.1°만 봐서 그 오차를 못 되돌린다
    _, binary = binarize(bgr)
    ys, xs = np.nonzero(binary)
    if len(ys) == 0:
        return bgr, 0.0
    xs = xs - w / 2

    def sharp(a):
        yy = np.round(ys - xs * math.tan(math.radians(a))).astype(np.int64)
        yy -= yy.min()
        return float((np.bincount(yy).astype(np.float64) ** 2).sum())
    if sharp(angle) <= sharp(0.0):           # estimate_skew = −(점수 최대 전단각) → 바로잡는 각 = 점수 최대 전단각
        return bgr, 0.0
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(bgr, rot, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE), float(angle)


def preprocess(path: str, pdf_page: int = 0, pdf_dpi: int = 300, photo: bool = False) -> PreprocessResult:
    """1단계 전체 파이프라인: 로드 -> 이진화 -> 오선 검출 -> 보표 그룹핑

    photo=True면 사진 입력 M1(`modules/photo_correct.py`)을 거친다 — 기울기 보정 · 종이 영역 잘라내기 뒤
    안전장치를 통과하지 못하면 PhotoRejectedError(「다시 찍어 주세요」). 기본값에서는 이 경로를 안 탄다.
    """
    bgr = load_image(path, pdf_page=pdf_page, pdf_dpi=pdf_dpi)
    correction = None
    deskew = 0.0
    if photo:
        from .photo_correct import correct_photo
        bgr, correction = correct_photo(bgr)
    else:
        bgr, deskew = _small_deskew(bgr)
    gray, binary = binarize(bgr)
    try:
        line_ys = detect_staff_lines(binary)
        staves = group_into_staves(line_ys, row_sum=staff_line_profile(binary))
        staves = _add_short_staves(binary, staves)
    except StaffNotFoundError as exc:
        if photo:                       # 못 재면 거부 — 오선을 못 찾은 사진은 안내로 돌린다
            raise PhotoRejectedError(f"오선 검출 실패: {exc}") from exc
        raise
    result = PreprocessResult(original_bgr=bgr, gray=gray, binary=binary, staves=staves, deskew_deg=deskew)
    if photo:
        from .photo_correct import check_photo
        ok, reason = check_photo(result)
        if not ok:
            raise PhotoRejectedError(reason)
        result.photo_correction = correction
    return result


# ------------------------------------------------------------------
# 디버그 시각화: 검출된 오선을 원본 이미지 위에 그려서 눈으로 확인
# ------------------------------------------------------------------
def draw_debug_image(result: PreprocessResult, save_path: str) -> None:
    """검출된 오선을 빨간 선으로, 보표 경계를 초록 박스로 표시해 저장한다."""
    debug_img = result.original_bgr.copy()
    width = debug_img.shape[1]

    for staff in result.staves:
        for y in staff.line_ys:
            cv2.line(debug_img, (0, y), (width, y), (0, 0, 255), 1)
        cv2.rectangle(
            debug_img,
            (0, staff.top - 5),
            (width, staff.bottom + 5),
            (0, 200, 0),
            2,
        )
        cv2.putText(
            debug_img,
            f"staff {staff.index} (spacing={staff.spacing:.1f}px)",
            (5, staff.top - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 0),
            1,
            cv2.LINE_AA,
        )

    # 한글 경로 저장 대응을 위해 imencode 사용
    ext = os.path.splitext(save_path)[1] or ".png"
    ok, buf = cv2.imencode(ext, debug_img)
    if not ok:
        raise SheetMusicImageError(f"디버그 이미지 저장 실패: {save_path}")
    buf.tofile(save_path)


# ------------------------------------------------------------------
# 단독 실행 시 간단한 테스트 (실제 이미지 경로를 인자로 넘겨 확인 가능)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "sample_images", "sample.png"
    )

    try:
        result = preprocess(target)
    except (SheetMusicImageError, StaffNotFoundError) as e:
        print(f"[오류] {e}")
        sys.exit(1)

    print(f"검출된 보표 수: {len(result.staves)}")
    for st in result.staves:
        print(f"  - 보표 {st.index}: y={st.line_ys}, 간격 평균={st.spacing:.2f}px")

    debug_out = os.path.join(
        os.path.dirname(__file__), "..", "debug", "staff_debug.png"
    )
    draw_debug_image(result, debug_out)
    print(f"디버그 이미지 저장됨: {debug_out}")
