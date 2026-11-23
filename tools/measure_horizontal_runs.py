# -*- coding: utf-8 -*-
"""Codex의 「막대쌍 사이 가로 연결 구간」 지표를 **정의만 받아 다시 구현해** 검증한다.

측정 전용. `modules/`는 읽기만 한다.

## 지표

두 막대의 세로 범위 교집합 안에서, **왼쪽 중심 열부터 오른쪽 중심 열까지 모든 픽셀이
잉크인 행**을 찾아 연속한 행을 한 구간으로 센다. 원본(`binary`) · 오선 제거(`no_staff`) ·
보표 밴드 closing(`closed`) 세 단계에서 각각 잰다.

> **이것은 가로획 개수가 아니다.** 깨끗한 글리프에서는 값이 같아지지만,
> 오선 잔여물·닿은 음표가 **구간을 더 만들고**, 괄호·이웃 잉크가 **구간을 지운다**.
> 「♯도 ♮도 가로획이 2개니 음악 규칙에서 나온 조건」이라고 부를 수 없다.

## 막대쌍 선택은 Codex 것을 그대로 쓴다

`connections.json`의 `bars`를 읽는다. **다시 구현한 것은 지표뿐이다.** 단,
`sweep` 모드는 음표에 매이지 않은 별도 경로로 후보를 모아 **집합 편향**을 본다.

## 모드

    python tools/measure_horizontal_runs.py check   [connections.json]
        170개 전부 다시 계산해 JSON과 대조하고, 단계·규칙별 분리력을 표로 낸다
    python tools/measure_horizontal_runs.py sheet   <그룹|runs=N> [출력png]
        그 집합을 확대 격자로 잘라 눈으로 본다(원본 | closing 나란히)
    python tools/measure_horizontal_runs.py tilt    [connections.json]
        대조군을 국소 회전시켜 **기울어진 획**에서 구간이 줄어드는지 본다
    python tools/measure_horizontal_runs.py sweep   <pdf파일명> <쪽(1부터)>
        보표 밴드 전체를 쓸어 **음표 기준 창 밖**의 막대쌍을 낸다
    python tools/measure_horizontal_runs.py sample  <개수> [출력폴더]
        미판정 closing 2구간에서 쪽별 비례로 뽑아 판정용 넓은 크롭 격자를 만든다

`connections.json` 기본 위치는 `~/Documents/악보헬퍼/direct-horizontal-20260911/`이다.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from modules import accidental_detect as ad
from modules.preprocess import preprocess
from modules.notehead_detect import remove_staff_lines

DEFAULT_JSON = os.path.expanduser(
    "~/Documents/악보헬퍼/direct-horizontal-20260911/connections.json")
STAGES = ("binary", "no_staff", "closed")

_pages = {}


def stages_of(filename, page):
    """(preprocess 결과, 오선 제거 영상). 쪽마다 한 번만 돌린다."""
    if (filename, page) not in _pages:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        res = preprocess(os.path.join(root, "test_scores", filename), pdf_page=page - 1)
        _pages[(filename, page)] = (res, remove_staff_lines(res.binary, res.staves))
    return _pages[(filename, page)]


def closed_band(res, ns, y):
    """그 y를 품는 보표 밴드를 제품과 같은 방식으로 닫는다. (밴드영상, top)

    밴드는 서로 겹친다(위 보표의 아래 여유 = 아래 보표의 위 여유). 제품은 음표의
    `staff_index`로 고르므로 **가장 가까운 보표**를 골라야 같은 밴드가 된다.
    처음에 「y를 포함하는 첫 보표」로 골랐다가 경계에 걸린 한 건이 어긋났다.
    """
    st = min(res.staves, key=lambda s: abs(y - (s.top + s.bottom) / 2))
    sp = st.spacing
    top = max(0, int(st.top - sp * 3.5))
    bot = min(ns.shape[0], int(st.bottom + sp * 3.5))
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    return cv2.morphologyEx(ns[top:bot], cv2.MORPH_CLOSE, k), top


def runs(img, ax, bx, lo, hi, yoff=0):
    """두 중심 열 사이를 **전부 잉크로 채우는 행**의 연속 구간 목록(절대 y)."""
    if hi < lo:
        return []
    assert 0 <= lo - yoff and hi - yoff < img.shape[0], "밴드 밖 — 조용히 잘릴 뻔했다"
    full = np.all(img[lo - yoff:hi - yoff + 1, int(ax):int(bx) + 1] > 0, axis=1)
    e = np.diff(np.r_[False, full, False].astype(int))
    return [[int(lo + u), int(lo + v - 1)]
            for u, v in zip(np.where(e == 1)[0], np.where(e == -1)[0])]


def recompute(row):
    """한 창의 단계별 구간을 다시 계산한다."""
    res, ns = stages_of(row["source"], row["page"])
    (ax, a0, a1), (bx, b0, b1) = row["bars"]
    lo, hi = max(a0, b0), min(a1, b1)
    cb, top = closed_band(res, ns, (lo + hi) // 2)
    return {"binary": runs(res.binary, ax, bx, lo, hi),
            "no_staff": runs(ns, ax, bx, lo, hi),
            "closed": runs(cb, ax, bx, lo, hi, top)}


def load(path):
    return json.load(open(path or DEFAULT_JSON, encoding="utf-8"))["rows"]


def mode_check(path):
    rows = load(path)
    bad = collections.Counter()
    for r in rows:
        got = recompute(r)
        for st in STAGES:
            if got[st] != r["stages"][st]["horizontal_runs"]:
                bad[st] += 1
                print(f"  불일치 {st} {r['source']} p{r['page']} {r['point']}: "
                      f"내 {got[st]} vs JSON {r['stages'][st]['horizontal_runs']}")
    print(f"{len(rows)}개 대조 — 불일치 {dict(bad) or 0}")

    for st in STAGES:
        print(f"\n== {st}")
        d = collections.defaultdict(collections.Counter)
        for r in rows:
            d[r["group"]][len(r["stages"][st]["horizontal_runs"])] += 1
        for g in ("direct_error", "known_control", "visual_control",
                  "observed_mismatch", "unreviewed"):
            c = d[g]
            print(f"  {g:18s} {sum(c.values()):4d}  {dict(sorted(c.items()))}")

    print("\n규칙별 분리력")
    err = [r for r in rows if r["group"] == "direct_error"]
    ctl = [r for r in rows if r["group"] in ("known_control", "visual_control")]
    unr = [r for r in rows if r["group"] == "unreviewed"]
    for name, keep in (("runs==2", lambda n: n == 2), ("runs>=2", lambda n: n >= 2)):
        for st in STAGES:
            n = lambda r: len(r["stages"][st]["horizontal_runs"])
            print(f"  {name:8s} {st:9s} 오류 거름 {sum(1 for r in err if not keep(n(r)))}/{len(err)}"
                  f"  대조 살림 {sum(1 for r in ctl if keep(n(r)))}/{len(ctl)}"
                  f"  미판정 거름 {sum(1 for r in unr if not keep(n(r)))}/{len(unr)}")


def _tile(row, idx, zoom=8, pad=6):
    res, ns = stages_of(row["source"], row["page"])
    (ax, a0, a1), (bx, b0, b1) = row["bars"]
    lo, hi = max(a0, b0), min(a1, b1)
    cb, top = closed_band(res, ns, (lo + hi) // 2)
    y0 = max(int(min(a0, b0)) - pad, top)
    y1 = min(int(max(a1, b1)) + pad, top + cb.shape[0])
    x0 = max(int(ax) - pad - 4, 0)
    x1 = min(int(bx) + pad + 4, cb.shape[1])
    pair = [res.original_bgr[y0:y1, x0:x1],
            np.repeat((255 - cb[y0 - top:y1 - top, x0:x1])[:, :, None], 3, axis=2)]
    pair = [cv2.resize(im, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
            for im in pair]
    for run in row["stages"]["closed"]["horizontal_runs"]:      # 왼쪽 여백에 눈금
        for im in pair:
            cv2.line(im, (0, (run[0] - y0) * zoom), (7, (run[1] - y0 + 1) * zoom), (0, 0, 255), 3)
    for im in pair:                                            # 재는 두 중심 열
        for x in (ax, bx):
            cv2.line(im, (int((x - x0) * zoom), 0), (int((x - x0) * zoom), im.shape[0]), (255, 0, 0), 1)
    body = np.hstack([pair[0], np.full((pair[0].shape[0], 10, 3), 255, np.uint8), pair[1]])
    head = np.full((26, body.shape[1], 3), 255, np.uint8)
    cv2.putText(head, f"{idx} {row['source'][:12]} p{row['page']} {tuple(row['point'])} "
                      f"{row['kind']} {row['group'][:12]} "
                      f"runs={len(row['stages']['closed']['horizontal_runs'])}",
                (2, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 0), 1)
    return np.vstack([head, body])


def mode_sheet(selector, out, path=None, cols=4):
    rows = load(path)
    if selector.startswith("runs="):
        want = int(selector.split("=")[1])
        sel = [(i, r) for i, r in enumerate(rows)
               if len(r["stages"]["closed"]["horizontal_runs"]) == want]
    else:
        sel = [(i, r) for i, r in enumerate(rows) if r["group"] == selector]
    if not sel:
        print("없음")
        return
    tiles = [_tile(r, i) for i, r in sel]
    W = max(t.shape[1] for t in tiles)
    H = max(t.shape[0] for t in tiles)
    canvas = np.full((((len(tiles) + cols - 1) // cols) * H, cols * W, 3), 255, np.uint8)
    for k, t in enumerate(tiles):
        r_, c_ = divmod(k, cols)
        canvas[r_ * H:r_ * H + t.shape[0], c_ * W:c_ * W + t.shape[1]] = t
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as f:                                  # 한글 경로 대응
        f.write(cv2.imencode(".png", canvas)[1].tobytes())
    print(f"{out}: {len(tiles)}개")


def _context_tile(row, idx, zoom=4):
    """판정용 넓은 크롭 — 막대쌍만 보면 음표와의 관계를 못 본다.

    막대 왼쪽 1.5sp부터 음표 오른쪽 1.2sp까지, 음표 위아래 3sp. 표시는 **잉크를 안
    가리게** 막대 범위 바깥에 파란 눈금, 음표 아래 빨간 눈금만 둔다.
    """
    res, _ = stages_of(row["source"], row["page"])
    (ax, a0, a1), (bx, b0, b1) = row["bars"]
    px, py = row["point"]
    sp = row["sp"]
    img = res.original_bgr
    x0, x1 = max(0, int(ax - sp * 1.5)), min(img.shape[1], int(px + sp * 1.2))
    y0, y1 = max(0, int(py - sp * 3)), min(img.shape[0], int(py + sp * 3))
    t = cv2.resize(img[y0:y1, x0:x1], None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
    for x, lo, hi in ((ax, a0, a1), (bx, b0, b1)):
        X = int((x - x0) * zoom)
        for y, d in ((lo, -1), (hi, 1)):
            Y = int((y - y0) * zoom) + d * 6
            cv2.line(t, (X, Y), (X, Y + d * 14), (255, 0, 0), 2)
    X, Y = int((px - x0) * zoom), int((py - y0 + sp * 0.8) * zoom)
    cv2.line(t, (X - 8, Y), (X + 8, Y), (0, 0, 255), 3)
    head = np.full((22, max(t.shape[1], 230), 3), 255, np.uint8)
    cv2.putText(head, f"#{idx} {row['source'][15:22]} p{row['page']} {tuple(row['point'])} {row['kind']}",
                (2, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 100, 0), 1)
    body = np.full((t.shape[0], head.shape[1], 3), 255, np.uint8)
    body[:, :t.shape[1]] = t
    return np.vstack([head, body])


def mode_sample(n_pick, out_dir, path=None, seed=0, per_sheet=10):
    """미판정 중 closing 2구간을 **쪽별 비례 층화**로 뽑아 판정용 격자를 만든다.

    한 쪽(B♭m 2쪽 33개)에 표본이 몰리면 쪽 특유의 조판이 비율을 끌고 가므로
    쪽별 개수에 비례해 뽑는다. 뽑힌 목록은 `sample.json`으로 남겨 판정을 붙인다.
    """
    import random
    rows = load(path)
    pool = [(i, r) for i, r in enumerate(rows) if r["group"] == "unreviewed"
            and len(r["stages"]["closed"]["horizontal_runs"]) == 2]
    by_page = collections.defaultdict(list)
    for i, r in pool:
        by_page[(r["source"], r["page"])].append((i, r))
    rng = random.Random(seed)
    # 최대 잉여 방식으로 정확히 n_pick개를 쪽에 나눈다
    quota = {k: n_pick * len(v) / len(pool) for k, v in by_page.items()}
    alloc = {k: int(q) for k, q in quota.items()}
    for k in sorted(quota, key=lambda k: quota[k] - alloc[k], reverse=True)[:n_pick - sum(alloc.values())]:
        alloc[k] += 1
    picked = []
    for k in sorted(by_page):
        picked += rng.sample(by_page[k], alloc[k])
    os.makedirs(out_dir, exist_ok=True)
    json.dump([{"idx": i, "source": r["source"], "page": r["page"], "point": r["point"],
                "kind": r["kind"]} for i, r in picked],
              open(os.path.join(out_dir, "sample.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for s in range(0, len(picked), per_sheet):
        tiles = [_context_tile(r, i) for i, r in picked[s:s + per_sheet]]
        cols = 5
        W = max(t.shape[1] for t in tiles) + 8
        H = max(t.shape[0] for t in tiles) + 8
        canvas = np.full((((len(tiles) + cols - 1) // cols) * H, cols * W, 3), 200, np.uint8)
        for k, t in enumerate(tiles):
            r_, c_ = divmod(k, cols)
            canvas[r_ * H:r_ * H + t.shape[0], c_ * W:c_ * W + t.shape[1]] = t
        out = os.path.join(out_dir, f"sample_{s // per_sheet + 1}.png")
        with open(out, "wb") as f:
            f.write(cv2.imencode(".png", canvas)[1].tobytes())
        print(f"{out}: {len(tiles)}개")
    print(f"모집단 {len(pool)} · 표본 {len(picked)} · 쪽별 {dict(sorted(alloc.items()))}")


def mode_tilt(path=None):
    """대조군을 국소 회전시켜 다시 잰다.

    글리프가 작아 페이지 기울기는 국소 회전과 거의 같다. 오선 제거 결과를 돌린 뒤
    제품과 같은 세로 closing을 걸고 **제품의 `_find_thin_bars`로 막대를 다시 찾는다**.
    오선 제거 자체가 기울기에서 달라지는 것은 안 담는다 — 그쪽은 `PORTABILITY.md`다.
    """
    rows = [r for r in load(path) if r["group"] in ("known_control", "visual_control")]

    def once(row, deg):
        res, ns = stages_of(row["source"], row["page"])
        (ax, a0, a1), (bx, b0, b1) = row["bars"]
        sp = row["sp"]
        pad = int(sp * 3)
        y0, x0 = max(0, int(min(a0, b0)) - pad), max(0, int(ax) - pad)
        patch = ns[y0:int(max(a1, b1)) + pad, x0:int(bx) + pad]
        if deg:
            h, w = patch.shape
            m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
            patch = cv2.warpAffine(patch, m, (w, h), flags=cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        closed = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, k)
        bars = ad._find_thin_bars(closed, sp)
        picked = []
        for want in (ax - x0, bx - x0):
            if not bars:
                return None
            cand = min(bars, key=lambda t: abs(t[0] - want))
            if abs(cand[0] - want) > sp * 0.35:
                return None
            picked.append(cand)
        (pax, pa0, pa1), (pbx, pb0, pb1) = picked
        if pbx <= pax:
            return None
        return len(runs(closed, pax, pbx, max(pa0, pb0), min(pa1, pb1)))

    print(f"대조군 {len(rows)}개 — 회전별 구간 수 (None = 막대쌍을 다시 못 찾음)")
    for deg in (0.0, 0.3, 0.6, 1.0, 2.0):
        c = collections.Counter(once(r, deg) for r in rows)
        print(f"  {deg:4.1f}도  {dict(sorted(c.items(), key=lambda kv: (kv[0] is None, kv[0])))}")
    print("\n여유가 왜 큰가 — 재는 폭이 좁다")
    for r in rows[:4]:
        (ax, _, _), (bx, _, _) = r["bars"]
        hs = [b - a + 1 for a, b in r["stages"]["closed"]["horizontal_runs"]]
        print(f"  {r['source'][:10]} p{r['page']} {tuple(r['point'])} "
              f"막대 간격 {bx - ax:.1f}px · 구간 높이 {hs}px")


def mode_sweep(filename, page, path=None):
    """음표에 매이지 않은 경로로 막대쌍을 모아 **집합 편향**을 본다."""
    rows = [r for r in load(path) if (r["source"], r["page"]) == (filename, page)]
    known = {(int(r["bars"][0][0]), int(r["bars"][0][1])) for r in rows}
    res, ns = stages_of(filename, page)
    out = []
    for st in res.staves:
        sp = st.spacing
        band, top = closed_band(res, ns, (st.top + st.bottom) // 2)
        bars = ad._find_thin_bars(band, sp)
        for a, b in zip(bars, bars[1:]):
            if not sp * 0.3 <= b[0] - a[0] <= sp * 0.95:
                continue
            kind = "natural" if a[1] + sp * .45 < b[1] and a[2] + sp * .45 < b[2] else "#"
            lo, hi = max(a[1], b[1]) + top, min(a[2], b[2]) + top
            out.append({"x": int(a[0]), "y": int((a[1] + a[2]) / 2) + top, "kind": kind,
                        "runs": len(runs(band, a[0], b[0], lo, hi, top)),
                        "known": (int(a[0]), int(a[1]) + top) in known})
    new = [f for f in out if not f["known"]]
    print(f"{filename} p{page}: 막대쌍 {len(out)}개 · 기존 목록({len(rows)}개)과 겹침 "
          f"{len(out) - len(new)}개 · 목록 밖 {len(new)}개")
    for kind in ("#", "natural"):
        c = collections.Counter(f["runs"] for f in new if f["kind"] == kind)
        print(f"  {kind:8s} {sum(c.values()):3d}개  구간수 {dict(sorted(c.items()))}")
    for f in new:
        if f["runs"] >= 2:
            print(f"  >> 목록 밖인데 {f['runs']}구간: ({f['x']},{f['y']}) {f['kind']} — 눈으로 볼 것")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    rest = sys.argv[2:]
    if mode == "check":
        mode_check(rest[0] if rest else None)
    elif mode == "sheet":
        mode_sheet(rest[0], rest[1] if len(rest) > 1 else "debug/runs_sheet.png")
    elif mode == "tilt":
        mode_tilt(rest[0] if rest else None)
    elif mode == "sweep":
        mode_sweep(rest[0], int(rest[1]))
    elif mode == "sample":
        mode_sample(int(rest[0]), rest[1] if len(rest) > 1 else "debug/runs_sample")
    else:
        print(f"모드는 check · sheet · tilt · sweep 이다: {mode}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
