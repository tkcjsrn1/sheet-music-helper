# -*- coding: utf-8 -*-
"""오선 안 기타 유령(ERROR_CENSUS_1015 「확실」 113) 중 가장 큰 하위 유형 「빔 위 · 기둥-빔 모서리」 41의 표시 신호. 제품 코드 무변경.

§1-13 `sloped_beam_suspects`는 **빈 머리**에만 건다(빔엔 채워진 머리가 붙는 게 정상이라서). 그런데 113 중 빔 41은 채워진 머리로 잡혔다.
같은 조건(기울어진 빔 마스크로 중심 ±0.2sp 「빔 위」, 또는 위아래 0.2~1.3sp 「빔 사이」)을 라벨 전부에 걸면 유령 · 진짜가 몇이나 걸리나.
라벨 = `debug/sim_lp/flatc1u`(census와 같은 것) · Mutopia = `debug/inputs_score/mutopia`. 유령 여부 = `debug/error_census.json`.
Aoharu는 정답 골든이라 라벨 전부가 진짜 — 걸리면 전부 헛표시.

    python tools/measure_filled_beam_check.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    from modules import verify as V
    from modules.preprocess import preprocess
    st, name, path, pg, lab, ghosts = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    mask = V.sloped_beam_mask(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in res.staves}
    out = []
    for l in json.load(open(lab, encoding="utf-8"))["labels"]:
        sp = sp_of.get(l["staff"])
        if sp is None:
            continue
        x, y = int(l["x"]), int(l["y"])
        half = max(1, int(sp * 0.5))
        on = V._band_ink(mask, x, y - int(sp * 0.2), y + int(sp * 0.2) + 1, half) > 0.05
        ab = V._band_ink(mask, x, y - int(sp * 1.3), y - int(sp * 0.2), half) > 0.05
        be = V._band_ink(mask, x, y + int(sp * 0.2), y + int(sp * 1.3), half) > 0.05
        if on or (ab and be):
            kind = ghosts.get((x, y), "진짜" if st == "aoharu" or st != "mutopia" else "진짜?")
            out.append((st, name, x, y, l["text"], l["confidence"], "빔 위" if on else "빔 사이", kind))
    return out


def main():
    import measure_sim_ledger_pair as S
    P = json.load(open(os.path.join(ROOT, "debug", "error_census.json"), encoding="utf-8"))
    g = {p["page"]: {(int(r["x"]), int(r["y"])): r["cause"] for r in p["rows"] if r["kind"] == "유령"} for p in P}
    jobs = []
    for st, n, p, pg in S.pages():
        lab = os.path.join(ROOT, "debug", "sim_lp", "flatc1u", n + ".json")
        if n != "organ2" and os.path.exists(lab):
            jobs.append((st, n, p, pg, lab, g.get(n, {})))
    M = os.path.join(ROOT, "debug", "inputs_score", "mutopia")
    for f in sorted(os.listdir(M)):
        stem, (fn, pno) = f[:-5], f[:-5].rsplit("_p", 1)
        jobs.append(("mutopia", stem, os.path.join("inputs", "mutopia", fn + ".pdf"), int(pno) - 1, os.path.join(M, f), g.get(stem, {})))
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        rows = [r for page in ex.map(_page, jobs) for r in page]
    json.dump(rows, open(os.path.join(ROOT, "debug", "filled_beam_check.json"), "w", encoding="utf-8"), ensure_ascii=False)
    c = Counter()
    for st, _n, _x, _y, _t, conf, why, kind in rows:
        k = "유령" if kind not in ("진짜", "진짜?") else kind
        c[(st, why, k, conf == "certain")] += 1
    for st in ("pdf", "unseen", "verovio", "mutopia", "aoharu"):
        for why in ("빔 위", "빔 사이"):
            for k in ("유령", "진짜", "진짜?"):
                a, b = c[(st, why, k, True)], c[(st, why, k, False)]
                if a or b:
                    print(f"{st:8s} {why} {k}: 확실 {a} · 그 밖 {b}")
    tgt = Counter(kind for *_r, conf, _w, kind in rows if conf == "certain")
    print("확실 라벨 중 걸린 것 원인별:", dict(tgt))


if __name__ == "__main__":
    main()
