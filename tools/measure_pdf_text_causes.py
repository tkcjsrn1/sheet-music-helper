# -*- coding: utf-8 -*-
"""야간 [6] PDF 17쪽 표기 틀림(음고는 맞고 임시표 표기가 다름) — 원인 분류. 제품 코드 무변경.

정답 = `measure_pdf_effective.effective`(머리마다 인쇄된 임시표 `own` · 실효 `eff`, 곡 조표). 라벨 = 지금 main(`debug/sim_lp/nograce`).
범주(Verovio `measure_verovio.cause_text`와 같은 갈래):
  인쇄된 임시표 오판   그 머리에 인쇄된 임시표가 있는데 표기가 다름
  마디 안 전파 놓침    인쇄 임시표 없음 · 실효가 곡 조표와 다름(같은 마디 앞 음에서 전파) · 표기가 조표값
  조표 오판           인쇄 · 전파 없음(실효 = 곡 조표) · 제품이 읽은 조표가 곡 조표와 다름
  없는 임시표          인쇄 · 전파 없음 · 제품 조표도 맞음 — 표기에 없는 임시표가 붙음(원시 오판 또는 전파가 마디선을 넘음)
  기타

    python tools/measure_pdf_text_causes.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
NORM = {"#": "#", "b": "b", "natural": "", "": "", None: "", "flatflat": "b", "doublesharp": "#"}


def _page(job):
    import numpy as np
    import measure_pdf_effective as E
    name, path, pg = job
    res, heads = E.effective(name, path, pg)
    tag = "".join(ch for ch in name if not ch.isdigit())
    sp = float(np.median([s.spacing for s in res.staves]))
    doc = json.load(open(os.path.join(ROOT, "debug", "sim_lp", os.environ.get("LABELS", "nograce"), name + ".json"), encoding="utf-8"))
    L = doc["labels"]
    pk = set(doc["music"].get("key_letters") or [])
    psign = {"♯": "#", "♭": "b"}.get(doc["music"].get("key_symbol", ""), doc["music"].get("key_symbol", ""))
    c = Counter()
    rows = []
    for h in heads:
        lab = [l for l in L if abs(l["x"] - h["x"]) <= 0.7 * sp and abs(l["y"] - h["y"]) <= 0.5 * sp]
        if not lab or lab[0]["pitch"] != h["pitch"]:
            continue
        got, eff = ACC(lab[0]["text"]), NORM.get(h["eff"], "")
        if got == eff:
            continue
        key_default = E.KEY_SIGN[tag] if h["pitch"][0] in E.KEYS[tag] else ""
        prod_default = psign if h["pitch"][0] in pk else ""
        if "own" in h:
            k = "인쇄된 임시표 오판"
        elif eff != key_default:
            k = "마디 안 전파 놓침" if got == prod_default else "기타"
            if k == "마디 안 전파 놓침":
                # 원천 = 같은 보표 · 같은 음 · 왼쪽 가장 가까운 인쇄 임시표 머리 — 그 라벨 표기가 맞나
                src = [o for o in heads if o.get("own") and o["staff"] == h["staff"] and o["pitch"] == h["pitch"] and o["x"] < h["x"]]
                if src:
                    sh = max(src, key=lambda o: o["x"])
                    sl = [l for l in L if abs(l["x"] - sh["x"]) <= 0.7 * sp and abs(l["y"] - sh["y"]) <= 0.5 * sp]
                    c["(전파 놓침의 원천: " + ("라벨 없음" if not sl else "표기 맞음" if ACC(sl[0]["text"]) == NORM.get(sh["own"], "") else "표기 틀림") + ")"] += 1
        elif prod_default != key_default:
            k = "조표 오판"
        elif got:
            k = "없는 임시표(원시 오판 또는 마디선 넘은 전파)"
        else:
            k = "기타"
        c[k] += 1
        rows.append(dict(page=name, x=round(h["x"]), y=round(h["y"]), pitch=h["pitch"], got=got, eff=eff, cause=k, conf=lab[0]["confidence"]))
    return name, c, rows


def main():
    import check_accidental_fix as C
    jobs = [(n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, jobs))
    tot = Counter()
    rows = []
    for _n, c, r in res:
        tot.update(c)
        rows += r
    json.dump(rows, open(os.path.join(ROOT, "debug", "pdf_text_causes.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"표기 틀림 {sum(n for k, n in tot.items() if not k.startswith('('))}: " + " · ".join(f"{k} {n}" for k, n in tot.most_common()))
    for k, _n in tot.most_common(3):
        v = [r for r in rows if r["cause"] == k]
        print(f"  {k}: 쪽 {dict(Counter(r['page'] for r in v).most_common(5))} · 표기→정답 {dict(Counter((r['got'] or '-') + '→' + (r['eff'] or '-') for r in v).most_common(4))} · 확실 {sum(r['conf'] == 'certain' for r in v)}")


if __name__ == "__main__":
    main()
