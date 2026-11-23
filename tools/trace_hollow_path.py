# -*- coding: utf-8 -*-
"""빈 음표가 왜 filled로 남는지 — 검출기 사본에 **기록 줄만** 넣어 경로를 가른다.

사본은 원본 notehead_detect.py 텍스트에 기록 두 줄을 끼운 것이다. 실행 전 원본과
검출 결과가 **완전히 같은지** 대조하고, 다르면 중단한다.
"""
import importlib.util
import json
import math
import os
import sys
import types
from collections import Counter

REPO = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import modules.notehead_detect as ORIG  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402

src = open(os.path.join(REPO, "modules", "notehead_detect.py"), encoding="utf-8").read()
A = "    # 합친 뒤에야 '구멍 하나로서 그럴듯한 크기인가'를 판정한다\n"
B = "    # 3도 간격으로 붙은 빈 음표 화음은"
C = "    # ---- 중복 제거 (가까운 좌표 병합) ----\n"
# 채택 여부는 **추정하지 말고** 실제 `accepted_holes`를 읽는다. 가리는 덩어리가 나중에
# 지워지는 것과 구멍이 채택되는 것은 별개다(실측: 쇼팽 D♭ (2174,2831)에서 갈렸다).
D = "    if accepted_holes:\n"
assert src.count(A) == 1 and src.count(B) == 1 and src.count(C) == 1
src = src.replace(A, "    _DBG.append(dict(staff=staff.index, sp=spacing, top=top, "
                     "patched=_hole_rects(patched), band_h=_hole_rects(band), enclosed=_enclosed_rects(), "
                     "merged=_merge_split_holes(_hole_rects(patched) + _hole_rects(band) + _enclosed_rects()), "
                     "comps=cv2.connectedComponentsWithStats(opened)[2]))\n" + A)
src = src.replace(B, "    _DBG[-1].update(cands=list(hollow_candidates), raw_before=list(raw))\n" + B)
src = src.replace(C, "    _DBG[-1].update(raw_after=list(raw))\n" + C)
assert src.count(D) == 1
src = src.replace(D, "    _DBG[-1].update(accepted=list(accepted_holes))\n" + D)
DBG = types.ModuleType("modules.notehead_detect")
DBG.__file__ = ORIG.__file__
DBG._DBG = []
exec(compile(src, "nd_trace", "exec"), DBG.__dict__)


def run(pdf):
    res = preprocess(pdf, pdf_dpi=300)
    ctx = analyze_staves(res)
    a = ORIG.detect_noteheads(res, contexts=ctx)
    DBG._DBG.clear()
    b = DBG.detect_noteheads(res, contexts=ctx)
    assert [(h.x, h.y, h.staff_index, h.filled) for h in a] == \
           [(h.x, h.y, h.staff_index, h.filled) for h in b], "사본이 원본과 다르다"
    return res, ctx, b, list(DBG._DBG)


def classify(dbg_by_staff, staff, x, y):
    """(x,y) 머리에 대해 구멍 경로가 어떻게 됐나."""
    d = dbg_by_staff[staff]
    sp, top = d["sp"], d["top"]
    near = lambda rx, ry, rw, rh: abs(rx + rw / 2 - x) <= sp * 0.9 and abs(ry + top + rh / 2 - y) <= sp * 0.8
    src = {k: sum(1 for r in d[k] if near(*r)) for k in ("patched", "band_h", "enclosed")}
    cands = [c for c in d["cands"] if abs(c[0] - x) <= sp * 0.9 and abs(c[1] - y) <= sp * 0.8]
    if not cands:
        way = "구멍없음(원천)" if not any(src.values()) else "구멍후보는있으나 크기/글자 필터 탈락"
        return way, src, None
    c = cands[0]
    if c[2] is None:
        return "구멍 채택", src, None
    blk = d["raw_before"][c[2]]
    kept = any(abs(r[0] - blk[0]) < 0.5 and abs(r[1] - blk[1]) < 0.5 for r in d["raw_after"])
    blob_h = (blk[4] - blk[3]) / sp
    return ("구멍이 filled에 가려짐" if kept else "가린 filled가 링조각으로 제거→구멍 채택"), src, \
        dict(blocker_x=round(blk[0] - x, 1), blocker_h_sp=round(blob_h, 2),
             hole_cy_in_blob=blk[3] - sp * 0.75 <= c[1] <= blk[4] + sp * 0.75)


