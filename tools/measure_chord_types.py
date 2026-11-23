# -*- coding: utf-8 -*-
"""(d) 화음 누락 유형별 수 + 「3도 쌓기 가운데 머리」 추가안의 보강 시뮬레이션 (2026-10-13 · 측정만, 제품 무변경, 보류 세트 미사용).

입력: `debug/chord_miss.json`(정답 머리 전부 · 누락 여부 · 단계, `measure_chord_miss.py trace`) · `debug/chord_middle.json`(`measure_chord_middle.py`).
유형(한 머리가 여러 유형에 들 수 있어 따로 센다) — 넓은 화음 = 가로 1.6sp · 세로 1.05sp 안에 다른 정답 머리:
  붙은 2도         세로 ≤ 0.6sp 이웃(2도)이 있다
  줄기 반대편 머리   같은 화음 다른 머리들 x 중앙에서 0.6sp 넘게 비껴 있다(2도 때문에 기둥 반대편으로 밀린 머리)
  3음 이상 가운데   가로 0.6sp 화음 사슬 크기 ≥ 3에서 맨 위 · 맨 아래가 아닌 머리
  덧줄 위 화음     오선 밖(±0.3sp) 화음 머리
  꼬리 · 빔 겹침   (Verovio만) 머리 중심 0.6sp 안에 빔 · 꼬리 상자
가운데 머리 추가안 보강: 양 끝 라벨이 둘 다 check가 아니어야 하고, 추가될 음 = 양 끝 음 단계의 가운데(3도 위). 정답 대조는 위치 + (Verovio) 음이름.

    python tools/measure_chord_types.py types
    python tools/measure_chord_types.py middle
"""
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LETTERS = "CDEFGAB"


def types():
    import measure_verovio as V
    R = json.load(open(os.path.join(ROOT, "debug", "chord_miss.json"), encoding="utf-8"))
    by = defaultdict(list)
    for r in R:
        by[r["page"]].append(r)
    cnt, tot, rows = Counter(), Counter(), []
    for page, v in by.items():
        boxes = []
        if v[0]["set"] == "verovio":
            boxes = [b for b in json.load(open(os.path.join(V.OUT, "truth", page + ".json"), encoding="utf-8"))["boxes"] if b["cls"] in ("beam", "flag")]
        for r in v:
            sp = r["sp"]
            wide = [q for q in v if q is not r and abs(q["x"] - r["x"]) <= 1.6 * sp and abs(q["y"] - r["y"]) <= 1.05 * sp]
            if not wide:
                continue
            group = [r] + wide
            ts = []
            if any(abs(q["y"] - r["y"]) <= 0.6 * sp for q in wide):
                ts.append("붙은 2도")
            others = [q["x"] for q in wide]
            if abs(r["x"] - float(np.median(others))) > 0.6 * sp:
                ts.append("줄기 반대편 머리")
            if r["size"] >= 3:
                col = [q["y"] for q in v if abs(q["x"] - r["x"]) <= 0.6 * sp and abs(q["y"] - r["y"]) <= 3.5 * sp]
                if min(col) < r["y"] < max(col):
                    ts.append("3음 이상 가운데")
            if r["ledger"]:
                ts.append("덧줄 위 화음")
            if boxes and any(b["box"][0] - 0.6 * sp <= r["x"] <= b["box"][2] + 0.6 * sp and b["box"][1] - 0.6 * sp <= r["y"] <= b["box"][3] + 0.6 * sp for b in boxes):
                ts.append("꼬리 · 빔 겹침")
            if not ts:
                ts = ["그 밖(3도 · 4도 이상 2음 등)"]
            for t in ts:
                tot[t] += 1
                cnt[t] += r["missed"]
            tot["넓은 화음 전체"] += 1
            cnt["넓은 화음 전체"] += r["missed"]
            if r["missed"]:
                rows.append(dict(page=page, set=r["set"], x=r["x"], y=r["y"], types=ts, stage=r.get("stage")))
    print("유형 | 누락/정답(누락률) — 한 머리가 여러 유형에 들 수 있음")
    for t, n in tot.most_common():
        print(f"  {t:22s} {cnt[t]:4d}/{n:5d} ({cnt[t] / n * 100:5.1f}%)")
    only = Counter(tuple(r["types"]) for r in rows)
    print("누락 머리의 유형 조합 상위:", only.most_common(8))
    print("유형별 단계(상위 2):")
    for t in tot:
        if t == "넓은 화음 전체":
            continue
        c = Counter(r["stage"] for r in rows if t in r["types"])
        print(f"  {t:22s}", c.most_common(2))
    json.dump(rows, open(os.path.join(ROOT, "debug", "chord_types.json"), "w", encoding="utf-8"), ensure_ascii=False)


