# -*- coding: utf-8 -*-
"""**음표 → 라벨** 방향 검사 — 「음표처럼 보이는데 라벨이 없는 자리」를 찾는다.

측정 전용. `modules/`는 읽기만 한다.

## 왜 필요한가

지금 검증은 전부 **라벨 → 음표** 방향이다. 사람의 전수 판정도, `verify.reverse_check`도
출력된 라벨 자리에 잉크가 있는지 본다. **그 방향으로는 오삭제가 안 보인다** —
지워진 음표는 라벨이 없어 대조 대상이 아니다.

조표 픽스처는 `.ly` 소스에 정답이 있어 셀 수 있었다(`count_fixture_notes.py`).
**실제 악보에는 그게 없다.** 이 도구는 정답 없이 그 방향을 만든다.

## 어떻게

「검출기가 버린 것」을 전부 모아 **라벨이 없는 것만** 남긴다. 정답을 몰라도 된다.

1. 보표 밴드를 **검출기와 같은 방식**으로 전처리한다(세로 close 0.4sp → 타원 open 0.65×0.5sp)
2. 연결 성분을 전부 뽑는다. **검출기의 크기 게이트를 적용하지 않고** 뽑는 것이 요점이다
3. **빈 음표 링이 쪼개진 조각을 다시 합친다** — 가로로 `0.5sp` 안에서 세로가 겹치는
   조각끼리 묶는다. 온음표는 타원 open에 링이 깎여 **좌우 벽 두 조각**이 되므로
   합치지 않으면 못 찾는다(`docs/FIXTURE_LOSS_TRACE.md` §3)
4. **합쳐진 상자 안에** 라벨이 있으면 짝으로 본다(여유 반칸), **짝 없는 것**을 후보로 낸다
5. 각 후보에 **검출기의 어느 게이트에 걸렸는지**를 붙인다 — 고칠 자리를 바로 가리킨다
6. **두 등급으로 나눈다** — 아래 참고

## 등급

| 등급 | 조건 | 뜻 |
|---|---|---|
| **1군** | **조각을 합쳐 복원한 것** 이거나 `h >= 0.68sp` | **음표 머리**다. 먼저 볼 목록 |
| **2군** | 나머지 — 얇거나 납작한 것 | **덧줄·빔·박자표 조각**이다. 실측에서 오탐의 전부 |

`0.68sp`는 검출기 자신의 높이 게이트다(`notehead_detect.py:533`).
**덧줄 조각은 실측 `h=0.44sp`**라 여기서 갈린다 — 이 한 줄로 촬영본(RE:Aoharu)의
1군이 **291개 → 73개**가 됐다.

## 검증 결과 (2026-09-09)

조표 픽스처 8종에서 **부족 12개 = 1군 후보 12개**로 정확히 일치한다. **오탐 0 · 미탐 0.**
`03`·`07`의 누락 3건씩이 전부 1군으로 잡히고, 부족 0인 `02`·`06`은 1군이 0이다.

실제 악보의 1군 후보 수(정답을 모르므로 **확인된 누락이 아니라 후보다**):

| 악보 | 라벨 | 1군 | 2군 |
|---|---:|---:|---:|
| 바흐 미뉴에트 | 185 | **12** | 48 |
| 쇼팽 D♭ 6쪽 | 331 | **6** | 24 |
| 쇼팽 B♭m 1쪽 | 270 | **14** | 54 |
| RE:Aoharu 1쪽 (**촬영본**) | 226 | **73** | 249 |

**인쇄 PDF는 쪽당 6~14개**라 사람이 한 번 훑을 만하다.
**촬영본은 73개로 아직 많다** — 잡음·가사·나타냄말이 섞인다. 그쪽은 회귀 지표로만 쓴다.

> **합쳐서 복원한 것을 1군에 두는 이유** — 온음표 링은 위아래 호가 타원 open에
> 깎여 **좌우 벽만** 남는다. 그 둘을 합치면 `w=1.98sp h=0.58sp`(종횡비 3.4)라
> **모양만 보면 덧줄과 구별이 안 된다.** 실측에서 진짜 누락 3건이 전부 그렇게
> 2군으로 밀렸다(`03_D_major_sharp2`).

등급은 **검출기 자신의 기준**을 쓴다(`notehead_detect.py:540` 「머리는 종횡비 ~1.6 이하」).
**2군을 버리지 않고 남기는 이유**는, 검출기가 그 기준으로 진짜 머리를 버리고 있는지
아직 모르기 때문이다. 숫자만 따로 센다.

**판정하지 않고 목록만 낸다.** 쉼표·임시표·음자리표 조각도 섞여 나온다.
숫자를 그대로 「누락 수」로 읽으면 안 된다. **회귀 지표로 얼리고, 목록은 사람이 훑는다.**

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요):
    python tools/audit_unlabeled_ink.py                    # 픽스처로 도구를 검증
    python tools/audit_unlabeled_ink.py <악보경로> [쪽] [--crop]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads, remove_staff_lines
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts

# 후보로 볼 최소 크기. 이보다 작으면 오선 잔여 잉크·점·글자 조각이다.
MIN_W_SP, MIN_H_SP = 0.45, 0.40
# 후보로 볼 최대 크기. 이보다 크면 빔·이음줄·글자 덩어리다.
MAX_W_SP, MAX_H_SP = 2.6, 1.8
# 라벨이 이 후보 **안에** 들어오면 같은 것으로 본다.
#
# **거리로는 못 가른다.** 온음표 링이 쪼개지면 검출기가 한쪽 벽에만 라벨을 찍고
# 반대쪽 벽이 남는데, 두 벽 사이가 실측 **1.25sp**다(06 픽스처 보표1:
# 라벨 x=2231, 남은 벽 x=2205). 그런데 **이웃 음표의 최소 간격이 1.30sp**라
# (`labels_io.MATCH_DNX_SP` 주석) 둘이 0.05sp밖에 안 떨어져 있다.
#
# 그래서 **먼저 조각을 합치고**(`_merge`), 합쳐진 상자 안에 라벨이 있는지를 본다.
# 상자 밖 여유는 반칸(0.5sp)만 준다.
MATCH_PAD_SP, MATCH_Y_SP = 0.5, 0.6
# 쪼개진 링 조각을 다시 합치는 가로 간격.
# 실측: 온음표 링의 좌우 벽은 중심이 1.35sp 떨어져 있고 각 벽이 0.63sp라
# **경계 사이가 0.72sp**다. 0.5로는 안 합쳐진다.
MERGE_GAP_SP = 0.95
# 합치는 것은 **조각끼리만**이다. 멀쩡한 머리 둘(2도 화음 등)을 합치면
# 가운데가 어느 라벨과도 안 맞아 오탐이 된다.
#
# **`1.0sp`는 코드 자신의 실측에서 온다** — `notehead_detect.py:543-551` 주석의
# 「진짜 머리는 폭 1.19sp 이상 / 링 조각은 0.78~1.07sp」. 1.0 미만이면 조각이다.
# (0.70으로 두면 라벨이 찍힌 쪽 벽(0.72sp)이 조각으로 안 쳐져 안 합쳐진다)
FRAGMENT_W_SP = 1.00


def _gates(w, h, area, sp, expected_area):
    """`notehead_detect`의 크기 게이트 중 어디에 걸리는지 (529~540행)."""
    out = []
    if area < expected_area * 0.5:
        out.append("area<0.5x기대")
    if w < sp * 0.7:
        out.append("w<0.7sp")
    if w > sp * 2.2:
        out.append("w>2.2sp")
    if h < sp * 0.68:
        out.append("h<0.68sp")
    if w > h * 2.1:
        out.append("w>h*2.1")
    return out


def _merge(boxes, sp):
    """쪼개진 **조각**끼리 다시 묶는다. 멀쩡한 머리는 안 건드린다.

    온음표 링은 타원 open에 깎여 **좌우 벽 두 조각**이 된다. 합치지 않으면
    (1) 진짜로 빠진 온음표를 못 찾고 (2) 온음표가 멀쩡히 라벨을 받은 자리에서도
    벽 두 개가 라벨과 0.6sp 넘게 떨어져 **오탐**이 된다. 실측에서 둘 다 났다.
    """
    boxes = sorted(boxes, key=lambda b: b[0])
    out = []
    for b in boxes:
        x, y, w, h, a = b[:5]
        if out:
            px, py, pw, ph, pa, _pm = out[-1]
            v_overlap = min(py + ph, y + h) - max(py, y)
            both_fragment = (w < sp * FRAGMENT_W_SP and pw < sp * FRAGMENT_W_SP)
            if (both_fragment and x - (px + pw) <= sp * MERGE_GAP_SP
                    and v_overlap > 0.4 * min(ph, h)):
                nx0, ny0 = min(px, x), min(py, y)
                nx1, ny1 = max(px + pw, x + w), max(py + ph, y + h)
                out[-1] = (nx0, ny0, nx1 - nx0, ny1 - ny0, pa + a, True)
                continue
        out.append((x, y, w, h, a, False))
    return out


def audit(path, page=0):
    """(후보 목록, 최종 라벨 수, 전처리 결과)"""
    res = preprocess(path, pdf_page=page)
    ctxs = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctxs)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves,
                              clef={i: c.clef for i, c in ctxs.items()})
    accs = annotate_accidentals(res, ctxs, notes)
    notes, _ = remove_accidental_ghosts(notes, accs, res.staves)

    labeled = {}
    for n in notes:
        labeled.setdefault(n.staff_index, []).append((int(n.x), int(n.y)))

    no_staff = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    cands = []
    for staff in res.staves:
        sp = staff.spacing
        ctx = ctxs.get(staff.index)
        header_end = ctx.header_end if ctx is not None else 0
        top = max(0, int(staff.top - sp * 4.0))
        bot = min(H, int(staff.bottom + sp * 4.0))
        band = no_staff[top:bot, :]
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        closed = cv2.morphologyEx(band, cv2.MORPH_CLOSE, vk)
        kw, kh = max(3, int(sp * 0.65)) | 1, max(3, int(sp * 0.5)) | 1
        opened = cv2.morphologyEx(
            closed, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kw, kh)))

        n, _lab, stats, _c = cv2.connectedComponentsWithStats(opened)
        raw = [tuple(stats[i][:5]) for i in range(1, n)
               if stats[i][4] >= sp * sp * 0.08]
        expected_area = math.pi * (sp * 0.6) * (sp * 0.42)

        for x, y, w, h, area, merged in _merge(raw, sp):
            cx, cy = x + w / 2.0, top + y + h / 2.0
            if cx < header_end:
                continue
            if not (sp * MIN_W_SP <= w <= sp * MAX_W_SP):
                continue
            if not (sp * MIN_H_SP <= h <= sp * MAX_H_SP):
                continue
            # 합쳐진 상자(+반칸) 안에 라벨이 있으면 같은 음표다
            lo, hi = x - sp * MATCH_PAD_SP, x + w + sp * MATCH_PAD_SP
            hit = any(lo <= lx <= hi and abs(cy - ly) <= sp * MATCH_Y_SP
                      for lx, ly in labeled.get(staff.index, ()))
            if hit:
                continue
            cands.append(dict(
                staff=staff.index, x=int(cx), y=int(cy),
                w_sp=round(w / sp, 2), h_sp=round(h / sp, 2),
                area_ratio=round(area / expected_area, 2),
                gates=_gates(w, h, area, sp, expected_area),
                merged=bool(merged),
                tier=1 if (merged or h >= sp * 0.68) else 2,
            ))
    return cands, len(notes), res


def _crop(res, cands, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for k, c in enumerate(cands):
        x0, x1 = max(0, c["x"] - 120), min(res.original_bgr.shape[1], c["x"] + 120)
        y0, y1 = max(0, c["y"] - 80), min(res.original_bgr.shape[0], c["y"] + 80)
        img = cv2.resize(res.original_bgr[y0:y1, x0:x1], None, fx=2, fy=2,
                         interpolation=cv2.INTER_NEAREST)
        cv2.rectangle(img, ((c["x"] - x0) * 2 - 24, (c["y"] - y0) * 2 - 20),
                      ((c["x"] - x0) * 2 + 24, (c["y"] - y0) * 2 + 20), (0, 0, 255), 2)
        cv2.putText(img, f"x={c['x']} y={c['y']} w={c['w_sp']}sp h={c['h_sp']}sp "
                         f"{'/'.join(c['gates']) or '게이트 통과'}",
                    (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
        ok, buf = cv2.imencode(".png", img)
        with open(os.path.join(out_dir, f"{k:03d}_x{c['x']}_y{c['y']}.png"), "wb") as f:
            f.write(buf.tobytes())


FIXTURES = ["01_C_major_0", "03_D_major_sharp2", "07_Fs_major_sharp6",
            "12_F_major_flat1", "13_Cs_major_sharp7", "15_Cb_major_flat7",
            "02_G_major_sharp1", "06_B_major_sharp5"]


def main():
    from collections import Counter
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        page = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
        cands, n, res = audit(sys.argv[1], page)
        t1 = [c for c in cands if c["tier"] == 1]
        print(f"라벨 {n}개 · **1군(음표 모양) {len(t1)}개** · 2군(납작·넓음) "
              f"{len(cands) - len(t1)}개")
        for c in sorted(cands, key=lambda c: (c["tier"], c["staff"], c["x"])):
            print(f"  [{c['tier']}군] 보표{c['staff']} x={c['x']:5d} y={c['y']:5d} "
                  f"w={c['w_sp']}sp h={c['h_sp']}sp 면적비={c['area_ratio']} "
                  f"| 걸린 게이트: {'/'.join(c['gates']) or '없음(다른 단계에서 삭제)'}")
        if "--crop" in sys.argv:
            _crop(res, cands, "debug/unlabeled_ink")
            print("크롭 저장: debug/unlabeled_ink")
        return

    print("=" * 96)
    print("도구 검증 — 조표 픽스처에서 「사라진 온음표」를 찾아내는가")
    print("(정답 168개. 부족분은 docs/FIXTURE_LOSS_TRACE.md)")
    print("=" * 96)
    print(f"{'픽스처':22s} {'라벨':>5s} {'부족':>5s} {'1군':>4s} {'2군':>4s}  1군의 게이트")
    tot_short = tot_t1 = 0
    for stem in FIXTURES:
        cands, n, _res = audit(f"tests/fixtures/key_signatures/pdf/{stem}.pdf")
        t1 = [c for c in cands if c["tier"] == 1]
        g = Counter("/".join(c["gates"]) or "없음" for c in t1)
        tot_short += 168 - n
        tot_t1 += len(t1)
        print(f"{stem:22s} {n:5d} {168 - n:5d} {len(t1):4d} {len(cands) - len(t1):4d}  "
              + " · ".join(f"{k} {v}" for k, v in g.most_common()))
    print(f"\n>> 부족 합계 {tot_short}개 · 1군 후보 합계 {tot_t1}개")
    print("   픽스처에서는 이 둘이 **정확히 같아야** 한다(오탐 0 · 미탐 0).")
    print("   실제 악보에는 정답이 없으므로 1군은 **확인된 누락이 아니라 후보**다.")


if __name__ == "__main__":
    main()
