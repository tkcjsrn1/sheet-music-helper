# -*- coding: utf-8 -*-
"""가림 규칙 사전 측정 — 「채워진 덩어리에 가려져 버려진 구멍」 92개의 형태값.

측정 전용. `modules/`는 읽기만 한다(`trace_hollow_path`의 기록 사본을 그대로 쓴다).

## 집단 (육안 전수 판정, `docs/HOLLOW_FILLED_TRACE.md` §2)

| 집단 | 뜻 | 수 |
|---|---|---:|
| **A** | 가짜 구멍을 옳게 막았다 (빔 사이·♯ 속·2도 화음 틈·이음줄) | 70 |
| **B** | 진짜 빈 음표가 가려졌지만 filled로 라벨은 남았다 | 16 |
| **C** | 진짜 2분음표가 라벨 없이 사라졌다 (쇼팽 Em 1쪽) | 6 (음표 5개) |

집단은 **좌표로** 붙인다 — 목록 순서가 바뀌어도 판정이 어긋나지 않는다.

## 재는 값

가리는 덩어리(blob)와 가려진 구멍(hole) 사이의 관계다.

- `dy` : 구멍 중심 − blob 중심 (sp). 세로 거리
- `edge` : 구멍 중심이 blob bbox **밖으로** 나간 거리 (sp, 안쪽이면 0)
- `blob_w/h` : blob 크기 (sp) — 링 벽은 좁고 진짜 머리는 1.1sp 이상
- `stem` : 구멍과 blob 사이 세로 잉크가 이어져 있는가 (같은 기둥인가)
- `own_hole` : blob bbox 안에 **다른 구멍**이 또 있는가 (제 링의 벽인가)
- `n_blocked` : 같은 blob이 막은 구멍 수 (이음매 판정이 쓰는 값)

    python tools/measure_blocked_holes.py
"""
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import numpy as np

import trace_hollow_path as T
from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import remove_staff_lines

PAGES = [("bach", "test_scores/bach_minuet_Am.pdf", 0),
         ("bbm1", "test_scores/chopin_nocturne_Bbm.pdf", 0),
         ("db1", "test_scores/chopin_nocturne_Db_6-8.pdf", 0),
         ("em1", "test_scores/chopin_nocturne_Em.pdf", 0),
         ("aoharu1", "sample_images/KakaoTalk_20260731_162400402.png", 0)]

# 육안 판정 좌표 (구멍 중심). 나머지는 전부 A.
GROUP_C = {"em1": [(1934, 1045), (642, 1581), (640, 1592), (1050, 2705), (1750, 2754), (2100, 2764)]}
GROUP_B = {"aoharu1": [(538, 490), (1238, 500), (442, 737), (720, 764), (950, 838), (1365, 772),
                       (1053, 862), (1128, 862), (1186, 862), (482, 1102), (592, 1000),
                       (936, 1157), (1123, 1157), (611, 1388)],
           "bbm1": [(1882, 1426), (2125, 1426)]}


def label(page, x, y):
    for g, table in (("C", GROUP_C), ("B", GROUP_B)):
        for px, py in table.get(page, ()):
            if abs(px - x) <= 3 and abs(py - y) <= 3:
                return g
    return "A"


def vertical_link(ns, x, y0, y1, sp):
    """두 y 사이가 세로 잉크로 이어져 있는 비율 — 같은 기둥에 달렸는지."""
    x = int(round(x))
    lo, hi = int(min(y0, y1)), int(max(y0, y1))
    if hi - lo < 2:
        return 1.0
    w = max(1, int(round(sp * 0.35)))
    col = ns[lo:hi + 1, max(0, x - w):x + w + 1] > 0
    return float(col.any(axis=1).mean())


def cap_run(ns, cx, cy, hy0, hy1, sp):
    """구멍 위·뚜껑과 아래·바닥의 **가로 잉크 런** 길이(sp) 중 작은 쪽.

    빔 사이 틈은 위아래가 빔(길이 2sp 이상의 가로 막대)이고, 빈 음표 링의 위아래는
    타원 호라 1.3sp 안팎에서 끝난다. 음악 규칙에 붙은 값이라 크기 문턱보다 낫다.
    """
    x = int(round(cx))
    w = int(round(sp * 2.2))
    out = []
    for yy in (int(hy0) - max(1, int(sp * 0.18)), int(hy1) + max(1, int(sp * 0.18))):
        if not (0 <= yy < ns.shape[0]):
            out.append(0.0)
            continue
        row = ns[yy, max(0, x - w):x + w + 1] > 0
        best = run = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        out.append(best / sp)
    return min(out)


