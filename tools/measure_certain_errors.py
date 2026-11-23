# -*- coding: utf-8 -*-
"""[3](e) 남은 「확실」 등급 오류 총정리 — 확실인데 틀린 라벨(음고 · 표기 · 유령)을 유형별로 세고, 유형마다 check로 내릴 신호가 있는지. 제품 코드 무변경.

정답: Verovio = SVG 머리(음고 · 실효 임시표 `eff`), PDF · 보지 않은 악보 = `measure_pdf_effective`(글리프 + 벡터 마디선 + 곡 조표).
Aoharu = 정답 골든 711(라벨 전부 일치 — 확실 오류 0)이라 뺀다. 라벨 = 현재 main 제품.
신호 후보(라벨마다, 판정 아님): 기록만 하는 신호(`snap_residual` · `off_staff` · `no_ledger`), 맥락 — 화음(같은 보표 0.6sp 안 x에 다른 라벨),
오선 밖(덧줄 구역), 시스템 첫머리(보표 맨 왼쪽 라벨), 글리프 모양(`measure_glyph_ghost` ♭형 · ♮형 규칙).
신호마다 「확실 라벨 중 그 신호가 걸린 것의 오류율」 = check로 내렸을 때 정밀도.

    python tools/measure_certain_errors.py
"""
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
NORM = {"#": "#", "b": "b", "natural": "", "": "", None: "", "flatflat": "b", "doublesharp": "#"}


def _truth(kind, name, path, pg):
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"], n["note_name"] + n["octave"], NORM.get(n["eff"], "")) for n in t["notes"]], 18.0
    import measure_pdf_effective as E
    # 빗방울 전주곡(Chop-28-15)은 1쪽 D♭장조(♭5) · 2~4쪽 올림다단조 부분(♯4 — 제품도 ♯4로 읽음). 4쪽은 끝에서 D♭으로 돌아갈 수 있어 정답 불확실
    rain_flat = name == "rain1"
    E.KEYS.update({"moon": "FCGD", "rain": "BEADG" if rain_flat else "FCGD"})
    E.KEY_SIGN.update({"moon": "#", "rain": "b" if rain_flat else "#"})
    res, heads = E.effective(name, path, pg)
    return [(h["x"], h["y"], h["pitch"], NORM.get(h["eff"], "")) for h in heads], float(np.median([s.spacing for s in res.staves]))


def _page(job):
    kind, name, path, pg, lab = job
    heads, sp = _truth(kind, name, path, pg)
    L = json.load(open(lab, encoding="utf-8"))["labels"]
    by_staff = defaultdict(list)
    for l in L:
        by_staff[l["staff"]].append(l)
    first_x = {s: min(l["x"] for l in v) for s, v in by_staff.items()}
    rows = []
    used = set()
    for l in sorted(L, key=lambda l: l["x"]):
        cand = [(abs(h[0] - l["x"]) + abs(h[1] - l["y"]), i) for i, h in enumerate(heads)
                if i not in used and abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp]
        if cand:
            i = min(cand)[1]
            used.add(i)
            err = "음고" if l["pitch"] != heads[i][2] else "표기" if ACC(l["text"]) != heads[i][3] else ""
        else:
            err = "유령"
        chord = any(m is not l and abs(m["x"] - l["x"]) <= 0.6 * sp for m in by_staff[l["staff"]])
        rows.append(dict(set=kind, page=name, x=l["x"], y=l["y"], conf=l["confidence"], err=err, flags=l["flags"],
                         chord=chord, first=l["x"] == first_x[l["staff"]]))
    return rows


def main():
    import check_accidental_fix as C
    if len(sys.argv) > 1:          # 라벨 폴더 하나에 전 세트(`measure_sim_ledger_pair` 출력 형식) — 예: debug/sim_lp/gshape
        import measure_sim_ledger_pair as S
        d = os.path.join(ROOT, sys.argv[1])
        jobs = [(("pdf" if st in ("pdf", "unseen") else st) if st != "unseen" else "unseen", n, p, pg, os.path.join(d, n + ".json"))
                for st, n, p, pg in S.pages() if st != "aoharu" and n != "organ2"]
        return _report(jobs)
    jobs = [("pdf", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    U = "output/unseen-scores-20260829/sources/"
    jobs += [("unseen", f"moon{p + 1}", U + "moonlight-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_unseen", f"moon{p + 1}.json")) for p in (0, 1, 10, 17)]
    jobs += [("unseen", f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_clefflag", "base_unseen", f"rain{p + 1}.json")) for p in range(4)]
    V = os.path.join(ROOT, "test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0, os.path.join(ROOT, "debug", "vrv_clefflag", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    _report(jobs)


def _report(jobs):
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_page, jobs) for r in part]
    # 글리프 모양 규칙(GLYPH_GHOST.md) — 같은 라벨 좌표로 잇는다
    G = json.load(open(os.path.join(ROOT, "debug", "glyph_ghost.json"), encoding="utf-8"))["rows"]
    shp = {(g["set"], g["page"], g["x"], g["y"]): g for g in G}
    fb = lambda g: g["LU"] >= 1.3 and g["LD"] <= 0.6 and g["RU"] <= 1.0
    fn = lambda g: g["LU"] >= 0.6 and g["RD"] >= 0.6 and g["LD"] <= 1.7 and g["RU"] <= 2.0
    for r in rows:
        g = shp.get((r["set"], r["page"], r["x"], r["y"]))
        r["glyph_shape"] = bool(g and (fb(g) or fn(g)))
    json.dump(rows, open(os.path.join(ROOT, "debug", "certain_errors.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st in ("pdf", "unseen", "verovio"):
        v = [r for r in rows if r["set"] == st]
        print(f"{st}: 라벨 {len(v)} · 표기 틀림(모든 등급) {sum(r['err'] == '표기' for r in v)} · 음고 {sum(r['err'] == '음고' for r in v)} · 유령 {sum(r['err'] == '유령' for r in v)}")
    cert = [r for r in rows if r["conf"] == "certain"]
    for st in ("pdf", "unseen", "verovio"):
        v = [r for r in cert if r["set"] == st]
        print(f"{st}: 확실 {len(v)} · 틀림 {sum(bool(r['err']) for r in v)} {dict(Counter(r['err'] for r in v if r['err']))}")
    sig = {"snap_residual": lambda r: "snap_residual" in r["flags"], "off_staff": lambda r: "off_staff" in r["flags"],
           "no_ledger": lambda r: "no_ledger" in r["flags"], "화음": lambda r: r["chord"], "보표 첫 라벨": lambda r: r["first"],
           "글리프 모양(♭형 · ♮형)": lambda r: r["glyph_shape"]}
    print("신호 | 확실 중 걸린 수 · 그중 틀림(정밀도) · 유형")
    for k, f in sig.items():
        v = [r for r in cert if f(r)]
        e = [r for r in v if r["err"]]
        print(f"  {k:18s} {len(v):6d} · {len(e):4d} ({len(e) / max(1, len(v)) * 100:.0f}%) {dict(Counter(r['err'] for r in e))}")
    e = [r for r in cert if r["err"]]
    print(f"확실 오류 {len(e)} 중 어떤 신호에도 안 걸림 {sum(not any(f(r) for f in sig.values()) for r in e)}")


if __name__ == "__main__":
    main()
