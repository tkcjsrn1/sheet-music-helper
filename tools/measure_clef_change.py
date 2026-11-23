# -*- coding: utf-8 -*-
"""(c) 보표 중간 음자리표 바뀜 — 바뀐 음자리표 글리프를 찾을 수 있는가(검출률 · 오검출). 제품 코드 무변경.

방법: 같은 쪽 보표 머리의 높은음 · 낮은음 음자리표를 본으로(**측정용 근사 — 본은 정답 상자에서 오린다**; 배포라면 머리 음자리표 검출 결과로 오려야 한다),
배율 0.55~1.0으로 오선 제거 영상과 정규화 상관(TM_CCOEFF_NORMED). 헤더 끝 뒤 · 그 보표 밴드 안 봉우리(가로 1.5sp 안 최댓값만).
정답: SVG 보표별 clefs 중 둘째부터(같은 x 중복 제거). 맞음 = 정답 x ±1sp · 같은 종류.

    python tools/measure_clef_change.py      → 문턱별 검출률 · 오검출, 바뀐 뒤 음표 수(효과 추정)
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
VRV = os.path.join(ROOT, "debug", "vrv")
SET = os.path.join(ROOT, "test_scores", "verovio")
SCALES = (0.55, 0.65, 0.75, 0.85, 1.0)


def _one(stem):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    t = json.load(open(os.path.join(VRV, "truth", stem + ".json"), encoding="utf-8"))
    res = preprocess(os.path.join(SET, stem + ".png"))
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves).astype(np.float32)
    boxes = [b["box"] for b in t["boxes"] if b["cls"] == "clef"]
    # 본: 정답 보표의 첫 음자리표(머리) 상자 — 종류별 첫 것
    tmpl = {}
    for s in t["staves"]:
        if not s["clefs"]:
            continue
        c0 = s["clefs"][0]
        if c0["val"] in tmpl or c0["val"] not in ("treble", "bass"):
            continue
        bx = [b for b in boxes if abs(b[0] - c0["x"]) < 15 and b[1] <= s["line_ys"][2] <= b[3]]
        if bx:
            x0, y0, x1, y1 = (int(round(v)) for v in bx[0])
            tmpl[c0["val"]] = ns[y0:y1 + 1, x0:x1 + 1]
    truth = set()
    for si, s in enumerate(t["staves"]):
        for k, c in enumerate(s["clefs"]):
            if k >= 1 and c["val"] in ("treble", "bass"):
                truth.add((si, round(c["x"]), c["val"]))
    cands = []
    for st in res.staves:
        sp = st.spacing
        si = min(range(len(t["staves"])), key=lambda i: abs(t["staves"][i]["line_ys"][0] - st.top))
        hdr = ctx[st.index].header_end if st.index in ctx else 0
        y0, y1 = max(0, int(st.top - 3 * sp)), int(st.bottom + 3 * sp)
        band = ns[y0:y1, :]
        for kind, tp in tmpl.items():
            for sc in SCALES:
                tt = cv2.resize(tp, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
                if tt.shape[0] >= band.shape[0] or tt.shape[1] < 3 or tt.std() == 0:
                    continue
                m = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED)
                prof = m.max(axis=0)
                xs = np.arange(len(prof))
                for x in xs[prof > 0.45]:
                    cx = x
                    if cx < hdr:
                        continue
                    w = int(1.5 * sp)
                    if prof[x] < prof[max(0, x - w):x + w + 1].max():
                        continue
                    cands.append(dict(si=si, x=int(cx), kind=kind, sc=sc, score=float(prof[x]), sp=sp))
    # 같은 자리 여러 배율 · 종류 → 최고 점수 하나
    best = {}
    for c in cands:
        k = (c["si"], round(c["x"] / (1.5 * c["sp"])))
        if k not in best or c["score"] > best[k]["score"]:
            best[k] = c
    return stem, sorted(truth), list(best.values())


def main():
    stems = sorted(f[:-4] for f in os.listdir(SET) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one, stems))
    json.dump(res, open(os.path.join(VRV, "clef_change.json"), "w", encoding="utf-8"), ensure_ascii=False)
    n_truth = sum(len(t) for _s, t, _c in res)
    print("정답 바뀐 음자리표", n_truth)
    for thr in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8):
        tp = fp = 0
        hit = set()
        for stem, truth, cands in res:
            for c in cands:
                if c["score"] < thr:
                    continue
                m = [tr for tr in truth if tr[0] == c["si"] and abs(tr[1] - c["x"]) <= c["sp"] * 1.0 and tr[2] == c["kind"]]
                if m:
                    tp += 1
                    hit.update((stem,) + tuple(x) for x in m)
                else:
                    fp += 1
        print(f"  점수 ≥ {thr}: 검출 {len(hit)}/{n_truth} ({len(hit) / max(1, n_truth) * 100:.0f}%) · 오검출 {fp}")


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


def _one_pdf(job):
    """PDF(LilyPond) — 정답 = clefs.*_change 글리프(보표 중간 · 줄 끝 예고 음자리표), 본 = 그 쪽 머리 clefs.G · clefs.F 글리프 상자."""
    import measure_omission_rate as M
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves).astype(np.float32)
    g = M.pdf_glyphs(path, pg, ("clefs.",))
    kind = lambda n: "treble" if n.split(".")[1].startswith("G") else "bass" if n.split(".")[1].startswith("F") else None
    tmpl = {}
    for q in g:
        if "_change" in q["name"] or kind(q["name"]) in tmpl or kind(q["name"]) is None:
            continue
        x0, y0 = int(q["cx"] - q["w"] / 2), int(q["cy"] - q["h"] / 2)
        tmpl[kind(q["name"])] = ns[y0:int(y0 + q["h"]) + 1, x0:int(x0 + q["w"]) + 1]
    staff_of = lambda y: min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))
    truth = sorted({(staff_of(q["cy"]).index, round(q["cx"] - q["w"] / 2), kind(q["name"])) for q in g if "_change" in q["name"]})
    cands = []
    for st in res.staves:
        sp = st.spacing
        hdr = ctx[st.index].header_end if st.index in ctx else 0
        y0, y1 = max(0, int(st.top - 3 * sp)), int(st.bottom + 3 * sp)
        band = ns[y0:y1, :]
        for k, tp in tmpl.items():
            for sc in SCALES:
                tt = cv2.resize(tp, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
                if tt.shape[0] >= band.shape[0] or tt.shape[1] < 3 or tt.std() == 0:
                    continue
                prof = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED).max(axis=0)
                w = int(1.5 * sp)
                for x in np.where(prof > 0.45)[0]:
                    if x < hdr or prof[x] < prof[max(0, x - w):x + w + 1].max():
                        continue
                    cands.append(dict(si=st.index, x=int(x), kind=k, sc=sc, score=float(prof[x]), sp=sp))
    best = {}
    for c in cands:
        kk = (c["si"], round(c["x"] / (1.5 * c["sp"])))
        if kk not in best or c["score"] > best[kk]["score"]:
            best[kk] = c
    return name, truth, list(best.values())


def main_pdf():
    import check_accidental_fix as C
    U = "output/unseen-scores-20260829/sources/"
    jobs = [j for j in C.PAGES if j[1].endswith(".pdf")] + [(f"moon{p + 1}", U + "moonlight-a4.pdf", p) for p in (0, 1, 10, 17)] \
        + [(f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p) for p in range(4)]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one_pdf, jobs))
    n_truth = sum(len(t) for _s, t, _c in res)
    print("PDF · 보지 않은 악보 정답 바뀐 음자리표", n_truth, [(s, t) for s, t, _c in res if t])
    for thr in (0.5, 0.6, 0.7, 0.75, 0.8):
        hit, fp, fps = set(), 0, []
        for stem, truth, cands in res:
            for c in cands:
                if c["score"] < thr:
                    continue
                m = [tr for tr in truth if tr[0] == c["si"] and abs(tr[1] - c["x"]) <= c["sp"] and tr[2] == c["kind"]]
                if m:
                    hit.update((stem,) + tuple(x) for x in m)
                else:
                    fp += 1
                    fps.append((stem, c["si"], c["x"], c["kind"], round(c["score"], 2)))
        print(f"  점수 ≥ {thr}: 검출 {len(hit)}/{n_truth} · 오검출 {fp}", fps[:6] if thr >= 0.7 else "")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "pdf":
    main_pdf()
