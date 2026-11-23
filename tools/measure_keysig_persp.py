# -*- coding: utf-8 -*-
"""원근 · 사진에서 조표를 0개로 읽는 원인 — 보표마다 조표 막대 x가 어디서 어긋나나 · 교차 투표 후보 시뮬레이션 (2026-10-13 · 측정만).

세트: `inputs/degraded/` 24장만(보류 세트 미사용), 일반 모드 · 사진 모드(`preprocess(photo=True)`) 각각. 정답 조표 = 원본 쪽(E단조 2 ♯1 · B♭단조 1 ♭5 · D♭ 3 ♭5).
보표마다 기록: 음자리표 끝(`clef_end`) · 조표 막대 후보 x(`bars`) · 첫 막대 − 음자리표 끝.
시스템 전체 퍼짐: 첫 막대 x의 최대 − 최소(절대 x) vs (첫 막대 − 음자리표 끝)의 최대 − 최소 — 투표 묶음 폭 ±3px와 비교.
후보(사본): 보표마다 막대 x를 (전 보표 음자리표 끝 중앙 − 그 보표 음자리표 끝)만큼 옮긴 뒤 **같은** `_vote_key_signature`를 돌린다(「음자리표 끝 기준 정렬 투표」).

    python tools/measure_keysig_persp.py
"""
import copy
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
TRUTH = {"em2": (1, "♯"), "bbm1": (5, "♭"), "db3": (5, "♭")}


def _job(job):
    stem, file, mode = job
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves, _vote_key_signature
    try:
        res = preprocess(os.path.join(ROOT, "inputs", "degraded", file), photo=(mode == "photo"))
    except Exception as e:      # 거부(오선 못 찾음 등)
        return dict(stem=stem, mode=mode, rejected=str(e)[:60])
    ctx = analyze_staves(res)
    found = [c for c in ctx.values() if c.clef_found and c.bars]
    now = (ctx[next(iter(ctx))].key_count, ctx[next(iter(ctx))].key_symbol) if ctx else (0, "")
    first = [min(x for x, _s in c.bars) for c in found]
    rel = [min(x for x, _s in c.bars) - c.clef_end for c in found]
    med = float(np.median([c.clef_end for c in found])) if found else 0.0
    shifted = {}
    for k, c in ctx.items():
        c2 = copy.copy(c)
        if c.clef_found:
            d = med - c.clef_end
            c2.bars = tuple((x + d, s) for x, s in c.bars)
        shifted[k] = c2
    kc, ks, _r = _vote_key_signature(shifted)
    sp = float(np.median([s.spacing for s in res.staves]))
    return dict(stem=stem, mode=mode, rejected=None, staves=len(ctx), with_bars=len(found), sp=round(sp, 1),
                now=f"{now[1]}{now[0]}" if now[0] else "0", cand=f"{ks}{kc}" if kc else "0",
                spread_abs=round(max(first) - min(first), 1) if first else None,
                spread_rel=round(max(rel) - min(rel), 1) if rel else None,
                clef_end=[c.clef_end for c in found], first_bar=[round(x, 1) for x in first])


def main():
    man = json.load(open(os.path.join(ROOT, "inputs", "degraded", "manifest.json"), encoding="utf-8"))
    jobs = [(m["stem"], m["file"], mode) for mode in ("normal", "photo") for m in man]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_job, jobs))
    json.dump(R, open(os.path.join(ROOT, "debug", "keysig_persp.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = Counter()
    for r in R:
        if r["rejected"]:
            print(f"  {r['mode']:6s} {r['stem']:16s} 거부")
            continue
        t = TRUTH[r["stem"].split("__")[0]]
        tt = f"{t[1]}{t[0]}"
        c[(r["mode"], "지금 맞음" if r["now"] == tt else "지금 틀림", "후보 맞음" if r["cand"] == tt else "후보 틀림")] += 1
        print(f"  {r['mode']:6s} {r['stem']:16s} 정답 {tt} · 지금 {r['now']:3s} · 후보 {r['cand']:3s} | 막대 있는 보표 {r['with_bars']}/{r['staves']}"
              f" · 첫 막대 x 퍼짐 {r['spread_abs']}px · 음자리표 끝 기준 퍼짐 {r['spread_rel']}px · sp {r['sp']}")
    print("요약", dict(c))


if __name__ == "__main__" and sys.argv[1:] != ["clean"]:
    main()


def votes(res):
    """(지금 조표, 후보 조표) — 후보 = 보표마다 막대 x를 음자리표 끝 중앙으로 맞춘 뒤 같은 투표."""
    from modules.clef_keysig import analyze_staves, _vote_key_signature
    ctx = analyze_staves(res)
    found = [c for c in ctx.values() if c.clef_found]
    first = next(iter(ctx.values())) if ctx else None
    now = f"{first.key_symbol}{first.key_count}" if first and first.key_count else "0"
    if not found:
        return now, now
    med = float(np.median([c.clef_end for c in found]))
    shifted = {}
    for k, c in ctx.items():
        c2 = copy.copy(c)
        if c.clef_found:
            d = med - c.clef_end
            c2.bars = tuple((x + d, s) for x, s in c.bars)
        shifted[k] = c2
    kc, ks, _r = _vote_key_signature(shifted)
    return now, (f"{ks}{kc}" if kc else "0")


def _clean_job(job):
    """깨끗한 입력 한 쪽(+ 가로 이동 dx px) — `measure_keysig_shift`와 같은 warpAffine(INTER_LINEAR · 흰 경계 · 0도 호출 생략 안 함)."""
    import cv2, tempfile
    from modules.preprocess import preprocess, load_image
    st, name, path, pg, dx = job
    bgr = load_image(os.path.join(ROOT, path), pdf_page=pg)
    bgr = cv2.warpAffine(bgr, np.float32([[1, 0, dx], [0, 1, 0]]), (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    d = tempfile.mkdtemp()
    p = os.path.join(d, "x.png")
    open(p, "wb").write(cv2.imencode(".png", bgr)[1].tobytes())
    try:
        now, cand = votes(preprocess(p))
    except Exception as e:
        now = cand = f"거부:{str(e)[:30]}"
    return dict(set=st, page=name, dx=dx, now=now, cand=cand)


def clean():
    import check_accidental_fix as C
    jobs = []
    for n, p, pg in C.PAGES:
        st = "aoharu" if not p.endswith(".pdf") else "pdf"
        for dx in (0.0, 0.25, 0.5, 0.75):
            jobs.append((st, n, p, pg, dx))
    FX = os.path.join("tests", "fixtures", "key_signatures", "pdf")
    for f in sorted(os.listdir(os.path.join(ROOT, FX))):
        for dx in (0.0, 0.25, 0.5, 0.75):
            jobs.append(("fixture", f[:-4], os.path.join(FX, f), 0, dx))
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0, 0.0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_clean_job, jobs))
    json.dump(R, open(os.path.join(ROOT, "debug", "keysig_persp_clean.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("입력", len(R), "· 세트별", dict(Counter(r["set"] for r in R)))
    ch = [r for r in R if r["now"] != r["cand"]]
    print("조표가 바뀌는 쪽", len(ch))
    for r in ch:
        print("   ", r)


if __name__ == "__main__" and sys.argv[1:] == ["clean"]:
    clean()
