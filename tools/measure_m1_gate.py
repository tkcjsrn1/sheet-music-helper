# -*- coding: utf-8 -*-
"""M1(전역 회전 보정) 안전장치 검증 — 안전장치가 라벨 손실보다 **먼저** 걸리나. 측정 전용, 제품 무변경.

합성: 원본에 좌우 원근 ks + 회전 θ(`measure_skew_local.make`) → M1: `estimate_skew` 하나로 되돌림(INTER_LINEAR 한 번)
→ 안전장치 후보: **보정된 영상에서만** 보표를 찾고, 보표 띠마다 `estimate_skew`로 남은 기울기를 재
  「|tan| × 오선 길이 / sp」(잔여 밀림) 최대가 0.21sp를 넘으면 멈춤. 오선 검출 실패도 멈춤(시끄러운 실패)
→ 전체 파이프라인 라벨을 원본 좌표 → 사진 → 보정 영상으로 옮겨 원본 라벨과 짝짓는다(±0.5sp)

    python tools/measure_m1_gate.py [bbm aoharu bach]
"""
import math
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.preprocess import preprocess  # noqa: E402
from measure_photo_robustness import estimate_skew, pipeline_stages, _write  # noqa: E402
from measure_skew_local import make, SCORES  # noqa: E402

GATE_SP = 0.21
CROP = "--crop" in sys.argv
if CROP:
    sys.argv.remove("--crop")
KS = (0.0, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03)
ROT = 2.0


def gate(st):
    """보정된 영상의 보표마다 잔여 밀림(sp). 반환: (최대, 보표별 목록) 또는 None(오선 검출 실패)."""
    if st["fail"] or not st["staves"]:
        return None
    from modules.preprocess import binarize
    img = st["bgr"]
    _g, binary = binarize(img)
    out = []
    for s in st["staves"]:
        sp = s.spacing
        y0 = max(0, int(s.top - 3 * sp)); y1 = min(img.shape[0], int(s.bottom + 3 * sp))
        row = binary[s.line_ys[2]] > 0
        xs = np.flatnonzero(row)
        if len(xs) < 10:
            continue
        L = xs[-1] - xs[0]
        th = estimate_skew(img[y0:y1, xs[0]:xs[-1]], -3.0, 3.0)
        out.append(abs(math.tan(math.radians(th))) * L / sp)
    return (max(out) if out else 0.0), out


def gate_bands(st, K=10):
    """안전장치 후보 B — 보표 위치를 몰라도 되고, **못 재면 거부**한다.

    1) 가로 띠 K개(반씩 겹침)마다 잔여 각을 재 「|tan| × 내용 폭 / sp」 최대가 0.21sp를 넘으면 거부
       (sp = 검출된 보표 중앙값. 보표가 하나도 없으면 거부). 잉크가 거의 없는 띠만 건너뛴다
    2) **덮이지 않은 오선 구조**: 가로선 프로파일에서 검출된 보표 밖에 sp 간격(±20%) 봉우리 5개가 이어지면
       「보표가 있는데 못 찾음」으로 거부 — 봉우리 문턱은 검출된 오선 봉우리 높이 중앙값의 0.3배
    반환: (판정, 띠 잔여 최대 sp, 덮이지 않은 구조 수)
    """
    from modules.preprocess import binarize, staff_line_profile
    from scipy.signal import find_peaks
    if st["fail"] or not st["staves"]:
        return "거부(오선 없음)", None, None
    img = st["bgr"]
    _g, binary = binarize(img)
    sp = float(np.median([s.spacing for s in st["staves"]]))
    cols = np.flatnonzero((binary > 0).sum(axis=0) > binary.shape[0] * 0.01)
    width = (cols[-1] - cols[0]) if len(cols) else binary.shape[1]
    H = img.shape[0]
    h = 2 * H // (K + 1)
    worst = 0.0
    for i in range(K):
        y0 = i * h // 2
        band = binary[y0:y0 + h]
        # 오선이 없는 띠(제목 글자·여백)는 각이 흔들린다 — 긴 가로 런(6sp)이 거의 없으면 건너뛴다.
        # 6sp는 잔여 1°에서도 0.1sp만 밀려 오선 런이 끊기지 않는다(못 재서 건너뛰는 일을 막는다).
        # 2026-09-28 B♭m 1쪽 제목 띠가 0.225°를 내 순수 회전도 거부됐다
        long_runs = cv2.morphologyEx(band, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * 6)), 1)))
        if (long_runs > 0).mean() < 0.002:
            continue
        th = estimate_skew(img[y0:y0 + h], -3.0, 3.0)
        worst = max(worst, abs(math.tan(math.radians(th))) * width / sp)
    prof = staff_line_profile(binary).astype(float)
    line_h = [prof[y] for s in st["staves"] for y in s.line_ys]
    pk, _ = find_peaks(prof, height=0.3 * float(np.median(line_h)), distance=max(2, int(sp * 0.5)))
    covered = np.zeros(H, bool)
    for s in st["staves"]:
        covered[max(0, int(s.top - sp)):int(s.bottom + sp) + 1] = True
    free = [y for y in pk if not covered[y]]
    uncovered, run_ = 0, 1
    for a, b in zip(free, free[1:]):
        if abs((b - a) - sp) <= 0.2 * sp:
            run_ += 1
            if run_ == 5:
                uncovered += 1
        else:
            run_ = 1
    verdict = "거부(띠 기울기)" if worst > GATE_SP else ("거부(못 찾은 보표)" if uncovered else "통과")
    return verdict, worst, uncovered