def _step(p):
    return LETTERS.index(p[0]) + 7 * int(p[-1])


def middle(lo=1.0, hi=1.6, h=0.0, keepcheck="0"):
    """h = 가운데 ±0.25sp 행 런 최소(sp) — 진짜 가운데 머리의 높이 조건(오선 잔여 조각 · 기둥 거르기)."""
    import measure_verovio as V
    lo, hi, h = float(lo), float(hi), float(h)
    C = json.load(open(os.path.join(ROOT, "debug", "chord_middle.json"), encoding="utf-8"))
    labs, vt = {}, {}
    SP = {r["page"]: r["sp"] for r in json.load(open(os.path.join(ROOT, "debug", "chord_miss.json"), encoding="utf-8"))}
    res = Counter()
    bad = []
    for r in C:
        if not lo <= r["run"] <= hi or min(r.get("up", 9), r.get("dn", 9)) < h:
            continue
        pg = r["page"]
        if pg not in labs:
            labs[pg] = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "beamgap1012", pg + ".json"), encoding="utf-8"))["labels"]
            if r["set"] == "verovio":
                vt[pg] = json.load(open(os.path.join(V.OUT, "truth", pg + ".json"), encoding="utf-8"))["notes"]
        L = labs[pg]
        sp = SP[pg]
        # 원래 후보를 만든 짝짓기와 같은 조건(같은 보표 · |dx| ≤ 0.3sp · 1.8~2.2sp)으로 가운데가 이 후보인 라벨 쌍을 찾는다
        pair = [(a, b) for i, a in enumerate(L) for b in L[i + 1:]
                if a["staff"] == b["staff"] and abs(a["x"] - b["x"]) <= 0.3 * sp and 1.8 * sp <= abs(a["y"] - b["y"]) <= 2.2 * sp
                and abs(round((a["x"] + b["x"]) / 2) - r["x"]) <= 1 and abs(round((a["y"] + b["y"]) / 2) - r["y"]) <= 1]
        if not pair:
            res["양 끝 라벨 못 찾음"] += 1
            continue
        ends = sorted(pair[0], key=lambda l: l["y"])
        a, b = ends[0], ends[-1]
        if keepcheck == "0" and "check" in (a["confidence"], b["confidence"]):
            res["양 끝 중 check → 제외"] += 1
            res["제외 · " + ("정답 있음" if r["truth"] else "유령")] += 1
            continue
        sa, sb = _step(a["pitch"]), _step(b["pitch"])
        mid = (sa + sb) / 2
        if mid != int(mid):
            res["양 끝 단계 차가 홀수 → 제외"] += 1
            continue
        mid = int(mid)
        name = LETTERS[mid % 7] + str(mid // 7)
        if not r["truth"]:
            res["새 유령"] += 1
            bad.append((pg, r["x"], r["y"], name))
            continue
        if r["set"] == "verovio":
            t = [n for n in vt[pg] if abs(n["x"] - r["x"]) <= 0.5 * sp and abs(n["y"] - r["y"]) <= 0.5 * sp]
            ok = any(n["note_name"] + n["octave"] == name for n in t)
            res["되찾음 · 음고 맞음" if ok else "되찾음 · 음고 틀림"] += 1
            if not ok:
                bad.append((pg, r["x"], r["y"], name, [n["note_name"] + n["octave"] for n in t]))
        else:
            res["되찾음 · 음고 대조 안 함(PDF)"] += 1
    add = sum(v for k, v in res.items() if k.startswith("되찾음") or k == "새 유령")
    good = sum(v for k, v in res.items() if k in ("되찾음 · 음고 맞음", "되찾음 · 음고 대조 안 함(PDF)"))
    print(f"런 {lo}~{hi} · 높이 ≥ {h} · {dict(res)}")
    print(f"추가 {add} · 맞음(위치+음고) {good} · 정밀도 {good / max(1, add) * 100:.1f}%")
    print("틀린 추가:", bad)


if __name__ == "__main__":
    {"types": types, "middle": middle}[sys.argv[1]](*sys.argv[2:])
