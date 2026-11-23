# -*- coding: utf-8 -*-
"""(큐 4) 줄기 반대편(2도로 밀린) 머리 누락 중 「각자 x」(#319)가 못 되찾는 117의 원인 분해 — 측정만 (2026-10-13 · 보류 세트 미사용).

입력 `debug/stem_side_remaining.json`(chord_types 행 중 #319 라벨로도 안 잡히는 줄기 반대편 머리).
「같은 높이 바로 옆의 중복」(dx 0.6~1.3sp · |dy| ≤ 0.35sp → 증거 약한 쪽 삭제)으로 지워진 것: 지워진 후보와 남은 짝의 검출 y차 vs 정답 y차, 후보 y 오차.
「모양 판정」: 정답 머리를 품은 열림 덩어리(제품 `_detect_noteheads_in_band`와 같은 타원 열림 · 세로 메움 뒤) 폭 · 높이 · 덩어리 안 정답 머리 수.

    python tools/measure_stem_side.py
"""
import json, os, sys
from collections import Counter, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def _page(job):
    page, rows = job
    import measure_chord_miss as C
    P = {n: (st, p, pg) for st, n, p, pg in C.pages()}
    st, path, pg = P[page]
    stg, _bin = C._stages(path, pg)
    T = C.truth(st, page, path, pg)
    sp = rows[0]["sp"] if "sp" in rows[0] else 18.0
    out = []
    for r in rows:
        x, y = r["x"], r["y"]
        o = dict(page=page, set=st, x=x, y=y, stage=r["stage"])
        if "옆의 중복" in r["stage"]:
            cand = min((c for c in stg["base_rej"] if "옆의 중복" in c[2]), key=lambda c: abs(c[0] - x) + abs(c[1] - y))
            part = [d for d in stg["base_det"] if 0.6 * sp <= abs(d[0] - cand[0]) <= 1.3 * sp and abs(d[1] - cand[1]) <= 0.35 * sp]
            if part:
                p = min(part, key=lambda d: abs(d[0] - cand[0]))
                tp = min(T, key=lambda t: abs(t[0] - p[0]) + abs(t[1] - p[1]))
                o.update(det_dy=round(abs(cand[1] - p[1]) / sp, 2), truth_dy=round(abs(y - tp[1]) / sp, 2),
                         cand_err=round((cand[1] - y) / sp, 2), part_err=round((p[1] - tp[1]) / sp, 2), dx=round(abs(cand[0] - p[0]) / sp, 2))
        out.append(o)
    return out


def main():
    rem = json.load(open(os.path.join(ROOT, "debug", "stem_side_remaining.json"), encoding="utf-8"))
    spm = {r["page"]: r["sp"] for r in json.load(open(os.path.join(ROOT, "debug", "chord_miss.json"), encoding="utf-8"))}
    by = defaultdict(list)
    for r in rem:
        r["sp"] = spm[r["page"]]
        by[r["page"]].append(r)
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = [o for part in ex.map(_page, list(by.items())) for o in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "stem_side.json"), "w", encoding="utf-8"), ensure_ascii=False)
    d = [o for o in R if "det_dy" in o]
    print(f"옆 중복으로 지워짐 {sum('옆의 중복' in o['stage'] for o in R)} · 짝 찾음 {len(d)}")
    for k in ("det_dy", "truth_dy", "cand_err", "part_err", "dx"):
        v = [o[k] for o in d]
        print(f"  {k}: " + " · ".join(f"{p}%={np.percentile(v, p):.2f}" for p in (0, 5, 50, 95, 100)))


if __name__ == "__main__" and sys.argv[1:] != ["dups"]:
    main()


def _dup_page(job):
    """한 쪽의 「옆 중복」 삭제 전부 — 지워진 후보 자리에 (다른 라벨이 없는) 정답 머리가 있나 · 꽉 참 여부 · 두 머리 증거값."""
    st, nm, path, pg = job
    import measure_chord_miss as C
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads, remove_staff_lines
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    rej = []
    heads = detect_noteheads(res, contexts=ctx, reject_log=rej)
    T = C.truth(st, nm, path, pg)
    ns = remove_staff_lines(res.binary, res.staves)
    sp = float(np.median([s.spacing for s in res.staves]))

    def ev(x, y):
        dy, inner, outer = max(1, int(round(sp * 0.25))), max(1, int(round(sp * 0.20))), max(2, int(round(sp * 0.55)))
        y0, y1 = max(0, int(y) - dy), int(y) + dy + 1
        s = [float((ns[y0:y1, max(0, int(x) - outer):max(0, int(x) - inner + 1)] > 0).mean()),
             float((ns[y0:y1, int(x) + inner:int(x) + outer + 1] > 0).mean())]
        return round(min(s), 2)
    out = []
    for r in rej:
        if "옆의 중복" not in r["reason"]:
            continue
        part = [h for h in heads if h.staff_index == r["staff"] and 0.6 * sp <= abs(h.x - r["x"]) <= 1.3 * sp and abs(h.y - r["y"]) <= 0.35 * sp]
        t = [q for q in T if abs(q[0] - r["x"]) <= 0.5 * sp and abs(q[1] - r["y"]) <= 0.5 * sp]
        tp = [q for q in T if part and abs(q[0] - part[0].x) <= 0.5 * sp and abs(q[1] - part[0].y) <= 0.5 * sp]
        out.append(dict(set=st, page=nm, x=r["x"], y=r["y"], filled=r["filled"], true=bool(t) and (not tp or tp[0] != t[0]),
                        ev=ev(r["x"], r["y"]), ev_part=ev(part[0].x, part[0].y) if part else None,
                        part_filled=part[0].filled if part else None))
    return out


def dups():
    import measure_chord_miss as C
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = [o for part in ex.map(_dup_page, C.pages()) for o in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "dup_rule.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for t in (True, False):
        v = [o for o in R if o["true"] == t]
        print(f"{'진짜 머리(유니즌 등)' if t else '유령'} {len(v)} · 꽉 참 {sum(o['filled'] for o in v)} · 세트 {dict(Counter(o['set'] for o in v))}")
        for k in ("ev", "ev_part"):
            a = [o[k] for o in v if o[k] is not None]
            if a:
                print(f"   {k}: " + " · ".join(f"{p}%={np.percentile(a, p):.2f}" for p in (0, 5, 50, 95, 100)))
        print("   둘 다 꽉 참", sum(o["filled"] and o["part_filled"] for o in v), "· 증거 둘 다 ≥ 0.4", sum(o["ev"] >= 0.4 and (o["ev_part"] or 0) >= 0.4 for o in v))


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "dups":
    dups()
