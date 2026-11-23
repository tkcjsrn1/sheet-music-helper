# -*- coding: utf-8 -*-
"""[2] 인쇄 임시표 원시 오판(PDF 표기 틀림 「인쇄된 임시표 오판」) — ♯ 창 밖 14(기각 33 · 35 방향) 제외 22의 단계. 제품 코드 무변경.

행 = debug/pdf_text_causes.json(라벨 = 지금 main). 정답 인쇄 글리프 = `measure_a17.truth`(종류 · 글리프 중심 gx · gy · 붙는 머리 hx · hy).
머리마다 제품 순서(`measure_sharp_miss._read`, 창 −2.0 ~ −0.55sp)로:
  원시 결과, 창 안 글리프(종류 · 머리와의 높이 차 sp), 글리프 자리 막대(`_find_thin_bars`: x · 길이 sp), 쌍 간격 · ♮ 어긋남 합(sp).
  원시가 맞는데 라벨이 틀리면 「원시 맞음 — 뒤 단계」.
몰림 까닭: 글리프 왼쪽 1.5sp 안 다른 인쇄 임시표(겹친 임시표 열), 같은 x ±0.6sp 다른 머리(화음), 조표 끝과의 거리(sp).

    python tools/measure_acc_misread.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
NAME = {"#": "♯", "b": "♭", "natural": "♮", "": "-", "doublesharp": "𝄪", "flatflat": "𝄫"}


def _page(job):
    import check_accidental_fix as C
    import measure_a17 as A
    import modules.accidental_detect as AD
    from measure_sharp_miss import _read
    from modules.notehead_detect import remove_staff_lines
    name, path, pg, rows = job
    res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = C.analyze_staves(res)
    glyphs = A.truth(path, pg, res, ctx)[0]
    _g, _s, heads = A.truth(path, pg, res, ctx)
    no_staff = remove_staff_lines(res.binary, res.staves)
    H = no_staff.shape[0]
    out = []
    for r in rows:
        g = min(glyphs, key=lambda q: abs(q["hx"] - r["x"]) + abs(q["hy"] - r["y"]))
        st = next(s for s in res.staves if s.index == g["staff"])
        sp = st.spacing
        if abs(g["hx"] - r["x"]) > 0.7 * sp or abs(g["hy"] - r["y"]) > 0.5 * sp:
            continue
        top = max(0, int(int(st.top - AD.WIDE_BAND_SP * sp) - sp * 3.5))
        bottom = min(H, int(int(st.bottom + AD.WIDE_BAND_SP * sp) + sp * 3.5))
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        band = cv2.morphologyEx(no_staff[top:bottom, :], cv2.MORPH_CLOSE, vk)
        raw, gl = _read(band, top, ctx, st, g["hx"], g["hy"], 2.0, sp)
        d_g = (g["hx"] - g["gx"]) / sp
        x0 = int(g["hx"] - 2.0 * sp)
        hdr = ctx[st.index].header_end if st.index in ctx else 0
        py0 = max(0, int(g["hy"] - top - sp * 2.0))
        patch = band[py0:min(band.shape[0], int(g["hy"] - top + sp * 2.0)), max(0, max(x0, hdr + int(0.2 * sp))):int(g["hx"] - 0.55 * sp)]
        bars = AD._find_thin_bars(patch, sp) if patch.size else []
        rec = dict(page=name, hx=round(g["hx"]), hy=round(g["hy"]), truth=NAME[g["kind"]], raw=NAME.get(raw, raw), label=NAME.get(r["got"], r["got"]),
                   gx_sp=round(d_g, 2), glyphs=[(NAME.get(k, k), round((top + py0 + gy - g["hy"]) / sp, 2)) for k, gy in gl],
                   bars=[(round(b[0] / sp, 2), round((b[2] - b[1]) / sp, 2)) for b in bars],
                   stacked=sum(1 for o in glyphs if o is not g and 0 < g["gx"] - o["gx"] <= 1.5 * sp and abs(o["gy"] - g["gy"]) <= 3 * sp),
                   chord=sum(1 for h in heads if abs(h["cx"] - g["hx"]) <= 0.6 * sp and 0 < abs(h["cy"] - g["hy"]) <= 3 * sp),
                   from_hdr=round((g["gx"] - hdr) / sp, 2))
        if d_g >= 2.2:
            rec["stage"] = "창 밖(♯ 14와 같은 갈래 — 제외)" if g["kind"] == "#" else "창 밖 — 글리프 중심 ≥ 2.2sp(♭ · ♮)"
        elif rec["raw"] == rec["truth"]:
            rec["stage"] = "원시 맞음 — 뒤 단계(전파 · 유령 제거 · 화음 구제)"
        elif d_g >= 1.75:
            rec["stage"] = "창 왼끝에 걸림 — 글리프 일부만 창 안(중심 1.75~2.2sp)"
        elif not gl:
            rec["stage"] = "창 안 글리프 없음(막대 · 고리 조건 실패)"
        elif any(abs(dy) <= 0.35 for _k, dy in rec["glyphs"]):
            rec["stage"] = "자기 높이에 다른 종류로 읽음"
        else:
            rec["stage"] = "글리프는 있으나 높이 차 > 0.35sp"
        out.append(rec)
    return out


def main():
    import check_accidental_fix as C
    rows = [r for r in json.load(open(os.path.join(ROOT, "debug", "pdf_text_causes.json"), encoding="utf-8")) if r["cause"] == "인쇄된 임시표 오판"]
    P = {n: (p, g) for n, p, g in C.PAGES}
    jobs = [(n, P[n][0], P[n][1], [r for r in rows if r["page"] == n]) for n in sorted({r["page"] for r in rows})]
    with ProcessPoolExecutor(2) as ex:
        recs = [x for part in ex.map(_page, jobs) for x in part]
    keep = [r for r in recs if not r["stage"].startswith("창 밖(♯")]
    print(f"인쇄 임시표 오판 {len(recs)} · ♯ 창 밖 제외 {len(keep)}")
    print("  단계:", dict(Counter(r["stage"] for r in keep).most_common()))
    print("  인쇄 → 원시:", dict(Counter(f"{r['truth']}→{r['raw']}" for r in keep).most_common()))
    print("  쪽:", dict(Counter(r["page"] for r in keep).most_common()))
    print("  겹친 임시표(왼쪽 1.5sp 안 다른 글리프) 있음:", sum(r["stacked"] > 0 for r in keep), "· 화음 머리:", sum(r["chord"] > 0 for r in keep))
    for r in keep:
        print("   ", r)


if __name__ == "__main__":
    main()
