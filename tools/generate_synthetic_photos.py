# -*- coding: utf-8 -*-
"""기존 세 악보를 재현 가능한 합성 촬영본으로 만든다. 제품 모듈은 변경하지 않는다.

실행: python tools/generate_synthetic_photos.py
출력: output/synthetic_photos/ (57장 + manifest.json + ZIP)
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from modules.preprocess import preprocess  # noqa: E402
from tools.measure_skew_local import homography  # noqa: E402
from tools.count_fixture_notes import count_notes  # noqa: E402

OUT = ROOT / "output" / "synthetic_photos"
SCORES = {
    "bach": ("test_scores/bach_minuet_Am.pdf", 0, None),
    "chopin_Db": ("test_scores/chopin_nocturne_Db_6-8.pdf", 0, None),
    "F_flat1": ("tests/fixtures/key_signatures/pdf/12_F_major_flat1.pdf", 0,
                "tests/fixtures/key_signatures/sources/12_F_major_flat1.ly"),
}
CASES = [("original", {}) , ("translate_x0p5_y0p5", {"shift": .5})]
CASES += [(f"rotation_{str(deg).replace('.', 'p')}deg", {"rot": deg})
          for deg in (.5, 1, 2, 3, 5)]
CASES += [(f"perspective_{level}", {"k": k, "ks": ks})
          for level, k, ks in (("weak", .04, .01), ("medium", .10, .03), ("strong", .20, .06))]
CASES += [(f"book_curve_{level}", {"curve_sp": amp})
          for level, amp in (("weak", 1.5), ("strong", 4.0))]
CASES += [("lighting_shadow_left", {"light": "shadow_left"}),
          ("lighting_dark", {"light": "dark"}),
          ("lighting_fluorescent", {"light": "fluorescent"}),
          ("noise_focus_blur", {"blur_sigma": 1.2}),
          ("noise_gaussian", {"noise_sigma": 8.0}),
          ("noise_jpeg_q35", {"jpeg_quality": 35}),
          ("combined_rot2_perspectiveweak_shadow_blur",
           {"rot": 2.0, "k": .04, "ks": .01, "light": "shadow_left", "blur_sigma": 1.2})]
assert len(CASES) == 19


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_case(src: np.ndarray, sp: float, cfg: dict, seed: int):
    h, w = src.shape[:2]
    pad = int(max(h, w) * .08) if any(k in cfg for k in ("rot", "k", "ks")) else 0
    curve_px = float(cfg.get("curve_sp", 0)) * sp
    work = src.copy()
    if curve_px:
        xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        d = curve_px * (1 - np.abs((xx - (w - 1) / 2) / ((w - 1) / 2))) ** 2
        work = cv2.remap(work, xx, yy - d.astype(np.float32), cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    H = homography(w, h, cfg.get("k", 0), cfg.get("ks", 0), cfg.get("rot", 0), pad)
    if "shift" in cfg:
        H[0, 2] += cfg["shift"]
        H[1, 2] += cfg["shift"]
    if cfg and (pad or "shift" in cfg):
        work = cv2.warpPerspective(work, H, (w + 2 * pad, h + 2 * pad),
                                   flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=(255, 255, 255))
    oh, ow = work.shape[:2]
    light = cfg.get("light")
    if light:
        if light == "shadow_left":
            factor = .45 + .55 * np.linspace(0, 1, ow, dtype=np.float32)[None, :]
        elif light == "dark":
            factor = np.full((1, 1), .55, dtype=np.float32)
        else:
            factor = (.75 + .20 * np.cos(np.linspace(0, 6 * math.pi, oh, dtype=np.float32)))[:, None]
        work = np.clip(work.astype(np.float32) * factor[..., None], 0, 255).astype(np.uint8)
    if "blur_sigma" in cfg:
        work = cv2.GaussianBlur(work, (0, 0), cfg["blur_sigma"])
    if "noise_sigma" in cfg:
        noise = np.random.default_rng(seed).normal(0, cfg["noise_sigma"], work.shape)
        work = np.clip(work.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    ext = ".jpg" if "jpeg_quality" in cfg else ".png"
    params = [cv2.IMWRITE_JPEG_QUALITY, cfg["jpeg_quality"]] if ext == ".jpg" else []
    ok, buf = cv2.imencode(ext, work, params)
    assert ok
    return bytes(buf), ext, H.tolist(), [ow, oh], curve_px


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for score, (relative, page, source) in SCORES.items():
        pdf = ROOT / relative
        result = preprocess(str(pdf), pdf_page=page)
        image = result.original_bgr
        sp = float(np.median([s.spacing for s in result.staves]))
        expected = count_notes(ROOT / source)[2] if source else None
        for i, (name, cfg) in enumerate(CASES):
            seed = 20260928 + i
            raw, ext, H, dims, amp = image_case(image, sp, cfg, seed)
            filename = f"{score}__{name}{ext}"
            path = OUT / filename
            path.write_bytes(raw)
            rows.append(dict(score=score, condition=name, file=filename,
                             source_pdf=relative, source_page=page, source_pdf_sha256=sha(pdf),
                             source_ly=source, source_note_count=expected,
                             input_size=[image.shape[1], image.shape[0]], output_size=dims,
                             source_sp=sp, forward_homography=H,
                             transform_order="center_book_curve_then_homography_then_lighting_then_blur_then_noise_or_jpeg",
                             curve=dict(formula="y_out=y_in+A*(1-abs((x-(w-1)/2)/((w-1)/2)))**2",
                                        amplitude_px=amp, center_x=(image.shape[1]-1)/2),
                             parameters=cfg, random_seed=seed, sha256=hashlib.sha256(raw).hexdigest()))
            print(filename, flush=True)
    assert len(rows) == 57
    manifest=dict(kind="synthetic, not a real camera photograph", dpi=300,
                  opencv=cv2.__version__, numpy=np.__version__, interpolation="INTER_LINEAR",
                  border="white", sources=SCORES, images=rows,
                  omissions=["lens distortion", "paper texture", "depth-dependent defocus",
                             "camera sensor color pipeline"])
    (OUT / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
    archive=OUT / "synthetic_photos_57.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(OUT / "manifest.json", "manifest.json")
        for row in rows:
            z.write(OUT / row["file"], row["file"])
    print("TOTAL",len(rows),"ZIP",archive,"SHA256",sha(archive),flush=True)

if __name__ == "__main__":
    main()
