# -*- coding: utf-8 -*-
"""야간 [3] 「빈 음표 링의 좌우 벽」 필터 — 지워지는 쪽이 정말 꽉 찬 머리인가(본 상관 · 자기 기둥). 제품 코드 무변경.

입력: `measure_ring_wall.py`가 남긴 `debug/ring_wall.json`(지운 꽉 찬 후보 · 정답 분류). 후보마다
  ncc   = 그 쪽 단독 꽉 찬 머리 본(`measure_chord_template`과 같은 방식, 라벨 = 지금 main `nograce`)과의 상관, 후보 중심 ±0.2sp 안 최댓값
  stem  = 기보: 머리 기둥은 오른쪽 위(RU) 또는 왼쪽 아래(LD)로 뻗는다 — `verify._side_runs`의 RU · LD 중 큰 값 ≥ 2.5sp
두 무리(잘못 지운 진짜 꽉 찬 머리 / 맞게 지운 링 벽 · 유령)가 갈리면 「확실한 꽉 찬 머리는 링 벽 판정에서 뺌」 시뮬레이션(이 도구는 분포만).

    python tools/measure_ring_wall.py && python tools/measure_ring_wall_head.py
"""
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules.verify import _side_runs
    (st, name, path, pg), rows = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    sp = float(np.median([s.spacing for s in res.staves]))
    nsb = remove_staff_lines(res.binary, res.staves) > 0
    ns = nsb.astype(np.float32)
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "nograce", name + ".json"), encoding="utf-8"))["labels"]
    hw, hh = int(0.65 * sp), int(0.55 * sp)
    crops = []
    for l in L:
        if l["confidence"] != "certain" or any(o is not l and o["staff"] == l["staff"] and abs(o["x"] - l["x"]) <= 1.2 * sp and abs(o["y"] - l["y"]) <= 1.2 * sp for o in L):
            continue
        c = ns[int(l["y"]) - hh:int(l["y"]) + hh + 1, int(l["x"]) - hw:int(l["x"]) + hw + 1]
        if c.shape == (2 * hh + 1, 2 * hw + 1) and c.mean() > 0.4:
            crops.append(c)
        if len(crops) >= 30:
            break
    tmpl = np.mean(crops, axis=0).astype(np.float32) if len(crops) >= 5 else None
    out = []
    r = int(0.2 * sp)
    for row in rows:
        x, y = int(row["x"]), int(row["y"])
        ncc = None
        if tmpl is not None:
            reg = ns[max(0, y - hh - r):y + hh + r + 1, max(0, x - hw - r):x + hw + r + 1]
            if reg.shape[0] > tmpl.shape[0] and reg.shape[1] > tmpl.shape[1]:
                ncc = float(cv2.matchTemplate(reg, tmpl, cv2.TM_CCOEFF_NORMED).max())
        g = _side_runs(nsb, x, y, row["sp"])
        out.append(dict(row, ncc=None if ncc is None else round(ncc, 3), stem=max(g["RU"], g["LD"]) >= 2.5))
    return out


def main():
    import measure_sim_ledger_pair as S
    rows = json.load(open(os.path.join(ROOT, "debug", "ring_wall.json"), encoding="utf-8"))
    P = {n: (st, n, p, g) for st, n, p, g in S.pages()}
    by = defaultdict(list)
    for r in rows:
        by[r["page"]].append(r)
    with ProcessPoolExecutor(3) as ex:
        res = [x for part in ex.map(_page, [(P[k], v) for k, v in by.items()]) for x in part]
    json.dump(res, open(os.path.join(ROOT, "debug", "ring_wall_head.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for what in sorted({r["what"] for r in res}):
        v = [r for r in res if r["what"] == what]
        nc = [r["ncc"] for r in v if r["ncc"] is not None]
        print(f"{what}: {len(v)} | 본 상관 최소 · 5 · 50 · 95 · 최대 " + " · ".join(f"{np.percentile(nc, q):.2f}" for q in (0, 5, 50, 95, 100))
              + f" | 자기 기둥 있음 {sum(r['stem'] for r in v)}")
    real = [r for r in res if r["what"] == "꽉 찬 진짜 머리"]
    wall = [r for r in res if r["what"] != "꽉 찬 진짜 머리"]
    for th in (0.6, 0.66, 0.7, 0.8):
        for need_stem in (False, True):
            keep = lambda r: r["ncc"] is not None and r["ncc"] >= th and (r["stem"] or not need_stem)
            print(f"  「상관 ≥ {th}" + (" · 기둥 있음" if need_stem else "") + f"이면 안 지움」: 되찾는 진짜 머리 {sum(keep(r) for r in real)}/{len(real)} · 되살아나는 링 벽 · 유령 {sum(keep(r) for r in wall)}/{len(wall)}")


if __name__ == "__main__":
    main()
