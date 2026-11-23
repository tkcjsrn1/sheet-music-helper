# -*- coding: utf-8 -*-
"""작은 기울기 보정 상한의 근거 — `photo_correct.estimate_skew`의 추정 오차 분포 (2026-10-13 · 측정만, 보류 세트 미사용).

깨끗한 쪽(바흐 · B♭단조 1 · D♭ 3 · E단조 2 · Aoharu 1)을 `make_degraded._rot`과 같은 회전(warpPerspective · 흰 경계)으로
±0.5 ~ ±3.5°(0.5° 간격) 돌리고, 사진 모드와 같은 약속(바로잡는 각 = −estimate_skew)으로 추정 → 오차 = 추정 바로잡는 각 + 실제 회전각.
상한 = 지원 목표 각(3°, 열화 세트 rot3) + |오차| 최댓값 — 목표 각의 입력이 오차 때문에 상한을 넘어 거부되지 않게.

    python tools/measure_skew_error.py
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
PAGES = ["bach", "bbm1", "db3", "em2", "aoharu1"]
# 격자(0.005°)에 안 맞는 각(소수 넷째 자리) — 0.5° · 0.01° 단위는 추정 격자에 딱 맞아 오차가 0으로 나오는 측정 함정이었다(2026-10-13)
ANGLES = [a * s for a in (0.3713, 0.8261, 1.2847, 1.7139, 2.2331, 2.6788, 2.9417, 2.9987, 3.0019, 3.2156) for s in (1, -1)]


def _job(job):
    import cv2
    from make_degraded import _rot
    from modules.preprocess import load_image
    from modules.photo_correct import estimate_skew
    name, path, pg = job
    bgr = load_image(os.path.join(ROOT, path), pdf_page=pg)
    h, w = bgr.shape[:2]
    out = []
    for a in ANGLES:
        img = cv2.warpPerspective(bgr, _rot(w, h, a), (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
        fix = -estimate_skew(img)
        out.append(dict(page=name, angle=a, fix=float(fix), err=round(fix + a, 4)))
    return out


def main():
    import check_accidental_fix as C
    P = {n: (p, pg) for n, p, pg in C.PAGES}
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = [r for part in ex.map(_job, [(n,) + P[n] for n in PAGES]) for r in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "skew_error.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    e = np.array([abs(r["err"]) for r in R])
    print(f"표본 {len(R)} · |오차| 중앙 {np.median(e):.4f}° · 95% {np.percentile(e, 95):.4f}° · 최대 {e.max():.4f}°")
    for a in sorted({abs(r['angle']) for r in R}):
        v = [abs(r["err"]) for r in R if abs(r["angle"]) == a]
        print(f"   |실제| {a:.1f}°: |오차| 최대 {max(v):.4f}° · 바로잡는 각 |최대| {max(abs(float(r['fix'])) for r in R if abs(r['angle']) == a):.4f}°")
    print(f"→ 상한 = 3° + {e.max():.4f}° = {3 + e.max():.4f}°")


if __name__ == "__main__":
    main()
