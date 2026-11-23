# -*- coding: utf-8 -*-
"""[3] 꾸밈음(작은 머리) → check 표시안 — 머리 크기 분포 · 문턱 유도 · 시뮬레이션. 제품 코드 무변경.

라벨 자리 머리 크기: 오선 제거 → 타원(0.5sp) 열림 → 라벨 중심을 품은 8연결 성분의 폭 · 높이(sp). 쪽마다 「정상 머리로 짝지어진 라벨」의 중앙값으로 나눈 비(폭 비 · 높이 비).
정답: PDF · 보지 않은 악보 = PDF 글리프 머리 크기(그 쪽 주 크기와 다르면 꾸밈음), Verovio = SVG `grace` · `cue`. 라벨 = 현재 main(`debug/sim_lp/cglyph`).
분류: 꾸밈음 / 정상 머리(단독) / 정상 머리(화음 — 같은 보표 0.6sp 안 x에 다른 라벨) / 유령. 덩어리가 열림 뒤 사라진 라벨(성분 없음)은 따로.
사진: 원본 PDF 정답을 정렬로 잇기 어려워(작은 머리 정답이 없음) 사진은 「걸리는 라벨 수」만 센다.

    python tools/measure_grace_size.py
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


def sizes(res, labels):
    from modules.notehead_detect import remove_staff_lines
    ns = remove_staff_lines(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in res.staves}
    sp0 = float(np.median(list(sp_of.values())))
    k = max(3, int(0.5 * sp0)) | 1
    op = cv2.morphologyEx(ns, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lab, stats, _c = cv2.connectedComponentsWithStats((op > 0).astype(np.uint8), connectivity=8)
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
        out.append((stats[c, cv2.CC_STAT_WIDTH] / sp, stats[c, cv2.CC_STAT_HEIGHT] / sp) if c else (None, None))
    return out


def _page(job):
    from modules.preprocess import preprocess
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "cglyph", name + ".json"), encoding="utf-8"))["labels"]
    sz = sizes(res, L)
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads = [(n["x"], n["y"], bool(n.get("grace") or n.get("cue"))) for n in t["notes"]]
        sp = 18.0
    else:
        import measure_omission_rate as M
        g = M.pdf_glyphs(path, pg, ("noteheads.",))
        main = Counter(round(q["size"], 2) for q in g).most_common(1)[0][0] if g else 0
        heads = [(q["cx"], q["cy"], abs(q["size"] - main) >= 0.05) for q in g]
        sp = float(np.median([s.spacing for s in res.staves]))
    rows = []
    for l, (w, h) in zip(L, sz):
        m = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
        chord = any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 0.6 * sp for o in L)
        kind = "유령" if not m else "꾸밈음" if m[0][2] else ("정상(화음)" if chord else "정상(단독)")
        rows.append(dict(set=st, page=name, kind=kind, w=w, h=h, conf=l["confidence"], chord=chord))
    ref = [r for r in rows if r["kind"].startswith("정상") and r["w"] is not None]
    mw = float(np.median([r["w"] for r in ref])) if ref else 1.0
    mh = float(np.median([r["h"] for r in ref])) if ref else 1.0
    for r in rows:
        r["rw"] = None if r["w"] is None else round(r["w"] / mw, 2)
        r["rh"] = None if r["h"] is None else round(r["h"] / mh, 2)
    return rows


def _photo(job):
    from modules.preprocess import preprocess
    name, path = job
    js = os.path.join(ROOT, "debug", "a17_cand1_photo_main1004", "base_photo", name + ".json")
    if not os.path.exists(js):
        return name, None
    res = preprocess(os.path.join(ROOT, path), photo=True)
    L = json.load(open(js, encoding="utf-8"))["labels"]
    sz = sizes(res, L)
    ok = [(w, h) for w, h in sz if w is not None]
    if not ok:
        return name, 0
    mw, mh = float(np.median([w for w, _h in ok])), float(np.median([h for _w, h in ok]))
    sp = float(np.median([s.spacing for s in res.staves]))
    n = 0
    for l, (w, h) in zip(L, sz):
        chord = any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 0.6 * sp for o in L)
        if w is not None and 0.66 <= w / mw <= 0.80 and 0.66 <= h / mh <= 0.80 and not chord:
            n += 1
    return name, n


def photo_main():
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_photo, [(n, p) for n, p, _pg in G.photo_pages()]))
    v = [n for _k, n in res if n is not None]
    print(f"사진 {len(v)}장 · 띠 0.66~0.80 · 화음 아님에 걸린 라벨 합 {sum(v)} · 장당 중앙 {np.median(v):.0f} · 최대 {max(v)}")
    by = {}
    for k, n in res:
        if n is not None:
            by.setdefault(k.split("__")[0], []).append(n)
    print({k: sum(x) for k, x in by.items()})


def main():
    import measure_sim_ledger_pair as S
    jobs = [p for p in S.pages() if p[0] != "aoharu" and p[1] != "organ2"]
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_page, jobs) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "grace_size.json"), "w", encoding="utf-8"), ensure_ascii=False)
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (1, 5, 50, 95, 99)) if len(a) else "-"
    for kind in ("꾸밈음", "정상(단독)", "정상(화음)", "유령"):
        v = [r for r in rows if r["kind"] == kind and r["rw"] is not None]
        print(f"{kind:7s} {len(v):6d} | 폭 비 1 · 5 · 50 · 95 · 99% {pct([r['rw'] for r in v])} | 높이 비 {pct([r['rh'] for r in v])}"
              f" | 덩어리 없음 {sum(1 for r in rows if r['kind'] == kind and r['rw'] is None)}")
    G = sum(r["kind"] == "꾸밈음" for r in rows)
    for lo, hi in ((0.66, 0.80), (0.68, 0.78)):
        for nochord in (False, True):
            f = lambda r: r["rw"] is not None and lo <= r["rw"] <= hi and lo <= r["rh"] <= hi and not (nochord and r["chord"])
            c = Counter(r["kind"] for r in rows if f(r))
            n = sum(c.values())
            print(f"  [띠] 폭 · 높이 비 {lo}~{hi}" + (" · 화음 아님(제품이 아는 기준)" if nochord else "") + f": 걸림 {n} = " + " · ".join(f"{k} {v}" for k, v in c.most_common())
                  + f" | 정밀도 {100 * c['꾸밈음'] / max(1, n):.0f}% · 꾸밈음 잡음 {c['꾸밈음']}/{G} | 확실 등급 정상 머리 헛표시 {sum(1 for r in rows if f(r) and r['kind'].startswith('정상') and r['conf'] == 'certain')}")
    for tw in (0.6, 0.7, 0.75, 0.8):
        for th in (0.7, 0.8, 0.85):
            f = lambda r: r["rw"] is not None and r["rw"] <= tw and r["rh"] <= th
            c = Counter(r["kind"] for r in rows if f(r))
            print(f"  폭 비 ≤ {tw} · 높이 비 ≤ {th}: 걸림 {sum(c.values())} = " + " · ".join(f"{k} {n}" for k, n in c.most_common())
                  + f" | 꾸밈음 잡음 {c['꾸밈음']}/{sum(r['kind'] == '꾸밈음' for r in rows)}")


if __name__ == "__main__":
    photo_main() if sys.argv[1:] == ["photo"] else main()
