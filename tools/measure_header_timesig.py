# -*- coding: utf-8 -*-
"""[2] 박자표 없는 줄의 헤더 끝 — 「조표 끝 뒤 박자표 숫자가 없으면 헤더 끝 = 조표 끝 + 여유」 사본 시뮬레이션. 제품 코드 무변경.

헤더 2차 패스(`analyze_staves`)는 조표 끝(base) 뒤 3sp 안 진한 잉크 블록을 박자표로 보고 `_extend_over_timesig`로 늘린다.
변형: 그 보표에서 `_timesig_span_end`(맨 윗줄 · 맨 아랫줄에 동시에 잉크가 있는 숫자 폭 열)가 base ~ base + TS_SP 안에서
아무것도 못 찾으면 늘리지 않고 base + 여유. 첫 시스템 박자표 처리(들여쓰기 판정 뒤 `_timesig_span_end`)는 그대로.

  dist   정답 머리로 여유 유도 — 조표가 있는 보표의 base에서 그 보표 첫 정답 머리 왼끝(cx − 0.6sp)까지 거리(sp) 분포,
         지금 헤더 끝이 첫 머리를 덮는 보표 수.
  run    변형 라벨 → debug/sim_lp/hdr (measure_sim_ledger_pair 방식).

    python tools/measure_header_timesig.py dist
    python tools/measure_header_timesig.py run
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
TS_SP = 2.0
MARGIN_SP = 0.5      # dist: 조표 끝 → 첫 머리 왼끝 최소 0.55sp(348보표) 아래


def _heads(st, name, path, pg):
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"]) for n in t["notes"]]
    if st == "aoharu":
        return None
    from measure_normalize_sp import truth_at
    return [(h["cx"], h["cy"]) for h in truth_at(path, pg, 1.0)[0]]


def _dist(job):
    import modules.clef_keysig as CK
    from modules.preprocess import preprocess
    st_, name, path, pg = job
    heads = _heads(*job)
    if heads is None:
        return []
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = CK.analyze_staves(res)
    out = []
    for s in res.staves:
        c = ctx.get(s.index)
        if c is None or not c.clef_found or not c.key_count:
            continue
        sp = s.spacing
        base = max(c.clef_end, int(max(b for b, _y in c.bars) + 0.5 * sp)) if c.bars else c.clef_end
        mine = [x for x, y in heads if s.top - 4 * sp <= y <= s.bottom + 4 * sp and x > c.clef_end]
        if not mine:
            continue
        first = min(mine)
        out.append(dict(page=name, staff=s.index, gap=round((first - 0.6 * sp - base) / sp, 2),
                        hdr_over=c.header_end > first, hdr_gap=round((c.header_end - base) / sp, 2)))
    return out


def dist():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_dist, [p for p in S.pages() if p[1] != "organ2"]) for r in part]
    g = sorted(r["gap"] for r in rows)
    print(f"조표 있는 보표 {len(rows)} · base → 첫 머리 왼끝(sp) 최소 · 1 · 5 · 50%: {g[0]} · {np.percentile(g, 1):.2f} · {np.percentile(g, 5):.2f} · {np.median(g):.2f}")
    print("  가장 작은 10:", sorted(rows, key=lambda r: r["gap"])[:10])
    print("  지금 헤더가 첫 머리를 덮는 보표:", sum(r["hdr_over"] for r in rows), dict(Counter(r["page"] for r in rows if r["hdr_over"])))


CUR = {}


def install():
    import modules.clef_keysig as CK
    if CUR.get("on"):
        return
    CUR["on"] = True
    o_prof, o_ext = CK._restricted_profile, CK._extend_over_timesig

    def prof(no_staff, staff, img_h):
        CUR["ns"], CUR["staff"] = no_staff, staff
        return o_prof(no_staff, staff, img_h)

    def ext(ink_cnt, sp, base, W, thin=0):
        if "staff" in CUR:
            st, ns = CUR.pop("staff"), CUR["ns"]
            lim = ns[:, :min(ns.shape[1], base + int(TS_SP * sp) + int(2.6 * sp))]
            if CK._timesig_span_end(lim, st, base) == base:
                return base + int(MARGIN_SP * sp)
        return o_ext(ink_cnt, sp, base, W, thin)
    CK._restricted_profile, CK._extend_over_timesig = prof, ext


if __name__ == "__main__":
    if sys.argv[1] == "dist":
        dist()
