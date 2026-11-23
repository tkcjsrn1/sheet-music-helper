# -*- coding: utf-8 -*-
"""TASKS [2](c) ♮ → ♯ 뒤바뀜 — ♮ · ♯ 두 세로획의 뻗음 분포를 세 조판에서 잰다. 제품 코드 무변경.

제품 ♮ 조건(`accidental_detect._find_glyphs`): 왼쪽 막대(s1, e1) · 오른쪽 막대(s2, e2)가 **위끝 · 아래끝 둘 다** 0.45sp 넘게 어긋남
(s1 + 0.45sp < s2 그리고 e1 + 0.45sp < e2). 판정 입력(막대 시작 · 끝)은 `measure_a17.probe`로 원본 함수를 가로채 읽는다(측정 함정 A-1 · B-4).

정답 글리프: PDF 17쪽 = PDF 글리프(`measure_a17.truth`, LilyPond), Verovio 20쪽 = SVG 임시표 상자(Bravura · Leipzig).
글리프 상자 안 막대 둘(왼쪽 끝 · 오른쪽 끝)만 쓴다 — 기둥 · 머리 가장자리 쌍과 섞지 않는다.

    python tools/measure_natural_sharp.py collect     → debug/natural_sharp/strokes.json
    python tools/measure_natural_sharp.py report
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "natural_sharp")


def _strokes(res, ctx, sp, notes, A, hx, hy, box):
    """정답 머리 (hx, hy)에 붙는 최종 음표의 판정 입력에서, 글리프 상자 안 막대 둘의 절대 y 시작 · 끝."""
    cand = [n for n in notes if abs(n.x - hx) <= 0.7 * sp and abs(n.y - hy) <= 0.5 * sp]
    if not cand:
        return dict(status="음표 없음")
    n = min(cand, key=lambda n: abs(n.x - hx) + abs(n.y - hy))
    p = A.probe(res, ctx, n)
    x0 = int(n.x - sp * 2.0)
    if n.staff_index in ctx:
        x0 = max(x0, ctx[n.staff_index].header_end + int(sp * 0.2))
    y0 = n.y - p["note_y_in_patch"]                          # 패치 원점의 절대 y
    bx0, by0, bx1, by1 = box
    own = [b for b in p.get("bars", []) if bx0 - 2 <= x0 + b["x"] <= bx1 + 2]
    rec = dict(raw=p["raw"] or "없음", note=(n.x, n.y), sp=sp, box=[round(v, 1) for v in box], n_bars=len(own),
               found=p.get("found"))
    if len(own) >= 2:
        a, b = own[0], own[-1]
        rec.update(status="막대 둘", L=(x0 + a["x"], y0 + a["s"], y0 + a["e"]), R=(x0 + b["x"], y0 + b["s"], y0 + b["e"]))
    else:
        rec["status"] = f"막대 {len(own)}"
    return rec


def _pdf_page(job):
    import measure_a17 as A
    name, path, pg = job
    res, ctx, sp, notes, _src = A.final_notes(path, pg)
    glyphs, _sk, _h = A.truth(path, pg, res, ctx)
    from measure_omission_rate import pdf_glyphs
    boxes = {(round(q["cx"]), round(q["oy"])): q for q in pdf_glyphs(path, pg, ("accidentals.",))}
    rows = []
    for t in glyphs:
        if t["kind"] not in ("#", "natural"):
            continue
        q = boxes[(round(t["gx"]), round(t["gy"]))]
        box = (q["cx"] - q["w"] / 2, q["cy"] - q["h"] / 2, q["cx"] + q["w"] / 2, q["cy"] + q["h"] / 2)
        rows.append(dict(set="pdf", font="LilyPond", page=name, kind=t["kind"], glyph=(round(t["gx"]), round(t["gy"])),
                         **_strokes(res, ctx, t["sp"], notes, A, t["hx"], t["hy"], box)))
    return rows


def _vrv_page(stem):
    import measure_a17 as A
    t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", stem + ".json"), encoding="utf-8"))
    res, ctx, sp, notes, _src = A.final_notes(os.path.join("test_scores", "verovio", stem + ".png"), 0)
    rows = []
    for h in t["notes"]:
        if h["grace"] or h["cue"] or h["accidental"] not in ("#", "natural") or not h["acc_box"]:
            continue
        rows.append(dict(set="verovio", font="Bravura" if "bravura" in stem else "Leipzig", page=stem, kind=h["accidental"],
                         glyph=(round(h["acc_box"][0]), round(h["y"])), **_strokes(res, ctx, sp, notes, A, h["x"], h["y"], h["acc_box"])))
    return rows


def collect():
    import check_accidental_fix as C
    os.makedirs(OUT, exist_ok=True)
    pdf = [j for j in C.PAGES if j[1].endswith(".pdf")]
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "test_scores", "verovio")) if f.endswith("_p1.png"))
    with ProcessPoolExecutor(4) as ex:
        rows = [r for part in ex.map(_pdf_page, pdf) for r in part] + [r for part in ex.map(_vrv_page, stems) for r in part]
    json.dump(rows, open(os.path.join(OUT, "strokes.json"), "w", encoding="utf-8"), ensure_ascii=False, default=list)
    print("글리프", len(rows))


def features(r):
    """두 획의 뻗음(sp): 위끝 차 dt = s2 − s1, 아래끝 차 db = e2 − e1, 길이, 상자 대비 끝."""
    sp = r["sp"]
    (_x1, s1, e1), (_x2, s2, e2) = r["L"], r["R"]
    by0, by1 = r["box"][1], r["box"][3]
    return dict(dt=(s2 - s1) / sp, db=(e2 - e1) / sp, lenL=(e1 - s1 + 1) / sp, lenR=(e2 - s2 + 1) / sp,
                # 상자 위끝 · 아래끝에서 각 획 끝까지(양수 = 획이 상자 안쪽에서 끝남 = 잘림)
                L_top_in=(s1 - by0) / sp, L_bot_in=(by1 - e1) / sp, R_top_in=(s2 - by0) / sp, R_bot_in=(by1 - e2) / sp)


def report():
    rows = json.load(open(os.path.join(OUT, "strokes.json"), encoding="utf-8"))
    from collections import Counter
    print("상태:", Counter((r["font"], r["kind"], r["status"]) for r in rows))
    for font in ("LilyPond", "Bravura", "Leipzig"):
        for kind in ("natural", "#"):
            v = [dict(features(r), raw=r["raw"]) for r in rows if r["font"] == font and r["kind"] == kind and r["status"] == "막대 둘"]
            if not v:
                continue
            q = lambda k: " / ".join(f"{f(np.array([x[k] for x in v])):.2f}" for f in (np.min, np.median, np.max))
            both = sum(1 for x in v if x["dt"] > 0.45 and x["db"] > 0.45)
            print(f"{font:8s} {kind:7s} n {len(v):3d} | dt {q('dt')} | db {q('db')} | 길이 L {q('lenL')} R {q('lenR')} | 둘 다>0.45 {both}"
                  f" | 원시 {dict(Counter(x['raw'] for x in v))}")


# ------------------------------------------------------------------ 판정 사본
# ♮ 조건 후보: 두 획 중심의 어긋남 dt + db > NAT_SUM_SP (기보 규칙 — ♮은 왼쪽 획이 위로, 오른쪽 획이 아래로 어긋나고 ♯은 같은 높이).
# 실측(두 획 찾은 글리프 932): ♮ 최소 LilyPond 0.51 · Bravura 0.61 · Leipzig 0.50 / ♯ 최대 0.00 · −0.11 · 0.06.
# 부호 있는 값이라 기하평균 대신 가운데 — (0.06 + 0.50) / 2 = 0.28, 양쪽 여유 0.22
NAT_SUM_SP = 0.28
RULE = {"natural": "product"}            # product = 제품 「위 · 아래 둘 다 > 0.45sp」, sum = 위 후보


def nat_find_glyphs(patch, sp):
    """제품 `accidental_detect._find_glyphs` 사본 — ♮ 조건만 RULE로 바꾼다(♭ · 쌍 짓기 · 막대는 그대로)."""
    import cv2
    from modules import accidental_detect as AD
    found = []
    bars = AD._find_thin_bars(patch, sp)
    for i in range(len(bars) - 1):
        (x1, s1, e1), (x2, s2, e2) = bars[i], bars[i + 1]
        if not (sp * 0.3 <= x2 - x1 <= sp * 0.95):
            continue
        center = ((s1 + e1) + (s2 + e2)) / 4.0
        if RULE["natural"] == "sum":
            nat = (s2 - s1) + (e2 - e1) > sp * NAT_SUM_SP
        else:
            nat = (s1 + sp * 0.45 < s2) and (e1 + sp * 0.45 < e2)
        found.append(("natural" if nat else "#", center))
    if bars:
        small = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        contours, hier = cv2.findContours(small, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hier is not None:
            for idx in range(len(contours)):
                if hier[0][idx][3] == -1:
                    continue
                _x, _y, hw, hh = cv2.boundingRect(contours[idx])
                if sp * 0.25 <= hw <= sp * 0.9 and sp * 0.25 <= hh <= sp * 0.9:
                    found.append(("b", _y + hh / 2.0))
    return found


def install_rule(rule):
    """다른 도구를 불러오기 **전에** 갈아 끼운다 — ghost6 · cand12가 import 때 잡는 「원래 _find_glyphs」까지 사본이 된다(측정 함정 B-4).
    product 규칙이면 매 호출 제품 원본과 대조한다(다르면 멈춤 — 측정 함정 A-1)."""
    from modules import accidental_detect as AD
    RULE["natural"] = rule
    orig = AD._find_glyphs
    if rule == "product":
        def checked(patch, sp):
            a, b = nat_find_glyphs(patch, sp), orig(patch, sp)
            if a != b:
                raise RuntimeError(f"사본 ≠ 제품: {a} / {b}")
            return a
        AD._find_glyphs = checked
    else:
        AD._find_glyphs = nat_find_glyphs


def run(tag, variant, which):
    """tag plain(제품 ♮ 조건) · nat(합 조건) × variant base · c12g3h3 × which pdf20 · unseen · photo · verovio."""
    install_rule("product" if tag == "plain" else "sum")
    import measure_a17_ghost6 as G
    if which == "verovio":
        import measure_verovio as V
        V.OUT = os.path.join(ROOT, "debug", f"vrv_{tag}")
        V.run(variant)
        return
    G.T1.OUT = os.path.join(ROOT, "debug", f"a17_cand1_{tag}")
    G.set_variant(variant)
    G.run_set(variant, which)


def raw_matrix(tag, variant, which):
    """A-17 원시 판정 행렬(PDF 글리프 정답) — pdf20 · unseen."""
    install_rule("product" if tag == "plain" else "sum")
    import measure_a17_ghost6 as G
    G.set_variant(variant)
    G.raw(variant, which)
    os.replace(os.path.join(ROOT, "debug", f"a17_raw_{variant}_{which}.json"), os.path.join(OUT, f"raw_{tag}_{variant}_{which}.json"))


def raw_vrv(tag, variant):
    """Verovio 원시 판정 행렬(`measure_verovio.raw`) — 같은 이름 파일이 겹치지 않게 순서대로 돌리고 이름을 바꾼다."""
    install_rule("product" if tag == "plain" else "sum")
    import measure_verovio as V
    V.raw(variant)
    os.replace(os.path.join(V.OUT, f"raw_{variant}.json"), os.path.join(OUT, f"raw_{tag}_{variant}_verovio.json"))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rawvrv":
        raw_vrv(*sys.argv[2:4])
    elif cmd == "run":
        run(*sys.argv[2:5])
    elif cmd == "raw":
        raw_matrix(*sys.argv[2:5])
    else:
        {"collect": collect, "report": report}[cmd]()
