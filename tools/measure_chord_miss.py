# -*- coding: utf-8 -*-
"""[4] 화음 누락 — 단계별 분해 · 누락이 큰 쪽의 공통점 (2026-10-12 · 측정만, 제품 코드 무변경).

**보류(holdout) 세트는 쓰지 않는다**(DECISIONS §3 원칙 9). 세트: PDF 17쪽 · 보지 않은 8쪽(월광 4 · 빗방울 4, 오르간 제외) · Verovio 20쪽.
라벨: 지금 main 제품(`debug/sim_lp/<이름>`). 누락 = 정답 머리 중 라벨 짝이 없는 것(`measure_omission_rate.match`, 가로 0.7 · 세로 0.5sp 1:1).
화음 = 같은 쪽 정답 머리 중 가로 0.6sp · 세로 1.05sp 안에 다른 머리가 있는 것(Verovio 측정과 같은 정의).
단계(`measure_missing_verovio._one`과 같은 순서를 제품 함수로 다시 돈다): 보표 없음 → 헤더 안 → 최종 음표 있음 · 라벨 짝 실패 →
  임시표 유령 필터 → 보표 밖 유령 필터 → 빔 유령 필터 → 검출 내부 필터(reject_log 사유: 링 좌우 벽 · 옆 중복 · 이음매 · 글자 …) →
  머리 검색 띠 밖 → 머리 후보 없음(이진화 잉크 부족 / 모양 판정). 붙은 화음 구제 경로(rescue)도 같은 단계로 따로 기록한다.
머리마다 속성: 화음 크기(같은 덩어리 머리 수) · 2도 이웃(세로 ≤ 0.65sp 이웃 머리) · 빈/꽉 찬 · 덧줄 구역 · 쪽 sp.

    python tools/measure_chord_miss.py trace [라벨=beamgap1012]   # debug/chord_miss.json
    python tools/measure_chord_miss.py report
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "chord_miss.json")
HOLLOW_PDF = ("noteheads.s0", "noteheads.s1", "noteheads.sM1")


def pages():
    import measure_sim_ledger_pair as S
    return [p for p in S.pages() if p[0] != "aoharu" and p[1] != "organ2"]


def truth(st, name, path, pg):
    """[(x, y, 빈 머리?)] — 꾸밈음 · 작은 음표는 뺀다."""
    if st == "verovio":
        import measure_verovio as V
        t = json.load(open(os.path.join(V.OUT, "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"], n["glyph"] in V.HOLLOW_GLYPHS) for n in t["notes"] if not n["grace"] and not n["cue"]]
    from measure_normalize_sp import truth_at
    return [(h["cx"], h["cy"], h["name"].startswith(HOLLOW_PDF)) for h in truth_at(path, pg, 1.0)[0]]


def _stages(path, pg):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts, filled_flags
    from modules.chord_rescue import detect_noteheads_rescue
    from modules import notehead_detect as ND
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    clef = {i: c.clef for i, c in ctx.items()}
    out = {}
    for tag, det in (("base", detect_noteheads), ("rescue", detect_noteheads_rescue)):
        rej = []
        heads = det(res, contexts=ctx, reject_log=rej)
        out[tag + "_det"] = [(h.x, h.y) for h in heads]
        out[tag + "_rej"] = [(r["x"], r["y"], r["reason"]) for r in rej]
        h1, _ = drop_beam_ghosts(res, heads)
        out[tag + "_beam"] = [(h.x, h.y) for h in h1]
        h2, _ = drop_offstaff_ghosts(res, h1)
        out[tag + "_off"] = [(h.x, h.y) for h in h2]
        notes = calculate_pitches(h2, res.staves, clef=clef)
        accs = annotate_accidentals(res, ctx, notes)
        kept, _a = remove_accidental_ghosts(notes, accs, res.staves, filled=filled_flags(notes, h2), result=res)
        out[tag + "_final"] = [(n.x, n.y) for n in kept]
    out["header"] = {i: c.header_end for i, c in ctx.items()}
    ns = ND.remove_staff_lines(res.binary, res.staves)
    out["margins"] = {s.index: ND._band_margins(s, res.staves, ns) for s in res.staves}
    out["staves"] = [(s.index, s.top, s.bottom, s.spacing) for s in res.staves]
    return out, res.binary


def _stage(st, x, y, sp, binary, tag):
    near = lambda lst, r=0.5: any(abs(a - x) <= r * sp and abs(b - y) <= r * sp for a, b, *_ in lst)
    if not st["staves"]:
        return "보표 없음"
    stf = min(st["staves"], key=lambda s: abs((s[1] + s[2]) / 2 - y))
    if abs((stf[1] + stf[2]) / 2 - y) > 8 * sp:
        return "보표 없음"
    if x < st["header"].get(stf[0], 0):
        return "헤더 안"
    if near(st[tag + "_final"]):
        return "최종 음표 있음 · 라벨 짝 실패"
    if near(st[tag + "_off"]):
        return "임시표 유령 필터"
    if near(st[tag + "_beam"]):
        return "보표 밖 유령 필터"
    if near(st[tag + "_det"]):
        return "빔 유령 필터"
    if near(st[tag + "_rej"]):
        why = next(c for a, b, c in st[tag + "_rej"] if abs(a - x) <= 0.5 * sp and abs(b - y) <= 0.5 * sp)
        return f"검출 내부 필터({why})"
    m = st["margins"][stf[0]]
    if not (stf[1] - m[0] + 0.5 * sp <= y <= stf[2] + m[1] - 0.5 * sp):
        return "머리 검색 띠 밖"
    box = binary[int(y - 0.4 * sp):int(y + 0.4 * sp), int(x - 0.55 * sp):int(x + 0.55 * sp)]
    return "머리 후보 없음 · 이진화 잉크 부족" if (box > 0).mean() < 0.25 else "머리 후보 없음 · 모양 판정"


def _page(job):
    lab, (st, name, path, pg) = job
    import measure_omission_rate as M
    heads = truth(st, name, path, pg)
    labels = json.load(open(os.path.join(ROOT, "debug", "sim_lp", lab, name + ".json"), encoding="utf-8"))["labels"]
    stg, binary = _stages(path, pg)
    sp = float(np.median([s[3] for s in stg["staves"]])) if stg["staves"] else 20.0
    hd = [dict(cx=x, cy=y) for x, y, _h in heads]
    pairs, _ut, _ul = M.match(hd, labels, sp)
    got = {i for i, _j in pairs}
    rows = []
    for i, (x, y, hollow) in enumerate(heads):
        mates = [j for j, (a, b, _h) in enumerate(heads) if j != i and abs(a - x) <= 0.6 * sp and abs(b - y) <= 1.05 * sp]
        # 화음 크기: 가로 0.6sp 안 · 세로로 1.05sp씩 이어지는 사슬
        group, todo = {i}, [i]
        while todo:
            k = todo.pop()
            for j, (a, b, _h) in enumerate(heads):
                if j not in group and abs(a - heads[k][0]) <= 0.6 * sp and abs(b - heads[k][1]) <= 1.05 * sp:
                    group.add(j)
                    todo.append(j)
        second = any(abs(heads[j][1] - y) <= 0.65 * sp for j in mates)
        stf = min(stg["staves"], key=lambda s: abs((s[1] + s[2]) / 2 - y)) if stg["staves"] else None
        ledger = bool(stf) and not (stf[1] - 0.3 * sp <= y <= stf[2] + 0.3 * sp)
        r = dict(set=st, page=name, x=round(x, 1), y=round(y, 1), sp=round(sp, 2), chord=bool(mates), size=len(group),
                 second=second, hollow=bool(hollow), ledger=ledger, missed=i not in got)
        if r["missed"]:
            r["stage"] = _stage(stg, x, y, sp, binary, "base")
            r["stage_rescue"] = _stage(stg, x, y, sp, binary, "rescue")
        rows.append(r)
    return rows


def trace(lab="beamgap1012"):
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        R = [r for part in ex.map(_page, [(lab, p) for p in pages()]) for r in part]
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("정답 머리", len(R), "· 누락", sum(r["missed"] for r in R), "· 쪽", len({r["page"] for r in R}))


def report():
    R = json.load(open(OUT, encoding="utf-8"))
    pct = lambda a, b: f"{a}/{b} ({a / max(1, b) * 100:.1f}%)"
    for st in ("pdf", "unseen", "verovio", None):
        v = [r for r in R if st is None or r["set"] == st]
        ch = [r for r in v if r["chord"]]
        si = [r for r in v if not r["chord"]]
        print(f"[{st or '합계'}] 화음 비중 {pct(len(ch), len(v))} · 화음 누락 {pct(sum(r['missed'] for r in ch), len(ch))} · 단일 누락 {pct(sum(r['missed'] for r in si), len(si))}")
    ch = [r for r in R if r["chord"]]
    miss = [r for r in ch if r["missed"]]
    print("\n화음 누락 단계(기본 경로 · 구제 경로가 같은 단계면 하나로):")
    for k, n in Counter(r["stage"] for r in miss).most_common():
        sub = [r for r in miss if r["stage"] == k]
        print(f"  {k:40s} {n:4d} · 세트 {dict(Counter(r['set'] for r in sub))} · 구제 경로 단계 {dict(Counter(r['stage_rescue'] for r in sub).most_common(3))}")
    print("\n화음 머리 속성별 누락률:")
    for nm, f in (("2도 이웃 있음", lambda r: r["second"]), ("2도 이웃 없음", lambda r: not r["second"]),
                  ("빈 머리", lambda r: r["hollow"]), ("꽉 찬 머리", lambda r: not r["hollow"]),
                  ("덧줄 구역", lambda r: r["ledger"]), ("오선 안", lambda r: not r["ledger"]),
                  ("화음 크기 2", lambda r: r["size"] == 2), ("크기 3", lambda r: r["size"] == 3), ("크기 ≥ 4", lambda r: r["size"] >= 4)):
        v = [r for r in ch if f(r)]
        print(f"  {nm:12s} {pct(sum(r['missed'] for r in v), len(v))}")
    print("\n쪽별(화음 누락률 높은 순):")
    pg = defaultdict(list)
    for r in R:
        pg[r["page"]].append(r)
    rows = []
    for p, v in pg.items():
        ch = [r for r in v if r["chord"]]
        cm = sum(r["missed"] for r in ch)
        rows.append((cm / max(1, len(ch)), p, v[0]["sp"], len(v), len(ch), cm,
                     np.mean([r["size"] for r in ch]) if ch else 0, np.mean([r["second"] for r in ch]) if ch else 0,
                     np.mean([r["hollow"] for r in ch]) if ch else 0))
    for rate, p, sp, n, nc, cm, size, sec, hol in sorted(rows, reverse=True):
        print(f"  {p:38s} sp {sp:5.2f} · 머리 {n:4d} · 화음 {nc:4d}({nc / n * 100:3.0f}%) · 화음 누락 {cm:3d}({rate * 100:4.1f}%) · 평균 크기 {size:.2f} · 2도 {sec * 100:3.0f}% · 빈 {hol * 100:3.0f}%")
    # 쪽 속성과 화음 누락률의 순위 상관(스피어만)
    from scipy.stats import spearmanr
    arr = np.array([(r[0], r[2], r[4] / r[3], r[6], r[7], r[8]) for r in rows if r[4] >= 20])
    for k, nm in enumerate(("sp", "화음 비중", "평균 화음 크기", "2도 비율", "빈 머리 비율"), 1):
        rho, p = spearmanr(arr[:, 0], arr[:, k])
        print(f"  쪽 화음 누락률 ~ {nm}: ρ={rho:+.2f} (p={p:.3f}, 화음 ≥ 20인 {len(arr)}쪽)")


if __name__ == "__main__":
    {"trace": trace, "report": report}[sys.argv[1]](*sys.argv[2:])