if __name__ == "__main__":
    mode = sys.argv[2]
    if mode == "fixture":
        fix = os.path.join(REPO, "tests", "fixtures", "hollow_notes")
        for size in (16, 20, 24):
            exp = json.load(open(os.path.join(fix, f"expected_{size}.json"), encoding="utf-8"))
            res, ctx, heads, dbg = run(os.path.join(fix, exp["pdf"]))
            by = {d["staff"]: d for d in dbg}
            tally = Counter()
            detail = []
            for n in exp["notes"]:
                x0, y0, x1, y1 = [v * 300 / 72 for v in n["bbox_pt"]]
                hs = [h for h in heads if h.staff_index == n["staff_index"] and x0 <= h.x <= x1 and y0 <= h.y <= y1]
                if not hs:
                    tally[(n["duration_denominator"], "검출없음")] += 1
                    continue
                h = hs[0]
                cx, cy = n["center_300dpi"]
                way, srcs, info = classify(by, n["staff_index"], cx, cy)
                key = (n["duration_denominator"], "filled" if h.filled else "빈", way)
                tally[key] += 1
                if h.filled and n["duration_denominator"] == 1:
                    detail.append((n["id"], round(h.x - cx, 1), srcs, info))
            print(f"== 크기 {size} sp={by[0]['sp']:.1f}")
            for k, v in sorted(tally.items(), key=str):
                print(f"   {k}: {v}")
            for d in detail[:12]:
                print("     온음표filled", d)

    if mode == "real":
        import cv2
        import numpy as np
        pages = [("bach", "test_scores/bach_minuet_Am.pdf", 0), ("bbm1", "test_scores/chopin_nocturne_Bbm.pdf", 0),
                 ("db1", "test_scores/chopin_nocturne_Db_6-8.pdf", 0), ("em1", "test_scores/chopin_nocturne_Em.pdf", 0),
                 ("aoharu1", "sample_images/KakaoTalk_20260731_162400402.png", 0)]
        out_dir = sys.argv[3]
        os.makedirs(out_dir, exist_ok=True)
        for name, path, pg in pages:
            res = preprocess(os.path.join(REPO, path), pdf_page=pg)
            ctx = analyze_staves(res)
            a = ORIG.detect_noteheads(res, contexts=ctx)
            DBG._DBG.clear()
            b = DBG.detect_noteheads(res, contexts=ctx)
            assert [(h.x, h.y, h.filled) for h in a] == [(h.x, h.y, h.filled) for h in b]
            tally = Counter()
            blocked = []
            for d in DBG._DBG:
                sp = d["sp"]
                for cx, cy, blk, _y0, _y1 in d["cands"]:
                    if blk is None:
                        tally["구멍 채택"] += 1
                        continue
                    bb = d["raw_before"][blk]
                    kept = any(abs(r[0] - bb[0]) < .5 and abs(r[1] - bb[1]) < .5 for r in d["raw_after"])
                    if not kept:
                        tally["가린 filled 제거→채택"] += 1
                        continue
                    tally["가려짐(버림)"] += 1
                    blocked.append(dict(staff=d["staff"], x=cx, y=cy, bx=bb[0], by=bb[1],
                                        bh=(bb[4] - bb[3]) / sp, dx=(bb[0] - cx) / sp, sp=sp))
            n_hollow = sum(1 for h in b if not h.filled)
            print(f"== {name}: 머리 {len(b)} (빈 {n_hollow}) | 구멍 후보 {dict(tally)}")
            # 가려진 구멍 격자
            img = res.original_bgr
            tiles = []
            for k, r in enumerate(blocked):
                sp = r["sp"]
                x, y = int(r["x"]), int(r["y"])
                R = int(sp * 1.8)
                t = img[max(0, y - R):y + R, max(0, x - R):x + R].copy()
                ox, oy = min(R, x), min(R, y)
                cv2.circle(t, (ox, oy), 2, (255, 0, 0), -1)
                cv2.drawMarker(t, (int(r["bx"] - x + ox), int(r["by"] - y + oy)), (0, 0, 255), cv2.MARKER_CROSS, 6, 1)
                t = cv2.resize(t, None, fx=100 / max(1, t.shape[0]), fy=100 / max(1, t.shape[0]))
                t = cv2.copyMakeBorder(t, 14, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                cv2.putText(t, f"{k}", (2, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 120, 0), 1)
                tiles.append(cv2.resize(t, (104, 116)))
            if tiles:
                cols = 12
                rows = [np.hstack(tiles[i:i + cols] + [np.full_like(tiles[0], 200)] * (cols - len(tiles[i:i + cols])))
                        for i in range(0, len(tiles), cols)]
                open(os.path.join(out_dir, f"blocked_{name}.png"), "wb").write(cv2.imencode(".png", np.vstack(rows))[1].tobytes())
            json.dump(blocked, open(os.path.join(out_dir, f"blocked_{name}.json"), "w"), default=float, indent=0)
            print(f"   가려진 구멍 {len(blocked)}개 — dx(sp) 분포 {Counter(round(abs(r['dx']) * 2) / 2 for r in blocked)}  "
                  f"blob h(sp) {Counter(round(r['bh'], 1) for r in blocked).most_common(6)}")
