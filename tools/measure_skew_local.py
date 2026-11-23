# -*- coding: utf-8 -*-
"""행 투영 기울기 추정기가 **원근·곡면**에서도 쓸 만한가 — 보표마다 잰다.

측정 전용. 합성본은 추정기 검증용 **최소한**이다(본 합성 세트는 Codex 몫).

    python tools/measure_skew_local.py [bbm|aoharu|bach ...]

변형(원본 좌표 → 사진 좌표를 **해석적으로** 알고 있어 보표마다 참 기울기를 계산할 수 있다):

- `persp` : 사다리꼴(윗변을 k만큼 좁힘) + 회전 2°. 카메라가 종이를 비스듬히 본 경우
- `curl`  : 오른쪽 가장자리 쪽으로 갈수록 y가 A·t² 만큼 내려감(t: 0→1). 책 제본 쪽 휨
- 둘을 합친 것

보표마다 가운데 줄을 원본에서 따라가 사진 좌표로 옮긴 뒤

- 참 각도   : 그 곡선의 최소제곱 직선 기울기
- 곡률 잔차 : 곡선이 그 직선에서 벗어나는 최대 폭(sp) — **보표 하나를 회전 하나로 펴면 남는 바닥**
- 전역 추정 : 페이지 전체에 `estimate_skew` 하나 → 보표별 잔여 밀림(sp)
- 보표 추정 : 참 위치로 자른 띠에 `estimate_skew` → 잔여 밀림(sp). 보표 위치를 미리 안다고 친 **상한**

밀림 = |tan(참 − 추정)| × 오선 길이 + 곡률 잔차는 따로. 기준은 `PORTABILITY.md`의 보표 소실 없음 0.21sp.
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
from measure_photo_robustness import estimate_skew  # noqa: E402
from measure_keysig_resample import SCORES  # noqa: E402

SAFE_SP = 0.21


def homography(w, h, k, ks, rot_deg, pad):
    """윗변을 양쪽에서 k·w/2씩, 오른변을 위아래에서 ks·h/2씩 좁히고 rot_deg 돌린다.

    윗변만 좁히면(k) 가로선은 가로로 남는다 — 보표 기울기를 바꾸는 것은 **좌우 원근**(ks)이다.
    """
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[k * w / 2, 0], [w - k * w / 2, ks * h / 2], [w, h - ks * h / 2], [0, h]])
    Hp = cv2.getPerspectiveTransform(src, dst)
    c = math.cos(math.radians(rot_deg)); s = math.sin(math.radians(rot_deg))
    cx, cy = w / 2, h / 2
    R = np.array([[c, s, cx - c * cx - s * cy], [-s, c, cy + s * cx - c * cy], [0, 0, 1]])
    T = np.array([[1, 0, pad], [0, 1, pad], [0, 0, 1.0]])
    return T @ R @ Hp


def make(img, k=0.0, ks=0.0, rot=0.0, curl=0.0):
    """합성 사진과 점 변환 함수. curl은 px 단위 최대 처짐(오른쪽 끝)."""
    h, w = img.shape[:2]
    pad = int(max(h, w) * 0.08)
    d = lambda x: curl * np.clip(np.asarray(x, float) / w, 0, 1) ** 2
    if curl:
        mx, my = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        src_y = (my - d(mx)).astype(np.float32)      # 출력 (x, y) ← 원본 (x, y − d(x))
        img = cv2.remap(img, mx, src_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                        borderValue=(255, 255, 255))
    H = homography(w, h, k, ks, rot, pad)
    out = cv2.warpPerspective(img, H, (w + 2 * pad, h + 2 * pad), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    def fwd(xs, ys):
        pts = np.stack([xs, ys + d(xs)], 1).astype(np.float64)[None]
        return cv2.perspectiveTransform(pts, H)[0]
    return out, fwd


def staff_curves(res):
    """보표마다 (가운데 줄 x 표본, y, sp, 길이px)."""
    out = []
    for s in res.staves:
        row = res.binary[s.line_ys[2]] > 0
        xs = np.flatnonzero(row)
        if len(xs) < 10:
            continue
        x = np.linspace(xs[0], xs[-1], 64)
        out.append((x, np.full_like(x, float(s.line_ys[2])), s.spacing, xs[-1] - xs[0]))
    return out


def measure(name, cases):
    path, page = SCORES[name]
    res = preprocess(path, pdf_page=page)
    img = res.original_bgr
    curves = staff_curves(res)
    sp0 = float(np.median([c[2] for c in curves]))
    print(f"\n## {name}  sp={sp0:.1f}px  보표 {len(curves)}")
    print(f"{'변형':24s} {'참각 범위':>14s} {'곡률잔차 최대':>12s} | {'전역 추정':>8s} {'전역 잔여 최대':>12s} "
          f"{'>0.21 보표':>9s} | {'보표별 잔여 최대':>14s} {'>0.21':>6s} | {'반폭 곡률':>9s}")
    for label, kw in cases:
        photo, fwd = make(img, **kw)
        g = estimate_skew(photo)                       # 되돌릴 각(도) — getRotationMatrix2D 부호
        rows = []
        for x, y, sp, L in curves:
            p = fwd(x, y)
            px, py = p[:, 0], p[:, 1]
            a, b = np.polyfit(px, py, 1)
            true = math.degrees(math.atan(a))          # 이미지 좌표(아래로 +)의 기울기
            Lp = px[-1] - px[0]
            sp_p = sp * Lp / L                          # 사진에서의 sp 근사(가로 배율)
            curv = float(np.abs(py - (a * px + b)).max()) / sp_p
            half = len(px) // 2                         # 반씩 나눠 직선을 맞췄을 때의 곡률 잔차
            curv2 = max(float(np.abs(py[i:j] - np.polyval(np.polyfit(px[i:j], py[i:j], 1), px[i:j])).max())
                        for i, j in ((0, half), (half, len(px)))) / sp_p
            gres = abs(math.tan(math.radians(true + g))) * Lp / sp_p
            # 보표별: 참 위치로 띠를 잘라 추정
            y0 = int(max(0, py.min() - 3 * sp_p)); y1 = int(min(photo.shape[0], py.max() + 3 * sp_p))
            x0 = int(max(0, px.min() - sp_p)); x1 = int(min(photo.shape[1], px.max() + sp_p))
            try:
                e = estimate_skew(photo[y0:y1, x0:x1])
                sres = abs(math.tan(math.radians(true + e))) * Lp / sp_p
            except Exception:
                sres = float("nan")
            rows.append((true, curv, gres, sres, curv2))
        t = np.array(rows)
        print(f"{label:24s} {t[:, 0].min():6.2f}~{t[:, 0].max():5.2f}° {t[:, 1].max():10.2f}sp | "
              f"{-g:7.3f}° {t[:, 2].max():10.2f}sp {int((t[:, 2] > SAFE_SP).sum()):5d}/{len(t)} | "
              f"{np.nanmax(t[:, 3]):12.2f}sp {int((t[:, 3] > SAFE_SP).sum()):4d}/{len(t)} | "
              f"{t[:, 4].max():7.2f}sp")


CASES = [
    ("회전 2° (대조)", dict(rot=2.0)),
    ("위아래 원근 k=0.20 + 2°", dict(k=0.20, rot=2.0)),
    ("좌우 원근 ks=0.05 + 2°", dict(ks=0.05, rot=2.0)),
    ("좌우 원근 ks=0.10 + 2°", dict(ks=0.10, rot=2.0)),
    ("좌우 원근 ks=0.20 + 2°", dict(ks=0.20, rot=2.0)),
    ("좌우+위아래 0.10 + 2°", dict(k=0.10, ks=0.10, rot=2.0)),
    ("휨 1sp", dict(curl=1.0)),
    ("휨 3sp", dict(curl=3.0)),
    ("휨 8sp", dict(curl=8.0)),
    ("좌우 원근 0.10 + 2° + 휨 3sp", dict(ks=0.10, rot=2.0, curl=3.0)),
]

def band_estimates(photo, K):
    """보표 위치를 모르는 채로 페이지를 가로 띠 K개(반씩 겹침)로 나눠 띠마다 각도를 잰다 → [(띠 중심 y, 각)]."""
    H = photo.shape[0]
    h = 2 * H // (K + 1)
    out = []
    for i in range(K):
        y0 = i * h // 2
        crop = photo[y0:y0 + h]
        try:
            out.append((y0 + h / 2, -estimate_skew(crop)))  # 이미지 좌표 기울기(참 각과 같은 부호)
        except Exception:
            pass
    return out


def measure_bands(name, cases, Ks=(6, 10)):
    """띠별 추정 → θ(y) 직선 맞춤 → 보표 중심 y에서의 θ로 되돌렸을 때 보표별 잔여(sp)."""
    path, page = SCORES[name]
    res = preprocess(path, pdf_page=page)
    img = res.original_bgr
    curves = staff_curves(res)
    print(f"\n## {name} — 띠별 추정 (보표 위치 모름)")
    print(f"{'변형':26s} " + " | ".join(f"K={K}: 잔여 최대 · >0.21" for K in Ks))
    for label, kw in cases:
        photo, fwd = make(img, **kw)
        cols = []
        for K in Ks:
            est = band_estimates(photo, K)
            ys = np.array([e[0] for e in est]); th = np.array([e[1] for e in est])
            # 흰 여백만 있는 띠는 추정이 흔들린다 — 중앙값에서 1° 넘게 벗어난 띠를 빼고 직선을 맞춘다
            ok = np.abs(th - np.median(th)) <= 1.0
            a, b = np.polyfit(ys[ok], th[ok], 1) if ok.sum() >= 2 else (0.0, float(np.median(th)))
            worst, over = 0.0, 0
            for x, y, sp, L in curves:
                p = fwd(x, y)
                px, py = p[:, 0], p[:, 1]
                s_, _ = np.polyfit(px, py, 1)
                true = math.degrees(math.atan(s_))
                Lp = px[-1] - px[0]
                sp_p = sp * Lp / L
                e = a * py.mean() + b
                r = abs(math.tan(math.radians(true - e))) * Lp / sp_p
                worst = max(worst, r); over += r > SAFE_SP
            cols.append(f"{worst:6.2f}sp · {over:2d}/{len(curves)}")
        print(f"{label:26s} " + " | ".join(cols))


# 「기울기만 보정」의 원근 한계 — 좌우 원근을 잘게 (2026-09-28)
CASES_FINE = [(f"좌우 원근 ks={k:.3f} + 2°", dict(ks=k, rot=2.0)) for k in (0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03)]


if __name__ == "__main__":
    if "--bands" in sys.argv:
        sys.argv.remove("--bands")
        cases = [(f"좌우 원근 ks={k:.3f} + 2°", dict(ks=k, rot=2.0)) for k in (0.0, 0.005, 0.01, 0.02, 0.05, 0.10)] +                 [("좌우+위아래 0.05 + 2°", dict(k=0.05, ks=0.05, rot=2.0)), ("회전 8°", dict(rot=8.0))]
        for n in (sys.argv[1:] or ["bbm", "aoharu", "bach"]):
            measure_bands(n, cases)
        sys.exit(0)
    fine = "--fine" in sys.argv
    if fine:
        sys.argv.remove("--fine")
        CASES = CASES_FINE
    for n in (sys.argv[1:] or ["bbm", "aoharu"]):
        sp = float(np.median([s.spacing for s in preprocess(*SCORES[n][:1], pdf_page=SCORES[n][1]).staves]))
        # 휨은 sp 배수로 준다
        cases = [(l, {k: (v * sp if k == "curl" else v) for k, v in kw.items()}) for l, kw in CASES]
        measure(n, cases)


def corner_error(trials=300, seed=0):
    """네 귀퉁이를 ε px 틀리게 잡고 원근을 펴면 무엇이 남나 — 해석 계산(이미지 처리 없음).

    A4 300dpi(2480×3508, sp≈20)를 좌우·위아래 원근 0.10 + 2°로 찍었다고 치고, 사진 속 귀퉁이에
    ±ε px 균등 잡음을 넣어 `getPerspectiveTransform`으로 편다. 원본 → 편 결과의 합성 변환에서
    - 기울기 잔여: 오선 길이 2270px 가로선의 좌우 끝 y 차이(sp) — 보표 소실 없음 0.21sp와 비교
    - 세로 배율 불균일: 페이지 안 국소 세로 배율의 (최대/최소 − 1)과 **한 보표 폭 안**의 같은 값(%)
      A-6 흔들기 δsp=−0.10px는 sp 20에서 0.5%, sp 11.6에서 0.9%다
    """
    w, h, sp, L = 2480, 3508, 20.0, 2270
    rng = np.random.default_rng(seed)
    Hp = homography(w, h, 0.10, 0.10, 2.0, 0)
    rect = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    photo_c = cv2.perspectiveTransform(rect[None].astype(np.float64), Hp)[0]
    xs = np.linspace((w - L) / 2, (w + L) / 2, 9)
    ys = np.linspace(200, h - 200, 15)
    print(f"{'ε px':>5s} {'기울기 잔여 p95':>14s} {'최대':>7s} {'>0.21':>6s} | {'페이지 세로배율 p95':>16s} {'보표 폭 안 p95':>13s}")
    for eps in (0, 2, 5, 10, 20, 40):
        drift, page_s, row_s = [], [], []
        for _ in range(trials):
            noisy = (photo_c + rng.uniform(-eps, eps, photo_c.shape)).astype(np.float32)
            Hr = cv2.getPerspectiveTransform(noisy, rect)
            M = Hr @ Hp
            f = lambda px, py: cv2.perspectiveTransform(np.stack([px, py], 1)[None].astype(np.float64), M)[0]
            worst, scales, rows = 0.0, [], []
            for y in ys:
                a = f(xs, np.full_like(xs, y))
                b = f(xs, np.full_like(xs, y + sp))
                worst = max(worst, abs(a[-1, 1] - a[0, 1]) / sp)
                s = (b[:, 1] - a[:, 1]) / sp               # 국소 세로 배율
                scales.extend(s)
                rows.append(s.max() / s.min() - 1)
            drift.append(worst)
            page_s.append(max(scales) / min(scales) - 1)
            row_s.append(max(rows))
        d = np.array(drift)
        print(f"{eps:5d} {np.percentile(d, 95):12.2f}sp {d.max():6.2f}sp {int((d > SAFE_SP).mean() * 100):4d}% | "
              f"{np.percentile(page_s, 95) * 100:14.2f}% {np.percentile(row_s, 95) * 100:12.2f}%")
