# -*- coding: utf-8 -*-
"""[8] · 야간 [2] 화음 덩어리 — 단독 머리 본 상관으로 머리 자리 확인(#193 「덩어리 높이」 기각과 다른 근거). 제품 코드 무변경.

본: 그 쪽 라벨 중 확실 · 단독(같은 보표 1.2sp 안 다른 라벨 없음) 머리 최대 30개의 오선 제거 영상 조각(±0.65sp × ±0.55sp) 평균 —
    꽉 찬 본(조각 잉크 비율 > 0.4)과 빈 본(0.15~0.4, 가운데가 비었음)을 따로.
대상 덩어리: 오선 제거 → 타원 0.5sp 열림 성분 중
    labeled — 라벨이 하나 이상 걸리고 높이 ≥ 1.4sp(화음 후보)
    all     — 위 + 라벨 없는 성분 중 오선 ±4sp 띠 안 · 높이 0.8~6sp · 폭 ≤ 3sp
상관(TM_CCOEFF_NORMED) 극댓값(0.4sp 안 최대) 중 기존 라벨 0.5sp 밖 = 추가 후보. 그 자리 음고 = 제품 `calculate_pitch`(그 보표 음자리표).
판정: 정답 머리 0.7 × 0.5sp 안 = 되찾음(음고까지 같으면 「음고 맞음」) — 그 머리에 이미 라벨이 있으면 중복, 정답 머리 없으면 새 유령. Aoharu는 정답 골든이 라벨 그대로라 추가 = 전부 변화로 센다.
라벨 = 현재 main(`debug/sim_lp/nograce`).

    python tools/measure_chord_template.py [labeled|all] [filled|hollow]
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
THRS = (0.5, 0.6, 0.7, 0.8, 0.85)
MODE = {"scope": "labeled", "kind": "filled"}


def _truth(st, name, path, pg, res):
    """(x, y, 음이름+옥타브 또는 None) — Verovio는 SVG, PDF는 글리프 머리 + 음자리표로 제품 정답 함수."""
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"], n["note_name"] + n["octave"]) for n in t["notes"]]
    if st == "aoharu":
        return None
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    heads, clefs = truth_at(path, pg, 1.0)
    for q in clefs:
        q["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["cy"])).index
    out = []
    for h in heads:
        try:
            out.append((h["cx"], h["cy"], M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1]))
        except Exception:
            out.append((h["cx"], h["cy"], None))
    return out


def _page(job):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines, Notehead
    from modules.pitch_calculator import calculate_pitch
    (st, name, path, pg), scope, kind = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    sp = float(np.median([s.spacing for s in res.staves]))
    ns = (remove_staff_lines(res.binary, res.staves) > 0).astype(np.float32)
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "nograce", name + ".json"), encoding="utf-8"))["labels"]
    heads = _truth(st, name, path, pg, res)
    hw, hh = int(0.65 * sp), int(0.55 * sp)
    crops = []
    for l in L:
        if l["confidence"] != "certain" or any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 1.2 * sp and abs(o["y"] - l["y"]) <= 1.2 * sp for o in L):
            continue
        x, y = int(l["x"]), int(l["y"])
        c = ns[y - hh:y + hh + 1, x - hw:x + hw + 1]
        if c.shape != (2 * hh + 1, 2 * hw + 1):
            continue
        if (kind == "filled" and c.mean() > 0.4) or (kind == "hollow" and 0.15 <= c.mean() <= 0.4 and c[hh - 2:hh + 3, hw - 3:hw + 4].mean() < 0.3):
            crops.append(c)
        if len(crops) >= 30:
            break
    out = {th: Counter() for th in THRS}
    if len(crops) < 5:
        return st, name, out, len(crops)
    tmpl = np.mean(crops, axis=0).astype(np.float32)
    k = max(3, int(0.5 * sp)) | 1
    op = cv2.morphologyEx((ns * 255).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, stats, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
    H, W = lab.shape
    labeled = {}
    for l in L:
        c = lab[min(H - 1, int(l["y"])), min(W - 1, int(l["x"]))]
        if c:
            labeled.setdefault(c, []).append(l)
    comps = [c for c in labeled if stats[c, cv2.CC_STAT_HEIGHT] >= 1.4 * sp]
    if scope == "all":
        for c in range(1, n):
            if c in labeled:
                continue
            cy = stats[c, cv2.CC_STAT_TOP] + stats[c, cv2.CC_STAT_HEIGHT] / 2
            if not (0.8 * sp <= stats[c, cv2.CC_STAT_HEIGHT] <= 6 * sp and stats[c, cv2.CC_STAT_WIDTH] <= 3 * sp):
                continue
            if any(s.top - 4 * s.spacing <= cy <= s.bottom + 4 * s.spacing for s in res.staves):
                comps.append(c)
    pad = int(0.3 * sp)
    for c in comps:
        x0, y0 = max(0, stats[c, cv2.CC_STAT_LEFT] - pad - hw), max(0, stats[c, cv2.CC_STAT_TOP] - pad - hh)
        x1 = min(W, stats[c, cv2.CC_STAT_LEFT] + stats[c, cv2.CC_STAT_WIDTH] + pad + hw)
        y1 = min(H, stats[c, cv2.CC_STAT_TOP] + stats[c, cv2.CC_STAT_HEIGHT] + pad + hh)
        region = ns[y0:y1, x0:x1]
        if region.shape[0] <= tmpl.shape[0] or region.shape[1] <= tmpl.shape[1]:
            continue
        m = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
        r = max(1, int(0.4 * sp))
        mx = cv2.dilate(m, np.ones((2 * r + 1, 2 * r + 1), np.uint8))
        for yy, xx in zip(*np.where((m >= min(THRS)) & (m >= mx))):
            px, py = x0 + xx + hw, y0 + yy + hh
            if any(abs(o["x"] - px) <= 0.5 * sp and abs(o["y"] - py) <= 0.5 * sp for o in L):
                continue
            stf = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - py))
            clef = ctx[stf.index].clef if stf.index in ctx else "treble"
            try:
                pn = calculate_pitch(Notehead(x=int(px), y=int(py), filled=kind == "filled", staff_index=stf.index), stf, clef=clef)
                pitch = pn.note_name + str(pn.octave)
            except Exception:
                pitch = None
            if heads is None:
                verdict = "Aoharu 변화"
            else:
                h = [q for q in heads if abs(q[0] - px) <= 0.7 * sp and abs(q[1] - py) <= 0.5 * sp]
                if h and any(abs(o["x"] - h[0][0]) <= 0.7 * sp and abs(o["y"] - h[0][1]) <= 0.5 * sp for o in L):
                    verdict = "중복(이미 라벨 있는 머리)"
                else:
                    verdict = "새 유령" if not h else ("되찾음 · 음고 맞음" if h[0][2] == pitch else "되찾음 · 음고 틀림")
            for th in THRS:
                if m[yy, xx] >= th:
                    out[th][verdict] += 1
    return st, name, out, len(crops)


def main():
    import measure_sim_ledger_pair as S
    scope = sys.argv[1] if len(sys.argv) > 1 else "labeled"
    kind = sys.argv[2] if len(sys.argv) > 2 else "filled"
    jobs = [(p, scope, kind) for p in S.pages() if p[1] != "organ2"]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    print(f"범위 {scope} · 본 {kind} · 본을 못 만든 쪽(단독 머리 < 5) {sum(1 for _s, _n, _o, c in res if c < 5)}")
    for st in ("verovio", "pdf", "unseen", "aoharu"):
        for th in THRS:
            c = Counter()
            for s, _n, o, _c in res:
                if s == st:
                    c.update(o[th])
            ok = c["되찾음 · 음고 맞음"]
            tot = sum(c.values())
            print(f"  {st:8s} 상관 ≥ {th}: 추가 {tot} · " + " · ".join(f"{k} {v}" for k, v in c.most_common())
                  + (f" · 정밀도(음고 맞음) {100 * ok / max(1, tot):.0f}%" if st != "aoharu" else ""))
    json.dump([(s, n, {str(k): dict(v) for k, v in o.items()}) for s, n, o, _c in res],
              open(os.path.join(ROOT, "debug", f"chord_template_{scope}_{kind}.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
