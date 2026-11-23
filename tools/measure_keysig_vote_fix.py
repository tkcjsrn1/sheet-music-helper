# -*- coding: utf-8 -*-
"""TASKS [2](a) 조표 오판 — 교차 투표 수정 후보를 네 세트에서 잰다. 측정 전용, 제품 코드 무변경.

세트: PDF 17쪽(LilyPond) · Aoharu 3쪽(사진) · Verovio 20쪽 · 조표 픽스처 15종.
보표별 막대 수집(`_analyze_one`)은 제품 그대로 한 번만 돌려 `debug/keysig_fix/bars.json`에 두고,
투표(`_vote_key_signature`)만 사본으로 바꿔 쪽 조표 정답률을 비교한다.

    python tools/measure_keysig_vote_fix.py collect     # 55쪽 막대 수집 (몇 분)
    python tools/measure_keysig_vote_fix.py eval        # 변형별 정답률
    python tools/measure_keysig_vote_fix.py collect_extra  # 사진 합성 · 기울였다 되돌리기 (TASKS [2] 여유 측정 입력)
    python tools/measure_keysig_vote_fix.py extra       # 그 입력에서 변형별 정답률
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "debug", "keysig_fix")

VRV = os.path.join(ROOT, "test_scores", "verovio")
FIX = os.path.join(ROOT, "tests", "fixtures", "key_signatures")


def pages():
    """(세트, 이름, 경로, pdf 쪽, 정답 (기호, 개수))"""
    P = []
    P.append(("pdf", "bach", os.path.join(ROOT, "test_scores", "bach_minuet_Am.pdf"), 0, ("", 0)))
    for i in range(6):
        P.append(("pdf", f"bbm{i + 1}", os.path.join(ROOT, "test_scores", "chopin_nocturne_Bbm.pdf"), i, ("♭", 5)))
    for i in range(6):
        P.append(("pdf", f"db{i + 1}", os.path.join(ROOT, "test_scores", "chopin_nocturne_Db_6-8.pdf"), i, ("♭", 5)))
    for i in range(4):
        P.append(("pdf", f"em{i + 1}", os.path.join(ROOT, "test_scores", "chopin_nocturne_Em.pdf"), i, ("♯", 1)))
    for tag, f in (("p1", ""), ("p2", "_01"), ("p3", "_02")):
        P.append(("aoharu", tag, os.path.join(ROOT, "sample_images", f"KakaoTalk_20260731_162400402{f}.png"), 0, ("♯", 2)))
    for f in sorted(os.listdir(VRV)):
        if f.endswith("_p1.png"):
            stem = f[:-4]
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", stem + ".json"), encoding="utf-8"))
            v = t["staves"][0]["keysigs"][0]["val"] if t["staves"][0]["keysigs"] else "0"
            key = ("", 0) if v == "0" else ({"s": "♯", "f": "♭"}[v[-1]], int(v[:-1]))
            P.append(("verovio", stem, os.path.join(VRV, f), 0, key))
    man = json.load(open(os.path.join(FIX, "manifest.json"), encoding="utf-8"))
    for k in man["keys"]:
        P.append(("fixture", k["slug"], os.path.join(FIX, k["pdf"].replace("\\", "/")), 0,
                  ({"sharp": "♯", "flat": "♭", "": ""}[k["symbol"]], k["count"])))
    return P


def _collect_one(p):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    import modules.clef_keysig as CK
    st, name, path, pg, key = p
    res = preprocess(path, pdf_page=pg) if path.endswith(".pdf") else preprocess(path)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    single = len(res.staves) <= 2
    ctxs = {s.index: CK._analyze_one(ns, s, H, single) for s in res.staves}
    prod = CK._vote_key_signature(ctxs)
    staves = [dict(i=s.index, sp=c.spacing, clef=c.clef, found=c.clef_found, clef_end=c.clef_end,
                   bars=[list(b) for b in c.bars], holes=c.holes, top=s.top)
              for s in res.staves for c in [ctxs[s.index]]]
    return dict(set=st, name=name, truth=list(key), product=[prod[1], prod[0]], staves=staves)


def collect():
    os.makedirs(OUT, exist_ok=True)
    P = pages()
    with ProcessPoolExecutor(4) as ex:
        rows = list(ex.map(_collect_one, P))
    json.dump(rows, open(os.path.join(OUT, "bars.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for r in rows:
        ok = tuple(r["truth"]) == tuple(r["product"])
        print(r["set"], r["name"], "정답", "".join(map(str, r["truth"])), "제품", "".join(map(str, r["product"])), "" if ok else "  ← 틀림", flush=True)


def _spy_staves(res):
    """제품 `analyze_staves`가 투표에 넘기는 문맥을 그대로 가로챈다(사진 경로 · 재표본화 입력용)."""
    import modules.clef_keysig as CK
    orig, got = CK._vote_key_signature, {}

    def spy(contexts):
        got["c"] = contexts
        got["p"] = orig(contexts)
        return got["p"]
    CK._vote_key_signature = spy
    try:
        CK.analyze_staves(res)
    finally:
        CK._vote_key_signature = orig
    ctxs = got["c"]
    st = [dict(i=i, sp=c.spacing, clef=c.clef, found=c.clef_found, clef_end=c.clef_end,
               bars=[list(b) for b in c.bars], holes=c.holes) for i, c in sorted(ctxs.items())]
    return st, [got["p"][1], got["p"][0]]


def _extra_one(job):
    """사진 합성 세트 · 기울였다 되돌리기 — `measure_keysig_margin`(TASKS [2] 여유 측정)과 같은 입력."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from modules.preprocess import preprocess
    import measure_keysig_margin as KM
    kind, arg = job
    rows = []
    if kind == "photo":
        for f in sorted(os.listdir(arg)):
            if not f.lower().endswith((".png", ".jpg")):
                continue
            name = os.path.splitext(f)[0]
            try:
                res = preprocess(os.path.join(arg, f), photo=True)
            except (SystemExit, Exception):                       # M1 거부 — 제품도 여기서 멈춘다
                continue
            st, prod = _spy_staves(res)
            t = KM.truth_of(name)
            rows.append(dict(set="photo", name=name, truth=["", 0] if t == "0" else [t[0], int(t[1:])], product=prod, staves=st))
    else:
        import measure_keysig_resample as R
        tmp = os.path.join(OUT, "sweep")
        os.makedirs(tmp, exist_ok=True)
        path, page = R.SCORES[arg]
        img = preprocess(path, pdf_page=page).original_bgr
        t = KM.TRUTH[arg]
        for deg in R.ANGLES + ("shift",):
            for m in R.METHODS:
                p = os.path.join(tmp, f"{arg}_{deg}_{m}.png")
                R._write(p, R.tilt_and_fix(img, deg, m))
                try:
                    st, prod = _spy_staves(preprocess(p))
                except Exception:
                    continue
                rows.append(dict(set="sweep", name=f"{arg}_{deg}_{m}", truth=["", 0] if t == "0" else [t[0], int(t[1:])],
                                 product=prod, staves=st))
    return rows


