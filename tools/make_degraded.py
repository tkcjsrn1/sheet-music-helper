# -*- coding: utf-8 -*-
"""실사용 대용 — PDF 17쪽 중 3쪽에 촬영 · 스캔 열화를 입히고 정답 머리를 같은 변환으로 옮긴다 (2026-10-13 야간 큐 2(b)).

출력 `inputs/degraded/`(커밋 안 함): `<쪽>__<변형>.png|jpg` + 같은 이름 `.tsv`(x · y · 음이름옥타브 · 실효 임시표) + `manifest.json`(변환 행렬 · 설정).
정답: `measure_certain_errors._truth`(PDF 글리프 + 실효 임시표, 300dpi 좌표)를 3×3 행렬로 옮긴다. 열화는 결정적(난수 씨앗 고정).
기존 사진 합성 세트(바흐 · D♭ 1쪽 · F장조 픽스처)와 겹치지 않게 E단조 2쪽 · B♭단조 1쪽 · D♭ 3쪽을 쓴다. **문턱 유도에 쓰지 않는다**(채점 전용).

변형: rot1 · rot3(회전 1° · 3°) · persp(위 모서리 1.5% 안으로 — 약한 원근) · blur(가우스 σ 1.2) · shadow(왼→오 밝기 1.0 → 0.55) ·
      jpeg60 · lowres(0.6배 축소 — 약 180dpi) · combo(회전 2° + 원근 + 흐림 + 그림자 + JPEG 60)

    python tools/make_degraded.py
"""
import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "inputs", "degraded")
PAGES = ["em2", "bbm1", "db3"]   # 경로 · 쪽은 check_accidental_fix.PAGES에서
VARIANTS = ("rot1", "rot3", "persp", "blur", "shadow", "jpeg60", "lowres", "combo")


def _pages():
    import check_accidental_fix as C
    P = {n: (p, pg) for n, p, pg in C.PAGES}
    return [(n, P[n][0], P[n][1]) for n in PAGES]


def _rot(w, h, deg):
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return np.vstack([M, [0, 0, 1]])


def _persp(w, h, k=0.015):
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[w * k, 0], [w * (1 - k), 0], [w, h], [0, h]])
    return cv2.getPerspectiveTransform(src, dst)


def degrade(gray, var):
    """(영상, 3×3 행렬, 저장 확장자)."""
    h, w = gray.shape
    H = np.eye(3)
    img = gray.copy()
    geo = {"rot1": _rot(w, h, 1.0), "rot3": _rot(w, h, 3.0), "persp": _persp(w, h),
           "combo": _persp(w, h) @ _rot(w, h, 2.0)}.get(var)
    if geo is not None:
        H = geo
        img = cv2.warpPerspective(img, H, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    if var in ("blur", "combo"):
        img = cv2.GaussianBlur(img, (0, 0), 1.2)
    if var in ("shadow", "combo"):
        ramp = np.linspace(1.0, 0.55, w)[None, :]
        img = np.clip(img.astype(np.float32) * ramp, 0, 255).astype(np.uint8)
    if var == "lowres":
        S = np.diag([0.6, 0.6, 1.0])
        img = cv2.resize(img, (int(w * 0.6), int(h * 0.6)), interpolation=cv2.INTER_AREA)
        H = S @ H
    ext = ".jpg" if var in ("jpeg60", "combo") else ".png"
    return img, H, ext


def main():
    from measure_certain_errors import _truth
    from modules.preprocess import load_image
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for name, path, pg in _pages():
        gray = cv2.cvtColor(load_image(os.path.join(ROOT, path), pdf_page=pg), cv2.COLOR_BGR2GRAY)
        heads, sp = _truth("pdf", name, path, pg)
        for var in VARIANTS:
            img, H, ext = degrade(gray, var)
            stem = f"{name}__{var}"
            enc = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 60] if ext == ".jpg" else [])[1]
            open(os.path.join(OUT, stem + ext), "wb").write(enc.tobytes())
            pts = np.array([[x, y, 1.0] for x, y, _p, _a in heads]).T
            q = H @ pts
            q = q[:2] / q[2]
            with open(os.path.join(OUT, stem + ".tsv"), "w", encoding="utf-8", newline="") as f:
                wr = csv.writer(f, delimiter="\t")
                wr.writerow(["x", "y", "pitch", "eff"])
                for (x, y), (_x, _y, p, a) in zip(q.T, heads):
                    wr.writerow([round(float(x), 1), round(float(y), 1), p, a])
            manifest.append(dict(stem=stem, file=stem + ext, source=path, page=pg, variant=var, H=np.round(H, 6).tolist(),
                                 size=list(img.shape[::-1]), heads=len(heads), sp_source=round(sp, 2)))
            print(stem, img.shape, len(heads))
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