def blob_box(d, px, py):
    """raw 항목 좌표를 품는 `opened` 성분 bbox (밴드 좌표 → 절대)."""
    best = None
    for x, y, w, h, area in d["comps"][1:]:
        if x - 1 <= px <= x + w + 1 and y - 1 <= py - d["top"] <= y + h + 1:
            c = (abs(x + w / 2 - px), w, h, area, x, y)
            if best is None or c[0] < best[0]:
                best = c
    return best


def rows_for(page, path, pg):
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    a = T.ORIG.detect_noteheads(res, contexts=ctx)
    T.DBG._DBG.clear()
    b = T.DBG.detect_noteheads(res, contexts=ctx)
    assert [(h.x, h.y, h.filled) for h in a] == [(h.x, h.y, h.filled) for h in b], "사본이 원본과 다르다"
    ns = remove_staff_lines(res.binary, res.staves)
    out = []
    for d in T.DBG._DBG:
        sp, top = d["sp"], d["top"]
        blocked = collections.Counter(c[2] for c in d["cands"] if c[2] is not None)
        holes = [(c[0], c[1]) for c in d["cands"]]
        for cx, cy, blk, hy0, hy1 in d["cands"]:
            if blk is None:
                # 가려지지 않고 채택된 구멍 — 「진짜 머리 구멍」의 크기 분포 대조군
                hw0, src0 = float("nan"), []
                for rx, ry, rw, rh in d["merged"]:
                    if abs(rx + rw / 2.0 - cx) < 0.01 and abs(ry + top + rh / 2.0 - cy) < 0.01:
                        hw0 = rw / sp
                        break
                for tag in ("patched", "band_h", "enclosed"):
                    for rx, ry, rw, rh in d[tag]:
                        if abs(rx + rw / 2 - cx) <= sp * 0.5 and abs(ry + top + rh / 2 - cy) <= sp * 0.6:
                            src0.append(tag)
                            break
                out.append(dict(page=page, x=round(cx), y=round(cy), group="채택",
                                hole_w=round(hw0, 2), hole_src="+".join(src0) or "-", sp=round(sp, 2),
                                dx=0.0, dy=0.0, edge=0.0, blob_w=float("nan"), blob_h=float("nan"),
                                hole_h=round((hy1 - hy0) / sp, 2), stem=0.0, own_hole=0, n_blocked=0))
                continue
            px, py, _f, by0, by1 = d["raw_before"][blk]
            # 채택 여부는 실제 `accepted_holes`로 본다. 가리는 덩어리가 나중에 지워지는 것과
            # 구멍이 채택되는 것은 별개다 — 이걸 혼동해 D♭ (2174,2831)이 목록에서 빠졌었다.
            if any(abs(h[0] - cx) < .5 and abs(h[1] - hy0) < .5 for h in d["accepted"]):
                continue                                   # 실제로 채택된 구멍
            bb = blob_box(d, px, py)
            bw, bh = (bb[1] / sp, bb[2] / sp) if bb else (float("nan"),) * 2
            edge = max(0.0, (by0 - cy) / sp, (cy - by1) / sp)
            own = sum(1 for hx, hy in holes
                      if abs(hx - px) < sp * 0.55 and by0 - sp * 0.1 <= hy <= by1 + sp * 0.1
                      and not (abs(hx - cx) < 1 and abs(hy - cy) < 1))
            # 구멍 bbox를 출처 목록에서 되찾는다(폭·종횡비·어느 단계에서 나왔나)
            src, hw = [], float("nan")
            # **병합 후** 구멍 폭 — 규칙이 실제로 보는 값이다(병합 전 출처 폭과 다르다)
            for rx, ry, rw, rh in d["merged"]:
                # 후보 중심은 병합 사각형 중심 그대로다 — **정확히 같은 것**만 짝짓는다.
                # 허용오차로 짝지으면 이웃 사각형을 집어 규칙이 보는 값과 어긋난다(실측으로 겪었다).
                if abs(rx + rw / 2.0 - cx) < 0.01 and abs(ry + top + rh / 2.0 - cy) < 0.01:
                    hw = rw / sp
                    break
            for tag in ("patched", "band_h", "enclosed"):
                for rx, ry, rw, rh in d[tag]:
                    if abs(rx + rw / 2 - cx) <= sp * 0.5 and abs(ry + top + rh / 2 - cy) <= sp * 0.6:
                        src.append(tag)
                        break
            out.append(dict(page=page, x=round(cx), y=round(cy), group=label(page, round(cx), round(cy)),
                            hole_w=round(hw, 2), hole_src="+".join(src) or "-",
                            sp=round(sp, 2), dx=round((px - cx) / sp, 2), dy=round((py - cy) / sp, 2),
                            edge=round(edge, 2), blob_w=round(bw, 2), blob_h=round(bh, 2),
                            hole_h=round((hy1 - hy0) / sp, 2),
                            stem=round(vertical_link(ns, cx, cy, py, sp), 2),
                            cap=round(cap_run(ns, cx, cy, hy0, hy1, sp), 2),
                            own_hole=own, n_blocked=blocked[blk]))
    return out


