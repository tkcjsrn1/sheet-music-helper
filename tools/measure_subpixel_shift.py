# -*- coding: utf-8 -*-
"""0.5px 평행이동에서 **무엇이 어느 단계에서 흔들리는지** 가른다.

측정 전용. `modules/`는 읽기만 한다(검출기 내부 값은 **가로채서** 읽는다 — 재구현하지 않는다).

## 단계 나누기

같은 원인이라 단정하지 않고 네 갈래로 나눈다.

| 비교 | 무엇을 보나 |
|---|---|
| 이동 영상 + **자기 보표** vs 이동 영상 + **기준 보표를 옮긴 것** | 보표 검출의 기여 |
| 기준 보표를 옮긴 run에서 차이 난 음표가 **처음 갈라진 단계** | 머리 검출 / 빔 필터 / 오선 밖 필터 / 임시표 필터 |

「기준 보표를 옮긴 것」은 `bottom_fit`에 이동량을 더하고 `line_ys`는 정수 내림으로 둔다
(`line_ys`가 정수라 0.5px를 표현할 수 없다).

## 게이트

`notehead_detect._detect_noteheads_in_band`의 `opened` 연결 성분을 **실제 호출에서 가로채**
크기 게이트(529~541행)와 화음 분할 진입(`h > CHORD_SPLIT_SP`)의 값을 남긴다.
성분을 run끼리 짝지어 **게이트별 뒤집힘**을 세고, 같은 쪽에서 `sp`를 −0.10 흔든 run
(A-4/A-6 방식)과 **같은 덩어리가 뒤집히는지** 겹쳐 본다.

## 대조

- 정수 1px 이동 — 보간이 없다. 흔들림이 0이어야 위치가 아니라 보간 탓이다
- x만 0.5px / y만 0.5px — y만 오선 검출에 들어간다

    python tools/measure_subpixel_shift.py [bach|bbm|aoharu ...]
"""
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cv2
import numpy as np

from modules.preprocess import (load_image, binarize, detect_staff_lines, group_into_staves,
                                staff_line_profile, PreprocessResult, Staff)
from modules.clef_keysig import analyze_staves
import modules.notehead_detect as ND
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts

sys.path.insert(0, os.path.join(ROOT, "tests"))
from _score_context import context_diff, context_summary, label_texts  # noqa: E402

SCORES = {
    "bach": ("test_scores/bach_minuet_Am.pdf", 0),
    "bbm": ("test_scores/chopin_nocturne_Bbm.pdf", 0),
    "aoharu": ("sample_images/KakaoTalk_20260731_162400402.png", 0),
}
STAGES = ("머리검출", "빔필터", "오선밖필터", "임시표필터")
GATE_ORDER = ("area<0.5E", "w<0.70", "w>2.2", "h<0.68", "w>h*2.1")   # 코드 순서
GATES = GATE_ORDER + ("h>분할",)

# ---------------------------------------------------------------- 가로채기
_comps, _cur = [], {}


class _CV:
    """`ND.cv2` 자리에 끼운다. `opened`의 연결 성분 호출(인자 없는 유일한 호출)만 기록한다."""

    def __getattr__(self, k):
        return getattr(cv2, k)

    def connectedComponentsWithStats(self, img, *a, **kw):
        out = cv2.connectedComponentsWithStats(img, *a, **kw)
        if not a and not kw and _cur:
            n, _l, stats, cents = out
            st, top = _cur["staff"], _cur["top"]
            for i in range(1, n):
                x, y, w, h, area = (int(v) for v in stats[i])
                if cents[i][0] < _cur["header_end"]:
                    continue                                  # 검출기도 첫 줄에서 건너뛴다
                _comps.append(dict(staff=st.index, sp=float(st.spacing), x=x, y=y + top,
                                   w=w, h=h, area=area,
                                   cx=float(cents[i][0]), cy=float(cents[i][1]) + top))
        return out


_orig_band = ND._detect_noteheads_in_band


def _band(no_staff_img, staff, img_height, header_end=0, margins=None, reject_log=None):
    up = margins[0] if margins else staff.spacing * ND.BASE_MARGIN_SP
    _cur.update(staff=staff, top=max(0, staff.top - int(round(up))), header_end=header_end)
    try:
        return _orig_band(no_staff_img, staff, img_height, header_end=header_end,
                          margins=margins, reject_log=reject_log)
    finally:
        _cur.clear()


ND.cv2 = _CV()
ND._detect_noteheads_in_band = _band


