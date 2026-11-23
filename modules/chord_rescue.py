# -*- coding: utf-8 -*-
"""
붙은 화음 구제 — 「추가」 방식 + 2b (2026-09-29, 사용자 승인, DECISIONS 1-9).

왜 필요한가: `preprocess.binarize`의 적응형 창 blockSize=25가 절대 px라, 300dpi(sp≈19.5)에서
3도로 쌓인 꽉 찬 머리 두 개의 덩어리(≈1.9sp) 안쪽이 흰색으로 뚫린다. 속 빈 「8」자가 된 머리는
타원 opening에 깎여 사라지고, 남은 조각이 두 머리 사이 한가운데에 **화음에 없는 가운데 음** 라벨을 만든다.
20쪽 기준 붙은 화음 522머리 중 269(51.5%) 누락(docs/CHORD_FRAGMENT_MEASURE.md).

이진화 자체를 바꾸면(교체) 지금 맞는 음이 사라진다(DECISIONS 기각 25). 그래서:

1. **추가**: 이진화 결과의 닫힌 구멍 중 원본 회색 평균이 HOLE_FILL_GRAY 미만인 것만 채운 영상으로
   음표 머리 검출을 **한 번 더** 하고(파이프라인 전체를 따로 끝까지), 그 라벨 중 기존 라벨과
   가로 · 세로 MATCH_SP 안에 짝이 없는 것만 **더한다**(check). 기존 라벨은 건드리지 않는다.
2. **2b**: 기존 라벨이 추가된 라벨 쌍(위 하나 · 아래 하나)에 끼고, 두 추가 라벨까지 거리가 각각
   0.5sp ± MIDPOINT_TOL_SP이면 — 두 머리 접합부의 가운데 유령 — 그 기존 라벨만 지운다.

이 모듈은 **좌표 단위 판정**만 한다. 두 번 돌리고 합치는 연결은 main.py · gui.py에서 한다 — 사진 모드에서는 enable=False.
측정: docs/FILL_ADDITIVE_MEASURE.md, tools/measure_normalize_sp.py (additive · v2).
"""
from typing import List, Sequence, Tuple

import cv2
import numpy as np

# 닫힌 구멍 채움 문턱(원본 회색 평균). 실측(PDF 17쪽 + 빈 음표 픽스처 3종, 300dpi, 정답 머리 중심을 품은 구멍):
#   뚫린 꽉 찬 머리 4411개 — 평균 전부 0.0 / 빈 머리(2분 · 온음표) 422개 — 최소 202.6(hollow_16), 중앙 243.7
#   → 겹침 없음, 틈 가운데 101.
# 한계: **PDF 렌더에서만 쟀다**(꽉 찬 머리 속이 정확히 0). 스캔 · 사진은 속이 0이 아니고 빈 음표 속도 202보다
# 어두울 수 있다 — 그런 입력에서 이 틈이 유지되는지 안 쟀다.
HOLE_FILL_GRAY = 101
# 흐린 인쇄: 잉크 자체가 옅으면 꽉 찬 머리 속 회색이 101을 넘어 구멍이 안 채워진다. 쪽 잉크 회색(오선 행 잉크 화소 중앙값)이
# HOLE_FILL_INK_LO 이하면 101 그대로, HOLE_FILL_INK_HI 이상이면 상대값 잉크 + (101/255) × (종이 − 잉크), 사이는 선형(2026-10-06 사용자 승인).
#   63 = 원본 전 세트의 잉크 회색 최대 — 원본 판정 변화 0이 구조적. 115 = 대비 0.55에서 잉크 회색 최소 근처.
#   측정(`ROBUSTNESS.md` §4, 대비 0.9~0.5 6단계): 계단 안과 되찾음 같고 대비 0.7 새 유령 10 → 0, 다시 잃음 0
HOLE_FILL_INK_LO, HOLE_FILL_INK_HI = 63.0, 115.0

# 2b 중점 허용오차(sp). 중점 어긋남 = max(|위 추가 라벨까지 − 0.5sp|, |아래 추가 라벨까지 − 0.5sp|).
#   가운데 유령(추가 라벨 쌍에 끼인, 음이 틀린 기존 라벨) 44개 — 최대 0.329 · 중앙 0.281
#   3화음 진짜 가운데 음(위 · 아래 0.8~1.2sp에 같은 기둥 머리, 기존 라벨이 맞는 음) 6개 — 최소 0.503
#   → 겹침 없음, 틈 가운데 0.416. 2b가 지우는 44칸 전부 눈으로 유령 확인(docs/review/fill_additive_2b/).
# 한계: **진짜 가운데 음 표본이 6개뿐**이다. 또 PDF 렌더에서만 쟀다. 두 번째 안전장치 — 20쪽에서 맞는 기존 라벨이
# 추가 라벨 쌍에 끼인 경우 자체가 0개였다(진짜 가운데 음은 위 · 아래가 기존 라벨이라 쌍 조건에 안 걸린다).
MIDPOINT_TOL_SP = 0.416