def dist(name, vals):
    v = sorted(vals)
    if not v:
        return f"{name}: 없음"
    return (f"{name}: n={len(v)} 최소 {v[0]:.2f} / 25% {v[len(v)//4]:.2f} / 중앙 {v[len(v)//2]:.2f} "
            f"/ 75% {v[3*len(v)//4]:.2f} / 최대 {v[-1]:.2f}")


def main():
    rows = []
    for page, path, pg in PAGES:
        rows += rows_for(page, path, pg)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    print(f"총 {len(rows)}개 — " + " · ".join(f"{g} {len(v)}" for g, v in sorted(by.items())))
    for key in ("hole_h", "hole_w", "edge", "dy", "blob_w", "blob_h", "stem", "own_hole", "n_blocked"):
        print(f"\n[{key}]")
        for g in ("A", "B", "C"):
            print("   " + dist(g, [abs(r[key]) if key == "dy" else r[key] for r in by[g]]))
    print("\n[구멍 출처]")
    for g in ("A", "B", "C"):
        print(f"   {g}: {dict(collections.Counter(r['hole_src'] for r in by[g]))}")
    print("\n[분리 후보] 규칙마다 — A를 몇 개 놓치나(가짜가 살아난다) / C를 몇 개 살리나")
    rules = {
        "hole_h>=0.93": lambda r: r["hole_h"] >= 0.93,
        "hole_h>=1.00": lambda r: r["hole_h"] >= 1.00,
        "hole_h>=0.93 & hole_w<=1.20": lambda r: r["hole_h"] >= 0.93 and r["hole_w"] <= 1.20,
        "hole_h>=0.93 & 종횡비<=1.35": lambda r: r["hole_h"] >= 0.93 and r["hole_w"] <= r["hole_h"] * 1.35,
        "edge>0 & hole_h>=0.93": lambda r: r["edge"] > 0 and r["hole_h"] >= 0.93,
    }
    for name, f in rules.items():
        a_lost = [r for r in by["A"] if f(r)]
        print(f"   {name:30s} A 놓침 {len(a_lost):2d}/70  C 살림 {sum(1 for r in by['C'] if f(r))}/6  "
              f"B 살림 {sum(1 for r in by['B'] if f(r))}/16")
        for r in a_lost[:4]:
            print(f"        A 놓침 예: {r['page']} ({r['x']},{r['y']}) hole {r['hole_w']}x{r['hole_h']} src={r['hole_src']}")
    print("\n== C 전수")
    for r in sorted(by["C"], key=lambda r: (r["page"], r["x"])):
        print("   ", {k: r[k] for k in ("page", "x", "y", "dy", "edge", "blob_w", "blob_h", "stem", "own_hole", "n_blocked")})
    print("\n== A 중 C와 겹치는 것 찾기 (edge>0 인 A)")
    for r in sorted((r for r in by["A"] if r["edge"] > 0), key=lambda r: -r["edge"])[:12]:
        print("   ", {k: r[k] for k in ("page", "x", "y", "dy", "edge", "blob_w", "blob_h", "stem", "own_hole", "n_blocked")})
    json.dump(rows, open(os.path.join(ROOT, "debug", "blocked_holes.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
