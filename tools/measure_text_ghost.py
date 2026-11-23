# -*- coding: utf-8 -*-
"""오선 밖 글자 · 셈여림 유령 → check 표시안 측정 (2026-10-15, 사용자 결정 16시 2 · 측정만, 보류 세트 미사용).

라벨마다 값(판정 아님): 오선 밖 거리(sp, 보표 윗줄 · 아랫줄에서), 덧줄 유무(기록 신호 ``no_ledger`` · ``off_staff``),
「같은 높이 글자 크기 덩어리 수」 = 오선 제거 영상에서 라벨 높이 ±0.6sp 안에 중심이 있고 높이 0.4~2.5sp · 폭 0.2~3sp인 8연결 성분 수
(라벨 좌우 ±4sp, 라벨 자신 포함). 글자 줄(나타냄말 · 셈여림)은 덩어리가 가로로 늘어서고, 덧줄 위 음표는 덧줄이 붙어 긴 성분이 된다.
정답: ``error_census``와 같다(라벨 ↔ 정답 머리 1:1). 유령 = 짝 없는 라벨. Mutopia는 머리 위치 정답만.
조건 후보마다: 걸리는 라벨 중 유령(맞힌 것) · 맞는 라벨(헛표시) · 「확실」 유령 감소.

    python tools/measure_text_ghost.py            → debug/text_ghost.json + 조건표
"""
import glob
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "text_ghost.json")


def _feat(job):
    import cv2
    import error_census as EC
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    st, name, path, pg, lab = job
    doc = json.load(open(lab, encoding="utf-8"))
    L = doc["labels"]
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ns = (remove_staff_lines(res.binary, res.staves) > 0).astype(np.uint8)
    n, cc, stt, cen = cv2.connectedComponentsWithStats(ns, connectivity=8)
    if st == "verovio":
        heads, _b, sp0 = EC._truth_vrv(name)
    elif st == "mutopia":
        from measure_normalize_sp import truth_at
        hs, _c = truth_at(path, pg, 1.0)
        heads = [dict(x=h["cx"], y=h["cy"], pitch="", eff="") for h in hs]
        sp0 = float(np.median([s["spacing"] for s in doc["staves"]]))
    else:
        heads, _b, sp0 = EC._truth_pdf(name, path, pg)
    m = EC._match(heads, L, sp0)
    truth_of = {j: heads[i] for i, j in m.items()}
    staves = {s["id"]: s for s in doc["staves"]}
    rows = []
    for j, l in enumerate(L):
        s = staves.get(l["staff"])
        if s is None:
            continue
        sp = s["spacing"]
        d = max(0.0, (s["top"] - l["y"]) / sp, (l["y"] - s["bottom"]) / sp)
        if d <= 0:
            continue
        x, y = l["x"], l["y"]
        sel = [k for k in range(1, n) if abs(cen[k][1] - y) <= 0.6 * sp and abs(cen[k][0] - x) <= 4 * sp
               and 0.4 * sp <= stt[k][3] <= 2.5 * sp and 0.2 * sp <= stt[k][2] <= 3.0 * sp]
        h = truth_of.get(j)
        ok = None if st == "mutopia" else (h is not None and h["pitch"] == l["pitch"] and EC.ACC(l["text"]) == h["eff"])
        rows.append(dict(set=st, page=name, x=x, y=y, d=round(d, 2), blobs=len(sel), flags=l["flags"], conf=l["confidence"],
                         ghost=h is None, correct=ok))
    return rows


def main():
    import measure_sim_ledger_pair as S
    jobs = [(st, n, p, pg, os.path.join(ROOT, "debug", "sim_lp", "dblacc", n + ".json")) for st, n, p, pg in S.pages()
            if st != "aoharu" and n != "organ2"]
    for lab in sorted(glob.glob(os.path.join(ROOT, "debug", "inputs_score", "mutopia", "*.json"))):
        stem = os.path.basename(lab)[:-5]
        f, p = stem.rsplit("_p", 1)
        jobs.append(("mutopia", stem, os.path.join("inputs", "mutopia", f + ".pdf"), int(p) - 1, lab))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = [r for part in ex.map(_feat, jobs) for r in part]
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(R)


def report(R=None):
    R = R or json.load(open(OUT, encoding="utf-8"))
    print("오선 밖 라벨", len(R), "· 유령", sum(r["ghost"] for r in R), "· 확실 유령", sum(r["ghost"] and r["conf"] == "certain" for r in R))
    for name, cond in [
        ("덩어리 ≥ 3", lambda r: r["blobs"] >= 3),
        ("덩어리 ≥ 3 · 거리 ≥ 1", lambda r: r["blobs"] >= 3 and r["d"] >= 1.0),
        ("덩어리 ≥ 3 · no_ledger", lambda r: r["blobs"] >= 3 and "no_ledger" in r["flags"]),
        ("덩어리 ≥ 4 · no_ledger", lambda r: r["blobs"] >= 4 and "no_ledger" in r["flags"]),
        ("덩어리 ≥ 3 · no_ledger · 거리 ≥ 1", lambda r: r["blobs"] >= 3 and "no_ledger" in r["flags"] and r["d"] >= 1.0),
        ("no_ledger 만", lambda r: "no_ledger" in r["flags"]),
    ]:
        F = [r for r in R if cond(r)]
        c = Counter()
        for r in F:
            if r["conf"] == "check":
                c["이미 check"] += 1
            elif r["ghost"]:
                c["유령 " + r["conf"]] += 1
            elif r["correct"] is False:
                c["틀린 라벨 " + r["conf"]] += 1
            else:
                c["맞는 라벨(헛표시) " + r["conf"]] += 1
        dec = c["유령 certain"] + c["틀린 라벨 certain"]
        fa = c["맞는 라벨(헛표시) certain"]
        print(f"  {name:30s} 걸림 {len(F):4d} · 확실 오류 감소 {dec:3d} · 확실 헛표시 {fa:3d} · {dict(c)}")


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
