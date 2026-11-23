# -*- coding: utf-8 -*-
"""(큐 6) D♭ 3~4쪽 인쇄된 ♯ 오독 원인 — 측정만 (2026-10-13). 보류 세트 미사용.

인쇄된 ♯ 글리프(PDF `accidentals.sharp`)마다 그 오른쪽 같은 높이(±0.35sp)의 가장 가까운 정답 머리 → 그 머리 라벨의 원시 임시표(`accidental`, 전파 전 인쇄 판독).
값: 글리프 크기(pt · 높이 sp) · 머리까지 가로 거리(글리프 오른끝 → 머리 중심, sp) · 세로 어긋남(글리프 중심 − 머리, sp) · 그 사이 다른 임시표 글리프 유무.
PDF 17쪽 전부를 대조군으로 같이 잰다.

    python tools/measure_db_sharp.py
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def main():
    import check_accidental_fix as C
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    rows = []
    for nm, path, pg in C.PAGES:
        if not path.endswith(".pdf"):
            continue
        g = M.pdf_glyphs(path, pg, ("accidentals.",))
        heads = truth_at(path, pg, 1.0)[0]
        L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "beamgap1012", nm + ".json"), encoding="utf-8"))["labels"]
        sp = float(np.median([s["spacing"] for s in json.load(open(os.path.join(ROOT, "debug", "sim_lp", "beamgap1012", nm + ".json"), encoding="utf-8"))["staves"]]))
        for q in g:
            if q["name"] != "accidentals.sharp":
                continue
            right = q["cx"] + q["w"] / 2
            cand = [h for h in heads if 0 < h["cx"] - right <= 3.0 * sp and abs(h["cy"] - q["cy"]) <= 0.35 * sp]
            if not cand:
                continue
            h = min(cand, key=lambda h: h["cx"] - right)
            lab = [l for l in L if abs(l["x"] - h["cx"]) <= 0.7 * sp and abs(l["y"] - h["cy"]) <= 0.5 * sp]
            between = [o for o in g if o is not q and right < o["cx"] < h["cx"] and abs(o["cy"] - q["cy"]) <= 2 * sp]
            rows.append(dict(page=nm, gx=round(q["cx"]), gy=round(q["cy"]), hx=round(h["cx"]), hy=round(h["cy"]),
                             size=q["size"], h_sp=round(q["h"] / sp, 2), w_sp=round(q["w"] / sp, 2),
                             dx=round((h["cx"] - right) / sp, 2), dy=round((q["cy"] - h["cy"]) / sp, 2), between=len(between),
                             read=(lab[0]["accidental"] or "-") if lab else "(라벨 없음)"))
    json.dump(rows, open(os.path.join(ROOT, "debug", "db_sharp.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for grp, f in (("D♭ 3 · 4쪽", lambda r: r["page"] in ("db3", "db4")), ("그 밖 PDF", lambda r: r["page"] not in ("db3", "db4"))):
        v = [r for r in rows if f(r)]
        print(f"[{grp}] 인쇄 ♯ {len(v)} · 읽음 {dict(Counter(r['read'] for r in v))}")
        for ok in (True, False):
            u = [r for r in v if (r["read"] == "#") == ok]
            if not u:
                continue
            print(f"   {'바르게 읽음' if ok else '틀리게 읽음'} {len(u)}: 크기 pt {dict(Counter(r['size'] for r in u))}"
                  + " · ".join(f" | {k} " + " ".join(f"{p}%={np.percentile([r[k] for r in u], p):.2f}" for p in (0, 50, 100)) for k in ("h_sp", "dx", "dy"))
                  + f" | 사이 글리프 있음 {sum(r['between'] > 0 for r in u)}")
    for r in rows:
        if r["page"] in ("db3", "db4") and r["read"] != "#":
            print("   틀림", r)


if __name__ == "__main__":
    main()
