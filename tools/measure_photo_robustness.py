# -*- coding: utf-8 -*-
"""인쇄 PDF를 **촬영본처럼 망가뜨려** 결론이 살아남는지 잰다.

측정 전용. `modules/`는 읽기만 한다.

## 왜 필요한가

`filled` 단서(`docs/ACCIDENTAL_GHOST_MEASURE.md`)는 **인쇄 PDF 다섯 악보에서만**
확인됐다. 앱으로 가면 촬영본이 주 입력이 되는데, 유일한 촬영 표본인 RE:Aoharu에는
**임시표가 0개**라 삭제 후보 자체가 없다 — 그쪽에서 시험할 표본이 없다.

그래서 임시표가 있는 인쇄본에 촬영 열화를 걸어 **대리 표본**을 만든다.

> **합성이지 실제 촬영본이 아니다.** 번짐·조명기울기·잡음·JPEG만 흉내낸다.
> 원근·종이 휨·손떨림 잔상은 안 들어 있다(`docs/PORTABILITY.md`의 관찰과 같은 한계).
> 여기서 살아남는다고 실제 사진에서 살아남는다는 뜻이 아니다. **깨지면 확실한 반증**이고
> 안 깨지면 「이 네 가지로는 안 깨진다」까지다.

## 두 가지 모드

    python tools/measure_photo_robustness.py filled <악보> [쪽]
        열화 단계별로 삭제 후보 수와 **채워짐/빈 분포**를 낸다

    python tools/measure_photo_robustness.py tilt <악보> [쪽]
        기울기 한계를 잰다. **폭을 잘라 가며** 재는 것이 요점이다 —
        한계가 각도가 아니라 **세로 밀림(px)**이라는 것을 그래야 가른다

`0도`도 똑같이 warpAffine을 통과시켜 **변환 자체의 영향**을 대조로 가른다.
"""
import collections
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts

from measure_accidental_ghost_drops import survey

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from _score_context import context_diff, label_texts  # noqa: E402

# (회전도, 블러시그마, 조명세기, 잡음시그마, JPEG품질)
LEVELS = [
    ("원본",      (0.0, 0.0, 0.00,  0, 100)),
    ("약",        (0.0, 0.8, 0.12,  3,  90)),
    ("중",        (0.0, 1.4, 0.25,  6,  80)),
    ("강",        (0.0, 2.2, 0.40, 10,  70)),
    ("블러만",    (0.0, 1.4, 0.00,  0, 100)),
    ("조명만",    (0.0, 0.0, 0.25,  0, 100)),
]


