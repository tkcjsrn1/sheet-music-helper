# -*- coding: utf-8 -*-
"""(d) 줄 중간 조표 증거 — 마디선 바로 뒤 창에서 조표를 읽을 수 있나(검출률 · 오검출). 제품 코드 무변경.

보표마다 마디선(`accidental_detect._propagation_barlines`, 전파 경계와 같은 함수) 뒤 0.3sp부터 그 마디 첫 라벨 0.4sp 앞까지(≥ 1sp)를 창으로,
제품 `clef_keysig._find_bars`(머리 조표 막대 검출과 같은 함수)로 막대를 모으고 같은 시스템 보표끼리 제품 `_vote_key_signature`(§1-10)로 읽는다.
읽힌 조표가 있으면 「증거」. 정답: Verovio SVG 보표별 keysigs 중 둘째부터(줄 중간 조바꿈). 그 밖의 증거는 오검출.
시스템: Verovio = SVG system, 그 밖 = 보표 두 개씩. 라벨 = 현재 main 제품 JSON.

    python tools/measure_midline_keysig.py
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _set_min(n):
    global MIN_STAVES
    MIN_STAVES = n


LAST_BARS = {}


def _attached_gap(cs, ks):
    """증거의 보표마다 마지막 조표 막대 오른쪽에서 같은 높이(±1칸) 라벨까지 가로 거리(sp) — 보표들 중 최소.
    기보 규칙: 임시표는 바로 오른쪽 같은 높이 음표에 붙는다 / 조표 글리프 바로 오른쪽에는 그 글리프가 꾸미는 음표가 없다.
    글리프 높이: ♯ = 마지막 두 막대 평균, ♭ = 막대 − FLAT_STEM_OFFSET_STEP(막대는 ♭ 기둥, 머리는 그 아래)."""
    import modules.clef_keysig as CK
    best = None
    for si, (_c, bx) in cs.items():
        bars, sp, labs = LAST_BARS[(si, round(bx))]
        if not bars:
            continue
        bars = sorted(bars)
        xr = bars[-1][0]
        st = (bars[-1][1] + bars[-2][1]) / 2 if ks == "♯" and len(bars) > 1 else bars[-1][1] - CK.FLAT_STEM_OFFSET_STEP
        d = [(x - xr) / sp for x, step in labs if x > xr and abs(step - st) <= 1.0]
        if d and (best is None or min(d) < best):
            best = round(min(d), 2)
    return best


def _page(job):
    import modules.clef_keysig as CK
    from modules import accidental_detect as AD
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg, lab = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = CK.analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    L = json.load(open(lab, encoding="utf-8"))["labels"]
    staves = sorted(res.staves, key=lambda s: s.top)
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        if len(t["staves"]) != len(staves):
            return kind, name, [], []
        sys_of = {s.index: ts["system"] for s, ts in zip(staves, t["staves"])}
        truth = sorted({(sys_of[s.index], round(k["x"]), k["val"]) for s, ts in zip(staves, t["staves"]) for k in ts["keysigs"][1:]})
    else:
        sys_of = {s.index: i // 2 for i, s in enumerate(staves)}
        truth = []
    # 보표마다 마디선 뒤 창의 막대
    win = defaultdict(dict)       # (시스템, 마디선 x 묶음) → {보표: StaffContext}
    for s in staves:
        sp = s.spacing
        pts = sorted((l["x"], l["y"]) for l in L if l["staff"] == s.index)
        if len(pts) < 2:
            continue
        for bx in AD._propagation_barlines(res.binary, ns, s, pts):
            nxt = [x for x, _y in pts if x > bx]
            if not nxt:
                continue
            top = max(0, int(s.top - sp * 3))
            band = ns[top:min(H, int(s.bottom + sp * 3)), :]
            r0 = max(0, int(s.top - top - sp * 1.5))
            r1 = min(band.shape[0], int(s.bottom - top + sp * 1.5) + 1)
            # 창 끝: 머리 조표 스캔과 같은 「막대 간격이 벌어지는 곳」(`_keysig_scan_end`). 첫 판(그 마디 첫 라벨 앞)은
            # 새 조표의 ♭ 글리프 자체가 유령 라벨이 되어 창이 거의 0이었다(Clara 1 B (1124, 2051) 「시b」 등)
            x0 = int(bx + 0.3 * sp)
            x1 = CK._keysig_scan_end(band, sp, x0, r0, r1, band.shape[1])
            if x1 - x0 < sp:
                continue
            bars, holes = CK._find_bars(band, sp, x0, x1, r0, r1)
            c = CK.StaffContext(clef=ctx[s.index].clef if s.index in ctx else "treble", clef_found=True, spacing=sp,
                                bars=tuple((x, (s.grid_bottom - (top + y)) / (sp / 2.0)) for x, y in bars), holes=holes)
            win[(sys_of[s.index], round(bx / (2 * sp)))][s.index] = (c, bx)
            LAST_BARS[(s.index, round(bx))] = (c.bars, sp, [(l["x"], l["step"]) for l in L if l["staff"] == s.index])
    found = []
    for (sy, _k), cs in win.items():
        if len(cs) < MIN_STAVES:
            continue
        kc, ks, _r = CK._vote_key_signature({i: c for i, (c, _b) in cs.items()})
        if kc:
            found.append((sy, round(min(b for _c, b in cs.values())), f"{kc}{'s' if ks == '♯' else 'f'}", len(cs),
                          _attached_gap(cs, ks)))
    return kind, name, truth, found


MIN_STAVES = 1


def main():
    import check_accidental_fix as C
    jobs = [("pdf", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES]
    U = "output/unseen-scores-20260829/sources/"
    jobs += [("unseen", f"moon{p + 1}", U + "moonlight-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"moon{p + 1}.json")) for p in (0, 1, 10, 17)]
    jobs += [("unseen", f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"rain{p + 1}.json")) for p in range(4)]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0, os.path.join(ROOT, "debug", "vrv_a25impl", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(3, initializer=_set_min, initargs=(MIN_STAVES,)) as ex:
        res = list(ex.map(_page, jobs))
    json.dump(res, open(os.path.join(ROOT, "debug", "midline_keysig.json"), "w", encoding="utf-8"), ensure_ascii=False)
    gaps = {"진짜": [], "오검출": []}
    c = Counter()
    for kind, name, truth, found in res:
        used = set()
        for sy, x, val in truth:
            hit = [f for f in found if f[0] == sy and x - 4 * 18 <= f[1] <= x and f[2] == val]
            near = [f for f in found if f[0] == sy and x - 4 * 18 <= f[1] <= x]
            c[(kind, "정답 조바꿈")] += 1
            c[(kind, "검출(값 맞음)")] += bool(hit)
            c[(kind, "검출(값 틀림)")] += bool(near) and not hit
            used.update(id(f) for f in near)
            gaps["진짜"] += [f[4] for f in hit]
            if not near:
                print("  놓침", name, sy, x, val, "| 그 시스템 증거", [f for f in found if f[0] == sy])
        fps = [f for f in found if id(f) not in used]
        c[(kind, "오검출")] += len(fps)
        gaps["오검출"] += [f[4] for f in fps]
        for f in fps[:3]:
            print("  오검출", kind, name, f)
    for kind in ("verovio", "pdf", "unseen"):
        print(kind, {k[1]: v for k, v in c.items() if k[0] == kind})
    for k, v in gaps.items():
        print(f"{k}: 마지막 막대 → 같은 높이 라벨 거리 sp(없음 = None)", sorted(v, key=lambda t: (t is None, t or 0)))


if __name__ == "__main__":
    MIN_STAVES = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main()
