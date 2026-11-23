# -*- coding: utf-8 -*-
"""A-18 (c) 막대 연속성 — 끊긴 진짜 ♯ 7건 vs A-18 가짜 막대: 「닫힘 전 최장 연속 잉크」 실측 (2026-09-30, 제품 코드 무변경).

(c) 규칙: 막대 구간에서 원 이진 영상(오선 제거 · 세로 닫힘 전)의 최장 연속 잉크 < 제품 막대 하한 1.5sp면 뺀다.
사진 세트에서 (c)가 진짜 ♯ 막대를 뺀 7건(바흐 파# → 파)과 A-18 가짜 막대 5건을 음표 하나씩 판정하며
창 안 막대마다 (쪽 x · 위 · 아래 · 닫힌 길이 · 최장 연속 잉크 · 음표 기준 dx)를 적는다. 기록만 하는 변형(a18probe)이라 판정은 c12 그대로.

    python tools/measure_a18_sharp_ink.py        → debug/a18_sharp_ink.json + 표
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import measure_a17_ghost6 as G  # noqa: E402
import measure_a18_bach_photo as B  # noqa: E402

REAL_SHARP = [("ph_bach__noise_focus_blur", 1084, 1356), ("ph_bach__noise_focus_blur", 2149, 1356),
              ("ph_bach__rotation_1deg", 2427, 1634), ("ph_bach__rotation_2deg", 1362, 1634),
              ("ph_bach__rotation_5deg", 1362, 1634), ("ph_bach__rotation_2deg__blackframe", 1302, 1574),
              ("ph_bach__rotation_2deg__graydesk", 1145, 1396)]
A18_FAKE = [("ph_bach__rotation_2deg", 945, 705), ("ph_bach__rotation_3deg", 945, 705), ("ph_bach__rotation_5deg", 946, 705),
            ("ph_bach__rotation_2deg__blackframe", 885, 645), ("ph_bach__rotation_2deg__graydesk", 728, 467)]


def main():
    import measure_normalize_sp as N
    G.set_variant("a18probe")
    G.install(True)
    paths = {f"ph_{os.path.splitext(f)[0]}": os.path.join(d, f) for d in (N.SYN, N.EDGE) for f in os.listdir(d)}
    out = []
    cache = {}
    for group, cases in (("진짜 ♯(c가 뺌)", REAL_SHARP), ("A-18 가짜", A18_FAKE)):
        for name, x, y in cases:
            if name not in cache:
                res = B.C.preprocess(paths[name], pdf_page=0, photo=True)
                ctx = B.C.analyze_staves(res)
                cache.clear()
                cache[name] = (res, ctx, B.A.pipeline_notes(res, ctx))
            res, ctx, notes = cache[name]
            n = min(notes, key=lambda m: abs(m.x - x) + abs(m.y - y))
            sp = next(s.spacing for s in res.staves if s.index == n.staff_index)
            G.LAST["res"] = res
            G.A18_GAPS.clear()
            raw = B.A.raw_judgments(res, ctx, [n])[0]
            bars = sorted({(b[0], b[1], b[2], b[5]) for b in G.A18_GAPS})
            rec = dict(group=group, photo=name, note=(int(n.x), int(n.y)), sp=round(sp, 2), raw=raw,
                       bars=[dict(x=bx, top=t, bottom=bt, closed_sp=round((bt - t + 1) / sp, 2), ink_sp=round(ink / sp, 2),
                                  dx_sp=round((bx - n.x) / sp, 2)) for bx, t, bt, ink in bars])
            out.append(rec)
            print(group, name[3:], rec["note"], "c12 원시", raw or "없음", "\n   ",
                  " | ".join(f"x{b['x']} dx{b['dx_sp']} 닫힘 {b['closed_sp']} · 연속 {b['ink_sp']}" for b in rec["bars"]), flush=True)
    json.dump(out, open(os.path.join(ROOT, "debug", "a18_sharp_ink.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
