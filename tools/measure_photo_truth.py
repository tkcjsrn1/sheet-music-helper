# -*- coding: utf-8 -*-
"""(e) 사진 합성 세트를 원본 PDF 정답으로 판정 — 사진 모드에서 ♮ · ♯ 수정(§1-12)과 A-25 경계(§1-14)를 켜도 되는가. 제품 코드 무변경.

합성 사진은 원본 PDF(바흐 1쪽 · 쇼팽 D♭ 1쪽 · F장조 ♭1 픽스처)에서 만들었다. 사진 모드 라벨(보정 · 잘라낸 영상 좌표)을 원본 PDF 정답 머리
좌표로 **점 집합 정렬**(무게중심 평행이동 → 부분 아핀 ICP 20회, 짝 0.5sp)한 뒤 `measure_pdf_effective`의 실효 임시표 정답과 대조한다.

  off       지금 제품(사진 모드는 정밀 판정 · 새 경계 끔) — `debug/a17_cand1_g1flag/base_photo`
  nat       수락안 + ♮ 조건을 사진에서도 켬(측정 사본) — `debug/a17_cand1_nat/c12g3h3_photo`
  bl        A-25 경계를 사진에서도 켬(측정 사본 (나), 판정은 예전) — `debug/a17_cand1_bl_gap/base_photo`
  a25       제품 그대로 — 사진 모드에서 A-25 전파 경계만 켬(DECISIONS §1-18), `python tools/measure_photo_truth.py run_a25`로 만든다
  a25raw    a25 + 임시표 유령 제거 판단을 원시 임시표로(`measure_propagated_drop.py`, PR #188 브랜치에서)
  impl      제품 그대로 — 사진 모드 A-25 경계 + 임시표 유령 제거 원시 기준(DECISIONS §1-18), `run_impl`로 만든다
  all       정밀 판정 전체(A-25 경계 + ♮ · ♯ 수정 · G3 · H3)를 사진에서도 켬 — `tools/measure_photo_refined.py`(현재 main 제품 + `_refined` 가로채기)

    python tools/measure_photo_truth.py
"""
import json
import os
import sys
from collections import Counter

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
VARIANTS = {"off": "debug/a17_cand1_g1flag/base_photo", "nat": "debug/a17_cand1_nat/c12g3h3_photo",
            "bl": "debug/a17_cand1_bl_gap/base_photo", "all": "debug/a17_cand1_photo_all/base_photo",
            "a25": "debug/a17_cand1_photo_a25/base_photo", "a25raw": "debug/propdrop/raw_photo",
            "impl": "debug/a17_cand1_photo_impl/base_photo", "flat": "debug/a17_cand1_photo_flat/base_photo",
            "main1004": "debug/a17_cand1_photo_main1004/base_photo", "main1006": "debug/a17_cand1_photo_main1006/base_photo",
            "pf_rescue": "debug/photo_filters/rescue", "pf_g3": "debug/photo_filters/g3"}
SOURCES = {"bach": ("bach", "test_scores/bach_minuet_Am.pdf", 0), "chopin_Db": ("db1", "test_scores/chopin_nocturne_Db_6-8.pdf", 0),
           "F_flat1": ("fflat", "tests/fixtures/key_signatures/pdf/12_F_major_flat1.pdf", 0)}


def truth_of(src):
    import measure_pdf_effective as E
    E.KEYS.setdefault("fflat", "B")
    E.KEY_SIGN.setdefault("fflat", "b")
    name, path, pg = SOURCES[src]
    res, heads = E.effective(name, path, pg)
    sp = float(np.median([s.spacing for s in res.staves]))
    return heads, sp


def align(pts, ref, sp):
    """pts(사진 라벨) → ref(정답 머리) 부분 아핀. 초기 평행이동은 격자 탐색(무게중심 ± 6sp, 0.25sp 간격, 0.5sp 안 짝 수 최대) —
    첫 판(무게중심에서 바로 RANSAC)은 쇼팽 조명 · 회전 8장에서 짝 0으로 실패했다. 그 뒤 부분 아핀 ICP."""
    P, R = np.float32(pts), np.float32(ref)
    base = R.mean(axis=0) - P.mean(axis=0)

    def score(Q):
        d = ((Q[:, None, :] - R[None, :, :]) ** 2).sum(-1)
        return int((d.min(axis=1) <= (0.5 * sp) ** 2).sum())
    best, bt = -1, base
    for dx in np.arange(-6, 6.01, 0.25) * sp:
        for dy in np.arange(-6, 6.01, 0.25) * sp:
            t = base + np.float32([dx, dy])
            sc = score(P[::3] + t)
            if sc > best:
                best, bt = sc, t
    P2 = P + bt
    for _ in range(20):
        d = ((P2[:, None, :] - R[None, :, :]) ** 2).sum(-1)
        j = d.argmin(axis=1)
        ok = d[np.arange(len(P2)), j] <= (0.75 * sp) ** 2
        if ok.sum() < 6:
            break
        M2, _inl = cv2.estimateAffinePartial2D(P[ok], R[j[ok]], method=cv2.LMEDS)
        if M2 is None:
            break
        Q = P @ M2[:, :2].T + M2[:, 2]
        if score(Q) < score(P2):
            break
        P2 = Q.astype(np.float32)
    return P2


