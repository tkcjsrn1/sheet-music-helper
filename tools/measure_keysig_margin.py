# -*- coding: utf-8 -*-
"""TASKS [2] 조표 투표 여유 분포 (2026-09-30, 측정 전용 · 제품 코드 무변경).

제품 `analyze_staves`가 `_vote_key_signature`에 넘기는 보표 문맥을 **그대로 가로채** 잰다
(`measure_keysig_vote_margin.py` · `measure_keysig_resample.header`는 `_analyze_one`을 직접 불러 제품 경로와 다를 수 있다 — 측정 함정 A-1).

여유(뒤집힘 거리) = 막대 클러스터 하나의 인정/탈락을 바꾸는 데 드는 표 수 중, **그 한 클러스터만 바꿨을 때 조표 판정이 실제로 달라지는 것**의 최솟값.
- 인정 클러스터: 지지 − 문턱 + 1표를 잃으면 빠진다 / 탈락 클러스터: 문턱 − 지지 표를 얻으면 들어온다
- 1 = 한 표로 뒤집힌다. 판정을 바꾸는 클러스터가 없으면 None(한 클러스터로는 안 뒤집힘)
- 투표 규칙은 `_vote_key_signature`를 인정 집합만 바꿔 다시 도는 사본 — 매 입력 제품 결과와 같은지 대조한다(다르면 멈춤)

    python tools/measure_keysig_margin.py pdf20 | photo | sweep <악보>     → debug/keysig_margin_<셋>.json
    python tools/measure_keysig_margin.py report                            → 분포 · 경계
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import modules.clef_keysig as CK  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402

OUT = os.path.join(ROOT, "debug")
# 정답 조표(원본 악보) — 사진 · 재표본화 변형은 원본 이름으로 찾는다
TRUTH = {"bach": "0", "bbm": "♭5", "db": "♭5", "em": "♯1", "aoharu": "♯2", "chopin_Db": "♭5", "F_flat1": "♭1"}
ORIG_VOTE = CK._vote_key_signature


def vote_with(contexts, consensus):
    """`_vote_key_signature`의 쌍 · 사슬 · ♭ 부분을 주어진 인정 집합으로(사본 — 제품과 대조)."""
    found = [c for c in contexts.values() if c.clef_found]
    sp = float(np.median([c.spacing for c in found]))
    pairs, singles, i = [], [], 0
    while i < len(consensus):
        if (i + 1 < len(consensus) and sp * 0.3 <= consensus[i + 1] - consensus[i] <= sp * 0.55
                and CK._same_glyph(found, consensus[i], consensus[i + 1])):
            pairs.append((consensus[i] + consensus[i + 1]) / 2.0)
            i += 2
        else:
            singles.append(consensus[i])
            i += 1
    if pairs:
        chains, cur = [], [pairs[0]]
        for p in pairs[1:]:
            if sp * 0.9 <= p - cur[-1] <= sp * 2.2:
                cur.append(p)
            else:
                chains.append(cur)
                cur = [p]
        chains.append(cur)
        best = max(chains, key=lambda ch: (len(ch), ch[0]))
        return f"♯{min(len(best), 7)}"
    if singles:
        n = min(len(singles), int(np.median([c.holes for c in found])))
        if n > 0:
            return f"♭{min(n, 7)}"
    return "0"


def detail(contexts):
    found = [c for c in contexts.values() if c.clef_found]
    if not found:
        return None
    thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    bars = sorted(x for c in found for x, _y in c.bars)
    clusters, i = [], 0
    while i < len(bars):                                         # 제품과 같은 ±3px 클러스터(첫 원소 기준)
        j = i
        while j + 1 < len(bars) and bars[j + 1] - bars[i] <= 3.0:
            j += 1
        clusters.append((float(np.mean(bars[i:j + 1])), j - i + 1))
        i = j + 1
    cons = [x for x, s in clusters if s >= thr]
    key = vote_with(contexts, cons)
    kc, ks, _ = ORIG_VOTE(contexts)
    prod = f"{ks}{kc}" if kc else "0"
    if key != prod:
        raise RuntimeError(f"투표 사본 불일치: 제품 {prod} / 사본 {key}")      # 측정 함정 A-1
    flips = []
    for x, s in clusters:
        inside = s >= thr
        need = s - thr + 1 if inside else thr - s
        alt = [c for c in cons if c != x] if inside else sorted(cons + [x])
        k2 = vote_with(contexts, alt)
        if k2 != key:
            flips.append(dict(x=round(x), support=s, inside=inside, need=need, to=k2))
    return dict(key=key, thr=thr, found=len(found), staves=len(contexts), clusters=[(round(x), s) for x, s in clusters],
                margin=min((f["need"] for f in flips), default=None), flips=sorted(flips, key=lambda f: f["need"])[:4])


def measure(res):
    got = {}

    def spy(contexts):
        got["d"] = detail(contexts)
        return ORIG_VOTE(contexts)

    CK._vote_key_signature = spy
    try:
        CK.analyze_staves(res)
    finally:
        CK._vote_key_signature = ORIG_VOTE
    return got.get("d")


def truth_of(name):
    for k in sorted(TRUTH, key=len, reverse=True):
        if name.startswith(k):
            return TRUTH[k]
    return None


def run_pdf20():
    import check_accidental_fix as C
    rows = []
    for name, path, pg in C.PAGES:
        d = measure(C.preprocess(os.path.join(ROOT, path), pdf_page=pg))
        rows.append(dict(set="pdf20", name=name, truth=truth_of(name), **d))
        print(name, d["key"], "여유", d["margin"], flush=True)
    return rows


def run_photo():
    import measure_normalize_sp as N
    rows = []
    for d_ in (N.SYN, N.EDGE):
        for f in sorted(os.listdir(d_)):
            if not f.lower().endswith((".png", ".jpg")):
                continue
            name = os.path.splitext(f)[0]
            try:
                res = preprocess(os.path.join(d_, f), photo=True)
            except (SystemExit, Exception) as exc:                 # M1 거부 — 제품도 여기서 멈춘다
                print(name, "거부", type(exc).__name__, flush=True)
                continue
            d = measure(res)
            if d:
                rows.append(dict(set="photo", name=name, truth=truth_of(name), **d))
                print(name, d["key"], "여유", d["margin"], flush=True)
    return rows


def run_sweep(score):
    import measure_keysig_resample as R
    tmp = os.path.join(OUT, "keysig_margin_sweep")
    os.makedirs(tmp, exist_ok=True)
    path, page = R.SCORES[score]
    img = preprocess(path, pdf_page=page).original_bgr
    rows = []
    for deg in R.ANGLES + ("shift",):
        for m in R.METHODS:
            p = os.path.join(tmp, f"{score}_{deg}_{m}.png")
            R._write(p, R.tilt_and_fix(img, deg, m))
            try:
                d = measure(preprocess(p))
            except RuntimeError:
                raise
            except Exception as exc:
                print(score, deg, m, "실패", type(exc).__name__, flush=True)
                continue
            if d:
                rows.append(dict(set="sweep", name=f"{score}_{deg}_{m}", truth=TRUTH[score], **d))
                print(score, deg, m, d["key"], "여유", d["margin"], flush=True)
    return rows


def report():
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, "keysig_margin_*.json"))):
        rows += json.load(open(f, encoding="utf-8"))
    from collections import Counter
    for st in ("pdf20", "photo", "sweep", None):
        sub = [r for r in rows if st is None or r["set"] == st]
        ok = Counter(r["margin"] for r in sub if r["key"] == r["truth"])
        bad = Counter(r["margin"] for r in sub if r["key"] != r["truth"])
        print(st or "전체", "맞음", len(sub) - sum(bad.values()), dict(sorted(ok.items(), key=lambda t: (t[0] is None, t[0] or 0))),
              "| 뒤집힘", sum(bad.values()), dict(sorted(bad.items(), key=lambda t: (t[0] is None, t[0] or 0))))
    for r in rows:
        if r["key"] != r["truth"]:
            print("  뒤집힘", r["set"], r["name"], r["truth"], "→", r["key"], "여유", r["margin"], r["flips"][:2])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "report":
        report()
    else:
        rows = {"pdf20": run_pdf20, "photo": run_photo}[cmd]() if cmd != "sweep" else run_sweep(sys.argv[2])
        tag = cmd if cmd != "sweep" else f"sweep_{sys.argv[2]}"
        json.dump(rows, open(os.path.join(OUT, f"keysig_margin_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
