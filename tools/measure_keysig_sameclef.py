# -*- coding: utf-8 -*-
"""조표 교차 투표 후보 (가) — 「같은 음자리표끼리 맞춤 + 들여쓴 첫 시스템 박자표 막대 제외」 (2026-10-13 · 측정만, 보류 세트 미사용).

`measure_keysig_persp.py`의 「음자리표 끝 기준 정렬」이 깨끗한 세트 160에서 조표 3쪽을 바꿔 중단된 두 원인을 막은 사본:
  ① 음자리표 종류마다 글리프 폭이 달라 clef_end가 3~6px 어긋난다(Aoharu 2 · Clara 1 L) → 옮김 = **같은 종류(`ctx.clef`)** 보표들의 clef_end 중앙 − 자기 clef_end
  ② 들여쓴 첫 시스템의 박자표 숫자 막대가 옮겨져 다른 보표 잡막대와 합의(Clara 2 B) → 들여쓴 보표(clef_end ≥ 전체 중앙 + 4sp, 보표 3개 이상 —
     `analyze_staves`의 첫 시스템 판정과 같음)는 **박자표 시작 x 이후 막대를 뺀다**. 박자표 시작 = `_timesig_span_end`와 같은 열 조건
     (맨 윗줄 · 맨 아랫줄 ±0.2sp에 동시에 잉크, 연속 폭 0.6~2.6sp)의 첫 구간 왼끝, clef_end부터 8sp 안. 없으면 막대 그대로.
그 뒤 **같은** `_vote_key_signature`. 제품 코드 무변경.

판정 기준(사용자): 깨끗한 세트 160 조표 변화 **0**이어야 다음 단계. 열화 세트는 지금 틀림 9장(일반 3 · 사진 6) 중 회복 수.

    python tools/measure_keysig_sameclef.py clean      # 깨끗한 세트 160 (PDF 17 · Aoharu 3 · 픽스처 15 × 이동 4 + Verovio 20)
    python tools/measure_keysig_sameclef.py degraded   # inputs/degraded 24장 × 일반 · 사진
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
TS_LOOK_SP = 8.0


def _timesig_start(no_staff, staff, x_from):
    """`clef_keysig._timesig_span_end`와 같은 열 조건으로 첫 숫자 구간의 **왼끝**. 없으면 None."""
    sp = staff.spacing
    H, W = no_staff.shape[:2]
    x_to = min(W, x_from + int(sp * TS_LOOK_SP))
    tol = max(1, int(round(sp * 0.2)))
    t0, t1 = max(0, int(staff.top) - tol), min(H, int(staff.top) + tol + 1)
    b0, b1 = max(0, int(staff.bottom) - tol), min(H, int(staff.bottom) + tol + 1)
    if x_to <= x_from or t1 <= t0 or b1 <= b0:
        return None
    spans = (no_staff[t0:t1, x_from:x_to] > 0).any(axis=0) & (no_staff[b0:b1, x_from:x_to] > 0).any(axis=0)
    lo, hi = int(sp * 0.6), int(sp * 2.6)
    i, n = 0, len(spans)
    while i < n:
        if not spans[i]:
            i += 1
            continue
        j = i
        while j < n and spans[j]:
            j += 1
        if lo <= j - i <= hi:
            return x_from + i
        i = j
    return None


def votes(res):
    """(지금 조표, 후보 조표, 옮김 · 제외 기록)."""
    from modules.clef_keysig import analyze_staves, _vote_key_signature
    from modules.notehead_detect import remove_staff_lines
    ctx = analyze_staves(res)
    first = next(iter(ctx.values())) if ctx else None
    now = f"{first.key_symbol}{first.key_count}" if first and first.key_count else "0"
    found = [c for c in ctx.values() if c.clef_found]
    if not found:
        return now, now, {}
    staff_of = {s.index: s for s in res.staves}
    med_all = float(np.median([c.clef_end for c in found]))
    med_kind = {k: float(np.median([c.clef_end for c in found if c.clef == k])) for k in {c.clef for c in found}}
    ns = None
    shifted, log = {}, {}
    for k, c in ctx.items():
        c2 = copy.copy(c)
        if c.clef_found:
            bars = list(c.bars)
            cut = None
            if len(found) >= 3 and c.clef_end >= med_all + staff_of[k].spacing * 4.0:
                if ns is None:
                    ns = remove_staff_lines(res.binary, res.staves)
                cut = _timesig_start(ns, staff_of[k], int(c.clef_end))
                if cut is not None:
                    bars = [b for b in bars if b[0] < cut]
            d = med_kind[c.clef] - c.clef_end
            c2.bars = tuple((x + d, s) for x, s in bars)
            log[k] = dict(clef=c.clef, shift=round(d, 1), ts_cut=cut, dropped=len(c.bars) - len(bars))
        shifted[k] = c2
    kc, ks, _r = _vote_key_signature(shifted)
    return now, (f"{ks}{kc}" if kc else "0"), log


def _clean_job(job):
    """`measure_keysig_persp._clean_job`과 같은 이동(warpAffine INTER_LINEAR · 흰 경계 · 0도 호출 생략 안 함)."""
    import cv2, tempfile
    from modules.preprocess import preprocess, load_image
    st, name, path, pg, dx = job
    bgr = load_image(os.path.join(ROOT, path), pdf_page=pg)
    bgr = cv2.warpAffine(bgr, np.float32([[1, 0, dx], [0, 1, 0]]), (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    p = os.path.join(tempfile.mkdtemp(), "x.png")
    open(p, "wb").write(cv2.imencode(".png", bgr)[1].tobytes())
    try:
        now, cand, log = votes(preprocess(p))
    except Exception as e:
        now = cand = f"거부:{str(e)[:30]}"
        log = {}
    return dict(set=st, page=name, dx=dx, now=now, cand=cand, log={str(k): v for k, v in log.items()})


def clean():
    import check_accidental_fix as C
    jobs = []
    for n, p, pg in C.PAGES:
        st = "aoharu" if not p.endswith(".pdf") else "pdf"
        jobs += [(st, n, p, pg, dx) for dx in (0.0, 0.25, 0.5, 0.75)]
    FX = os.path.join("tests", "fixtures", "key_signatures", "pdf")
    for f in sorted(os.listdir(os.path.join(ROOT, FX))):
        jobs += [("fixture", f[:-4], os.path.join(FX, f), 0, dx) for dx in (0.0, 0.25, 0.5, 0.75)]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0, 0.0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    assert len(jobs) == 160, len(jobs)    # measure_keysig_persp.clean()과 같은 입력
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_clean_job, jobs))
    json.dump(R, open(os.path.join(ROOT, "debug", "keysig_sameclef_clean.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("입력", len(R), "· 세트별", dict(Counter(r["set"] for r in R)))
    ch = [r for r in R if r["now"] != r["cand"]]
    print("조표가 바뀌는 쪽", len(ch), "(0이어야 다음 단계)")
    for r in ch:
        print("   ", {k: r[k] for k in ("set", "page", "dx", "now", "cand")}, r["log"])


def _deg_job(job):
    stem, file, mode = job
    from modules.preprocess import preprocess
    try:
        res = preprocess(os.path.join(ROOT, "inputs", "degraded", file), photo=(mode == "photo"))
    except Exception as e:
        return dict(stem=stem, mode=mode, rejected=str(e)[:60])
    now, cand, log = votes(res)
    return dict(stem=stem, mode=mode, rejected=None, now=now, cand=cand, log={str(k): v for k, v in log.items()})


def degraded():
    from measure_keysig_persp import TRUTH
    man = json.load(open(os.path.join(ROOT, "inputs", "degraded", "manifest.json"), encoding="utf-8"))
    jobs = [(m["stem"], m["file"], mode) for mode in ("normal", "photo") for m in man]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_deg_job, jobs))
    json.dump(R, open(os.path.join(ROOT, "debug", "keysig_sameclef_degraded.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = Counter()
    for r in R:
        if r["rejected"]:
            print(f"  {r['mode']:6s} {r['stem']:16s} 거부")
            continue
        n, s = TRUTH[r["stem"].split("__")[0]]
        tt = f"{s}{n}"
        c[(r["mode"], "지금 맞음" if r["now"] == tt else "지금 틀림", "후보 맞음" if r["cand"] == tt else "후보 틀림")] += 1
        print(f"  {r['mode']:6s} {r['stem']:16s} 정답 {tt} · 지금 {r['now']:3s} · 후보 {r['cand']:3s}")
    print("요약", dict(c), "· 지금 틀림 → 후보 맞음 =", sum(v for k, v in c.items() if k[1:] == ("지금 틀림", "후보 맞음")), "/ 9")


if __name__ == "__main__":
    {"clean": clean, "degraded": degraded}[sys.argv[1]]()