def main():
    acc = lambda t: "#" if t and t.endswith("#") else "b" if t and t.endswith("b") else ""
    norm = {"#": "#", "b": "b", "natural": "", "": "", "flatflat": "b", "doublesharp": "#"}
    truths = {s: truth_of(s) for s in SOURCES}
    tot = {v: Counter() for v in VARIANTS}
    per = []
    names = sorted({f for d in VARIANTS.values() for f in os.listdir(os.path.join(ROOT, d)) if f.endswith(".json") and not f.endswith(("_g2.json", "_gaps.json"))})
    for f in names:
        src = next(s for s in SOURCES if f.startswith("ph_" + s + "__"))
        heads, sp = truths[src]
        ref = [(h["x"], h["y"]) for h in heads]
        row = {"photo": f[3:-5]}
        for v, d in VARIANTS.items():
            p = os.path.join(ROOT, d, f)
            if not os.path.exists(p):
                continue
            L = json.load(open(p, encoding="utf-8"))["labels"]
            if len(L) < 6:
                continue
            P2 = align([(l["x"], l["y"]) for l in L], ref, sp)
            used, c = set(), Counter()
            for l, (x, y) in sorted(zip(L, P2), key=lambda t: t[0]["x"]):
                cand = [(abs(h["x"] - x) + abs(h["y"] - y), i) for i, h in enumerate(heads)
                        if i not in used and abs(h["x"] - x) <= 0.7 * sp and abs(h["y"] - y) <= 0.5 * sp]
                if not cand:
                    c["유령"] += 1
                    continue
                i = min(cand)[1]
                used.add(i)
                c["짝"] += 1
                if l["pitch"] != heads[i]["pitch"]:
                    c["음고"] += 1
                elif acc(l["text"]) != norm.get(heads[i]["eff"], ""):
                    c["표기"] += 1
            c["누락"] = len(heads) - len(used)
            tot[v].update(c)
            row[v] = dict(c)
        per.append(row)
    json.dump(per, open(os.path.join(ROOT, "debug", "photo_truth.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # 정렬이 된 사진만: off에서 라벨의 85% 이상이 정답 머리와 짝(정렬 실패 사진은 비교에서 뺀다 — 수를 따로 적는다)
    good = [r for r in per if "off" in r and r["off"].get("짝", 0) >= 0.85 * (r["off"].get("짝", 0) + r["off"].get("유령", 0))
            and all(v in r for v in VARIANTS)]
    print(f"정렬된 사진 {len(good)} / {len(per)}(나머지는 정렬 실패로 뺌)")
    for v in VARIANTS:
        t = Counter()
        for r in good:
            t.update(r[v])
        print(f"{v:4s} 짝 {t['짝']} · 음고 틀림 {t['음고']} · 표기 틀림 {t['표기']} · 유령 {t['유령']} · 누락 {t['누락']}")
    for v in ("nat", "bl", "all", "a25", "a25raw", "impl", "flat", "main1004", "main1006", "pf_rescue", "pf_g3"):
        worse = [(r["photo"], r["off"].get("표기", 0), r[v].get("표기", 0)) for r in good if r[v].get("표기", 0) > r["off"].get("표기", 0)]
        better = sum(1 for r in good if r[v].get("표기", 0) < r["off"].get("표기", 0))
        print(f"  {v}: 표기 틀림이 준 사진 {better} · 는 사진 {len(worse)}", worse[:8])


if __name__ == "__main__":
    if sys.argv[1:] in (["run_a25"], ["run_impl"], ["run_flat"], ["run_main1004"], ["run_main1006"], ["run_hdr"], ["run_rwkeep"]):
        import measure_a17_ghost6 as G
        G.T1.OUT = os.path.join(ROOT, "debug", {"run_a25": "a17_cand1_photo_a25", "run_impl": "a17_cand1_photo_impl", "run_flat": "a17_cand1_photo_flat",
                                                "run_main1004": "a17_cand1_photo_main1004", "run_main1006": "a17_cand1_photo_main1006", "run_hdr": "a17_cand1_photo_hdr", "run_rwkeep": "a17_cand1_photo_rwkeep"}[sys.argv[1]])
        G.set_variant("base")
        G.run_set("base", "photo")
    else:
        main()
