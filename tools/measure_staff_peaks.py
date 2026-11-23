# -*- coding: utf-8 -*-
"""(f) A-24 굵은 오선 한 줄이 두 줄로 — `detect_staff_lines`의 봉우리 조건 대안을 전 세트 보표 수 정답률로 비교. 제품 코드 무변경.

입력마다 이진화는 한 번(제품 `load_image` → (사진이면 `correct_photo`) → `binarize`), 같은 영상에 변형별 봉우리 → `group_into_staves` → `_add_short_staves`.
정답: `measure_short_system.pages()`(PDF 벡터 · Verovio SVG · Aoharu 골든 · 픽스처 · 사진 원본) + PDF 17쪽을 400 · 450 · 500 · 600dpi로(보표 수 = 300dpi 정답).

  product   find_peaks(height, distance=2)
  plateau   위 결과에서 3행 이내 이웃 봉우리 사이 골이 낮은 봉우리의 90% 이상이면 하나로(평평한 꼭대기 — 한 줄의 두께)
  dist3     distance=3
  prom      + prominence ≥ 0.1 × ref

    python tools/measure_staff_peaks.py          # all 을 붙이면 기울였다 되돌리기(sweep) · 사진을 사진 모드 없이(photo_plain)도
"""
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
VARIANTS = ("product", "plateau", "dist3", "prom", "impl")    # impl = 지금 제품 detect_staff_lines(구현 대조용)


def peaks(binary, variant):
    from scipy.signal import find_peaks
    from modules.preprocess import staff_line_profile
    width = binary.shape[1]
    row = staff_line_profile(binary)
    ref = float(row.max())
    thr = max(ref * 0.6, width * 0.5 * 0.5)
    if variant == "impl":
        from modules.preprocess import detect_staff_lines, StaffNotFoundError
        try:
            return detect_staff_lines(binary), row
        except StaffNotFoundError:
            return [], row
    if variant == "dist3":
        pk, _ = find_peaks(row, height=thr, distance=3)
    elif variant == "prom":
        pk, _ = find_peaks(row, height=thr, distance=2, prominence=0.1 * ref)
    else:
        pk, _ = find_peaks(row, height=thr, distance=2)
    pk = sorted(int(p) for p in pk)
    if variant == "plateau":
        out = []
        for p in pk:
            if out and p - out[-1] <= 3 and row[out[-1]:p + 1].min() >= 0.9 * min(row[out[-1]], row[p]):
                out[-1] = (out[-1] + p) // 2
            else:
                out.append(p)
        pk = out
    return pk, row


def _one(job):
    from modules.preprocess import load_image, binarize, group_into_staves, _add_short_staves
    st, name, path, pg, photo, n_truth, dpi = job
    bgr = load_image(path, pdf_page=pg, pdf_dpi=dpi) if path.endswith(".pdf") else load_image(path)
    if photo:
        from modules.photo_correct import correct_photo
        try:
            bgr, _ = correct_photo(bgr)
        except Exception:
            return st, name, dpi, n_truth, dict({v: "거부" for v in VARIANTS}, **{"plateau 봉우리 바뀜": False, "impl = plateau": True})
    _g, binary = binarize(bgr)
    got = {}
    base_pk = peaks(binary, "product")[0]
    got["plateau 봉우리 바뀜"] = peaks(binary, "plateau")[0] != base_pk
    got["impl = plateau"] = peaks(binary, "impl")[0] == peaks(binary, "plateau")[0]
    for v in VARIANTS:
        try:
            pk, row = peaks(binary, v)
            staves = _add_short_staves(binary, group_into_staves(pk, row_sum=row))
            got[v] = len(staves)
        except Exception as e:
            got[v] = type(e).__name__
    return st, name, dpi, n_truth, got


def main():
    import measure_short_system as S
    jobs = []
    for st, name, path, pg, photo, truth in S.pages():
        n = truth if isinstance(truth, int) else len(truth)
        if (st in ("sweep", "photo_plain") and "all" not in sys.argv) or not n:
            continue
        jobs.append((st, name, path, pg, photo, n, 300))
        if st == "pdf":
            for dpi in (400, 450, 500, 600):
                jobs.append((f"pdf{dpi}", name, path, pg, False, n, dpi))
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one, jobs))
    c = Counter()
    for st, name, dpi, n, got in res:
        for v in VARIANTS:
            c[(st, v)] += got[v] == n
        c[(st, "n")] += 1
        c[(st, "봉우리 바뀐 입력")] += bool(got["plateau 봉우리 바뀜"])
        c[(st, "impl ≠ plateau")] += not got["impl = plateau"]
        if any(got[v] != got["product"] for v in VARIANTS) or got["plateau 봉우리 바뀜"]:
            print("  변형마다 다름", st, name, "정답", n, got)
    sets = sorted({k[0] for k in c})
    for st in sets:
        print(f"{st:10s} {c[(st, 'n')]:3d}쪽 | " + " · ".join(f"{v} {c[(st, v)]}" for v in VARIANTS) + f" | plateau로 봉우리 목록이 바뀐 입력 {c[(st, '봉우리 바뀐 입력')]} · 제품 ≠ 사본 {c[(st, 'impl ≠ plateau')]}")


if __name__ == "__main__":
    main()
