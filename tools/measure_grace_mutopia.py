# -*- coding: utf-8 -*-
"""(아침 5) Mutopia 꾸밈음이 「확실」로 나온 이유 — `verify.grace_size_suspects`와 같은 계산의 실측값 (2026-10-13 · 측정만).

정답 꾸밈음 = PDF 머리 글리프 중 그 쪽 주 크기와 다른 크기(작은 글리프). 그 자리 라벨마다 같은 계산:
오선 제거 → 타원(0.5sp) 열림 → 그 자리 성분 폭 · 높이 / 그 쪽 「화음 아닌」 라벨 성분 중앙값 = 크기 비. 문턱 GRACE_RATIO(0.66~0.80) · 「화음 아님」(같은 보표 0.6sp 안 x에 다른 라벨 없음).

    python tools/measure_grace_mutopia.py
"""
import json, os, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def main():
    import cv2, fitz
    import measure_omission_rate as M
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules.verify import GRACE_RATIO
    D = os.path.join(ROOT, "inputs", "mutopia")
    rows = []
    for f in sorted(os.listdir(D)):
        path = os.path.join(D, f)
        for pg in range(len(fitz.open(path))):
            g = [q for q in M.pdf_glyphs(os.path.relpath(path, ROOT), pg) if q["name"].startswith("noteheads.")]
            main_size = Counter(q["size"] for q in g).most_common(1)[0][0]
            small = [q for q in g if abs(q["size"] - main_size) >= 0.05]
            js = os.path.join(ROOT, "debug", "inputs_score", "mutopia", f"{f[:-4]}_p{pg + 1}.json")
            L = json.load(open(js, encoding="utf-8"))["labels"]
            res = preprocess(path, pdf_page=pg)
            ns = remove_staff_lines(res.binary, res.staves)
            sp = float(np.median([s.spacing for s in res.staves]))
            k = max(3, int(0.5 * sp)) | 1
            op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            _n, lab, st, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
            H, W = lab.shape

            def size(l):
                y, x = min(H - 1, max(0, int(l["y"]))), min(W - 1, max(0, int(l["x"])))
                c = lab[y, x]
                if not c:
                    win = lab[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
                    nz = win[win > 0]
                    c = int(np.bincount(nz).argmax()) if nz.size else 0
                return (st[c, cv2.CC_STAT_WIDTH] / sp, st[c, cv2.CC_STAT_HEIGHT] / sp) if c else None
            sizes = [size(l) for l in L]
            chord = [any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 0.6 * sp for o in L) for l in L]
            ref = [s for s, ch in zip(sizes, chord) if s is not None and not ch]
            mw, mh = float(np.median([w for w, _h in ref])), float(np.median([h for _w, h in ref]))
            print(f"{f[:-4]}_p{pg + 1} 기준 성분 폭 · 높이 {mw:.2f} · {mh:.2f}sp (화음 아닌 라벨 {len(ref)}) · 꾸밈음 성분", sorted({(round(s[0], 2), round(s[1], 2)) for l, s in zip(L, sizes) if s and any(abs(q["cx"] - l["x"]) <= 0.5 * sp and abs(q["cy"] - l["y"]) <= 0.5 * sp for q in small)})[:6])
            for l, s, ch in zip(L, sizes, chord):
                if not any(abs(q["cx"] - l["x"]) <= 0.5 * sp and abs(q["cy"] - l["y"]) <= 0.5 * sp for q in small):
                    continue
                rw, rh = (s[0] / mw, s[1] / mh) if s else (None, None)
                why = ("성분 없음" if s is None else "화음으로 봄(0.6sp 안 x에 다른 라벨)" if ch else
                       "크기 비 범위 밖" if not (GRACE_RATIO[0] <= rw <= GRACE_RATIO[1] and GRACE_RATIO[0] <= rh <= GRACE_RATIO[1]) else "걸림")
                rows.append(dict(page=f"{f[:-4]}_p{pg + 1}", x=l["x"], y=l["y"], conf=l["confidence"], flags=l["flags"],
                                 rw=None if rw is None else round(rw, 2), rh=None if rh is None else round(rh, 2), why=why,
                                 glyph_ratio=round(small[0]["size"] / main_size, 2)))
    json.dump(rows, open(os.path.join(ROOT, "debug", "grace_mutopia.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("꾸밈음 자리 라벨", len(rows), "· 확신도", dict(Counter(r["conf"] for r in rows)), "· 이유", dict(Counter(r["why"] for r in rows)))
    print("글꼴 크기 비(작은/주)", dict(Counter(r["glyph_ratio"] for r in rows)))
    for k in ("rw", "rh"):
        v = [r[k] for r in rows if r[k] is not None]
        print(f"  {k}: " + " · ".join(f"{p}%={np.percentile(v, p):.2f}" for p in (0, 5, 50, 95, 100)), "| 문턱", GRACE_RATIO)
    print("범위 밖 중 폭 · 높이", Counter((r["rw"] > GRACE_RATIO[1] or r["rw"] < GRACE_RATIO[0], r["rh"] > GRACE_RATIO[1] or r["rh"] < GRACE_RATIO[0]) for r in rows if r["why"] == "크기 비 범위 밖"))


if __name__ == "__main__":
    main()