# 「짝 있음」 판정 거리(sp, 가로 · 세로 각각). 사용자 지정 ±0.5sp.
MATCH_SP = 0.5
# 추가 라벨 쌍 조건: 기존 라벨과 가로 SANDWICH_X_SP 안, 쌍 사이 세로 SANDWICH_GAP_SP 이하(3도 쌓임 ≈1sp에 여유).
# 이것이 첫 번째 방어선이다 — 3화음의 진짜 가운데 음은 위 · 아래 머리가 2sp 떨어져 있어 쌍 조건(≤1.6sp)에 안 걸린다.
# MIDPOINT_TOL_SP는 그 다음 방어선(측정도 이 쌍 조건 아래에서 했다, tools/measure_normalize_sp.py `sandwich`).
SANDWICH_X_SP = 0.6
SANDWICH_GAP_SP = 1.6


def hole_filled_binary(binary: np.ndarray, gray: np.ndarray, gray_max: float = HOLE_FILL_GRAY) -> np.ndarray:
    """이진화 결과(전경 255)의 닫힌 구멍 중 원본 회색 평균 < gray_max인 것만 전경으로 채운 사본.

    닫힌 구멍 = 배경(0)의 4연결 성분 중 영상 가장자리에 닿지 않는 것. 구멍 밖 화소는 더하지 않는다
    (구멍 밖까지 어두운 화소를 더하면 임시표 옆 빈 음표 · 붙은 화음이 흔들린다 — 기각 25의 3번).
    """
    bg = (binary == 0).astype(np.uint8)
    n, lab, stats, _c = cv2.connectedComponentsWithStats(bg, connectivity=4)
    if n <= 1:
        return binary.copy()
    edge = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    sums = np.bincount(lab.ravel(), weights=gray.ravel().astype(np.float64), minlength=n)
    area = stats[:, cv2.CC_STAT_AREA].astype(np.float64)
    mean = sums / np.maximum(area, 1.0)
    dark = mean < gray_max
    dark[0] = False
    dark[edge] = False
    out = binary.copy()
    out[dark[lab]] = 255
    return out


def hole_fill_threshold(binary: np.ndarray, gray: np.ndarray, staves) -> float:
    """구멍 채움 문턱 — 쪽 잉크 회색이 옅을수록 상대값 쪽으로(위 HOLE_FILL_INK_LO · HI 주석)."""
    rows = sorted({int(round(y)) for s in staves for y in s.line_ys})
    ink = [gray[r][binary[r] > 0] for r in rows if 0 <= r < gray.shape[0]]
    ink = np.concatenate(ink) if ink else np.array([0])
    ink_g = float(np.median(ink)) if ink.size else 0.0
    if ink_g <= HOLE_FILL_INK_LO:
        return float(HOLE_FILL_GRAY)
    paper = float(np.median(gray[binary == 0]))
    rel = ink_g + HOLE_FILL_GRAY / 255.0 * (paper - ink_g)
    w = min(1.0, (ink_g - HOLE_FILL_INK_LO) / (HOLE_FILL_INK_HI - HOLE_FILL_INK_LO))
    return (1 - w) * HOLE_FILL_GRAY + w * rel


def detect_noteheads_rescue(result, contexts=None, reject_log=None):
    """보강 영상으로 음표 머리 검출. `result`는 바꾸지 않는다 — 이진화만 잠시 바꿔 검출하고 되돌린다.

    두 번째 파이프라인의 **머리 검출 한 단계만** 이것으로 바꾸고, 나머지(유령 제거 · 음고 · 임시표 · 확신도)는
    원래 `result`로 그대로 돈다(측정한 방식과 같다).
    """
    from .notehead_detect import detect_noteheads
    original = result.binary
    result.binary = hole_filled_binary(original, result.gray, hole_fill_threshold(original, result.gray, result.staves))
    try:
        return detect_noteheads(result, contexts=contexts, reject_log=reject_log)
    finally:
        result.binary = original


