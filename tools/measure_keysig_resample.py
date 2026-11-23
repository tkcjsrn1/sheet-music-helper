# -*- coding: utf-8 -*-
"""기울였다 되돌린 이미지에서 **조표가 왜 뒤집히나**, 보정 보간을 바꾸면 달라지나를 잰다.

측정 전용. `modules/`는 읽기만 한다(`_find_bars` 호출 인자를 가로채 기록할 뿐 결과는 안 바꾼다).

    python tools/measure_keysig_resample.py sweep  [출력.tsv]   # 악보 × 각도 × 보정 방식
    python tools/measure_keysig_resample.py why    <악보> <각도> <방식>   # 뒤집힌 한 건 해부

- 기울이기(카메라 흉내)는 항상 INTER_LINEAR로 고정한다 — 바꾸는 것은 **되돌리는 쪽**뿐이다
- 되돌리기는 정확히 −θ(oracle). 추정 오차는 이 측정에서 뺀다(`measure_photo_robustness.py recover`에서 0이었다)
- `up2`: 기울어진 이미지를 2배(INTER_CUBIC)로 키워 되돌리고(INTER_LINEAR) INTER_AREA로 줄인다
- `shift`는 기울기 없이 (0.5, 0.5)px 평행이동 — 보간 위상만 흔드는 대조
"""
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.preprocess import preprocess, load_image, binarize, detect_staff_lines, \
    group_into_staves, staff_line_profile, PreprocessResult  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402

SCORES = {
    "aoharu": (os.path.join(ROOT, "sample_images", "KakaoTalk_20260731_162400402.png"), 0),
    "bbm": (os.path.join(ROOT, "test_scores", "chopin_nocturne_Bbm.pdf"), 0),
    "bach": (os.path.join(ROOT, "test_scores", "bach_minuet_Am.pdf"), 0),
}
ANGLES = (0.15, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0,          # 기존 24회와 같은 8각
          0.2, 0.7, 1.5, 2.5, 4.0, 6.0, -1.0, -3.0)          # 표본을 늘리려 더한 8각
FLAGS = {"linear": cv2.INTER_LINEAR, "nearest": cv2.INTER_NEAREST,
         "cubic": cv2.INTER_CUBIC, "lanczos4": cv2.INTER_LANCZOS4}
METHODS = tuple(FLAGS) + ("up2",)


def _write(path, img):
    with open(path, "wb") as f:                        # 한글 경로 imwrite 실패 회피
        f.write(cv2.imencode(".png", img)[1].tobytes())