def gate_values(c):
    """게이트별 (걸림 여부, 문턱까지 px 여유 — 양수면 통과 쪽)."""
    sp = c["sp"]
    E = math.pi * (sp * 0.6) * (sp * 0.42)
    return {
        "area<0.5E": (c["area"] < E * 0.5, c["area"] - E * 0.5),
        "w<0.70": (c["w"] < sp * 0.7, c["w"] - sp * 0.7),
        "w>2.2": (c["w"] > sp * 2.2, sp * 2.2 - c["w"]),
        "h<0.68": (c["h"] < sp * 0.68, c["h"] - sp * 0.68),
        "w>h*2.1": (c["w"] > c["h"] * 2.1, c["h"] * 2.1 - c["w"]),
        "h>분할": (c["h"] > sp * ND.CHORD_SPLIT_SP, sp * ND.CHORD_SPLIT_SP - c["h"]),
    }


def first_fail(c):
    g = gate_values(c)
    return next((k for k in GATE_ORDER if g[k][0]), "통과")


# ---------------------------------------------------------------- 실행
def run(bgr, staves=None):
    gray, binary = binarize(bgr)
    if staves is None:
        staves = group_into_staves(detect_staff_lines(binary), row_sum=staff_line_profile(binary))
    res = PreprocessResult(original_bgr=bgr, gray=gray, binary=binary, staves=staves)
    ctxs = analyze_staves(res)
    _comps.clear()
    rej = []
    heads = ND.detect_noteheads(res, contexts=ctxs, reject_log=rej)
    comps = list(_comps)
    b, _ = drop_beam_ghosts(res, heads)
    o, _ = drop_offstaff_ghosts(res, b)
    notes = calculate_pitches(o, staves, clef={i: c.clef for i, c in ctxs.items()})
    final, final_acc = remove_accidental_ghosts(notes, annotate_accidentals(res, ctxs, notes), staves)
    pts = lambda L: [(float(h.x), float(h.y), h.staff_index) for h in L]
    texts = label_texts(final, ctxs, final_acc)
    return dict(staves=staves, header={i: c.header_end for i, c in ctxs.items()},
                comps=comps, rej=rej, ctxs=ctxs,
                text={(float(n.x), float(n.y)): t for n, t in zip(final, texts)},
                st={"머리검출": pts(heads), "빔필터": pts(b), "오선밖필터": pts(o),
                    "임시표필터": pts(final)},
                pitch={(float(n.x), float(n.y)): f"{n.note_name}{n.octave}" for n in final})


def moved_staves(staves, dy, dsp=0.0):
    return [Staff(line_ys=[int(math.floor(v + dy)) for v in s.line_ys], spacing=s.spacing + dsp,
                  index=s.index, bottom_fit=s.bottom_fit + dy) for s in staves]


