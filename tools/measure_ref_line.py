# -*- coding: utf-8 -*-
"""A-12 — 오선 문턱의 기준 ref(가장 긴 가로선 행)가 **오선이 아닌 선**에 끌려 올라가는가. 측정 전용.

`detect_staff_lines`는 `threshold = max(0.6 × ref, …)`, ref = `staff_line_profile(binary).max()`다.
영상마다 ref 행이 검출된 보표(±1sp) 안인지 밖인지, ref가 **오선 봉우리 최대**보다 얼마나 큰지(문턱 상승률),
그 문턱 때문에 문턱 아래로 떨어진 오선 줄이 몇 개인지를 잰다.

「떨어진 줄」은 **오선 봉우리 최대 × 0.6**을 쓴 가상의 문턱과 비교해 센다 — 가짜 선이 없었으면 살았을 줄.

    python tools/measure_ref_line.py <이미지>...
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.preprocess import (load_image, binarize, staff_line_profile, detect_staff_lines,  # noqa: E402
                                group_into_staves, StaffNotFoundError)


def one(path):
    bgr = load_image(path)
    _g, binary = binarize(bgr)
    prof = staff_line_profile(binary).astype(float)
    ref, ref_y = float(prof.max()), int(prof.argmax())
    try:
        ys = detect_staff_lines(binary)
        staves = group_into_staves(ys, row_sum=staff_line_profile(binary))
    except StaffNotFoundError as exc:
        return dict(file=os.path.basename(path), fail=str(exc)[:30], ref=ref, ref_y=ref_y)
    sp = float(np.median([s.spacing for s in staves]))
    in_staff = any(s.top - sp <= ref_y <= s.bottom + sp for s in staves)
    line_peak = max(prof[y] for s in staves for y in s.line_ys)
    # 가짜 선이 없었다면 쓰였을 문턱으로 살아남았을 오선 봉우리 중, 지금 문턱에 떨어진 것
    from scipy.signal import find_peaks
    width = binary.shape[1]
    cur_thr = max(ref * 0.6, width * 0.25 * 0.5) if False else ref * 0.6
    alt_thr = line_peak * 0.6
    pk_alt, _ = find_peaks(prof, height=alt_thr, distance=2)
    pk_cur, _ = find_peaks(prof, height=cur_thr, distance=2)
    return dict(file=os.path.basename(path), fail=None, ref=ref, ref_y=ref_y, in_staff=in_staff,
                line_peak=line_peak, rise=ref / line_peak - 1, staves=len(staves),
                dropped=len(pk_alt) - len(pk_cur))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = one(p)
        if r["fail"]:
            print(f"{r['file']:62s} 오선 실패 — ref {r['ref']:.0f} @y{r['ref_y']}")
            continue
        tag = "오선" if r["in_staff"] else "**오선 밖**"
        print(f"{r['file']:62s} ref @y{r['ref_y']:5d} {tag:9s} 문턱 상승 {r['rise'] * 100:+6.1f}% · "
              f"떨어진 봉우리 {r['dropped']:3d} · 보표 {r['staves']}", flush=True)
