# -*- coding: utf-8 -*-
"""(b) Verovio 남은 누락 — 정답 머리가 어느 단계에서 빠지는지 · 붙은 화음 구제 문턱(101 · 0.416)이 Verovio에서도 맞는지. 제품 코드 무변경.

단계(제품 `main.run_page` 순서를 따라 다시 돈다 — 라벨 JSON 대신 단계별 목록이 필요해서):
  보표 없음 → 헤더 안 → 머리 후보 없음(이진화 잉크 부족 / 모양) → 검출 내부 필터(reject_log 사유) → 빔 · 보표 밖 유령 필터 →
  임시표 유령 필터 → (붙은 화음 구제로 되찾음) → 최종 음표에 있는데 라벨 짝 실패(붙은 화음 라벨 위치)
정답: `debug/vrv/truth/*.json`(SVG 머리), 평가 행 `debug/vrv/eval_na_base.json`(A-25 상태 · `measure_verovio eval na_base`).

    python tools/measure_missing_verovio.py trace     → debug/vrv/missing_trace.json  (MISSING_EVAL=main1005 → missing_trace_main1005.json)
    python tools/measure_missing_verovio.py rescue    → 구멍 회색 분포 · 2b 중점 어긋남 분포
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
VRV = os.path.join(ROOT, "debug", "vrv")
EVAL = os.environ.get("MISSING_EVAL", "na_base")     # 평가 변형 — 지금 main은 MISSING_EVAL=main1005
SET = os.path.join(ROOT, "test_scores", "verovio")


def _stages(stem):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts, filled_flags
    from modules.chord_rescue import detect_noteheads_rescue
    res = preprocess(os.path.join(SET, stem + ".png"))
    ctx = analyze_staves(res)
    clef = {i: c.clef for i, c in ctx.items()}
    out = {}
    for tag, det in (("base", detect_noteheads), ("rescue", detect_noteheads_rescue)):
        rej = []
        heads = det(res, contexts=ctx, reject_log=rej)
        out[tag + "_det"] = [(h.x, h.y) for h in heads]
        out[tag + "_rej"] = [(r["x"], r["y"], r["reason"]) for r in rej]
        h1, _ = drop_beam_ghosts(res, heads)
        out[tag + "_beam"] = [(h.x, h.y) for h in h1]
        h2, _ = drop_offstaff_ghosts(res, h1)
        out[tag + "_off"] = [(h.x, h.y) for h in h2]
        notes = calculate_pitches(h2, res.staves, clef=clef)
        accs = annotate_accidentals(res, ctx, notes)
        kept, _a = remove_accidental_ghosts(notes, accs, res.staves, filled=filled_flags(notes, h2), result=res)
        out[tag + "_final"] = [(n.x, n.y) for n in kept]
    out["header"] = {i: c.header_end for i, c in ctx.items()}
    from modules import notehead_detect as ND
    ns = ND.remove_staff_lines(res.binary, res.staves)
    try:
        out["margins"] = {s.index: ND._band_margins(s, res.staves, ns) for s in res.staves}
    except TypeError:          # 덧줄 사다리(§1-19) 이전 제품
        out["margins"] = {s.index: ND._band_margins(s, res.staves) for s in res.staves}
    out["staves"] = [(s.index, s.top, s.bottom, s.spacing) for s in res.staves]
    out["binary"] = None
    return stem, out, res.binary


def _one(stem):
    stem, st, binary = _stages(stem)
    t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
    ev = next(e for e in json.load(open(os.path.join(VRV, f"eval_{EVAL}.json"), encoding="utf-8")) if e["stem"] == stem)
    sp = float(np.median([s[3] for s in st["staves"]]))
    near = lambda lst, x, y, r=0.5: any(abs(a - x) <= r * sp and abs(b - y) <= r * sp for a, b, *_ in lst)
    rows = []
    for r in ev["rows"]:
        if r["status"] != "누락":
            continue
        x, y = r["x"], r["y"]
        cat = "화음" if r["chord"] else ("빈 머리" if r["hollow"] else ("덧줄 구역" if r["ledger"] else "단일"))
        if not r["staff_found"]:
            stage = "보표 없음"
        else:
            stf = min(st["staves"], key=lambda s: abs((s[1] + s[2]) / 2 - y))
            hdr = st["header"].get(stf[0], 0)
            box = binary[int(y - 0.4 * sp):int(y + 0.4 * sp), int(x - 0.55 * sp):int(x + 0.55 * sp)]
            ink = float((box > 0).mean()) if box.size else 0.0
            if x < hdr:
                stage = "헤더 안"
            elif near(st["base_final"], x, y) or near(st["rescue_final"], x, y):
                stage = "최종 음표 있음 · 라벨 짝 실패"
            elif near(st["base_off"], x, y):
                stage = "임시표 유령 필터"
            elif near(st["base_beam"], x, y):
                stage = "보표 밖 유령 필터"
            elif near(st["base_det"], x, y):
                stage = "빔 유령 필터"
            elif near(st["base_rej"], x, y):
                why = next(c for a, b, c in st["base_rej"] if abs(a - x) <= 0.5 * sp and abs(b - y) <= 0.5 * sp)
                stage = f"검출 내부 필터({why})"
            elif not (stf[1] - st["margins"][stf[0]][0] + 0.5 * sp <= y <= stf[2] + st["margins"][stf[0]][1] - 0.5 * sp):
                stage = "머리 검색 띠 밖"
            elif ink < 0.25:
                stage = "머리 후보 없음 · 이진화 잉크 부족"
            else:
                stage = "머리 후보 없음 · 모양 판정"
        rows.append(dict(stem=stem, x=x, y=y, cat=cat, stage=stage))
    return rows


def trace():
    stems = sorted(f[:-4] for f in os.listdir(SET) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_one, stems) for r in part]
    json.dump(rows, open(os.path.join(VRV, "missing_trace.json" if EVAL == "na_base" else f"missing_trace_{EVAL}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter as _C
    print(len(rows), _C(r["stage"] for r in rows).most_common())
    for cat in ("단일", "화음", "빈 머리", "덧줄 구역"):
        print("  ", cat, _C(r["stage"] for r in rows if r["cat"] == cat).most_common(5))
    print("누락", len(rows))
    for cat in ("단일", "화음", "빈 머리", "덧줄 구역"):
        c = Counter(r["stage"] for r in rows if r["cat"] == cat)
        print(f"  {cat} {sum(c.values())}: " + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    c = Counter(r["stage"] for r in rows)
    print("  합계: " + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    c = Counter("bravura" if "bravura" in r["stem"] else "leipzig" for r in rows)
    print("  글꼴:", dict(c), "| 쪽 상위:", Counter(r["stem"] for r in rows).most_common(5))


def _rescue_one(stem):
    """정답 머리 중심을 품은 닫힌 구멍의 원본 회색 평균(꽉 찬 / 빈 머리) · 2b 중점 어긋남(기존 라벨이 유령 / 진짜)."""
    import cv2
    from modules.preprocess import preprocess
    res = preprocess(os.path.join(SET, stem + ".png"))
    t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
    bg = (res.binary == 0).astype(np.uint8)
    n, lab, stats, _c = cv2.connectedComponentsWithStats(bg, connectivity=4)
    edge = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist())
    sums = np.bincount(lab.ravel(), weights=res.gray.ravel().astype(np.float64), minlength=n)
    mean = sums / np.maximum(stats[:, cv2.CC_STAT_AREA], 1)
    holes = []
    for h in t["notes"]:
        if h["grace"] or h["cue"]:
            continue
        k = lab[int(round(h["y"])), int(round(h["x"]))]
        if k == 0 or k in edge:
            continue                                            # 중심이 잉크(꽉 찬 머리 그대로) — 구멍 아님
        hollow = h["glyph"] in ("E0A3", "E0A2", "E0A0")             # SMuFL noteheadHalf · Whole · DoubleWhole
        holes.append(("빈" if hollow else "꽉 찬", float(mean[k])))
    return stem, holes


def rescue():
    stems = sorted(f[:-4] for f in os.listdir(SET) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_rescue_one, stems))
    for font in ("bravura", "leipzig"):
        for k in ("꽉 찬", "빈"):
            v = np.array([g for s, hs in res if font in s for kk, g in hs if kk == k])
            if len(v):
                print(f"{font} {k} 머리 구멍 {len(v)}: 회색 평균 최소 {v.min():.1f} · 중앙 {np.median(v):.1f} · 최대 {v.max():.1f} · < 101 {int((v < 101).sum())}")




def _mid_one(stem):
    """2b(추가 라벨 쌍에 끼인 기존 라벨 삭제)의 중점 어긋남 — 그 기존 라벨이 유령인지(정답 머리 0.5sp 안 없음) 진짜인지."""
    from modules.chord_rescue import MATCH_SP, SANDWICH_X_SP, SANDWICH_GAP_SP
    stem, st, _b = _stages(stem)
    t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
    sp = float(np.median([s[3] for s in st["staves"]]))
    base, extra = st["base_final"], st["rescue_final"]
    add = [p for p in extra if not any(abs(p[0] - bx) <= MATCH_SP * sp and abs(p[1] - by) <= MATCH_SP * sp for bx, by in base)]
    out = []
    for bx, by in base:
        col = [(x, y) for x, y in add if abs(x - bx) <= SANDWICH_X_SP * sp]
        up = [y for _x, y in col if y < by]
        lo = [y for _x, y in col if y > by]
        if not up or not lo:
            continue
        u, d = max(up), min(lo)
        if d - u > SANDWICH_GAP_SP * sp:
            continue
        dev = max(abs((by - u) / sp - 0.5), abs((d - by) / sp - 0.5))
        real = any(abs(h["x"] - bx) <= 0.5 * sp and abs(h["y"] - by) <= 0.3 * sp for h in t["notes"])
        out.append((stem, round(dev, 3), real))
    return out


def midpoint():
    stems = sorted(f[:-4] for f in os.listdir(SET) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_mid_one, stems) for r in part]
    for real in (False, True):
        v = np.array([d for _s, d, r in rows if r == real])
        if len(v):
            print(f"{'진짜 머리' if real else '유령'} {len(v)}: 어긋남 최소 {v.min():.3f} · 중앙 {np.median(v):.3f} · 최대 {v.max():.3f} · ≤ 0.416(지움) {int((v <= 0.416).sum())}")
        else:
            print('진짜 머리' if real else '유령', 0)
    json.dump(rows, open(os.path.join(VRV, "midpoint_2b.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    {"trace": trace, "rescue": rescue, "midpoint": midpoint}[sys.argv[1]]()