def shift(bgr, dx, dy):
    m = np.array([[1.0, 0, dx], [0, 1.0, dy]])
    return cv2.warpAffine(bgr, m, (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _find(pts, p, r):
    best = None
    for q in pts:
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d <= r and (best is None or d < best[0]):
            best = (d, q)
    return None if best is None else best[1]


def diff(r0, r1, dx, dy, sp):
    """최종 라벨 차이를 **처음 갈라진 단계**로 나눈다."""
    r = sp * 0.5
    out = []
    for p in r0["st"]["임시표필터"]:
        q = (p[0] + dx, p[1] + dy)
        m = _find(r1["st"]["임시표필터"], q, r)
        if m is None:
            stage = next(s for s in STAGES if _find(r1["st"][s], q, r) is None)
            out.append(dict(kind="소실", x=p[0], y=p[1], staff=p[2], stage=stage))
        elif r0["pitch"][p[:2]] != r1["pitch"][m[:2]]:
            out.append(dict(kind="음고", x=p[0], y=p[1], staff=p[2], stage="음고계산",
                            was=r0["pitch"][p[:2]], now=r1["pitch"][m[:2]]))
        elif r0["text"][p[:2]] != r1["text"][m[:2]]:
            # 음고는 같은데 표기가 다르다 = 조표·임시표가 바뀌었다. 음고만 보면 안 보인다
            out.append(dict(kind="표기", x=p[0], y=p[1], staff=p[2], stage="조표·임시표",
                            was=r0["text"][p[:2]], now=r1["text"][m[:2]]))
    for q in r1["st"]["임시표필터"]:
        p = (q[0] - dx, q[1] - dy)
        if _find(r0["st"]["임시표필터"], p, r) is None:
            stage = next(s for s in STAGES if _find(r0["st"][s], p, r) is None)
            out.append(dict(kind="신규", x=p[0], y=p[1], staff=q[2], stage=stage))
    return out


def comp_at(r, x, y, staff):
    """점을 품는 `opened` 성분(같은 보표). 여러 개면 중심이 가까운 것."""
    cs = [c for c in r["comps"] if c["staff"] == staff
          and c["x"] - 1 <= x <= c["x"] + c["w"] + 1 and c["y"] - 1 <= y <= c["y"] + c["h"] + 1]
    return min(cs, key=lambda c: math.hypot(c["cx"] - x, c["cy"] - y)) if cs else None


def rej_at(r, x, y, sp):
    return sorted({e["reason"] for e in r["rej"] if math.hypot(e["x"] - x, e["y"] - y) <= sp * 0.5})


def gate_flips(ca, cb, dx, dy):
    """두 run의 성분을 짝지어 게이트별 뒤집힘 목록. (게이트, 기준 성분)"""
    flips, unmatched = [], 0
    for a in ca:
        r = a["sp"] * 0.35
        cand = [b for b in cb if b["staff"] == a["staff"]
                and abs(b["cx"] - a["cx"] - dx) <= r and abs(b["cy"] - a["cy"] - dy) <= r]
        if not cand:
            unmatched += 1
            continue
        b = min(cand, key=lambda b: math.hypot(b["cx"] - a["cx"] - dx, b["cy"] - a["cy"] - dy))
        ga, gb = gate_values(a), gate_values(b)
        for k in GATES:
            if ga[k][0] != gb[k][0]:
                flips.append((k, a, b))
    return flips, unmatched


def describe(r0, r1, d, dx, dy):
    """차이 난 음표 하나에 게이트·거부 사유를 붙인다."""
    x0, y0 = d["x"], d["y"]
    sp = next(s.spacing for s in r0["staves"] if s.index == d["staff"]) if any(
        s.index == d["staff"] for s in r0["staves"]) else 20.0
    a = comp_at(r0, x0, y0, d["staff"])
    b = comp_at(r1, x0 + dx, y0 + dy, d["staff"])
    info = dict(d)
    for tag, c in (("기준", a), ("이동", b)):
        if c is None:
            info[tag] = None
            continue
        g = gate_values(c)
        info[tag] = dict(w_sp=round(c["w"] / sp, 3), h_sp=round(c["h"] / sp, 3),
                         first=first_fail(c),
                         margin={k: round(v[1], 2) for k, v in g.items()})
    if a and b:
        ga, gb = gate_values(a), gate_values(b)
        info["뒤집힌게이트"] = [k for k in GATES if ga[k][0] != gb[k][0]]
    info["거부사유_기준"] = rej_at(r0, x0, y0, sp)
    info["거부사유_이동"] = rej_at(r1, x0 + dx, y0 + dy, sp)
    return info


def crops(bgr, rows, sp, out):
    tiles = []
    for k, d in enumerate(rows):
        x, y = int(d["x"]), int(d["y"])
        r = int(sp * 2.5)
        t = bgr[max(0, y - r):y + r, max(0, x - r):x + r].copy()
        cx, cy = min(r, x), min(r, y)
        cv2.rectangle(t, (cx - int(sp * .75), cy - int(sp * .6)), (cx + int(sp * .75), cy + int(sp * .6)),
                      (0, 0, 255) if d["kind"] == "소실" else (255, 0, 0), 1)
        t = cv2.resize(t, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        t = cv2.copyMakeBorder(t, 22, 6, 4, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        tag = {"소실": "L", "신규": "N", "음고": "P", "표기": "K"}[d["kind"]]
        cv2.putText(t, f"#{k} {tag} ({x},{y}) {d['stage'][:2]}", (2, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 110, 0), 1)
        tiles.append(t)
    if not tiles:
        return
    W = max(t.shape[1] for t in tiles)
    H = max(t.shape[0] for t in tiles)
    cols = 6
    canvas = np.full((((len(tiles) + cols - 1) // cols) * H, cols * W, 3), 190, np.uint8)
    for k, t in enumerate(tiles):
        rr, cc = divmod(k, cols)
        canvas[rr * H:rr * H + t.shape[0], cc * W:cc * W + t.shape[1]] = t
    with open(out, "wb") as f:
        f.write(cv2.imencode(".png", canvas)[1].tobytes())


def measure(name):
    src, page = SCORES[name]
    bgr = load_image(os.path.join(ROOT, src), pdf_page=page)
    r0 = run(bgr)
    sp = float(np.mean([s.spacing for s in r0["staves"]]))
    n0 = len(r0["st"]["임시표필터"])
    print(f"\n######## {name}  sp={sp:.2f}  최종 라벨 {n0}  성분 {len(r0['comps'])}  "
          f"{context_summary(r0['ctxs'])}")
    report = dict(name=name, sp=sp, labels=n0, cases={})

    for label, dx, dy in (("정수1px", 1.0, 1.0), ("x0.5", 0.5, 0.0), ("y0.5", 0.0, 0.5), ("xy0.5", 0.5, 0.5)):
        img = shift(bgr, dx, dy)
        own = run(img)
        fixed = run(img, moved_staves(r0["staves"], dy))
        st_same = (len(own["staves"]) == len(r0["staves"]) and all(
            [v - int(math.floor(u + dy)) for u, v in zip(a.line_ys, b.line_ys)] == [0] * 5
            and abs(b.spacing - a.spacing) < 1e-9 for a, b in zip(r0["staves"], own["staves"])))
        dsp = [round(b.spacing - a.spacing, 3) for a, b in zip(r0["staves"], own["staves"])]
        d_own, d_fix = diff(r0, own, dx, dy, sp), diff(r0, fixed, dx, dy, sp)
        d_between = diff(fixed, own, 0, 0, sp)            # 보표만 다른 두 run
        hd = sum(1 for k in r0["header"] if own["header"].get(k) is not None
                 and abs(own["header"][k] - r0["header"][k] - dx) > 1)
        fl, unm = gate_flips(r0["comps"], fixed["comps"], dx, dy)
        ctx_d = context_diff(r0["ctxs"], own["ctxs"], dx=dx)
        print(f"== {label}: 보표 동일={st_same} Δsp={dsp}  header_end 1px 넘게 바뀐 보표 {hd}")
        print(f"   문맥: {context_summary(own['ctxs'])}  차이 {len(ctx_d)} {ctx_d[:4]}")
        c = lambda ds: dict(collections.Counter(f"{d['kind']}@{d['stage']}" for d in ds))
        print(f"   자기 보표   : 차이 {len(d_own):3d}  {c(d_own)}")
        print(f"   기준 보표   : 차이 {len(d_fix):3d}  {c(d_fix)}")
        print(f"   보표만 다름 : 차이 {len(d_between):3d}  {c(d_between)}")
        print(f"   성분 게이트 뒤집힘(기준 보표 run): {dict(collections.Counter(k for k, _, _ in fl))}"
              f"  짝 없음 {unm}/{len(r0['comps'])}")
        report["cases"][label] = dict(
            staves_same=st_same, dsp=dsp, header_changed=hd, context_diff=ctx_d,
            own=[describe(r0, own, d, dx, dy) for d in d_own],
            fixed=[describe(r0, fixed, d, dx, dy) for d in d_fix],
            between=len(d_between),
            gate_flips=dict(collections.Counter(k for k, _, _ in fl)),
            flip_blobs=[dict(gate=k, x=a["cx"], y=a["cy"], staff=a["staff"],
                             margin0=round(gate_values(a)[k][1], 2), margin1=round(gate_values(b)[k][1], 2))
                        for k, a, b in fl])
        if label == "xy0.5":
            crops(bgr, report["cases"][label]["own"], sp, os.path.join(ROOT, "debug", f"shift_{name}.png"))

    # A-6 방식: sp를 −0.10 흔든다(영상 그대로)
    jit = run(bgr, moved_staves(r0["staves"], 0.0, -0.10))
    fl, unm = gate_flips(r0["comps"], jit["comps"], 0, 0)
    report["jitter"] = [dict(gate=k, x=a["cx"], y=a["cy"], staff=a["staff"]) for k, a, _ in fl]
    print(f"== δsp=−0.10: 성분 게이트 뒤집힘 {dict(collections.Counter(k for k, _, _ in fl))}  "
          f"최종 차이 {len(diff(r0, jit, 0, 0, sp))}")
    shift_blobs = report["cases"]["xy0.5"]["flip_blobs"]
    for g in GATES:
        s = [b for b in shift_blobs if b["gate"] == g]
        j = [b for b in report["jitter"] if b["gate"] == g]
        both = sum(1 for b in s if any(b2["staff"] == b["staff"] and abs(b2["x"] - b["x"]) <= 3
                                       and abs(b2["y"] - b["y"]) <= 3 for b2 in j))
        if s or j:
            print(f"   {g:9s} 이동 뒤집힘 {len(s):3d} · δsp 뒤집힘 {len(j):3d} · 같은 덩어리 {both}")
    with open(os.path.join(ROOT, "debug", f"shift_{name}.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    for nm in (sys.argv[1:] or list(SCORES)):
        measure(nm)
