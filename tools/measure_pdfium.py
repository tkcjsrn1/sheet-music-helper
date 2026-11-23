"""PDFium과 현재 PyMuPDF의 300dpi 첫 쪽 렌더 결과를 비교한다."""

import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import fitz
import numpy as np


def render_fitz(path):
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def render_pdfium(path):
    import pypdfium2

    doc = pypdfium2.PdfDocument(str(path))
    try:
        page = doc[0]
        try:
            rgb = np.asarray(page.render(scale=300 / 72).to_pil().convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        finally:
            page.close()
    finally:
        doc.close()


def main(paths):
    rows = []
    for path in paths:
        rendered = {}
        elapsed = {}
        for name, render in (("fitz", render_fitz), ("pdfium", render_pdfium)):
            samples = []
            for _ in range(3):
                start = time.perf_counter()
                image = render(path)
                samples.append(time.perf_counter() - start)
            rendered[name] = image
            elapsed[name] = round(statistics.median(samples), 3)
        first, second = rendered.values()
        height = min(first.shape[0], second.shape[0])
        width = min(first.shape[1], second.shape[1])
        delta = np.abs(first[:height, :width].astype(np.int16)
                       - second[:height, :width].astype(np.int16))
        changed = np.any(delta != 0, axis=2)
        over_10 = np.any(delta > 10, axis=2)
        difference = {
            "comparison_size": [width, height],
            "changed_fraction": round(float(changed.mean()), 6),
            "over_10_fraction": round(float(over_10.mean()), 6),
            "mean_abs_channel_delta": round(float(delta.mean()), 3),
        }
        rows.append({
            "file": str(path),
            "fitz_size": [first.shape[1], first.shape[0]],
            "pdfium_size": [second.shape[1], second.shape[0]],
            "median_seconds": elapsed,
            "pixel_difference": difference,
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main([Path(item) for item in sys.argv[1:]])
