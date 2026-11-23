# -*- coding: utf-8 -*-
"""사람 확인에서 나온 「확실」 유령 두 유형 측정 (2026-10-12, 제품 코드 무변경 · 측정만).

[1] 겹빔 사이 흰 틈 → 빈 머리 유령 (Verovio bach_bwv846_bravura_p1 첫 시스템 오른손 위)
[2] 셈여림 「p」 → 빈 머리 유령 (beethoven_op18no1_bravura_p1)

라벨: `measure_sim_ledger_pair.py run main1012`(지금 main 제품 run_page 출력, 측정 함정 A-3b). 정답 대응: 가까운 쌍부터 1:1(가로 0.7sp · 세로 0.5sp).
라벨마다 판정 없이 값만 남긴다(오선 제거 영상 `remove_staff_lines` 위):
  위 · 아래 막대  중심 ±0.3sp 열에서 위/아래로 첫 잉크까지 거리(gap) · 그 잉크의 세로 두께(thick) · 그 막대 가운데 행의 가로 런(run, x를 지나는) — 열 중앙값
  LU LD RU RD    `verify._side_runs`(글리프 모양 규칙과 같은 값)
  stem           후보 행을 지나는 세로 잉크 최장(중심 ±0.9sp 열, sp) — `_has_stem`과 같은 창
  off            오선 밖 거리(sp, 안이면 0) · ledger = `verify.ledger_check`
  kind           그 자리 기호 — Verovio SVG 상자 종류 · PDF 글리프 이름(0.6sp 안 가장 가까운 것, 없으면 「선」)

    python tools/measure_beamgap_dynamic.py rows      # debug/beamgap_dynamic.json
    python tools/measure_beamgap_dynamic.py report
    python tools/measure_beamgap_dynamic.py crops <규칙>   # docs/review/beamgap_dynamic/<규칙>_*.png
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LAB = os.path.join(ROOT, "debug", "sim_lp", "main1012")
OUT = os.path.join(ROOT, "debug", "beamgap_dynamic.json")


def _bar(ns, x, y, sp, step):
    """중심 ±0.3sp 열마다 위(step=-1)/아래(+1)로 첫 잉크까지 거리 · 두께, 그 막대 가운데 행의 가로 런 (sp, 열 중앙값)."""
    H, W = ns.shape
    lim = int(sp * 1.0)
    gaps, thicks, mids = [], [], []
    for c in range(max(0, int(x - 0.3 * sp)), min(W, int(x + 0.3 * sp) + 1)):
        r, g = y, 0
        while 0 <= r < H and not ns[r, c] and g <= lim:
            r += step
            g += 1
        if g > lim or not (0 <= r < H):
            gaps.append(np.inf)
            continue
        t = 0
        r0 = r
        while 0 <= r < H and ns[r, c]:
            r += step
            t += 1
        gaps.append(g)
        thicks.append(t)
        mids.append(r0 + step * (t // 2))
    if not thicks or np.median(gaps) == np.inf:
        return None, 0.0, 0.0
    m = int(np.median(mids))
    row = ns[m]
    a = b = int(x)
    if not row[a]:
        near = [c for c in range(max(0, int(x - 0.3 * sp)), min(W, int(x + 0.3 * sp) + 1)) if row[c]]
        if not near:
            return round(float(np.median(gaps)) / sp, 2), round(float(np.median(thicks)) / sp, 2), 0.0
        a = b = near[len(near) // 2]
    while a > 0 and row[a - 1]:
        a -= 1
    while b + 1 < W and row[b + 1]:
        b += 1
    return round(float(np.median(gaps)) / sp, 2), round(float(np.median(thicks)) / sp, 2), round((b - a + 1) / sp, 2)


def _stem(ns, x, y, sp):
    H, W = ns.shape
    best = 0
    for c in range(max(0, int(x - 0.9 * sp)), min(W, int(x + 0.9 * sp) + 1)):
        if not ns[y, c]:
            continue
        u = d = y
        while u - 1 >= 0 and ns[u - 1, c]:
            u -= 1
        while d + 1 < H and ns[d + 1, c]:
            d += 1
        best = max(best, d - u + 1)
    return round(best / sp, 2)


def _kinds(st, name, path, pg, labels, sp):
    """라벨마다 그 자리 기호 종류. Verovio = SVG 상자(머리 · 덧줄 · 기둥 제외), PDF = 가장 가까운 글리프 이름."""
    if st == "verovio":
        import measure_verovio as V
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [[k for k in V.box_hits(t["boxes"], l["x"], l["y"]) if k not in ("ledger", "stem")] for l in labels]
    if st == "aoharu":
        return [[] for _ in labels]
    import measure_omission_rate as M
    g = [q for q in M.pdf_glyphs(path, pg, ("",)) if not q["name"].startswith("noteheads.")]
    out = []
    for l in labels:
        near = [(abs(q["cx"] - l["x"]) + abs(q["cy"] - l["y"]), q["name"]) for q in g
                if abs(q["cx"] - l["x"]) <= 0.6 * sp + q["w"] / 2 and abs(q["cy"] - l["y"]) <= 0.6 * sp + q["h"] / 2]
        out.append([min(near)[1]] if near else [])
    return out


def _page(job):
    st, name, path, pg = job
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules import verify as VF
    import measure_sim_ledger_pair as S
    js = os.path.join(LAB, name + ".json")
    if not os.path.exists(js):
        return []
    labels = json.load(open(js, encoding="utf-8"))["labels"]
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ns = remove_staff_lines(res.binary, res.staves) > 0
    by = {s.index: s for s in res.staves}
    sp_page = float(np.median([s.spacing for s in res.staves]))
    if st == "aoharu":
        err = [""] * len(labels)
    else:
        heads, _ = S._truth(st, name, path, pg)
        used, err = set(), []
        idx = sorted(range(len(labels)), key=lambda i: labels[i]["x"])
        err = [None] * len(labels)
        for i in idx:
            l = labels[i]
            cand = [(abs(h[0] - l["x"]) + abs(h[1] - l["y"]), j) for j, h in enumerate(heads)
                    if j not in used and abs(h[0] - l["x"]) <= 0.7 * sp_page and abs(h[1] - l["y"]) <= 0.5 * sp_page]
            if cand:
                used.add(min(cand)[1])
                err[i] = ""
            else:
                err[i] = "유령"
    kinds = _kinds(st, name, path, pg, labels, sp_page)
    rows = []
    for l, e, k in zip(labels, err, kinds):
        staff = by.get(l["staff"]) or min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - l["y"]))
        sp = staff.spacing
        x, y = int(l["x"]), int(l["y"])
        gu, tu, ru = _bar(ns, x, y, sp, -1)
        gd, td, rd = _bar(ns, x, y, sp, 1)
        off = max(0.0, (staff.top - y) / sp, (y - staff.bottom) / sp)
        led = VF.ledger_check(res.binary, staff, x, y)
        rows.append(dict(set=st, page=name, path=path, pg=pg, x=x, y=y, sp=round(sp, 2), text=l["text"], conf=l["confidence"],
                         flags=l["flags"], err=e, kind=k, gu=gu, tu=tu, ru=ru, gd=gd, td=td, rd=rd,
                         center=bool(ns[y, x]), stem=_stem(ns, x, y, sp), off=round(off, 2),
                         ledger=None if led is None else bool(led), **VF._side_runs(ns, x, y, sp)))
    return rows


def rows():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        R = [r for part in ex.map(_page, S.pages()) for r in part]
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("라벨", len(R), "· 쪽", len({r["page"] for r in R}))


def is_dyn(r):
    return any(k == "dynam" or k.startswith("dynamics.") for k in r["kind"])


def is_beam(r):
    return "beam" in r["kind"] or (r["set"] in ("pdf", "unseen") and not r["kind"])


# 규칙 — 판정은 제품이 아니라 여기서만(시뮬레이션). 문턱은 report의 분포에서 고른다
RULES = {
    # [1] 위 · 아래가 굵은 가로 막대로 막힌 흰 칸: 중심 흰색 · 위아래 첫 잉크가 가깝고(≤ 0.5sp) 두껍고(≥ T) 머리 폭보다 길다(≥ R)
    "sandwich": lambda r, T=0.4, R=1.5: (not r["center"] and r["gu"] is not None and r["gd"] is not None
                                          and r["gu"] <= 0.5 and r["gd"] <= 0.5
                                          and r["tu"] >= T and r["td"] >= T and r["ru"] >= R and r["rd"] >= R),
    # [1] 구현판(§1-31): 위 sandwich에 두께 상한 0.6(화음 이웃 머리 0.81~0.86 제외)
    "beamgap": lambda r: (not r["center"] and r["gu"] is not None and r["gd"] is not None and r["gu"] <= 0.5 and r["gd"] <= 0.5
                          and min(r["tu"], r["td"]) >= 0.4 and max(r["tu"], r["td"]) <= 0.6 and min(r["ru"], r["rd"]) >= 1.5),
    # [2] 좁은 구멍: 기둥 없는(< 2.5sp, `_has_stem`과 같은 길이) 오선 밖 흰 중심인데 위 · 아래 막대가 둘 다 짧다(≤ M).
    #     머리 링의 위 · 아래 테두리는 머리 폭만큼 가로로 이어진다(진짜 최소 0.82sp) — 「p」 고리 속은 좁다(셈여림 유령 대부분 ≤ 0.45)
    "narrow": lambda r, M=0.6: (r["off"] > 0 and r["stem"] < 2.5 and not r["center"] and r["gu"] is not None
                                and r["gd"] is not None and max(r["ru"], r["rd"]) <= M),
}


def q(v, ps=(0, 5, 50, 95, 100)):
    v = sorted(v)
    return " ".join(f"{p}%={np.percentile(v, p):.2f}" for p in ps) if v else "—"


def report():
    R = json.load(open(OUT, encoding="utf-8"))
    true = [r for r in R if r["err"] != "유령"]
    gh = [r for r in R if r["err"] == "유령"]
    print(f"라벨 {len(R)} · 진짜(정답 짝) {len(true)} · 유령 {len(gh)}")
    for st in ("pdf", "unseen", "verovio", "aoharu"):
        v = [r for r in gh if r["set"] == st]
        print(f"  {st}: 유령 {len(v)} · 확실 {sum(r['conf'] == 'certain' for r in v)}")

    print("\n[1] 겹빔 틈 — 위·아래 막대 값 분포")
    bg = [r for r in gh if is_beam(r) and not r["center"] and r["gu"] is not None and r["gd"] is not None]
    tw = [r for r in true if not r["center"] and r["gu"] is not None and r["gd"] is not None]
    for nm, v in (("빔 자리 유령(흰 중심)", bg), ("진짜 머리(흰 중심)", tw)):
        print(f"  {nm} {len(v)}: min(tu,td) {q([min(r['tu'], r['td']) for r in v])}")
        print(f"     min(ru,rd) {q([min(r['ru'], r['rd']) for r in v])} · max(gu,gd) {q([max(r['gu'], r['gd']) for r in v])}")
    for T in (0.3, 0.35, 0.4):
        for Rr in (1.3, 1.5, 1.8):
            f = lambda r: RULES["sandwich"](r, T, Rr)
            h = [r for r in R if f(r)]
            print(f"  T={T} R={Rr}: 걸림 {len(h)} · 유령 {sum(r['err'] == '유령' for r in h)} · 진짜 {sum(r['err'] != '유령' for r in h)}"
                  f" · 확실 유령 {sum(r['err'] == '유령' and r['conf'] == 'certain' for r in h)}"
                  f" · 확실 진짜 {sum(r['err'] != '유령' and r['conf'] == 'certain' for r in h)}")

    print("\n[2] 셈여림 자리 라벨")
    dy = [r for r in R if is_dyn(r)]
    print(f"  {len(dy)}: {dict(Counter((r['set'], r['err'] or '짝', r['conf']) for r in dy))}")
    dg = [r for r in dy if r["err"] == "유령"]
    tn = [r for r in true if r["off"] > 0 and r["stem"] < 2.5 and not r["center"]]
    for nm, v in (("셈여림 유령", dg), ("진짜 · 오선 밖 · 기둥 없음 · 흰 중심", tn)):
        print(f"  {nm} {len(v)}: LD {q([r['LD'] for r in v])} · RD {q([r['RD'] for r in v])} · stem {q([r['stem'] for r in v])}")
    for L in (0.5, 0.6, 0.7):
        h = [r for r in R if RULES["pglyph"](r, L)]
        print(f"  L={L}: 걸림 {len(h)} · 유령 {sum(r['err'] == '유령' for r in h)}(셈여림 {sum(r['err'] == '유령' and is_dyn(r) for r in h)})"
              f" · 진짜 {sum(r['err'] != '유령' for r in h)} · 확실 유령 {sum(r['err'] == '유령' and r['conf'] == 'certain' for r in h)}"
              f" · 확실 진짜 {sum(r['err'] != '유령' and r['conf'] == 'certain' for r in h)}")


def crops(rule, *args):
    """규칙에 걸린 라벨 전부를 격자로(유령 · 진짜 따로). 빨간 원 = 라벨 자리, 제목 = 쪽 좌표 확신도."""
    import cv2
    R = json.load(open(OUT, encoding="utf-8"))
    f = RULES[rule]
    a = [float(x) for x in args]
    hit = [r for r in R if f(r, *a)]
    d = os.path.join(ROOT, "docs", "review", "beamgap_dynamic")
    os.makedirs(d, exist_ok=True)
    from modules.preprocess import load_image
    cache = {}
    for tag, v in (("ghost", [r for r in hit if r["err"] == "유령"]), ("true", [r for r in hit if r["err"] != "유령"])):
        tiles = []
        for r in v:
            k = (r["path"], r["pg"])
            if k not in cache:
                cache[k] = cv2.cvtColor(load_image(os.path.join(ROOT, r["path"]), pdf_page=r["pg"]), cv2.COLOR_BGR2GRAY)
            g = cache[k]
            h = int(r["sp"] * 3)
            c = np.full((2 * h, 2 * h), 255, np.uint8)
            y0, x0 = r["y"] - h, r["x"] - h
            sub = g[max(0, y0):r["y"] + h, max(0, x0):r["x"] + h]
            c[max(0, -y0):max(0, -y0) + sub.shape[0], max(0, -x0):max(0, -x0) + sub.shape[1]] = sub
            c = cv2.cvtColor(cv2.resize(c, (160, 160)), cv2.COLOR_GRAY2BGR)
            cv2.circle(c, (80, 80), 5, (0, 0, 255), 1)
            c = cv2.copyMakeBorder(c, 14, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(c, f"{r['page'][:14]} {r['x']},{r['y']} {r['conf'][:2]}", (2, 10), cv2.FONT_HERSHEY_PLAIN, 0.7, (0, 0, 0), 1)
            tiles.append(c)
        for i in range(0, len(tiles), 60):
            part = tiles[i:i + 60]
            part += [np.full_like(part[0], 255)] * (-len(part) % 10)
            img = np.vstack([np.hstack(part[j:j + 10]) for j in range(0, len(part), 10)])
            p = os.path.join(d, f"{rule}_{tag}_{i // 60}.png")
            open(p, "wb").write(cv2.imencode(".png", img)[1].tobytes())
            print(p, len(part))


if __name__ == "__main__":
    {"rows": rows, "report": report, "crops": crops}[sys.argv[1]](*sys.argv[2:])
