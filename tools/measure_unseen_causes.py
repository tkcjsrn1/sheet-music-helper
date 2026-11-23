# -*- coding: utf-8 -*-
"""야간 [5] 보지 않은 악보 8쪽(월광 4 · 빗방울 4) — 누락 · 음고 틀림 원인별(Verovio 추적 `measure_missing_verovio`와 같은 단계 구분). 제품 코드 무변경.

정답 = PDF 글리프 주 크기 머리(`truth_at`) + 음자리표 글리프로 정답 음고(`measure_omission_rate.truth_pitch`). 라벨 = 지금 main(`debug/sim_lp/nograce`).
누락(라벨이 0.7 × 0.5sp 안에 없는 정답 머리)의 단계: 제품 단계(`measure_faded_stages.stages` — 두 검출 경로)를 같은 쪽에 다시 돌려
  헤더 안 → 최종 음표 있음 · 라벨 짝 실패 → 임시표 유령 필터 → 보표 밖 유령 필터 → 빔 유령 필터 → 검출 내부 필터(사유) → 머리 검색 띠 밖 → 잉크 부족(< 0.25) → 모양 판정.
음고 틀림의 원인: 그 머리 정답 음자리표(왼쪽 가장 가까운 음자리표 글리프) ≠ 제품 보표 음자리표 → 「음자리표(바뀜 · 오판)」, 같으면 위치 차(반칸 ±1 · ±2 · 옥타브 · 기타).

    python tools/measure_unseen_causes.py
"""
import json
import os
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
L_ = "CDEFGAB"
step = lambda p: L_.index(p[0]) + 7 * int(p[1:])


def _page(job):
    import measure_faded_stages as F
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    from modules.preprocess import load_image, preprocess
    from modules.clef_keysig import analyze_staves
    from modules import notehead_detect as ND
    name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    sp = float(np.median([s.spacing for s in res.staves]))
    tmp = tempfile.mkdtemp(prefix="unseen_")
    f = os.path.join(tmp, "p.png")
    open(f, "wb").write(cv2.imencode(".png", load_image(os.path.join(ROOT, path), pdf_page=pg))[1].tobytes())
    S = F.stages(f)[0]
    os.remove(f)
    os.rmdir(tmp)
    heads, clefs = truth_at(path, pg, 1.0)
    for q in clefs:
        q["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["cy"])).index
    L = json.load(open(os.path.join(ROOT, "debug", "sim_lp", "nograce", name + ".json"), encoding="utf-8"))["labels"]
    ns = ND.remove_staff_lines(res.binary, res.staves)
    margins = {s.index: ND._band_margins(s, res.staves, ns) for s in res.staves}
    near = lambda lst, x, y, r=0.5: [t for t in lst if abs(t[0] - x) <= r * sp and abs(t[1] - y) <= r * sp]
    c = Counter()
    rows = []
    for h in heads:
        x, y = h["cx"], h["cy"]
        lab = [l for l in L if abs(l["x"] - x) <= 0.7 * sp and abs(l["y"] - y) <= 0.5 * sp]
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))
        if lab:
            try:
                tp = M.truth_pitch(x, y, res.staves, clefs)
            except Exception:
                continue
            if lab[0]["pitch"] != tp[1]:
                tclef = tp[3]          # truth_pitch = (보표, 음고, 반칸, 음자리표)
                pclef = ctx[st.index].clef if st.index in ctx else "treble"
                if tclef and tclef != pclef:
                    c[("음고", "음자리표(바뀜 · 오판)")] += 1
                    c[("음자리표 다름의 확신도", lab[0]["confidence"])] += 1
                else:
                    d = step(lab[0]["pitch"]) - step(tp[1])
                    c[("음고", f"반칸 {d:+d}" if abs(d) <= 2 else ("옥타브" if abs(d) in (7, 14) else "기타"))] += 1
                    if abs(d) == 1:
                        rel = (y - st.top) / sp
                        c[("반칸 자리", "오선 위 덧줄 구역" if rel < -0.3 else "오선 아래 덧줄 구역" if rel > 4.3 else "오선 안")] += 1
            continue
        hdr = ctx[st.index].header_end if st.index in ctx else 0
        up, down = margins[st.index]
        box = res.binary[int(y - 0.4 * sp):int(y + 0.4 * sp), int(x - 0.55 * sp):int(x + 0.55 * sp)]
        if x < hdr:
            stage = "헤더 안"
        elif near(S["base_final"], x, y) or near(S["rescue_final"], x, y):
            stage = "최종 음표 있음 · 라벨 짝 실패"
        elif near(S["base_off"], x, y) or near(S["rescue_off"], x, y):
            stage = "임시표 유령 필터"
        elif near(S["base_beam"], x, y) or near(S["rescue_beam"], x, y):
            stage = "보표 밖 유령 필터"
        elif near(S["base_det"], x, y) or near(S["rescue_det"], x, y):
            stage = "빔 유령 필터"
        elif near(S["base_rej"] + S["rescue_rej"], x, y):
            stage = "검출 내부 필터(" + near(S["base_rej"] + S["rescue_rej"], x, y)[0][2] + ")"
        elif not (st.top - up + 0.5 * sp <= y <= st.bottom + down - 0.5 * sp):
            stage = "머리 검색 띠 밖"
        elif (float((box > 0).mean()) if box.size else 0) < 0.25:
            stage = "잉크 부족"
        else:
            stage = "머리 후보 없음 · 모양 판정"
        chord = sum(1 for o in heads if o is not h and abs(o["cx"] - x) <= 0.6 * sp and abs(o["cy"] - y) <= 2 * sp) > 0
        c[("누락", stage)] += 1
        rows.append(dict(page=name, x=x, y=y, staff=st.index, name=h["name"], stage=stage, hdr=hdr, sp=sp))
        c[("누락 범주", "화음" if chord else "단독")] += 1
    return name, c, rows


def main():
    import measure_a17_ghost6 as G
    jobs = [j for j in G.UNSEEN if j[0] != "organ2"]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    tot = Counter()
    for _n, c, _r in res:
        tot.update(c)
    for kind in ("누락", "누락 범주", "음고", "반칸 자리", "음자리표 다름의 확신도"):
        v = {k[1]: n for k, n in tot.items() if k[0] == kind}
        print(f"{kind} {sum(v.values())}: " + " · ".join(f"{k} {n}" for k, n in sorted(v.items(), key=lambda t: -t[1])))
    for name, c, _r in res:
        print("  ", name, "누락", sum(n for k, n in c.items() if k[0] == "누락"), "· 음고", sum(n for k, n in c.items() if k[0] == "음고"))


if __name__ == "__main__":
    main()
