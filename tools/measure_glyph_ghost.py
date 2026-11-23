# -*- coding: utf-8 -*-
"""[3](a) 임시표 글리프가 음표로 잡히는 문제 — 유형 세기 + 글리프 모양으로 가를 수 있나. 제품 코드 무변경.

유형: 「글리프 자리 유령」 = 정답 머리와 짝 없는 라벨(가로 0.7sp · 세로 0.5sp)이 정답 임시표 글리프 상자(±0.3sp) 안,
      「주인 표기 누락」 = 그 글리프의 주인 머리(Verovio `acc_box` 주인 / PDF 글리프 오른쪽 3sp 안 같은 높이 ±0.5sp 가장 가까운 머리)의 라벨 표기에 그 임시표가 없음.
모양: 라벨 중심에서 좌(x − 0.75 ~ − 0.2sp) · 우(+ 0.2 ~ + 0.75sp) 칸의 열마다, 머리 중심 행 ± 0.3sp에서 위 · 아래로 끊김 없이 이어진 잉크 길이(오선 제거 영상, sp)의 최댓값
      LU · LD · RU · RD. 기보 규칙: 머리 기둥은 오른쪽 위(RU) 또는 왼쪽 아래(LD)로 뻗는다. ♭은 왼쪽 위(LU), ♯은 넷 다, ♮은 LU · RD.
라벨: 현재 main 제품(Verovio `debug/vrv_clefflag/base`, PDF · 보지 않은 `debug/a17_cand1_clefflag/base_*`). Aoharu는 글리프 정답이 없어 빠진다(정답 골든 711과 일치 = 이 유형 0).

    python tools/measure_glyph_ghost.py
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
SIGN = {"#": "#", "b": "b", "natural": ""}


def runs(ns, x, y, sp):
    H, W = ns.shape
    out = {}
    for side, (a, b) in (("L", (-0.75, -0.2)), ("R", (0.2, 0.75))):
        cols = range(max(0, int(x + a * sp)), min(W, int(x + b * sp) + 1))
        for d, step in (("U", -1), ("D", 1)):
            best = 0
            for c in cols:
                r = int(y + step * 0.3 * sp)
                n = 0
                while 0 <= r < H and ns[r, c]:
                    n += 1
                    r += step
                best = max(best, n)
            out[side + d] = round(best / sp, 2)
    return out


def _page(job):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg, lab = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ns = remove_staff_lines(res.binary, res.staves) > 0
    sp_of = {s.index: s.spacing for s in res.staves}
    L = json.load(open(lab, encoding="utf-8"))["labels"]
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        heads = [(n["x"], n["y"]) for n in t["notes"]]
        glyphs = []      # (x0, y0, x1, y1, 종류, 주인 머리 번호)
        for i, n in enumerate(t["notes"]):
            if n.get("acc_box") and n.get("accidental") in ("#", "b", "natural"):
                x0, y0, x1, y1 = n["acc_box"]
                if x1 - x0 > 2:
                    glyphs.append((x0, y0, x1, y1, n["accidental"], i))
    else:
        import measure_omission_rate as M
        from measure_normalize_sp import truth_at
        hs = truth_at(path, pg, 1.0)[0]
        heads = [(h["cx"], h["cy"]) for h in hs]
        sp0 = float(np.median(list(sp_of.values())))
        glyphs = []
        for q in M.pdf_glyphs(path, pg, ("accidentals.",)):
            k = {"sharp": "#", "flat": "b", "natural": "natural"}.get(q["name"].split(".")[1].split("_")[0].replace("arrow", ""))
            if k is None:
                continue
            x0, y0 = q["cx"] - q["w"] / 2, q["cy"] - q["h"] / 2
            gy = q["cy"] + (0.5 * sp0 if k == "b" else 0)      # ♭ 머리 자리는 글리프 중심보다 아래
            own = [(h[0] - (x0 + q["w"]), j) for j, h in enumerate(heads) if 0 < h[0] - (x0 + q["w"]) <= 3 * sp0 and abs(h[1] - gy) <= 0.5 * sp0]
            glyphs.append((x0, y0, x0 + q["w"], y0 + q["h"], k, min(own)[1] if own else None))
    rows = []
    for l in L:
        sp = sp_of.get(l["staff"], 18.0)
        real = any(abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp for h in heads)
        at = [g for g in glyphs if g[0] - 0.3 * sp <= l["x"] <= g[2] + 0.3 * sp and g[1] - 0.3 * sp <= l["y"] <= g[3] + 0.3 * sp]
        if real or at:
            rows.append(dict(set=kind, page=name, x=l["x"], y=l["y"], text=l["text"], conf=l["confidence"],
                             real=real, glyph=(at[0][4] if at and not real else None), **runs(ns, l["x"], l["y"], sp)))
    owners = []
    for x0, y0, x1, y1, k, oi in glyphs:
        if oi is None:
            continue
        hx, hy = heads[oi]
        sp = 18.0 if kind == "verovio" else float(np.median(list(sp_of.values())))
        ol = [l for l in L if abs(l["x"] - hx) <= 0.7 * sp and abs(l["y"] - hy) <= 0.5 * sp]
        ghost = any(not any(abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp for h in heads)
                    and x0 - 0.3 * sp <= l["x"] <= x1 + 0.3 * sp and y0 - 0.3 * sp <= l["y"] <= y1 + 0.3 * sp for l in L)
        miss = bool(ol) and not ((SIGN[k] and ol[0]["text"].endswith(SIGN[k])) or (not SIGN[k] and not ol[0]["text"].endswith(("#", "b"))))
        owners.append(dict(set=kind, page=name, kind=k, ghost=ghost, miss=miss, lost=not ol))
    return rows, owners


def main():
    import check_accidental_fix as C
    jobs = [("pdf", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    U = "output/unseen-scores-20260829/sources/"
    jobs += [("unseen", f"moon{p + 1}", U + "moonlight-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_unseen", f"moon{p + 1}.json")) for p in (0, 1, 10, 17)]
    jobs += [("unseen", f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_unseen", f"rain{p + 1}.json")) for p in range(4)]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0, os.path.join(ROOT, "debug", "vrv_clefflag", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    rows = [r for a, _b in res for r in a]
    owners = [o for _a, b in res for o in b]
    json.dump(dict(rows=rows, owners=owners), open(os.path.join(ROOT, "debug", "glyph_ghost.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st in ("pdf", "unseen", "verovio"):
        o = [x for x in owners if x["set"] == st]
        g = [r for r in rows if r["set"] == st and r["glyph"]]
        print(f"{st}: 글리프 {len(o)} · 글리프 자리 유령 라벨 {len(g)} {dict(Counter(r['glyph'] for r in g))} (확실 {sum(r['conf'] == 'certain' for r in g)})"
              f" | 주인 표기 누락 {sum(x['miss'] for x in o)} · 유령+누락 동시 {sum(x['miss'] and x['ghost'] for x in o)} · 주인 라벨 없음 {sum(x['lost'] for x in o)}")
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (5, 50, 95)) if len(a) else "-"
    for grp, f in (("진짜 머리", lambda r: r["real"]), ("♭ 유령", lambda r: r["glyph"] == "b"), ("♯ 유령", lambda r: r["glyph"] == "#"),
                   ("♮ 유령", lambda r: r["glyph"] == "natural")):
        v = [r for r in rows if f(r)]
        print(f"{grp:6s} {len(v):5d} | " + " | ".join(f"{k} 5·50·95% {pct([r[k] for r in v])}" for k in ("LU", "LD", "RU", "RD")))


if __name__ == "__main__":
    main()