def run(name, tmp):
    path, page = SCORES[name]
    res = preprocess(path, pdf_page=page)
    img = res.original_bgr
    base = pipeline_stages_from(img, os.path.join(tmp, f"{name}_orig.png"))
    sp0 = float(np.median([s.spacing for s in res.staves]))
    print(f"\n## {name}  기준 라벨 {len(base['notes'])}  sp {sp0:.1f}")
    print(f"조건: {'여백 잘라냄(스캐너형)' if CROP else '여백 경계 남음(사진형)'}  |  유지 · 소실 · 음고 · 표기 · 새로")
    for ks in KS:
        photo, fwd = make(img, ks=ks, rot=ROT)
        th = estimate_skew(photo)
        H, W = photo.shape[:2]
        M = cv2.getRotationMatrix2D((W / 2, H / 2), -th, 1.0)
        fixed = cv2.warpAffine(photo, M, (W, H), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
        pad = (W - img.shape[1]) // 2
        if CROP:                                              # 스캐너형: 원본 틀로 잘라 여백 경계를 없앤다
            fixed = fixed[pad:pad + img.shape[0], pad:pad + img.shape[1]]
        st = pipeline_stages_from(fixed, os.path.join(tmp, f"{name}_ks{ks}{'_crop' if CROP else ''}.png"))
        g = gate(st)
        verdict = "멈춤(오선 실패)" if g is None else ("멈춤" if g[0] > GATE_SP else "통과")
        vb, wb, ub = gate_bands(st)
        if st["fail"]:
            print(f"{ks:7.4f} {-th:7.3f} | {'-':>10s} {verdict} | {vb}")
            continue
        # 원본 좌표 → 사진(fwd) → 보정(M) → (잘랐으면) 여백만큼 이동
        pts = fwd(np.array([n[0] for n in base["notes"]], float), np.array([n[1] for n in base["notes"]], float))
        moved = (M @ np.c_[pts, np.ones(len(pts))].T).T
        if CROP:
            moved = moved - pad
        got = st["notes"]
        used, keep, lost, pitch, text = set(), 0, 0, 0, 0
        for (bx, by, bp, _s, bt), (mx, my) in zip(base["notes"], moved):
            best = None
            for j, (gx, gy, gp, _gs, gt) in enumerate(got):
                d = math.hypot(gx - mx, gy - my)
                if j not in used and d <= sp0 * 0.5 and (best is None or d < best[0]):
                    best = (d, j)
            if best is None:
                lost += 1
                continue
            used.add(best[1])
            keep += 1
            if got[best[1]][2] != bp:
                pitch += 1
            elif got[best[1]][4] != bt:
                text += 1
        new = len(got) - len(used)
        print(f"{ks:7.4f} {-th:7.3f} | A 보표별 {g[0]:5.2f}sp {verdict:4s} | B 띠 {wb:5.2f}sp 덮이지않음 {ub} {vb:10s} | "
              f"{keep} · {lost} · {pitch} · {text} · {new}", flush=True)


def pipeline_stages_from(bgr, png):
    _write(png, bgr)
    st = pipeline_stages(png)
    st["bgr"] = bgr
    return st


if __name__ == "__main__":
    tmp = os.path.join(ROOT, "debug", "m1_gate")
    os.makedirs(tmp, exist_ok=True)
    for n in (sys.argv[1:] or ["bbm", "aoharu", "bach"]):
        run(n, tmp)