def degrade(bgr, rot=0.0, sigma=0.0, light=0.0, noise=0, quality=100):
    """촬영 열화를 흉내낸다. 인자가 전부 0이면 원본을 그대로 돌려준다."""
    h, w = bgr.shape[:2]
    img = bgr.astype(np.float32)
    if rot:
        m = cv2.getRotationMatrix2D((w / 2, h / 2), rot, 1.0)
        img = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
    if sigma:
        img = cv2.GaussianBlur(img, (0, 0), sigma)
    if light:
        # 대각 조명 기울기. 한쪽 귀퉁이가 어두워진다
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        img *= (1.0 - light * ((xx / w) * 0.6 + (yy / h) * 0.4))[:, :, None]
    if noise:
        img += np.random.default_rng(0).normal(0, noise, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if quality < 100:
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


def _write(path, img):
    """한글 경로에서 `imwrite`가 조용히 실패하므로 `imencode`로 쓴다(`CLAUDE.md` §6)."""
    with open(path, "wb") as f:
        f.write(cv2.imencode(".png", img)[1].tobytes())


def filled_of(path, page=0):
    """(x, y) -> filled. `survey`와 **같은 순서**로 검출해야 좌표가 맞는다.

    `PitchedNote`가 `filled`를 안 들고 있어 검출 단계에서 다시 뽑는다.
    """
    res = preprocess(path, pdf_page=page)
    heads = detect_noteheads(res, contexts=analyze_staves(res))
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    return ({(int(h.x), int(h.y)): bool(h.filled) for h in heads},
            len(heads), sum(1 for h in heads if not h.filled))


def mode_filled(src, page, out_dir):
    base = preprocess(src, pdf_page=page).original_bgr
    print(f"{'단계':8s} {'라벨':>5s} {'임시표':>5s} {'빈비율':>6s} "
          f"{'삭제':>4s} {'채워짐':>5s} {'빈':>4s}")
    for name, params in LEVELS:
        png = os.path.join(out_dir, f"{name}.png")
        _write(png, degrade(base, *params))
        try:
            fmap, n_head, n_hollow = filled_of(png)
            summary, hits, notes, _ = survey(png, 0)
        except Exception as exc:                      # 실패도 결과다. 숨기지 않는다
            print(f"{name:8s} 실패 {type(exc).__name__}")
            continue
        flags = [fmap.get((int(notes[i].x), int(notes[i].y)))
                 for i in sorted({h["i"] for h in hits})]
        print(f"{name:8s} {summary['라벨(삭제 전)']:5d} {summary['임시표']:5d} "
              f"{100 * n_hollow / max(1, n_head):5.1f}% {len(flags):4d} "
              f"{sum(1 for f in flags if f is True):5d} "
              f"{sum(1 for f in flags if f is False):4d}  {summary['문맥']}")


def mode_tilt(src, page, out_dir):
    """기울기 × 폭. 한계가 각도가 아니라 밀림(px)이면 좁은 폭은 더 큰 각도를 견딘다."""
    res = preprocess(src, pdf_page=page)
    base = res.original_bgr
    sp = sum(s.spacing for s in res.staves) / len(res.staves)
    print(f"기준 sp={sp:.1f}px  폭={base.shape[1]}px")
    print(f"{'각도':>7s} {'폭':>6s} {'밀림px':>7s} {'밀림/sp':>8s}  결과")
    for deg in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.6):
        for frac in (1.0, 0.5, 0.25):
            img = degrade(base, rot=deg)
            if frac < 1.0:
                w = img.shape[1]
                img = img[:, int(w * (0.5 - frac / 2)):int(w * (0.5 + frac / 2))]
            png = os.path.join(out_dir, f"tilt{deg}_{frac}.png")
            _write(png, img)
            drift = math.tan(math.radians(deg)) * img.shape[1]
            try:
                summary, _, _, _ = survey(png, 0)
                got = f"라벨 {summary['라벨(삭제 전)']}  {summary['문맥']}"
            except Exception as exc:
                got = f"실패 {type(exc).__name__}"
            print(f"{deg:6.2f}° {img.shape[1]:6d} {drift:7.1f} {drift / sp:8.2f}  {got}")


def pipeline_stages(png):
    """골든과 같은 순서로 돌리되 **단계마다 결과를 남긴다.** 예외도 어느 단계인지 적는다."""
    from modules.preprocess import (load_image, binarize, detect_staff_lines,
                                    group_into_staves, staff_line_profile,
                                    PreprocessResult, StaffNotFoundError)
    from modules.pitch_calculator import calculate_pitches
    st = {"fail": None, "peaks": 0, "staves": [], "heads": [], "kept": [], "notes": []}
    bgr = load_image(png)
    gray, binary = binarize(bgr)
    try:
        ys = detect_staff_lines(binary)
        st["peaks"] = len(ys)
        staves = group_into_staves(ys, row_sum=staff_line_profile(binary))
    except StaffNotFoundError as exc:
        st["fail"] = "오선검출" if not st["peaks"] else "보표묶기"
        st["msg"] = str(exc)[:40]
        return st
    st["staves"] = staves
    res = PreprocessResult(original_bgr=bgr, gray=gray, binary=binary, staves=staves)
    try:
        ctxs = analyze_staves(res)
        heads = detect_noteheads(res, contexts=ctxs)
    except Exception as exc:                          # 실패도 결과다
        st["fail"] = f"머리검출:{type(exc).__name__}"
        return st
    st["heads"] = [(h.x, h.y) for h in heads]
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    st["kept"] = [(h.x, h.y) for h in heads]
    notes = calculate_pitches(heads, staves, clef={i: c.clef for i, c in ctxs.items()})
    from modules.accidental_detect import annotate_accidentals
    texts = label_texts(notes, ctxs, annotate_accidentals(res, ctxs, notes))
    st["ctxs"] = ctxs
    st["notes"] = [(n.x, n.y, f"{n.note_name}{n.octave}", n.staff_index, t)
                   for n, t in zip(notes, texts)]
    return st


def _near(pt, pts, r):
    """pt에서 r 안의 가장 가까운 점 번호, 없으면 None."""
    if not pts:
        return None
    a = np.asarray([p[:2] for p in pts], dtype=float)
    d = np.hypot(a[:, 0] - pt[0], a[:, 1] - pt[1])
    k = int(d.argmin())
    return k if d[k] <= r else None