def merge_additive(base: Sequence[Tuple[float, float]], extra: Sequence[Tuple[float, float]],
                   spacing: float, enable: bool = True) -> Tuple[List[int], List[int]]:
    """기존 라벨 좌표(base)와 보강 파이프라인 라벨 좌표(extra)를 합친다.

    Returns:
        (added, deleted) — added: 더할 extra 번호(기존 라벨 가로 · 세로 MATCH_SP 안에 짝 없는 것, check로 표시),
        deleted: 지울 base 번호(2b — 추가 라벨 쌍의 중점).
    기존 라벨은 deleted에 든 것 말고는 그대로 둔다.

    enable=False면 ([], []) — **사진 모드(photo_correct 경로)에서는 False**(DECISIONS 1-9). 문턱 101 · 0.416은
    PDF 렌더로만 유도됐고, 사진 합성 세트의 2b 삭제 28개는 미검증이다(docs/review/chord_rescue_photo/).
    """
    if not enable:
        return [], []
    sp = float(spacing)
    added = [j for j, (x, y) in enumerate(extra)
             if not any(abs(x - bx) <= MATCH_SP * sp and abs(y - by) <= MATCH_SP * sp for bx, by in base)]
    add_xy = [extra[j] for j in added]
    deleted = []
    for i, (bx, by) in enumerate(base):
        col = [(x, y) for x, y in add_xy if abs(x - bx) <= SANDWICH_X_SP * sp]
        up = [y for _x, y in col if y < by]
        lo = [y for _x, y in col if y > by]
        if not up or not lo:
            continue
        u, d = max(up), min(lo)
        if d - u > SANDWICH_GAP_SP * sp:
            continue
        dev = max(abs((by - u) / sp - 0.5), abs((d - by) / sp - 0.5))
        if dev <= MIDPOINT_TOL_SP:
            deleted.append(i)
    return added, deleted


# ---------------------------------------------------------------------------
# 3도로 쌓인 화음의 가운데 머리 — 「추가만」 (2026-10-13 야간 · DECISIONS §1-32 · 병합 전 사용자 승인 대상, `docs/CHORD_MISSING.md`)
#
# 3음 이상 화음의 가운데 머리는 75%가 빠진다(위 · 아래는 4~8%) — 위 · 아래 머리와 붙어 한 덩어리가 되어
# 모양 판정에서 후보가 안 된다. 위 · 아래 라벨은 대개 있다(빠진 가운데 206 중 203).
# 그래서 이미 있는 라벨 둘이 위치를 정한다: 같은 보표 · 같은 기둥(|dx| ≤ 0.3sp) · 세로 1.8~2.2sp(5도) · 가운데 0.5sp 안에 라벨 없음 ·
# 양 끝 라벨이 둘 다 check가 아님(바뀐 음자리표 구간 등 — 양 끝 음고부터 틀려 있다).
# 판정은 가운데의 잉크 하나 — 오선 제거 영상에서 가운데 행(±0.15sp)과 위 · 아래 행(±0.2~0.3sp) **모두** 가로 런 ≥ 0.65sp.
#   빈 5도(가운데 머리 없음)는 기둥 · 오선 잔여 조각뿐이라 위 · 아래 행이 비거나 짧다.
#   문턱 0.65sp: 위 · 아래 행 런 최솟값 — 진짜 가운데 머리 5% 0.86 · 가운데 머리 없음(가운데 행 런 1.0~1.6인 것) 최대 0.50 → √(0.50 × 0.86) = 0.66
# #193(덩어리 **높이**로 머리 수 추정)과 달리 위치는 라벨 둘이 정하고, 「본 상관」(보류)은 쓰지 않는다.
# 시뮬레이션(PDF 17 · 보지 않은 8 · Verovio 20, 보류 세트 미사용): 추가 77 · 위치 + 음고 전부 맞음(Verovio 76 음고 대조) · 새 유령 0 · Aoharu 후보 0.
# 사진 모드에서는 끈다(미측정).
MIDDLE_PAIR_DX_SP = 0.3
MIDDLE_PAIR_DY_SP = (1.8, 2.4)
# 위끝 2.2 → 2.4 + 두 끝 음고 차 = 5도(온음계 4단계) 조건 (2026-10-19 · §1-47 초안, `docs/CHORD_MISSING.md` 끝 절):
#   셋이 붙은 덩어리에서는 끝 머리 중심이 바깥으로 0.1 ~ 0.15sp씩 밀려 끝 쌍이 2.21 ~ 2.36sp가 된다(Verovio 빠진 가운데 34).
#   가운데가 없는 5도 쌍(따로 떨어진 두 머리)은 최대 2.17sp → 그 사이 · 6도(2.5sp) 아래 2.4. 음고 조건은 넓힌 창에 6도가 들지 않게.
MIDDLE_FREE_SP = 0.5
MIDDLE_RUN_SP = 0.65
MIDDLE_CENTER_SP = 0.6     # 가운데 행 런 하한 — 시뮬레이션 창 하한과 같다(진짜 가운데 머리 최소 0.61)


