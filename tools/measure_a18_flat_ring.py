# -*- coding: utf-8 -*-
"""A-18 (c) 막대 연속성 적용 뒤 「도 → 도b」 — 창 안 ♭ 고리의 출처 추적 (2026-09-30, 제품 코드 무변경).

(c) 사본(`measure_a17_ghost6` 변형 a18c)으로 바흐 회전 사진 5장 + 원본의 같은 음표를 판정하며,
창(쪽 좌표) · 남은 막대 · ♭ 고리 윤곽(쪽 좌표 상자 · 크기 sp)을 적고 고리를 이루는 잉크가 무엇인지 원 이진 · 오선 제거 · 닫힘 단계로 본다.

실행: python tools/measure_a18_flat_ring.py → debug/a18_flat_ring.json + 표
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import measure_a17_ghost6 as G  # noqa: E402
import measure_a18_bach_photo as B  # noqa: E402

CASES = [("ph_bach__original", 667, 427), ("ph_bach__rotation_2deg", 945, 705), ("ph_bach__rotation_3deg", 945, 705),
         ("ph_bach__rotation_5deg", 946, 705), ("ph_bach__rotation_2deg__blackframe", 885, 645),
         ("ph_bach__rotation_2deg__graydesk", 728, 467)]
LOG = {}


def spy_fixed(patch, sp):
    out = ORIG_FIXED(patch, sp)
    band = patch.base
    off = patch.__array_interface__["data"][0] - band.__array_interface__["data"][0]
    r0, c0 = divmod(off, band.strides[0])
    c0 //= band.strides[1]
    top = G.BAND_TOP.get(band.__array_interface__["data"][0])
    if top is None:                      # c12fix_annotate 밖(파이프라인 준비 중 제품 판정)으로 새어 든 호출 — 기록 안 함
        return out
    small = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    contours, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    rings = []
    if hier is not None:
        for i, c in enumerate(contours):
            if hier[0][i][3] == -1:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if sp * 0.25 <= w <= sp * 0.9 and sp * 0.25 <= h <= sp * 0.9:
                rings.append(dict(x0=c0 + x, y0=top + r0 + y, x1=c0 + x + w - 1, y1=top + r0 + y + h - 1,
                                  w_sp=round(w / sp, 2), h_sp=round(h / sp, 2), cy_patch=y + h / 2))
    LOG.setdefault("calls", []).append(dict(origin=(int(c0), int(top + r0)), size=patch.shape, glyphs=[(k, round(float(v), 1)) for k, v in out],
                                            bars=[(int(c0 + b[0]), int(top + r0 + b[1]), int(top + r0 + b[2])) for b in G.T.ORIG_BARS(patch, sp)],
                                            rings=rings))
    return out


def main():
    global ORIG_FIXED
    G.set_variant("a18c")
    G.install(True)
    ORIG_FIXED = G.fixed_glyphs
    import measure_normalize_sp as N
    paths = {f"ph_{os.path.splitext(f)[0]}": os.path.join(d, f) for d in (N.SYN, N.EDGE) for f in os.listdir(d)}
    rows = []
    for name, x, y in CASES:
        res = B.C.preprocess(paths[name], pdf_page=0, photo=True)
        ctx = B.C.analyze_staves(res)
        notes = B.A.pipeline_notes(res, ctx)
        n = min(notes, key=lambda m: abs(m.x - x) + abs(m.y - y))
        prev = max((m for m in notes if m.staff_index == n.staff_index and m.x < n.x - 0.3 * 20), key=lambda m: m.x)
        G.LAST["res"] = res
        LOG.clear()

        keep = G.fixed_glyphs
        G.fixed_glyphs = spy_fixed
        try:
            raw = B.A.raw_judgments(res, ctx, [n])[0]
        finally:
            G.fixed_glyphs = keep
        call = LOG["calls"][-1] if LOG.get("calls") else {}
        sp = float(np.median([s.spacing for s in res.staves]))
        rec = dict(photo=name, note=(int(n.x), int(n.y)), prev=(int(prev.x), int(prev.y)), sp=round(sp, 2), raw=raw, **call)
        # 고리마다: 앞 음표 머리 중심과의 거리, 원 이진 · 오선 제거 뒤 고리 테두리가 닫혀 있나
        ns = G.AD.remove_staff_lines(res.binary, res.staves)
        for r in rec.get("rings", []):
            r["dx_prev_sp"] = round(((r["x0"] + r["x1"]) / 2 - prev.x) / sp, 2)
            r["dy_prev_sp"] = round(((r["y0"] + r["y1"]) / 2 - prev.y) / sp, 2)
            box = (slice(r["y0"] - 2, r["y1"] + 3), slice(r["x0"] - 2, r["x1"] + 3))
            inside = (slice(r["y0"], r["y1"] + 1), slice(r["x0"], r["x1"] + 1))
            r["원이진_속잉크비"] = round(float((res.binary[inside] > 0).mean()), 2)
            r["오선제거_속잉크비"] = round(float((ns[inside] > 0).mean()), 2)
            r["원이진_테두리잉크비"] = round(float((res.binary[box] > 0).mean()), 2)
        rows.append(rec)
        print(name, "원시", raw or "없음", "음표", rec["note"], "앞 음표", rec["prev"], "창 원점", call.get("origin"),
              "\n   막대(쪽 x, 위, 아래)", call.get("bars"), "\n   글리프", call.get("glyphs"),
              "\n   ♭ 고리", [{k: v for k, v in r.items() if k != "cy_patch"} for r in rec.get("rings", [])], flush=True)
    json.dump(rows, open(os.path.join(ROOT, "debug", "a18_flat_ring.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
