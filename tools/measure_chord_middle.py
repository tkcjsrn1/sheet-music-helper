# -*- coding: utf-8 -*-
"""[4] 3도 쌓기 화음의 가운데 머리 — 「라벨 둘 사이 가운데 행의 가로 잉크 폭」 사본 시뮬레이션 (2026-10-12 · 측정만, 제품 무변경).

후보 = 같은 보표 라벨 둘이 같은 기둥(|dx| ≤ 0.3sp)에 세로 1.8~2.2sp(5도 간격) · 가운데(±0.5sp)에 라벨 없음.
값 = 가운데 행(±0.15sp 행 중 최대) 오선 제거 영상의 x를 지나는 가로 잉크 런(sp). 3화음이면 머리 폭(≈1.2sp), 빈 5도면 기둥 · 오선 조각뿐.
정답 = `debug/chord_miss.json`(정답 머리, holdout 미사용) — 가운데 0.5sp 안에 정답 머리가 있으면 「가운데 머리 있음」.
#193(덩어리 높이 → 머리 수)과 다르다: 위치는 라벨 둘이 정하고, 값은 그 한 행의 폭이다. 보류된 「본 상관」(모양 비교)도 쓰지 않는다.

    python tools/measure_chord_middle.py      # 분포 + 문턱별 되찾음 · 새 유령
"""
import json, os, sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def _page(job):
    st, name, path, pg = job
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "beamgap1012", name + ".json"), encoding="utf-8"))["labels"]
    T = [r for r in json.load(open(os.path.join(ROOT, "debug", "chord_miss.json"), encoding="utf-8")) if r["page"] == name]
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ns = remove_staff_lines(res.binary, res.staves) > 0
    H, W = ns.shape
    sp = float(np.median([s.spacing for s in res.staves]))
    out = []
    for i, a in enumerate(L):
        for b in L[i + 1:]:
            if a["staff"] != b["staff"] or abs(a["x"] - b["x"]) > 0.3 * sp or not 1.8 * sp <= abs(a["y"] - b["y"]) <= 2.2 * sp:
                continue
            mx, my = (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2
            if any(abs(l["x"] - mx) <= 0.5 * sp and abs(l["y"] - my) <= 0.5 * sp for l in L):
                continue
            def run_at(y0, y1):
                best = 0
                for y in range(int(y0), int(y1) + 1):
                    if not 0 <= y < H:
                        continue
                    row = ns[y]
                    xs = [x for x in range(int(mx - 0.4 * sp), int(mx + 0.4 * sp) + 1) if 0 <= x < W and row[x]]
                    for x0 in xs[:1] + xs[len(xs) // 2:len(xs) // 2 + 1]:
                        p = q = x0
                        while p > 0 and row[p - 1]: p -= 1
                        while q + 1 < W and row[q + 1]: q += 1
                        best = max(best, q - p + 1)
                return best
            best = run_at(my - 0.15 * sp, my + 0.15 * sp)
            # 높이: 가운데 머리라면 가운데 ±0.25sp 행에도 머리 폭 잉크가 있다(오선 잔여 조각 · 기둥만이면 없다)
            up = run_at(my - 0.3 * sp, my - 0.2 * sp)
            dn = run_at(my + 0.2 * sp, my + 0.3 * sp)
            truth = any(abs(t["x"] - mx) <= 0.5 * sp and abs(t["y"] - my) <= 0.5 * sp for t in T)
            out.append(dict(set=st, page=name, x=round(mx), y=round(my), run=round(best / sp, 2), up=round(up / sp, 2), dn=round(dn / sp, 2), truth=truth))
    return out


if __name__ == "__main__":
    import measure_chord_miss as C
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        R = [r for part in ex.map(_page, C.pages()) for r in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "chord_middle.json"), "w", encoding="utf-8"), ensure_ascii=False)
    yes = sorted(r["run"] for r in R if r["truth"]); no = sorted(r["run"] for r in R if not r["truth"])
    pc = lambda v: " ".join(f"{p}%={np.percentile(v, p):.2f}" for p in (0, 1, 5, 50, 95, 100)) if v else "—"
    print(f"후보 {len(R)} · 가운데 정답 머리 있음 {len(yes)}: {pc(yes)}")
    print(f"           없음(빈 5도 등) {len(no)}: {pc(no)}")
    for th in (0.6, 0.7, 0.8, 0.9, 1.0):
        h = [r for r in R if r["run"] >= th]
        print(f"  런 ≥ {th}: 추가 {len(h)} · 되찾음 {sum(r['truth'] for r in h)} · 새 유령 {sum(not r['truth'] for r in h)} · 세트 {dict(__import__('collections').Counter(r['set'] for r in h if r['truth']))}")
