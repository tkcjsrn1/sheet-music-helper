# -*- coding: utf-8 -*-
"""[3] 보표 중간 음자리표 글리프 상자 안의 라벨 — 유령 / 진짜 머리, 확신도 분포, 표시안 · 삭제안의 오삭제. 제품 코드 무변경.

글리프 상자: 제품 `clef_keysig.clef_change_regions`와 같은 본 · 배율 · 문턱(`CLEF_CHANGE_SCORE`)으로 보표 몸통에서 걸린 음자리표(바뀜 · 되돌아옴 모두)의
「matchTemplate 최고 자리(x, y) ~ + 본 폭 × 배율 · 본 높이 × 배율」. 망가진 본 거르기(재표기 > 1)도 제품과 같게.
라벨 = 현재 main 제품(`debug/sim_lp/ucheck`). 정답: Verovio SVG 머리, PDF · 보지 않은 악보 = PDF 글리프 머리(오르간 2쪽은 정답 좌표 불일치로 뺌).

    python tools/measure_clef_glyph_labels.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def boxes(res, contexts):
    import cv2
    import modules.clef_keysig as CK
    from modules.notehead_detect import remove_staff_lines
    ns = remove_staff_lines(res.binary, res.staves).astype(np.float32)
    H = ns.shape[0]
    tmpl = {}
    for st in sorted(res.staves, key=lambda s: s.top):
        c = contexts.get(st.index)
        if c is None or not c.clef_found or c.clef in tmpl or c.clef_end <= c.clef_start:
            continue
        win = ns[max(0, int(st.top - 1.5 * st.spacing)):min(H, int(st.bottom + 1.5 * st.spacing) + 1), c.clef_start:c.clef_end]
        rows, cols = np.where(win.any(axis=1))[0], np.where(win.any(axis=0))[0]
        if len(rows) and len(cols):
            tmpl[c.clef] = win[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    out = []
    hits_of = {}
    for st in res.staves:
        c = contexts.get(st.index)
        if c is None:
            continue
        sp = st.spacing
        y0 = max(0, int(st.top - 3 * sp))
        band = ns[y0:min(H, int(st.bottom + 3 * sp)), :]
        w = max(1, int(1.5 * sp))
        best = {}
        for kind, tp in tmpl.items():
            for sc in CK.CLEF_CHANGE_SCALES:
                tt = cv2.resize(tp, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
                if tt.shape[0] >= band.shape[0] or tt.shape[1] < 3 or tt.std() == 0:
                    continue
                m = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED)
                prof = m.max(axis=0)
                for x in np.where(prof >= CK.CLEF_CHANGE_SCORE)[0]:
                    if x < c.header_end or prof[x] < prof[max(0, x - w):x + w + 1].max():
                        continue
                    k = int(round(x / w))
                    if k not in best or prof[x] > best[k][0]:
                        best[k] = (float(prof[x]), int(x), kind, y0 + int(m[:, x].argmax()), tt.shape[1], tt.shape[0])
        hits_of[st.index] = sorted(best.values(), key=lambda t: t[1])
    bad = set()
    for si, hs in hits_of.items():
        n = 0
        for h in hs:
            if h[2] != contexts[si].clef:
                break
            n += 1
        if n > CK.CLEF_REPRINT_MAX:
            bad.add(contexts[si].clef)
    for si, hs in hits_of.items():
        if contexts[si].clef in bad or contexts[si].clef not in tmpl:
            continue
        for _s, x, kind, y, bw, bh in hs:
            if kind in bad:
                continue
            out.append((si, x, y, x + bw, y + bh, kind))
    return out


def _page(job):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    st, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    bx = boxes(res, ctx)
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "ucheck", name + ".json"), encoding="utf-8"))["labels"]
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads, sp = [(n["x"], n["y"]) for n in t["notes"]], 18.0
    else:
        from measure_normalize_sp import truth_at
        heads = [(h["cx"], h["cy"]) for h in truth_at(path, pg, 1.0)[0]]
        sp = float(np.median([s.spacing for s in res.staves]))
    rows = []
    for l in L:
        inb = [b for b in bx if b[0] == l["staff"] and b[1] <= l["x"] <= b[3] and b[2] <= l["y"] <= b[4]]
        if not inb:
            continue
        real = any(abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp for h in heads)
        rows.append(dict(set=st, page=name, x=l["x"], y=l["y"], text=l["text"], conf=l["confidence"], real=real))
    return st, len(bx), rows


def main():
    import measure_sim_ledger_pair as S
    jobs = [p for p in S.pages() if p[0] != "aoharu" and p[1] != "organ2"]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    rows = [r for _s, _n, rs in res for r in rs]
    json.dump(rows, open(os.path.join(ROOT, "debug", "clef_glyph_labels.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st in ("pdf", "unseen", "verovio"):
        v = [r for r in rows if r["set"] == st]
        nb = sum(n for s, n, _r in res if s == st)
        print(f"{st}: 글리프 상자 {nb} · 상자 안 라벨 {len(v)} | 유령 {sum(not r['real'] for r in v)} · 진짜 머리 {sum(r['real'] for r in v)}"
              f" | 확신도 {dict(Counter(r['conf'] for r in v))} · 유령의 확신도 {dict(Counter(r['conf'] for r in v if not r['real']))}")
    real = [r for r in rows if r["real"]]
    print(f"표시안(check) 오삭제 0(지우지 않음) · 진짜 머리 헛표시 {len(real)} · 그중 지금 확실 {sum(r['conf'] == 'certain' for r in real)}")
    print(f"삭제안 오삭제 {len(real)}", [(r["page"], r["x"], r["y"], r["text"]) for r in real][:12])


if __name__ == "__main__":
    main()