def _row_run(ns: np.ndarray, mx: float, y0: float, y1: float, sp: float) -> float:
    """y0~y1 행 중 가로 런 최대(sp) — x는 가운데 ±0.4sp 안 잉크에서 시작(측정 도구 `measure_chord_middle.run_at`과 같은 정의)."""
    H, W = ns.shape
    best = 0
    for y in range(int(y0), int(y1) + 1):
        if not 0 <= y < H:
            continue
        row = ns[y]
        xs = [x for x in range(int(mx - 0.4 * sp), int(mx + 0.4 * sp) + 1) if 0 <= x < W and row[x]]
        for x0 in xs[:1] + xs[len(xs) // 2:len(xs) // 2 + 1]:
            a = b = x0
            while a > 0 and row[a - 1]:
                a -= 1
            while b + 1 < W and row[b + 1]:
                b += 1
            best = max(best, b - a + 1)
    return best / sp


def _diatonic(n) -> int:
    return "CDEFGAB".index(n.note_name) + 7 * int(n.octave)


def chord_middle_heads(result, pitched, diag_rows, *, enable=True) -> list:
    """가운데 머리를 더할 자리(Notehead 목록). 기존 라벨은 건드리지 않는다."""
    if not enable or not pitched:
        return []
    from .labels_io import flags_of, confidence_of, CONFIDENCE_CHECK
    from .notehead_detect import Notehead, remove_staff_lines
    ns = remove_staff_lines(result.binary, result.staves) > 0
    by_staff = {s.index: s for s in result.staves}
    conf = {(int(r["staff"]), int(r["x"]), int(r["y"])): confidence_of(flags_of(r)) for r in diag_rows}
    out = []
    for i, a in enumerate(pitched):
        staff = by_staff.get(a.staff_index)
        if staff is None:
            continue
        sp = staff.spacing
        for b in pitched[i + 1:]:
            if b.staff_index != a.staff_index or abs(a.x - b.x) > MIDDLE_PAIR_DX_SP * sp:
                continue
            if not MIDDLE_PAIR_DY_SP[0] * sp <= abs(a.y - b.y) <= MIDDLE_PAIR_DY_SP[1] * sp:
                continue
            if abs(_diatonic(a) - _diatonic(b)) != 4:      # 5도
                continue
            mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
            if any(abs(n.x - mx) <= MIDDLE_FREE_SP * sp and abs(n.y - my) <= MIDDLE_FREE_SP * sp for n in pitched):
                continue
            if CONFIDENCE_CHECK in (conf.get((a.staff_index, int(a.x), int(a.y))), conf.get((b.staff_index, int(b.x), int(b.y)))):
                continue
            if _row_run(ns, mx, my - 0.15 * sp, my + 0.15 * sp, sp) < MIDDLE_CENTER_SP:
                continue
            if min(_row_run(ns, mx, my - 0.3 * sp, my - 0.2 * sp, sp),
                   _row_run(ns, mx, my + 0.2 * sp, my + 0.3 * sp, sp)) < MIDDLE_RUN_SP:
                continue
            if not any(abs(h.x - round(mx)) <= 1 and abs(h.y - round(my)) <= 1 for h in out):
                out.append(Notehead(x=int(round(mx)), y=int(round(my)), staff_index=a.staff_index, filled=True))
    return out


def apply_chord_middles(result, contexts, clef_arg, key_letters, key_symbol, notation, tonic,
                        pitched, accidentals, named, diag_rows, rare_warnings, *, enable=True):
    """`chord_middle_heads` 자리를 라벨로 **더한다**(기존 라벨 · 행은 그대로). 음고 · 임시표 · 계이름 · 진단 행은 제품 함수로 만든다.
    새 라벨 행에 `chord_middle_added`(주의 등급 — `chord_rescue_added`와 같은 정책)를 붙인다.

    Returns: (pitched, accidentals, named, diag_rows, 더한 수)
    """
    heads = chord_middle_heads(result, pitched, diag_rows, enable=enable)
    if not heads:
        return pitched, accidentals, named, diag_rows, 0
    from .pitch_calculator import calculate_pitches
    from .accidental_detect import annotate_accidentals
    from .note_namer import to_solfege_batch
    from .verify import diagnose_labels
    from .labels_io import mark_accidental_candidates
    extra = calculate_pitches(heads, result.staves, clef=clef_arg)
    # 마디 안 임시표 전파(같은 보표 음표를 x순으로 훑는다)를 받도록 기존 음표와 함께 판정하고 **새 머리 몫만** 쓴다 — 기존 라벨의 임시표는 그대로
    # (새 머리만 따로 넣으면 앞 음의 ♭을 못 받는다: Clara 4 B (1063,438) · (1121,438) 「라」 → 정답 「라b」, 2026-10-13)
    extra_acc = annotate_accidentals(result, contexts, list(pitched) + list(extra))[len(pitched):]
    extra_named = to_solfege_batch(extra, key_letters, key_symbol, extra_acc, notation, rare_warnings, tonic)
    rows = mark_accidental_candidates(list(diag_rows) + diagnose_labels(result, extra), extra, "chord_middle_added")
    return pitched + extra, list(accidentals) + list(extra_acc), list(named) + list(extra_named), rows, len(extra)

