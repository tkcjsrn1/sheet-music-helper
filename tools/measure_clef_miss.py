# -*- coding: utf-8 -*-
"""야간 [7] 바뀐 음자리표 놓침 — 배율 · 문턱 재유도(헛 구간 0 유지 범위). 제품 코드 무변경.

정답: Verovio SVG 보표별 음자리표(둘째부터, 높은음 · 낮은음). 제품 검출 = `clef_keysig._clef_detections`(본 = 머리 음자리표 검출 구간).
① 놓친 정답마다(제품 걸림이 정답 x ±1.5sp 안에 없음) 제품 본 · 배율 0.40~1.20(0.05 간격)으로 정답 x ±1.5sp 안 최고 상관과 그 배율.
② 변형(문턱 · 배율 목록)마다 `clef_change_regions` 결과의 구간 시작을 정답과 맞춰 「맞음 · 헛 구간」 — 헛 구간 0을 유지하는 범위.

    python tools/measure_clef_miss.py
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
VARIANTS = {"지금(0.6 · 0.55~1.0)": (0.6, (0.55, 0.65, 0.75, 0.85, 1.0)),
            "0.55 · 0.55~1.0": (0.55, (0.55, 0.65, 0.75, 0.85, 1.0)),
            "0.5 · 0.55~1.0": (0.5, (0.55, 0.65, 0.75, 0.85, 1.0)),
            "0.6 · 0.45~1.0": (0.6, (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0)),
            "0.55 · 0.45~1.0 촘촘": (0.55, (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0))}


def _page(stem):
    import modules.clef_keysig as CK
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    res = preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))
    ctx = CK.analyze_staves(res)
    t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", stem + ".json"), encoding="utf-8"))
    staves = sorted(res.staves, key=lambda s: s.top)
    if len(t["staves"]) != len(staves):
        return stem, [], {}
    truth = []
    for st, ts in zip(staves, t["staves"]):
        seen = set()
        for c in ts["clefs"][1:]:
            if c["val"] in ("treble", "bass") and round(c["x"] / 10) not in seen:
                seen.add(round(c["x"] / 10))
                truth.append((st.index, c["x"], c["val"]))
    staves_d, hits, bad, tmpl = CK._clef_detections(res, ctx)
    ns = remove_staff_lines(res.binary, res.staves).astype(np.float32)
    H = ns.shape[0]
    rows = []
    for si, x, kind in truth:
        st = next(s for s in res.staves if s.index == si)
        sp = st.spacing
        found = any(abs(hx - x) <= 1.5 * sp and k == kind for hx, k, *_b in hits.get(si, []))
        best = (0.0, None)
        if not found and kind in tmpl:
            band = ns[max(0, int(st.top - 3 * sp)):min(H, int(st.bottom + 3 * sp)), :]
            for sc in np.arange(0.40, 1.201, 0.05):
                tt = cv2.resize(tmpl[kind], None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
                if tt.shape[0] >= band.shape[0] or tt.shape[1] < 3 or tt.std() == 0:
                    continue
                prof = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED).max(axis=0)
                a, b = max(0, int(x - 1.5 * sp)), min(len(prof), int(x + 1.5 * sp))
                if b > a and prof[a:b].max() > best[0]:
                    best = (float(prof[a:b].max()), round(float(sc), 2))
        rows.append(dict(stem=stem, si=si, x=round(x), kind=kind, found=found, ncc=round(best[0], 3), sc=best[1],
                         header_clef=ctx[si].clef if si in ctx else None, in_bad=kind in bad, tmpl=kind in tmpl))
    var = {}
    for name, (thr, scales) in VARIANTS.items():
        o_thr, o_sc = CK.CLEF_CHANGE_SCORE, CK.CLEF_CHANGE_SCALES
        CK.CLEF_CHANGE_SCORE, CK.CLEF_CHANGE_SCALES = thr, scales
        try:
            reg = CK.clef_change_regions(res, ctx)
        finally:
            CK.CLEF_CHANGE_SCORE, CK.CLEF_CHANGE_SCALES = o_thr, o_sc
        ok = fp = 0
        for si, rs in reg.items():
            sp = next(s for s in res.staves if s.index == si).spacing
            for a, _b in rs:
                if any(tsi == si and abs(tx - a) <= 1.5 * sp for tsi, tx, _k in truth):
                    ok += 1
                else:
                    fp += 1
        var[name] = (ok, fp)
    return stem, rows, var


def main():
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "test_scores", "verovio")) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, stems))
    rows = [r for _s, rs, _v in res for r in rs]
    json.dump(rows, open(os.path.join(ROOT, "debug", "clef_miss.json"), "w", encoding="utf-8"), ensure_ascii=False)
    miss = [r for r in rows if not r["found"]]
    print(f"정답 바뀐 음자리표 {len(rows)} · 검출 {len(rows) - len(miss)} · 놓침 {len(miss)}")
    print("  놓침 원인: " + " · ".join(f"{k} {n}" for k, n in Counter(
        "그 종류 본 없음/버림" if (not r["tmpl"] or r["in_bad"]) else ("최고 상관 < 0.5" if r["ncc"] < 0.5 else "0.5~0.6" if r["ncc"] < 0.6 else "0.6 이상(배율 범위 밖 등)")
        for r in miss).most_common()))
    print("  놓침의 최고 상관 배율:", dict(Counter(r["sc"] for r in miss if r["sc"]).most_common(8)))
    for name in VARIANTS:
        ok = sum(v[name][0] for _s, _r, v in res if v)
        fp = sum(v[name][1] for _s, _r, v in res if v)
        print(f"  {name}: 맞는 구간 {ok} · 헛 구간 {fp}")




def why41():
    """확실 등급 음고 틀림 중 「음자리표 바뀜(보표 중간)」 원인 라벨이 왜 clef_changed로 안 걸렸나 — 지금 main 평가(eval_main1005)."""
    import modules.clef_keysig as CK
    from modules.preprocess import preprocess
    evs = json.load(open(os.path.join(ROOT, "debug", "vrv", "eval_main1005.json"), encoding="utf-8"))
    c = Counter()
    for e in evs:
        rows = [r for r in e["rows"] if r["status"] == "음고" and r.get("label") and r["label"].get("conf") == "certain" and r["clef_now"] != r["clef_start"]]
        if not rows:
            continue
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", e["stem"] + ".png"))
        ctx = CK.analyze_staves(res)
        reg = CK.clef_change_regions(res, ctx)
        _st, hits, bad, tmpl = CK._clef_detections(res, ctx)
        for r in rows:
            si = r["label"]["staff"]
            hd = ctx[si].clef if si in ctx else None
            if hd in bad or hd not in tmpl:
                k = "그 보표 머리 종류의 본 없음 · 버림"
            elif hd == r["clef_now"]:
                k = "머리 음자리표를 바뀐 종류로 잘못 읽음(구간이 반대)"
            elif any(a <= r["label"]["x"] < b for a, b in reg.get(si, [])):
                k = "구간 안인데 확실(다른 경로)"
            elif any(hx < r["label"]["x"] and kk == r["clef_now"] for hx, kk, *_b in hits.get(si, [])):
                k = "글리프는 걸렸는데 구간이 앞에서 끝남(되돌아옴 오검출)"
            else:
                k = "이 보표에서 바뀐 글리프를 못 찾음(앞 시스템에서 바뀐 채 이어짐 등)"
            c[(e["stem"].split("_")[0], k)] += 1
    for k, n in c.most_common():
        print("  ", k, n)




def _regions(job):
    """PDF · 보지 않은 · Aoharu: 변형(문턱 thr, 검색 시작 start)에서 지금 제품에 없던 새 구간과 그 판정(PDF 음자리표 글리프)."""
    thr, start, (st, name, path, pg) = job
    import modules.clef_keysig as CK
    import measure_omission_rate as M
    from modules.preprocess import preprocess
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = CK.analyze_staves(res)
    base = CK.clef_change_regions(res, ctx)
    o = CK.CLEF_CHANGE_SCORE, getattr(CK, "CLEF_CHANGE_START", None)
    CK.CLEF_CHANGE_SCORE = thr
    if start is not None:
        CK.CLEF_CHANGE_START = start
    try:
        new = CK.clef_change_regions(res, ctx)
    finally:
        CK.CLEF_CHANGE_SCORE = o[0]
        if o[1] is not None:
            CK.CLEF_CHANGE_START = o[1]
    glyphs = [] if not path.endswith(".pdf") else [g for g in M.pdf_glyphs(path, pg, ("clefs.",))]
    out = []
    for si, rs in new.items():
        st_ = next(s for s in res.staves if s.index == si)
        sp = st_.spacing
        for a, b in rs:
            if any(abs(a - a0) <= 1.5 * sp for a0, _b0 in base.get(si, [])):
                continue
            ok = any(abs(g["cx"] - a) <= 2.5 * sp and st_.top - 3 * sp <= g["cy"] <= st_.bottom + 3 * sp for g in glyphs)
            out.append((name, si, round(a), round(b), "맞음(글리프 있음)" if ok else "헛 구간" if glyphs else "정답 없음(Aoharu — 육안)"))
    return out


def others(thr, start=None):
    import measure_sim_ledger_pair as S
    jobs = [(thr, start, p) for p in S.pages() if p[0] != "verovio" and p[1] != "organ2"]
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_regions, jobs) for r in part]
    print(f"문턱 {thr} 검색 시작 {start or '지금'}: 지금 없던 새 구간 {len(rows)}", dict(Counter(r[4] for r in rows)))
    for r in rows:
        print("   ", r)


if __name__ == "__main__":
    if sys.argv[1:2] == ["others"]:
        others(float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        why41() if sys.argv[1:] == ["why"] else main()