def compare(base, got, m, sp):
    """기준 음표를 변환 m으로 옮겨 대응시키고, 사라진 음표를 **단계별로** 나눈다.

    - 보표소실: 그 음표의 보표 자리에 검출된 보표가 없다(오선 검출 쪽 손실)
    - 머리검출: 보표는 있는데 머리 후보부터 없다
    - 유령제거: 머리는 나왔는데 빔·덧줄 유령 제거에서 지워졌다

    유지된 음표는 음고와 **표기**(조표·임시표 반영)를 따로 센다. 조표가 뒤집히면 음고는
    그대로이고 표기만 바뀐다. 음자리표·조표 차이도 `문맥차이`로 센다(회전이면 header_end 제외).
    """
    out = collections.Counter()
    mv = lambda x, y: tuple((m @ np.array([x, y, 1.0]))[:2])
    moved = [mv(x, y) for x, y, _, _, _ in base["notes"]]
    staff_ys = [(s.top + s.bottom) / 2 for s in got["staves"]]
    base_c = {s.index: (s.top + s.bottom) / 2 for s in base["staves"]}
    rotated = not np.allclose(m, np.array([[1.0, 0, 0], [0, 1.0, 0]]))
    ctx_d = [d for d in context_diff(base["ctxs"], got["ctxs"])
             if not (rotated and "header_end" in d)]
    if ctx_d:
        out["문맥차이"] = len(ctx_d)
    used = set()
    for (x, y, pitch, si, text), (bx, by) in zip(base["notes"], moved):
        k = _near((bx, by), got["notes"], sp * 0.5)
        if k is not None and k not in used:
            used.add(k)
            out["유지"] += 1
            if got["notes"][k][2] != pitch:
                out["음고바뀜"] += 1
            elif got["notes"][k][4] != text:
                out["표기바뀜"] += 1
            continue
        # 음표 자리가 아니라 **그 음표가 속했던 보표의 중심**이 옮겨진 자리에 보표가 있나
        # (덧줄 음표는 보표 중심에서 3sp 넘게 떨어져 있어 음표 y로 보면 오분류된다)
        _, sy = mv(x, base_c[si])
        if not any(abs(sy - c) <= sp for c in staff_ys):
            out["소실:보표소실"] += 1
        elif _near((bx, by), got["heads"], sp * 0.5) is None:
            out["소실:머리검출"] += 1
        elif _near((bx, by), got["kept"], sp * 0.5) is None:
            out["소실:유령제거"] += 1
        else:
            out["소실:기타"] += 1
    out["새로생김"] = len(got["notes"]) - len(used)
    return out


def _staff_length(res):
    """오선 한 줄의 실제 가로 길이(px) 중앙값 — 밀림은 이미지 폭이 아니라 이 길이에 걸린다."""
    lens = []
    for s in res.staves:
        row = res.binary[s.line_ys[2]] > 0
        xs = np.flatnonzero(row)
        if len(xs):
            lens.append(xs[-1] - xs[0])
    return float(np.median(lens))


