# -*- coding: utf-8 -*-
"""[4] 「확실」인데 틀린 라벨 — 현재 main 기준 원인별(유령 정체 · 음고 원인 · 표기 원인). 제품 코드 무변경.

Verovio: `measure_verovio eval <변형>` 결과(`debug/vrv/eval_<변형>.json`)에서 라벨 확신도 certain만 — 원인은 리포트와 같은 `cause_pitch` · `cause_text`, 유령은 SVG 상자 종류.
PDF · 보지 않은 악보: `measure_certain_errors` 행(`debug/certain_errors.json`, 같은 라벨로 먼저 돌린다) 중 확실 —
  유령 정체 = 0.6sp 안 가장 가까운 PDF 글리프의 종류(이름 앞부분), 없으면 「선(빔 · 이음줄 · 기둥 등 벡터)」.

    python tools/measure_certain_errors.py debug/sim_lp/ucheck && python tools/measure_verovio.py eval main1005
    python tools/measure_certain_by_cause.py main1005
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def verovio(variant):
    import measure_verovio as V
    evs = json.load(open(os.path.join(ROOT, "debug", "vrv", f"eval_{variant}.json"), encoding="utf-8"))
    music = {e["stem"]: json.load(open(os.path.join(ROOT, "debug", "vrv", variant, e["stem"] + ".json"), encoding="utf-8"))["music"] for e in evs}
    c = defaultdict(Counter)
    for e in evs:
        for r in e["rows"]:
            if not r.get("label") or r["label"].get("conf") != "certain":
                continue
            if r["status"] == "음고":
                c["음고"][V.cause_pitch(r, e["header"]) + (" — " + e["stem"].split("_")[0] if r["clef_now"] == r["clef_start"] else "")] += 1
            elif r["status"] == "표기":
                c["표기"][V.cause_text(r, music[e["stem"]], e["header"])] += 1
        for g in e["ghosts"]:
            if g.get("conf") != "certain":
                continue
            on = [x for x in g["on"] if x != "ledger"] or (["덧줄만"] if g["on"] else ["표시 없는 자리"])
            c["유령"][on[0] if len(on) == 1 else "+".join(on[:2])] += 1
    return c


def _pdf_page(job):
    import measure_omission_rate as M
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    name, rows = job
    P = {n: (p, pg) for n, p, pg in C.PAGES}
    P.update({n: (p, pg) for n, p, pg in G.UNSEEN})
    path, pg = P[name]
    g = M.pdf_glyphs(path, pg, ("",))
    sp = 20.0
    out = []
    for r in rows:
        near = [(abs(q["cx"] - r["x"]) + abs(q["cy"] - r["y"]), q["name"]) for q in g
                if abs(q["cx"] - r["x"]) <= 0.6 * sp + q["w"] / 2 and abs(q["cy"] - r["y"]) <= 0.6 * sp + q["h"] / 2]
        kind = min(near)[1].split(".")[0] if near else "선(빔 · 이음줄 · 기둥 등 벡터)"
        out.append((r["set"], kind))
    return out


def pdf_sets():
    rows = json.load(open(os.path.join(ROOT, "debug", "certain_errors.json"), encoding="utf-8"))
    cert = [r for r in rows if r["conf"] == "certain" and r["err"]]
    c = {st: defaultdict(Counter) for st in ("pdf", "unseen")}
    by = defaultdict(list)
    for r in cert:
        if r["set"] in c:
            if r["err"] == "유령":
                by[r["page"]].append(r)
            else:
                c[r["set"]][r["err"]]["(원인 분류 없음)"] += 1
    with ProcessPoolExecutor(3) as ex:
        for part in ex.map(_pdf_page, list(by.items())):
            for st, kind in part:
                c[st]["유령"][kind] += 1
    return c


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "main1005"
    out = {"verovio": verovio(variant)}
    out.update(pdf_sets())
    json.dump({k: {t: dict(v) for t, v in d.items()} for k, d in out.items()}, open(os.path.join(ROOT, "debug", "certain_by_cause.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st, d in out.items():
        print(f"== {st}: " + " · ".join(f"{t} {sum(v.values())}" for t, v in d.items()))
        for t, v in d.items():
            print(f"   {t}: " + " · ".join(f"{k} {n}" for k, n in v.most_common(8)))


if __name__ == "__main__":
    main()
