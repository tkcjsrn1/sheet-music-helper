# -*- coding: utf-8 -*-
"""[5] 원천은 맞는데 전파가 끊긴 표기 틀림(NIGHT_CAUSES [6]-2) — 원천 ~ 대상 사이 경계를 정답 마디선과 대조. 제품 코드 무변경.

라벨 = 지금 main(debug/sim_lp/hdrimpl2). 정답 = `measure_pdf_effective.effective`(인쇄 임시표 own · 실효 eff), 정답 마디선 = `pdf_verticals` barline.
대상: 음고는 맞는데 표기 = 제품 조표값이고 실효는 같은 마디 앞 음에서 전파된 것, 원천(같은 보표 · 같은 음 · 왼쪽 가장 가까운 인쇄 임시표 머리) 라벨 표기는 맞음.
제품 경계 = `accidental_detect._propagation_barlines`(가로채 기록). 원천 x < 경계 < 대상 x인 제품 경계마다 정답 마디선(±0.5sp)이 있으면 「진짜 마디선」, 없으면 「잘못 세운 경계」
(그 자리 PDF 세로선 종류 — 기둥 등 — 와 함께). 경계가 없으면 같은 음 중간 라벨의 표기가 원천과 다른지(덮어씀)를 본다.

    python tools/measure_prop_break.py
"""
import io
import contextlib
import json
import os
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LABELS = "hdrimpl2"
CAP = {}


def _page(job):
    import main as MAIN
    import modules.accidental_detect as AD
    import measure_pdf_effective as E
    import measure_pdf_text_causes as TC
    from measure_barline_stem import pdf_verticals
    name, path, pg = job
    if not CAP.get("on"):
        CAP["on"] = True
        orig = AD._propagation_barlines

        def rec(binary, no_staff, staff, pts):
            out = orig(binary, no_staff, staff, pts)
            CAP.setdefault("bars", {})[staff.index] = list(out)
            return out
        AD._propagation_barlines = rec
    CAP["bars"] = {}
    tmp = tempfile.mkdtemp(prefix="pb_")
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp]
    with contextlib.redirect_stdout(io.StringIO()):
        MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
    bars = dict(CAP["bars"])
    res, heads = E.effective(name, path, pg)
    sp = float(sum(s.spacing for s in res.staves) / len(res.staves))
    tbars = [(x, a, b) for x, a, b, k in pdf_verticals(os.path.join(ROOT, path), pg) if k == "barline"]
    verts = pdf_verticals(os.path.join(ROOT, path), pg)
    doc = json.load(open(os.path.join(ROOT, "debug", "sim_lp", LABELS, name + ".json"), encoding="utf-8"))
    L = doc["labels"]
    pk = set(doc["music"].get("key_letters") or [])
    psign = {"♯": "#", "♭": "b"}.get(doc["music"].get("key_symbol", ""), "")
    tag = "".join(ch for ch in name if not ch.isdigit())
    lab_of = lambda h: next((l for l in L if abs(l["x"] - h["x"]) <= 0.7 * sp and abs(l["y"] - h["y"]) <= 0.5 * sp), None)
    st_of = {s.index: s for s in res.staves}
    rows = []
    for h in heads:
        lab = lab_of(h)
        if not lab or lab["pitch"] != h["pitch"] or "own" in h:
            continue
        got, eff = TC.ACC(lab["text"]), TC.NORM.get(h["eff"], "")
        key_default = E.KEY_SIGN[tag] if h["pitch"][0] in E.KEYS[tag] else ""
        prod_default = psign if h["pitch"][0] in pk else ""
        if got == eff or eff == key_default or got != prod_default:
            continue
        src = [o for o in heads if o.get("own") and o["staff"] == h["staff"] and o["pitch"] == h["pitch"] and o["x"] < h["x"]]
        if not src:
            continue
        s = max(src, key=lambda o: o["x"])
        sl = lab_of(s)
        if not sl or TC.ACC(sl["text"]) != TC.NORM.get(s["own"], ""):
            continue
        st = st_of[h["staff"]]
        pb = [b for b in bars.get(lab["staff"], []) if s["x"] < b < h["x"]]
        on_staff = lambda a, b: a <= st.bottom + 0.5 * sp and b >= st.top - 0.5 * sp
        rec = dict(page=name, x=round(h["x"]), y=round(h["y"]), src_x=round(s["x"]), bars=[round(b) for b in pb])
        if pb:
            wrong = [b for b in pb if not any(abs(tx - b) <= 0.5 * sp and on_staff(a, bb) for tx, a, bb in tbars)]
            if wrong:
                kinds = [next((k for x, a, bb, k in verts if abs(x - b) <= 0.5 * sp and on_staff(a, bb)), "PDF 세로선 없음") for b in wrong]
                rec["cause"] = "잘못 세운 경계(" + "·".join(sorted(set(kinds))) + ")"
            else:
                rec["cause"] = "진짜 마디선이 사이에 있음(정답 전파가 마디를 넘음?)"
        else:
            mid = [l for l in L if l["staff"] == lab["staff"] and l["pitch"] == h["pitch"] and s["x"] + 0.7 * sp < l["x"] < h["x"] - 0.7 * sp]
            rec["cause"] = ("같은 음 중간 라벨 표기가 원천과 다름(덮어씀)" if any(TC.ACC(m["text"]) != TC.ACC(sl["text"]) for m in mid)
                            else "원천 라벨이 제품 보표 · 음이 다름" if sl["staff"] != lab["staff"] or sl["pitch"] != lab["pitch"] else "경계 없음 · 덮어씀 없음(기타)")
        rows.append(rec)
    return rows


def main():
    import check_accidental_fix as C
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, [p for p in C.PAGES if p[1].endswith(".pdf")]) for r in part]
    print(f"원천 맞음 · 전파 끊김 {len(rows)}:", dict(Counter(r["cause"] for r in rows).most_common()))
    for r in rows:
        print("   ", r)


if __name__ == "__main__":
    main()