def mode_stages(src, page, out_dir):
    """각도별로 어느 단계에서 음표가 사라지는지 센다."""
    res = preprocess(src, pdf_page=page)
    img = res.original_bgr
    h, w = img.shape[:2]
    sp = sum(s.spacing for s in res.staves) / len(res.staves)
    L = _staff_length(res)
    print(f"sp={sp:.1f}px  폭={w}px  오선길이={L:.0f}px (={L / sp:.0f}sp)  보표 {len(res.staves)}")
    base = None
    # 대조 둘: 0.5px 평행이동(보간 번짐 최대, 기울기 0)과 0.001° 회전
    shift = np.array([[1.0, 0, 0.5], [0, 1.0, 0.5]])
    cases = [("원본", 0.0, None), ("이동0.5px", 0.0, shift), ("0.001°", 0.001, None)]
    cases += [(f"{d:.3f}°", d, None) for d in (0.05, 0.1, 0.125, 0.15, 0.175, 0.2, 0.25)]
    for label, deg, mat in cases:
        m = mat if mat is not None else cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
        png = os.path.join(out_dir, f"st_{label}.png")
        warped = img if base is None else cv2.warpAffine(
            img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        _write(png, warped)
        got = pipeline_stages(png)
        if base is None:
            base = got
        drift = math.tan(math.radians(deg)) * L / sp
        head = (f"{label:>9s} 밀림 {drift:4.2f}sp  봉우리 {got['peaks']:3d} "
                f"보표 {len(got['staves']):2d}  라벨 {len(got['notes']):3d}")
        if got["fail"]:
            print(f"{head}  실패@{got['fail']} ({got.get('msg', '')})")
            continue
        print(f"{head}  {dict(compare(base, got, m, sp))}")


def estimate_skew(bgr, lo=-8.0, hi=8.0):
    """행 투영이 가장 뾰족해지는 기울기(도)를 찾는다. **측정용 최소 구현**이다.

    회전 대신 전단(y - x·tanθ)으로 근사하고 잉크 좌표의 bincount 제곱합을 최대화한다.
    거친 탐색(1/4 축소, 0.05°) → 원해상도 미세 탐색(±0.1°, 0.005°).
    """
    from modules.preprocess import binarize
    _, binary = binarize(bgr)

    def best(bin_img, scale, angles):
        ys, xs = np.nonzero(bin_img)
        xs = xs - bin_img.shape[1] / 2
        top = None
        for a in angles:
            yy = np.round(ys - xs * math.tan(math.radians(a))).astype(np.int64)
            yy -= yy.min()
            score = float((np.bincount(yy).astype(np.float64) ** 2).sum())
            if top is None or score > top[0]:
                top = (score, a)
        return top[1]

    small = cv2.resize(binary, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    coarse = best(small > 127, 0.25, np.arange(lo, hi + 1e-9, 0.05))
    # 전단 각도와 `getRotationMatrix2D`의 각도는 부호가 반대다(y축이 아래로 향한다)
    return -best(binary, 1.0, np.arange(coarse - 0.1, coarse + 0.1 + 1e-9, 0.005))


def mode_recover(src, page, out_dir):
    """기울였다가 되돌렸을 때 얼마나 돌아오는가.

    - 이론 상한(oracle): 정확히 -θ로 되돌린다 → **재표본화 두 번의 번짐만** 남는다
    - 추정 보정: `estimate_skew`로 잰 각도로 되돌린다 → 추정 오차까지 포함
    회전으로 모서리가 잘리지 않게 흰 여백을 붙였다가 되돌린 뒤 원래 크기로 자른다.
    """
    res = preprocess(src, pdf_page=page)
    img = res.original_bgr
    h, w = img.shape[:2]
    sp = sum(s.spacing for s in res.staves) / len(res.staves)
    pad = int(max(h, w) * 0.1)
    big = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    H, W = big.shape[:2]

    def rot(im, deg):
        m = cv2.getRotationMatrix2D((W / 2, H / 2), deg, 1.0)
        return cv2.warpAffine(im, m, (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    base_png = os.path.join(out_dir, "rc_base.png")
    _write(base_png, img)
    base = pipeline_stages(base_png)
    ident = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    print(f"sp={sp:.1f}px  기준 라벨 {len(base['notes'])}")
    print(f"{'각도':>6s} {'방식':6s} {'추정':>7s} {'잔차':>7s}  결과")
    hows = sys.argv[5].split(",") if len(sys.argv) > 5 else ("oracle", "추정")
    # 여섯째 인자: 각도 목록(쉼표). 8°를 넘으면 추정 범위도 넓힌다(기본 ±8°)
    degs = [float(v) for v in sys.argv[6].split(",")] if len(sys.argv) > 6 else (0.15, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0)
    for deg in degs:
        tilted = rot(big, deg)
        rng = max(8.0, abs(deg) + 2.0)
        for how in hows:
            back = -deg if how == "oracle" else -estimate_skew(tilted, -rng, rng)
            fixed = rot(tilted, back)[pad:pad + h, pad:pad + w]
            png = os.path.join(out_dir, f"rc{deg}_{how}.png")
            _write(png, fixed)
            got = pipeline_stages(png)
            resid = deg + back
            tag = "실패@" + got["fail"] if got["fail"] else dict(compare(base, got, ident, sp))
            print(f"{deg:5.2f}° {how:6s} {-back:7.3f} {resid:+7.3f}  라벨 {len(got['notes'])} {tag}", flush=True)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mode, src = sys.argv[1], sys.argv[2]
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    out_dir = sys.argv[4] if len(sys.argv) > 4 else "debug/photo_proxy"
    os.makedirs(out_dir, exist_ok=True)
    if mode == "filled":
        mode_filled(src, page, out_dir)
    elif mode == "tilt":
        mode_tilt(src, page, out_dir)
    elif mode == "stages":
        mode_stages(src, page, out_dir)
    elif mode == "recover":
        mode_recover(src, page, out_dir)
    else:
        print(f"모드는 filled · tilt · stages · recover 다: {mode}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