def _rot(im, deg, flag):
    H, W = im.shape[:2]
    m = cv2.getRotationMatrix2D((W / 2, H / 2), deg, 1.0)
    return cv2.warpAffine(im, m, (W, H), flags=flag,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def tilt_and_fix(img, deg, method):
    """흰 여백 → +θ(LINEAR) → −θ(method) → 원래 크기로 자름. `recover` 모드와 같은 틀."""
    h, w = img.shape[:2]
    pad = int(max(h, w) * 0.1)
    big = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    if deg == "shift":
        m = np.array([[1.0, 0, 0.5], [0, 1.0, 0.5]])
        flag = FLAGS.get(method, cv2.INTER_LINEAR)
        if method == "up2":
            up = cv2.resize(big, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            m2 = np.array([[1.0, 0, 1.0], [0, 1.0, 1.0]])
            out = cv2.warpAffine(up, m2, (up.shape[1], up.shape[0]), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
            out = cv2.resize(out, (big.shape[1], big.shape[0]), interpolation=cv2.INTER_AREA)
        else:
            out = cv2.warpAffine(big, m, (big.shape[1], big.shape[0]), flags=flag,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
        return out[pad:pad + h, pad:pad + w]
    tilted = _rot(big, deg, cv2.INTER_LINEAR)
    if method == "up2":
        up = cv2.resize(tilted, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        back = cv2.resize(_rot(up, -deg, cv2.INTER_LINEAR), (big.shape[1], big.shape[0]),
                          interpolation=cv2.INTER_AREA)
    else:
        back = _rot(tilted, -deg, FLAGS[method])
    return back[pad:pad + h, pad:pad + w]


class _Spy:
    """`_find_bars` 호출 인자를 보표 순서대로 기록한다(반환값은 그대로)."""

    def __init__(self):
        self.calls = []
        self._orig = CK._find_bars

    def __enter__(self):
        def spy(band, sp, x0, x1, r0, r1):
            out = self._orig(band, sp, x0, x1, r0, r1)
            self.calls.append(dict(band=band, sp=sp, x0=x0, x1=x1, r0=r0, r1=r1, out=out))
            return out
        CK._find_bars = spy
        return self

    def __exit__(self, *a):
        CK._find_bars = self._orig


def header(path, page=0):
    """보표별 막대·창과 투표 결과."""
    res = preprocess(path, pdf_page=page)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    single = len(res.staves) <= 2
    ctxs, win = {}, {}
    for s in res.staves:
        with _Spy() as spy:
            ctxs[s.index] = CK._analyze_one(ns, s, H, single)
        win[s.index] = spy.calls[0] if spy.calls else None
    kc, ks, _ = CK._vote_key_signature(ctxs)
    found = [c for c in ctxs.values() if c.clef_found]
    thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    return dict(key=f"{ks}{kc}" if kc else "0", ctxs=ctxs, win=win, thr=thr,
                staves=len(res.staves), found=len(found))


def clusters(h):
    """_vote_key_signature와 같은 ±3px 클러스터: [(x평균, {보표번호})]."""
    pts = sorted((x, i) for i, c in h["ctxs"].items() if c.clef_found for x, _ in c.bars)
    out, k = [], 0
    while k < len(pts):
        j = k
        while j + 1 < len(pts) and pts[j + 1][0] - pts[k][0] <= 3.0:
            j += 1
        out.append((float(np.mean([p[0] for p in pts[k:j + 1]])), {p[1] for p in pts[k:j + 1]}))
        k = j + 1
    return out


def margin(h):
    """인정 클러스터 중 가장 약한 것의 여유(지지 − 문턱)."""
    inc = [len(s) - h["thr"] for _x, s in clusters(h) if len(s) >= h["thr"]]
    return min(inc) if inc else None


def _max_run(col):
    best = run = 0
    for v in col:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def why_missing(h, si, x):
    """보표 si에서 구조 막대 x가 왜 안 잡혔나 — 한 줄 분류."""
    ctx, w = h["ctxs"].get(si), h["win"].get(si)
    if ctx is None or not ctx.clef_found:
        return "음자리표 못 찾음(보표 전체 탈락)"
    near = [bx for bx, _ in ctx.bars if abs(bx - x) <= 8]
    if near:
        return f"막대는 있음 x={near[0]:.1f} (Δ{near[0] - x:+.1f}px) — 클러스터 ±3px 밖"
    if w is None or not (w["x0"] <= x < w["x1"]):
        return f"수집 창 밖 [{w['x0'] if w else '?'}, {w['x1'] if w else '?'})"
    sp = w["sp"]
    seg_raw = w["band"][w["r0"]:w["r1"], w["x0"]:w["x1"]]
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    seg = cv2.morphologyEx(seg_raw, cv2.MORPH_CLOSE, vk)
    lx = int(round(x - w["x0"]))
    cols = range(max(0, lx - 4), min(seg.shape[1], lx + 5))
    runs = [_max_run(seg[:, c] > 0) for c in cols]
    is_bar = [sp * 1.6 <= r <= sp * 3.4 for r in runs]
    # 막대 열 덩어리 폭(x 주변으로 연속된 is_bar 열)
    allcols = np.array([sp * 1.6 <= _max_run(seg[:, c] > 0) <= sp * 3.4 for c in range(seg.shape[1])])
    c0 = c1 = lx
    if 0 <= lx < len(allcols) and allcols[lx]:
        while c0 > 0 and allcols[c0 - 1]:
            c0 -= 1
        while c1 + 1 < len(allcols) and allcols[c1 + 1]:
            c1 += 1
        width = c1 - c0 + 1
        if width > sp * 0.45:
            return (f"막대 열 폭 {width}px = {width / sp:.2f}sp > max_w 0.45sp → "
                    f"분할(_split_merged_bars) 실패")
    rmax = max(runs) if runs else 0
    if not any(is_bar):
        return (f"세로 run 최대 {rmax}px = {rmax / sp:.2f}sp — 높이 창 [1.6, 3.4]sp 밖")
    return "막대 열은 있는데 목록에 없음(기타)"


def compare(base, got):
    """원본 구조 막대마다 지지 보표가 어떻게 바뀌었나."""
    lines = []
    gc = clusters(got)
    for x, sup in clusters(base):
        if len(sup) < base["thr"]:
            continue
        match = [s for gx, s in gc if abs(gx - x) <= 3.0]
        now = set().union(*match) if match else set()
        lost, gained = sorted(sup - now), sorted(now - sup)
        tag = "인정" if len(now) >= got["thr"] else "**탈락**"
        lines.append(f"  구조막대 x={x:6.1f}: 지지 {len(sup)} → {len(now)} (문턱 {got['thr']}) {tag}"
                     + (f"  잃음 {lost}" if lost else "") + (f"  얻음 {gained}" if gained else ""))
        for si in lost:
            lines.append(f"      보표 {si}: {why_missing(got, si, x)}")
    for gx, s in gc:
        if len(s) >= got["thr"] and not any(abs(gx - x) <= 3.0 for x, _ in clusters(base)):
            lines.append(f"  새 구조막대 x={gx:6.1f}: 지지 {len(s)} 보표 {sorted(s)}")
    return lines


def _base(name, tmp):
    path, page = SCORES[name]
    img = preprocess(path, pdf_page=page).original_bgr
    p0 = os.path.join(tmp, f"{name}_base.png")
    _write(p0, img)
    return img, header(p0)


def sweep(out_tsv):
    tmp = os.path.join(ROOT, "debug", "keysig_resample")
    os.makedirs(tmp, exist_ok=True)
    rows = ["악보\t각도\t방식\t조표\t원본조표\t뒤집힘\t최약여유\t보표"]
    for name in SCORES:
        img, base = _base(name, tmp)
        print(f"{name}: 원본 {base['key']} 여유 +{margin(base)} 보표 {base['found']}/{base['staves']}", flush=True)
        for deg in ANGLES + ("shift",):
            for m in METHODS:
                p = os.path.join(tmp, f"{name}_{deg}_{m}.png")
                _write(p, tilt_and_fix(img, deg, m))
                try:
                    g = header(p)
                    key, mg, st = g["key"], margin(g), f"{g['found']}/{g['staves']}"
                except Exception as exc:                     # 실패도 결과다
                    key, mg, st = f"실패:{type(exc).__name__}", None, "-"
                flip = key != base["key"]
                rows.append(f"{name}\t{deg}\t{m}\t{key}\t{base['key']}\t{int(flip)}\t{mg}\t{st}")
                print(f"  {str(deg):>6s} {m:9s} {key:6s} {'뒤집힘' if flip else ''} 여유 {mg}", flush=True)
    with open(out_tsv, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")


def why(name, deg, method):
    tmp = os.path.join(ROOT, "debug", "keysig_resample")
    os.makedirs(tmp, exist_ok=True)
    img, base = _base(name, tmp)
    deg = deg if deg == "shift" else float(deg)
    p = os.path.join(tmp, f"{name}_{deg}_{method}_why.png")
    _write(p, tilt_and_fix(img, deg, method))
    got = header(p)
    print(f"{name} {deg} {method}: {base['key']} → {got['key']}  "
          f"보표 {got['found']}/{got['staves']} 문턱 {got['thr']}  여유 {margin(base)} → {margin(got)}")
    print("\n".join(compare(base, got)))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "sweep":
        sweep(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "debug", "keysig_resample.tsv"))
    elif len(sys.argv) >= 5 and sys.argv[1] == "why":
        why(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