def collect_extra():
    jobs = [("photo", os.path.join(ROOT, "output", "synthetic_photos")), ("photo", os.path.join(ROOT, "output", "m1_edge")),
            ("sweep", "bach"), ("sweep", "bbm"), ("sweep", "aoharu")]
    with ProcessPoolExecutor(4) as ex:
        rows = [r for part in ex.map(_extra_one, jobs) for r in part]
    json.dump(rows, open(os.path.join(OUT, "bars_extra.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("추가 입력", len(rows))


# ------------------------------------------------------------------ 투표 사본
class _Ctx:
    def __init__(self, s):
        self.spacing, self.clef, self.clef_found = s["sp"], s["clef"], s["found"]
        self.bars = [tuple(b) for b in s["bars"]]
        self.holes = s["holes"]


FLAT_STEP_TREBLE = (4, 7, 3, 6, 2, 5, 1)   # FLAT_ORDER BEADGCF의 높은음자리표 자리(맨아랫줄 기준 반칸) — 낮은음은 −2
FLAT_STEM_OFFSET = 1.17                     # ♭ 세로획 중심 − 음 자리(step). 실측 쪽 중앙값 1.06~1.39(LilyPond · Bravura · Leipzig)
FLAT_POS_TOL = 0.68                         # √(진짜 최대 편차 0.46 × 한 음 차이 1step)


def _flat_at_position(found, x, k, tol=FLAT_POS_TOL):
    """k번째 ♭ 자리에 있는가 — 막대가 잡힌 보표 중 과반이 그 음 자리(± tol)에 있을 것."""
    hits = []
    for c in found:
        bb = [s for bx, s in c.bars if abs(bx - x) <= 3.0]
        if bb:
            e = FLAT_STEP_TREBLE[k] - (2 if c.clef == "bass" else 0) + FLAT_STEM_OFFSET
            hits.append(abs(bb[0] - e) <= tol)
    return bool(hits) and float(np.mean(hits)) >= 0.5


def _staff_pairs(c, sp):
    """보표 안에서 ♯ 쌍 — 제품 쌍 조건(간격 0.3~0.55sp · `KEYSIG_PAIR_Y_STEP`)을 보표 막대에 그대로, 떨어지면 한 칸 전진."""
    import modules.clef_keysig as CK
    b = sorted(c.bars)
    out, i = [], 0
    while i < len(b):
        if (i + 1 < len(b) and sp * 0.3 <= b[i + 1][0] - b[i][0] <= sp * 0.55
                and abs(b[i + 1][1] - b[i][1]) <= CK.KEYSIG_PAIR_Y_STEP):
            out.append((b[i][0] + b[i + 1][0]) / 2.0)
            i += 2
        else:
            i += 1
    return out


def vote(staves, tol_px=3.0, tol_sp=None, flat_pos=False, pair_first=False):
    """제품 `_vote_key_signature` 사본. 기본 인자면 제품과 같은 값이 나와야 한다(eval이 대조)."""
    import modules.clef_keysig as CK
    found = [_Ctx(s) for s in staves if s["found"]]
    if not found:
        return "", 0
    sp = float(np.median([c.spacing for c in found]))
    if tol_sp is not None:
        tol_px = sp * tol_sp
    threshold = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    all_bars = sorted(x for c in found for x, _y in c.bars)
    consensus = []
    i = 0
    while i < len(all_bars):
        j = i
        while j + 1 < len(all_bars) and all_bars[j + 1] - all_bars[i] <= tol_px:
            j += 1
        if j - i + 1 >= threshold:
            consensus.append(float(np.mean(all_bars[i:j + 1])))
        i = j + 1
    pairs, singles = [], []
    if pair_first:
        # 보표 안 쌍 중심을 교차 투표 — 묶음 폭 = 사슬 최소 간격 0.9sp의 절반(다른 ♯ 글리프끼리는 안 섞인다)
        allp = sorted(x for c in found for x in _staff_pairs(c, sp))
        i = 0
        while i < len(allp):
            j = i
            while j + 1 < len(allp) and allp[j + 1] - allp[i] <= sp * 0.45:
                j += 1
            if j - i + 1 >= threshold:
                pairs.append(float(np.mean(allp[i:j + 1])))
            i = j + 1
        if not pairs:
            singles = consensus
    i = len(consensus) if pair_first else 0
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
        return "♯", min(len(best), 7)
    if singles:
        n_holes = int(np.median([c.holes for c in found]))
        n_flat = min(len(singles), n_holes)
        if flat_pos:
            n_pos = 0
            while n_pos < min(len(singles), 7) and _flat_at_position(found, singles[n_pos], n_pos):
                n_pos += 1
            n_flat = min(n_flat, n_pos)
        if n_flat > 0:
            return "♭", min(n_flat, 7)
    return "", 0


def vote_max(staves, **kw):
    """막대 먼저(제품)와 쌍 먼저 중 ♯ 사슬이 긴 쪽. 둘 다 ♯이 아니면 막대 먼저 결과."""
    a = vote(staves, **kw)
    b = vote(staves, pair_first=True, **kw)
    if b[0] == "♯" and (a[0] != "♯" or b[1] > a[1]):
        return b
    return a


def evaluate(rows, name, fn=None, **kw):
    bad = []
    by = {}
    for r in rows:
        got = (fn or vote)(r["staves"], **kw)
        ok = tuple(got) == tuple(r["truth"])
        by.setdefault(r["set"], [0, 0])
        by[r["set"]][0] += ok
        by[r["set"]][1] += 1
        if not ok:
            bad.append(f'{r["name"]} {"".join(map(str, r["truth"]))}→{"".join(map(str, got))}')
    print(f"{name:24s}", " · ".join(f"{k} {a}/{b}" for k, (a, b) in by.items()), "| 틀림:", ", ".join(bad) or "없음")
    return by, bad


def main():
    if sys.argv[1] == "collect":
        collect()
        return
    if sys.argv[1] == "collect_extra":
        collect_extra()
        return
    rows = json.load(open(os.path.join(OUT, "bars.json"), encoding="utf-8"))
    if sys.argv[1] == "extra":
        rows = json.load(open(os.path.join(OUT, "bars_extra.json"), encoding="utf-8"))
    # 사본 대조: 기본 인자 = 제품
    mism = [r["name"] for r in rows if tuple(vote(r["staves"])) != tuple(r["product"])]
    print("사본 ≠ 제품:", mism or "0")
    if mism:
        sys.exit(1)
    evaluate(rows, "제품(±3px)")
    evaluate(rows, "♭ 자리", flat_pos=True)
    for t in (0.25, 0.3):
        evaluate(rows, f"묶음 ±{t}sp + ♭ 자리", tol_sp=t, flat_pos=True)
    evaluate(rows, "쌍 먼저", pair_first=True)
    evaluate(rows, "쌍 먼저 + ♭ 자리", pair_first=True, flat_pos=True)
    evaluate(rows, "긴 사슬(막대·쌍) + ♭ 자리", fn=vote_max, flat_pos=True)
    # 더 세는 쪽으로 틀린 적이 있나 — 막대 먼저 / 쌍 먼저 각각 ♯ 개수가 정답보다 큰 입력
    for pf in (False, True):
        over = [r["name"] for r in rows for g in [vote(r["staves"], pair_first=pf, flat_pos=True)]
                if g[0] == "♯" and (r["truth"][0] != "♯" or g[1] > r["truth"][1])]
        print("쌍 먼저" if pf else "막대 먼저", "♯ 과다(정답보다 많이 셈):", over or "0")


if __name__ == "__main__":
    main()
