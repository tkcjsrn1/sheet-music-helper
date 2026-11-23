# -*- coding: utf-8 -*-
"""꾸밈음 크기 기준 보완 시뮬레이션 (2026-10-13 · 측정만, 보류 세트 미사용).

`verify.grace_size_suspects`와 같은 계산(오선 제거 → 타원 0.5sp 열림 → 라벨 자리 성분 폭 · 높이 / 기준)을 하되,
기준(「화음 아닌」 라벨 성분 중앙)이 **작거나(라벨 수 < N_MIN) 꾸밈음에 오염된(기준 폭 < 기대 × SHRINK)** 쪽은
기준을 **sp 기대 머리 크기**로 바꾼다. 기대 크기 = 49쪽(PDF 17 · Aoharu 3 · 보지 않은 9 · Verovio 20) 쪽별 기준의 중앙값(폭 · 높이 sp).
세는 것: Mutopia 꾸밈음 「확실」 33 중 새로 걸리는 수, 49쪽에서 새로 걸리는 라벨 중 정상 크기 진짜 머리(헛표시).

    python tools/measure_grace_fallback.py
"""
import json, os, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def _sizes(path, pg, labels):
    import cv2
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ns = remove_staff_lines(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in res.staves}
    sp0 = float(np.median(list(sp_of.values())))
    k = max(3, int(0.5 * sp0)) | 1
    op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    _n, lab, st, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
    H, W = lab.shape
    out = []
    for l in labels:
        sp = sp_of.get(l["staff"], sp0)
        y, x = min(H - 1, max(0, int(l["y"]))), min(W - 1, max(0, int(l["x"])))
        c = lab[y, x]
        if not c:
            win = lab[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
            nz = win[win > 0]
            c = int(np.bincount(nz).argmax()) if nz.size else 0
        s = (st[c, cv2.CC_STAT_WIDTH] / sp, st[c, cv2.CC_STAT_HEIGHT] / sp) if c else None
        ch = any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 0.6 * sp for o in labels)
        out.append((s, ch))
    return out, sp0


def _job(job):
    st, name, path, pg, labfile = job
    L = json.load(open(labfile, encoding="utf-8"))["labels"]
    sz, sp = _sizes(path, pg, L)
    ref = [s for s, ch in sz if s is not None and not ch]
    # 진짜 · 꾸밈음 정답
    small, normal = [], []
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))["notes"]
        small = [(n["x"], n["y"]) for n in t if n["grace"] or n["cue"]]
        normal = [(n["x"], n["y"]) for n in t if not n["grace"] and not n["cue"]]
    elif st in ("pdf", "unseen", "mutopia"):
        import measure_omission_rate as M
        g = [q for q in M.pdf_glyphs(path, pg) if q["name"].startswith("noteheads.")]
        main = Counter(q["size"] for q in g).most_common(1)[0][0]
        small = [(q["cx"], q["cy"]) for q in g if abs(q["size"] - main) >= 0.05]
        normal = [(q["cx"], q["cy"]) for q in g if abs(q["size"] - main) < 0.05]
    near = lambda l, pts: any(abs(px - l["x"]) <= 0.5 * sp and abs(py - l["y"]) <= 0.5 * sp for px, py in pts)
    rows = [dict(conf=l["confidence"], flags=l["flags"], size=s, chord=ch, grace=near(l, small),
                 normal=(st == "aoharu") or near(l, normal)) for l, (s, ch) in zip(L, sz)]
    return dict(set=st, page=name, n_ref=len(ref), ref=(float(np.median([w for w, _ in ref])), float(np.median([h for _, h in ref]))) if ref else None,
                rows=rows)


def flags(page, ref, lo=0.66, hi=0.80):
    if ref is None:
        return [False] * len(page["rows"])
    mw, mh = ref
    return [r["size"] is not None and not r["chord"] and lo <= r["size"][0] / mw <= hi and lo <= r["size"][1] / mh <= hi for r in page["rows"]]


def main():
    import measure_sim_ledger_pair as S
    import fitz
    jobs = [(st, n, p, pg, os.path.join(ROOT, "debug", "sim_lp", "chordmidprop", n + ".json")) for st, n, p, pg in S.pages()]
    D = os.path.join(ROOT, "inputs", "mutopia")
    for f in sorted(os.listdir(D)):
        for pg in range(len(fitz.open(os.path.join(D, f)))):
            jobs.append(("mutopia", f"{f[:-4]}_p{pg + 1}", os.path.relpath(os.path.join(D, f), ROOT), pg,
                         os.path.join(ROOT, "debug", "inputs_score", "mutopia", f"{f[:-4]}_p{pg + 1}.json")))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        P = list(ex.map(_job, jobs))
    json.dump(P, open(os.path.join(ROOT, "debug", "grace_fallback.json"), "w", encoding="utf-8"), ensure_ascii=False)
    dev = [p for p in P if p["set"] != "mutopia" and p["ref"] is not None and p["n_ref"] >= 50]
    ew, eh = float(np.median([p["ref"][0] for p in dev])), float(np.median([p["ref"][1] for p in dev]))
    print(f"49쪽 기준(화음 아닌 라벨 ≥ 50인 {len(dev)}쪽) 폭 " + " ".join(f"{q}%={np.percentile([p['ref'][0] for p in dev], q):.2f}" for q in (0, 5, 50, 95, 100))
          + " · 높이 " + " ".join(f"{q}%={np.percentile([p['ref'][1] for p in dev], q):.2f}" for q in (0, 5, 50, 95, 100)) + f" → 기대 {ew:.2f} × {eh:.2f}sp")
    for nmin, shrink in ((50, 0.85), (30, 0.85), (50, 0.80)):
        tot = Counter()
        for p in P:
            now = flags(p, p["ref"])
            bad_ref = p["ref"] is None or p["n_ref"] < nmin or p["ref"][0] < ew * shrink
            cand = flags(p, (ew, eh)) if bad_ref else now
            for r, a, b in zip(p["rows"], now, cand):
                if b and not a:
                    k = ("Mutopia " if p["set"] == "mutopia" else "49쪽 ") + ("꾸밈음" if r["grace"] else "정상 진짜 머리(헛표시)" if r["normal"] else "유령 · 기타")
                    tot[k + (" · 확실→" if r["conf"] == "certain" else " · ")] += 1
                if a and not b:
                    tot["표시 사라짐"] += 1
            tot["기준 대체 쪽 " + ("Mutopia" if p["set"] == "mutopia" else "49쪽")] += bad_ref
        print(f"  기준 대체(라벨 < {nmin} 또는 기준 폭 < 기대 × {shrink}): {dict(tot)}")
    mg = [r for p in P if p["set"] == "mutopia" for r in p["rows"] if r["grace"] and r["conf"] == "certain"]
    print("  (Mutopia 꾸밈음 자리 「확실」 라벨 전체", len(mg), ")")


if __name__ == "__main__":
    main()
