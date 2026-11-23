# -*- coding: utf-8 -*-
"""A-18 바흐 회전 사진 「도 → 도#」 원인 조사 (2026-09-30, 제품 코드 무변경).

A-17 결합안(c12 = 후보 1 넓은 밴드 + 후보 2 자기 머리 막대 제외)이 바흐 회전 사진에서 C5 하나를 C#5로 바꿨다.
사진 변형 전부에서 **같은 음표**(같은 보표 · x순 같은 번째)를 찾아 기준 · c12의 판정 창 막대를 쪽 좌표로 적는다.

실행: python tools/measure_a18_bach_photo.py            → debug/a18_bach.json + 표 출력
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import check_accidental_fix as C  # noqa: E402
import measure_a17 as A  # noqa: E402
import measure_a17_cand12 as T  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402

OUT = os.path.join(ROOT, "debug", "a17_cand1")
REF = ("ph_bach__rotation_2deg", 945, 705)          # 회귀가 처음 보인 자리(A-18 1번)


def ordinal(labels, x, y):
    """(보표, 그 보표 x순 번째) — 사진 변형끼리 같은 음표를 맞추는 열쇠."""
    me = min(labels, key=lambda l: abs(l["x"] - x) + abs(l["y"] - y))
    row = sorted((l for l in labels if l["staff"] == me["staff"]), key=lambda l: (l["x"], l["y"]))
    return me["staff"], row.index(me), me


def spy_run(res, ctx, note, mode):
    """한 음표의 원시 판정 + 창 안 막대 · 글리프(창 좌표)."""
    log = {}
    fb, fg, tg = AD._find_thin_bars, AD._find_glyphs, T.ORIG_GLYPHS

    def bars(p, sp):
        out = fb(p, sp)
        log.setdefault("bars", [(float(x), int(s), int(e)) for x, s, e in out])
        return out

    def glyphs(p, sp, _f=None):
        out = (_f or fg)(p, sp)
        log["glyphs"] = [(k, round(float(y), 1)) for k, y in out]
        return out

    AD._find_thin_bars = bars
    AD._find_glyphs = glyphs
    keep = AD.annotate_accidentals
    try:
        if mode == "c12":
            T.ORIG_GLYPHS = lambda p, sp: glyphs(p, sp, tg)
            AD.annotate_accidentals = T.MODES["c12"]
        log["raw"] = A.raw_judgments(res, ctx, [note])[0]
    finally:
        AD._find_thin_bars, AD._find_glyphs, T.ORIG_GLYPHS = fb, fg, tg
        AD.annotate_accidentals = keep
    return log


def main():
    global PATHS
    import measure_normalize_sp as N
    PATHS = {f"ph_{os.path.splitext(f)[0]}": os.path.relpath(os.path.join(d, f), ROOT)
             for d in (N.SYN, N.EDGE) for f in os.listdir(d) if f.lower().endswith((".png", ".jpg"))}
    base = json.load(open(os.path.join(OUT, "base_photo", REF[0] + ".json"), encoding="utf-8"))["labels"]
    staff, k, me = ordinal(base, REF[1], REF[2])
    print("기준 음표", REF, "보표", staff, "번째", k, me["pitch"], me["text"])
    rows = []
    for js in sorted(glob.glob(os.path.join(OUT, "base_photo", "ph_bach__*.json"))):
        name = os.path.basename(js)[:-5]
        labs = json.load(open(js, encoding="utf-8"))["labels"]
        row = sorted((l for l in labs if l["staff"] == staff), key=lambda l: (l["x"], l["y"]))
        if k >= len(row) or row[k]["pitch"] != me["pitch"]:
            print(name, "같은 음표 못 맞춤(건너뜀)")
            continue
        lab = row[k]
        cand = json.load(open(os.path.join(OUT, "c12_photo", name + ".json"), encoding="utf-8"))["labels"]
        after = next((l["text"] for l in cand if abs(l["x"] - lab["x"]) <= 2 and abs(l["y"] - lab["y"]) <= 2), "(없음)")
        path = os.path.join(ROOT, PATHS[name])        # 합성 세트 · M1 경계 세트 두 폴더, .png · .jpg 섞임
        res = C.preprocess(path, pdf_page=0, photo=True)
        ctx = C.analyze_staves(res)
        notes = A.pipeline_notes(res, ctx)
        n = min(notes, key=lambda n: abs(n.x - lab["x"]) + abs(n.y - lab["y"]))
        st = next(s for s in res.staves if s.index == n.staff_index)
        sp = st.spacing
        top = max(0, int(st.top - sp * 3.5))
        x0 = max(0, int(n.x - sp * 2.0))
        y0 = max(0, int(n.y - top - sp * 2.0))
        # 앞 음표(같은 보표, 바로 왼쪽) — 막대가 무엇인지 짚는 기준
        prev = max((m for m in notes if m.staff_index == n.staff_index and m.x < n.x - 0.3 * sp), key=lambda m: m.x, default=None)
        rec = dict(photo=name, note=(int(n.x), int(n.y)), sp=round(sp, 2), base_label=lab["text"], c12_label=after,
                   prev=(int(prev.x), int(prev.y)) if prev else None, note_y_in_patch=round(n.y - top - y0, 1))
        for mode in ("base", "c12"):
            lg = spy_run(res, ctx, n, mode)
            # 창 좌표 → 쪽 좌표 · 음표 기준 sp
            rec[mode] = dict(raw=lg["raw"], glyphs=lg.get("glyphs", []),
                             bars=[dict(x=int(x0 + bx), top=int(top + y0 + s), bottom=int(top + y0 + e),
                                        len_sp=round((e - s + 1) / sp, 2), dx_note_sp=round((x0 + bx - n.x) / sp, 2),
                                        dx_prev_sp=round((x0 + bx - prev.x) / sp, 2) if prev else None,
                                        clipped_top=s == 0)
                                   for bx, s, e in lg.get("bars", [])])
        rows.append(rec)
        print(f"{name:42s} {rec['base_label']:>4s} → {rec['c12_label']:<5s} 기준 {rec['base']['raw'] or '없음':8s} c12 {rec['c12']['raw'] or '없음':8s} "
              f"막대(쪽 x · 길이sp · 앞 음표 기준 dx) " + ", ".join(f"({b['x']} · {b['len_sp']} · {b['dx_prev_sp']}{' 위잘림' if b['clipped_top'] else ''})"
                                                            for b in rec["base"]["bars"]))
    json.dump(rows, open(os.path.join(ROOT, "debug", "a18_bach.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
