# -*- coding: utf-8 -*-
"""큐 1 — 머리 빈 ↔ 꽉 참 엇갈림(RHYTHM_SCOPE §6의 68)을 원인별로 가른다 (2026-10-19 · 측정만, 제품 코드 무변경).

짝짓기는 `measure_rhythm_base.py`와 같다(가로 0.7sp · 세로 0.5sp 안 가장 가까운 머리, 꾸밈음 · 작은 음표 제외).
구멍 경로는 `trace_hollow_path.py`의 기록 사본으로 읽는다(원본과 검출 결과가 같은지 매 쪽 대조).

    python tools/classify_hollow_mismatch.py [출력폴더]      # 기본 debug/hollow_mismatch
출력: mismatch.tsv(한 줄 = 엇갈림 하나) · grid.png(번호 = tsv 순서, 가운데 + = 정답 좌표)
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
FILLED = {"E0A4"}
HOLLOW = {"E0A3", "E0A2"}


def staff_pos(st, y):
    """맨 아랫줄에서 반칸 단위 위치 — 짝수 = 줄 위, 홀수 = 칸. 0 ~ 8 밖이면 덧줄 구역."""
    return int(round((st.line_ys[-1] - y) / (st.spacing / 2)))


def main():
    import cv2
    import numpy as np
    import trace_hollow_path as T
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves

    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "debug", "hollow_mismatch")
    os.makedirs(out, exist_ok=True)
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    rows, crops = [], []
    for f in sorted(os.listdir(D)):
        if not f.endswith("_p1.json"):
            continue
        nm = f[:-5]
        T_all = json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"]
        notes = [n for n in T_all if not (n["grace"] or n["cue"])]
        png = os.path.join(ROOT, "test_scores", "verovio", nm + ".png")
        res = preprocess(png)
        ctx = analyze_staves(res)
        a = T.ORIG.detect_noteheads(res, contexts=ctx)
        T.DBG._DBG.clear()
        heads = T.DBG.detect_noteheads(res, contexts=ctx)
        assert [(h.x, h.y, h.staff_index, h.filled) for h in a] == \
               [(h.x, h.y, h.staff_index, h.filled) for h in heads], "사본이 원본과 다르다"
        dbg = {d["staff"]: d for d in T.DBG._DBG}
        gray = cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        sp0 = 18.0
        for n in notes:
            if n["glyph"] not in FILLED | HOLLOW:
                continue
            near = [h for h in heads if abs(h.x - n["x"]) <= 0.7 * sp0 and abs(h.y - n["y"]) <= 0.5 * sp0]
            if not near:
                continue
            h = min(near, key=lambda h: abs(h.x - n["x"]) + abs(h.y - n["y"]))
            truth_filled = n["glyph"] in FILLED
            if truth_filled == h.filled:
                continue
            st = res.staves[h.staff_index]
            sp = st.spacing
            pos = staff_pos(st, n["y"])
            # 정답 이웃: 같은 열(가로 1.6sp) 안 세로 2.6sp 안 다른 음 — 2도 · 3도 화음 · 성부 겹침
            nb = [m for m in T_all if m is not n and abs(m["x"] - n["x"]) <= 1.6 * sp and abs(m["y"] - n["y"]) <= 2.6 * sp]
            nb_desc = ",".join(f"{'빈' if m['glyph'] in HOLLOW else '꽉' if m['glyph'] in FILLED else m['glyph']}"
                               f"{(m['y'] - n['y']) / sp:+.1f}/{(m['x'] - n['x']) / sp:+.1f}" for m in nb)
            if truth_filled:
                way = "꽉→빈"
                # 제품 빈 머리가 이웃 빈 음의 구멍인가(짝이 옆 음표로 붙음) · 자기 자리 구멍인가
                hol_nb = [m for m in nb if m["glyph"] in HOLLOW]
                detail = "이웃 빈 음과 짝" if any(abs(h.x - m["x"]) + abs(h.y - m["y"]) <
                                               abs(h.x - n["x"]) + abs(h.y - n["y"]) for m in hol_nb) else "자기 자리 구멍"
                info = ""
            else:
                way = "빈→꽉"
                detail, srcs, inf = T.classify(dbg, h.staff_index, n["x"], n["y"])
                info = json.dumps(inf or srcs, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
            rows.append(dict(page=nm, x=round(n["x"]), y=round(n["y"]), pitch=f"{n['note_name']}{n['octave']}",
                             glyph=n["glyph"], way=way, pos=pos,
                             zone="덧줄" if pos < -1 or pos > 9 else "줄" if pos % 2 == 0 else "칸",
                             chord=n["chord"], detail=detail, neighbors=nb_desc, info=info,
                             head=f"{h.x},{h.y}", sp=round(sp, 1)))
            r = int(3 * sp)
            cx, cy = int(round(n["x"])), int(round(n["y"]))
            pad = cv2.copyMakeBorder(gray, r, r, r, r, cv2.BORDER_CONSTANT, value=255)
            c = cv2.cvtColor(pad[cy:cy + 2 * r, cx:cx + 2 * r], cv2.COLOR_GRAY2BGR)
            c = cv2.resize(c, (128, 128), interpolation=cv2.INTER_AREA)
            cv2.drawMarker(c, (64, 64), (0, 0, 255) if way == "빈→꽉" else (255, 0, 0), cv2.MARKER_CROSS, 10, 1)
            cv2.putText(c, str(len(rows)), (2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 140, 0), 1)
            crops.append(c)
        print(nm, len(rows), flush=True)

    keys = list(rows[0].keys()) if rows else []
    with open(os.path.join(out, "mismatch.tsv"), "w", encoding="utf-8") as fp:
        fp.write("#\t" + "\t".join(keys) + "\n")
        for i, r in enumerate(rows, 1):
            fp.write(f"{i}\t" + "\t".join(str(r[k]) for k in keys) + "\n")
    if crops:
        cols = 10
        blank = np.full_like(crops[0], 255)
        crops += [blank] * (-len(crops) % cols)
        grid = np.vstack([np.hstack(crops[i:i + cols]) for i in range(0, len(crops), cols)])
        open(os.path.join(out, "grid.png"), "wb").write(cv2.imencode(".png", grid)[1].tobytes())
    print("합계", len(rows))
    for k, v in sorted(Counter((r["way"], r["detail"]) for r in rows).items()):
        print("  ", k, v)
    for k, v in sorted(Counter((r["way"], r["zone"]) for r in rows).items()):
        print("  ", k, v)


if __name__ == "__main__":
    main()
