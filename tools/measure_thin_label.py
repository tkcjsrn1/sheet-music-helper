# -*- coding: utf-8 -*-
"""오선 안 기타 유령 「머리 옆」 24 · 「꼬리」 21의 표시 신호 후보 — 라벨 자리 잉크 모양(측정만, 제품 코드 무변경).

라벨마다 오선 지운 영상에서
  t   = 세로 잉크 두께(`verify._vertical_thickness`, §1-42와 같은 함수 — x ± 0.4sp 열별 연속 길이 중앙값, sp)
  w   = 가로 잉크 폭(같은 방식을 가로로 — y ± 0.3sp 행별, x를 지나는 연속 길이 중앙값, sp)
  fr  = 머리 크기 창(± 0.55sp × ± 0.40sp) 잉크 비율
를 재서 진짜 · 유령(`debug/error_census.json`) · 하위 유형(`debug/misc113_classes.json`, 격자 눈 분류)별 분포를 낸다.
머리 옆 쌍(`measure_side_dup` 거리대)은 두 라벨 중 어느 값이 유령을 고르는지도 센다.
라벨 = `debug/sim_lp/flatc1u` · Mutopia `debug/inputs_score/mutopia`. 결과 `debug/thin_label.json`.

    python tools/measure_thin_label.py            # MEASURE_WORKERS(기본 1)
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _hrun(ns, x, y, sp):
    runs = []
    H, W = ns.shape
    for cy in range(int(y - 0.3 * sp), int(y + 0.3 * sp) + 1):
        if not (0 <= cy < H) or not (0 <= x < W) or not ns[cy, x]:
            runs.append(0)
            continue
        row = ns[cy] > 0
        a = b = x
        while a > 0 and row[a - 1]:
            a -= 1
        while b < W - 1 and row[b + 1]:
            b += 1
        runs.append(b - a + 1)
    return float(np.median(runs)) / sp


def _page(job):
    from modules.notehead_detect import remove_staff_lines
    from modules.preprocess import preprocess
    from modules.verify import _vertical_thickness
    st, n, path, pg, lab, ghosts, kinds = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ns = remove_staff_lines(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in res.staves}
    out = []
    for l in json.load(open(lab, encoding="utf-8"))["labels"]:
        sp = sp_of.get(l["staff"])
        if sp is None:
            continue
        x, y = int(l["x"]), int(l["y"])
        win = ns[max(0, int(y - 0.4 * sp)):int(y + 0.4 * sp) + 1, max(0, int(x - 0.55 * sp)):int(x + 0.55 * sp) + 1]
        g = (x, y) in ghosts
        out.append(dict(set=st, page=n, x=x, y=y, staff=l["staff"], pitch=l["pitch"], conf=l["confidence"],
                        kind=kinds.get((x, y), "유령" if g else "진짜"), ghost=g,
                        t=round(_vertical_thickness(ns, x, y, sp), 2), w=round(_hrun(ns, x, y, sp), 2),
                        fr=round(float((win > 0).mean()) if win.size else 0.0, 2), sp=sp))
    return out


def main():
    import measure_sim_ledger_pair as S
    P = json.load(open(os.path.join(ROOT, "debug", "error_census.json"), encoding="utf-8"))
    ghosts = {p["page"]: {(r["x"], r["y"]) for r in p["rows"] if r["kind"] == "유령"} for p in P}
    C = json.load(open(os.path.join(ROOT, "debug", "misc113_classes.json"), encoding="utf-8"))
    kinds = {}
    for k, v in C.items():
        for n, x, y in v:
            kinds.setdefault(n, {})[(x, y)] = k
    jobs = [(st, n, p, pg, os.path.join(ROOT, "debug", "sim_lp", "flatc1u", n + ".json"), ghosts.get(n, set()), kinds.get(n, {}))
            for st, n, p, pg in S.pages() if st != "aoharu" and n != "organ2"]
    M = os.path.join(ROOT, "debug", "inputs_score", "mutopia")
    for f in sorted(os.listdir(M)):
        stem, (fn, pno) = f[:-5], f[:-5].rsplit("_p", 1)
        jobs.append(("mutopia", stem, os.path.join("inputs", "mutopia", fn + ".pdf"), int(pno) - 1, os.path.join(M, f), ghosts.get(stem, set()), kinds.get(stem, {})))
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "1"))) as ex:
        rows = [r for page in ex.map(_page, jobs) for r in page]
    json.dump(rows, open(os.path.join(ROOT, "debug", "thin_label.json"), "w", encoding="utf-8"), ensure_ascii=False)
    report(rows)


def report(rows=None):
    rows = rows or json.load(open(os.path.join(ROOT, "debug", "thin_label.json"), encoding="utf-8"))
    pct = lambda v: [round(float(np.percentile(v, q)), 2) for q in (0, 5, 50, 95, 100)] if v else []
    real = [r for r in rows if not r["ghost"] and r["set"] != "mutopia"]
    print("진짜(t > 0만) t 분위 0/5/50/95/100:", pct([r["t"] for r in real if r["t"] > 0]), "· t = 0:", sum(r["t"] == 0 for r in real))
    for k in ("머리 옆", "꼬리"):
        v = [r for r in rows if r["kind"] == k]
        print(k, len(v), "t", sorted(r["t"] for r in v), "\n   w", sorted(r["w"] for r in v), "\n   fr", sorted(r["fr"] for r in v))
    # 후보: 0 < t < T 이고 확실 라벨 — 진짜 · 유령 수
    for T in (0.6, 0.7, 0.8):
        hit = [r for r in rows if 0 < r["t"] < T and r["conf"] == "certain"]
        print(f"후보 0 < t < {T} · 확실: 유령 {sum(r['ghost'] for r in hit)} · 진짜 {sum(not r['ghost'] and r['set'] != 'mutopia' for r in hit)}"
              f" (꼬리 {sum(r['kind'] == '꼬리' for r in hit)} · 머리 옆 {sum(r['kind'] == '머리 옆' for r in hit)})")
    # 머리 옆 쌍: 어느 값이 작은 쪽이 유령인가
    by = {}
    for r in rows:
        by.setdefault((r["page"], r["staff"], r["pitch"]), []).append(r)
    for key in ("t", "w", "fr"):
        ok = bad = 0
        for v in by.values():
            for i, a in enumerate(v):
                for b in v[i + 1:]:
                    h, d = abs(a["x"] - b["x"]) / a["sp"], abs(a["y"] - b["y"]) / a["sp"]
                    if 0.6 <= h <= 1.2 and d <= 0.3 and a["ghost"] != b["ghost"]:
                        g, t = (a, b) if a["ghost"] else (b, a)
                        ok += g[key] < t[key]
                        bad += g[key] >= t[key]
        print(f"머리 옆 쌍(진짜+유령)에서 유령 쪽 {key}가 더 작음 {ok} · 아님 {bad}")


if __name__ == "__main__":
    report() if sys.argv[1:] == ["report"] else main()
