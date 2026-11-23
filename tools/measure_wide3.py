# -*- coding: utf-8 -*-
"""D2 후보 ③ — 「가로로 긴 덩어리(폭 > 2.2sp) 버림」의 제품 경로 거절 기록 (2026-10-19 · 측정만, 제품 코드 무변경).

`_detect_noteheads_in_band` 소스를 메모리에서만 바꿔(파일 무변경) 그 규칙이 버리는 덩어리마다 기록을 남긴다:
폭 · 높이(sp) · 위 · 아래 4분의 1 좌우 중심 차(`spread`, 제품 분할이 쓰는 값) · 채움률 · 행 밀도 띠 수.
덩어리 bbox(±0.3sp) 안 정답 머리 수(`error_census._truth_*`)로 3+ = 화음 덩어리, 0 = 잡음(빔 · 글자 등).
`debug/second94/rows.json`(통째 누락 후보 94) 중 bbox 안에 드는 것도 센다.

    python tools/measure_wide3.py          → debug/wide3_log.json (쪽마다 순서대로, 워커 없음)
    python tools/measure_wide3.py report
"""
import inspect
import json
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "wide3_log.json")
LOG = []


def install():
    import modules.notehead_detect as ND
    src = inspect.getsource(ND._detect_noteheads_in_band)
    key = "            if not wide_pair:\n                continue\n"
    assert src.count(key) == 1
    rec = ("            if not wide_pair:\n"
           "                _sb = patched[y:y + h, x:x + w] > 0\n"
           "                _q = max(1, h // 4)\n"
           "                _xs = np.arange(w)\n"
           "                def _xc(r0, r1):\n"
           "                    col = _sb[r0:r1].sum(axis=0)\n"
           "                    return float((_xs * col).sum() / col.sum()) if col.sum() else w / 2.0\n"
           "                _d = _sb.sum(axis=1) / max(1, w) > 0.55\n"
           "                _nb = int(np.sum(np.diff(np.concatenate(([0], _d.astype(np.int8), [0]))) == 1))\n"
           "                _WLOG.append(dict(staff=staff.index, x=int(x), y=int(y + top), w=int(w), h=int(h), sp=float(spacing),\n"
           "                                  spread=abs(_xc(0, _q) - _xc(h - _q, h)) / spacing, fill=float(_sb.mean()), bands=_nb))\n"
           "                continue\n")
    src = src.replace(key, rec)
    ND._WLOG = LOG
    exec(compile(src, ND.__file__, "exec"), ND.__dict__)
    return ND


def main():
    import measure_sim_ledger_pair as S
    import error_census as EC
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    ND = install()
    miss = json.load(open(os.path.join(ROOT, "debug", "second94", "rows.json"), encoding="utf-8"))
    rows = []
    for st, nm, path, pg in S.pages():
        if st == "aoharu" or nm == "organ2":
            continue
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        LOG.clear()
        ND.detect_noteheads(res, contexts=analyze_staves(res))
        truth = EC._truth_vrv(nm)[0] if st == "verovio" else EC._truth_pdf(nm, path, pg)[0]
        for g in LOG:
            m = 0.3 * g["sp"]
            inb = lambda px, py: g["x"] - m <= px <= g["x"] + g["w"] + m and g["y"] - m <= py <= g["y"] + g["h"] + m
            rows.append(dict(g, set=st, page=nm, n=sum(1 for t in truth if inb(t["x"], t["y"])),
                             miss=sum(1 for r in miss if r["page"] == nm and inb(r["x"], r["y"]))))
        print(nm, len(LOG), flush=True)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(rows)


def report(rows=None):
    rows = rows or json.load(open(OUT, encoding="utf-8"))
    pct = lambda a: " · ".join(f"{np.percentile(a, q):.2f}" for q in (0, 5, 50, 95, 100)) if a else "-"
    print("버려진 넓은 덩어리", len(rows), "· 정답 머리 수:", sorted(Counter(r["n"] for r in rows).items()),
          "· 통째 누락 후보 든 덩어리", sum(1 for r in rows if r["miss"]), "(후보", sum(r["miss"] for r in rows), ")")
    for name, sel in (("머리 3+", lambda r: r["n"] >= 3), ("머리 2", lambda r: r["n"] == 2), ("머리 1", lambda r: r["n"] == 1), ("머리 0", lambda r: r["n"] == 0)):
        v = [r for r in rows if sel(r)]
        print(f"  {name}: {len(v)} | 폭 {pct([r['w'] / r['sp'] for r in v])} | 높이 {pct([r['h'] / r['sp'] for r in v])}")
    for H0, H1 in ((2.3, 2.8), (2.4, 2.7)):
        win = [r for r in rows if r["w"] <= 2.65 * r["sp"] and H0 * r["sp"] <= r["h"] <= H1 * r["sp"]]
        print(f"창 폭 2.2~2.65 · 높이 {H0}~{H1}: 머리 수", sorted(Counter(r["n"] for r in win).items()))
        for k in sorted({r["n"] for r in win}):
            v = [r for r in win if r["n"] == k]
            print(f"   머리 {k}: spread {pct([r['spread'] for r in v])} | 채움 {pct([r['fill'] for r in v])} | 띠 {sorted(Counter(r['bands'] for r in v).items())}")
            if k < 3:
                for r in v:
                    print("     ", r["page"], r["x"], r["y"], round(r["w"] / r["sp"], 2), round(r["h"] / r["sp"], 2), round(r["spread"], 2))
    # 창 바로 바깥의 잡음(문턱 여유 확인)
    near = [r for r in rows if r["n"] < 3 and r["w"] <= 2.9 * r["sp"] and 2.0 * r["sp"] <= r["h"] <= 3.2 * r["sp"]]
    print("창 둘레(폭 ≤ 2.9 · 높이 2.0~3.2) 머리 < 3:", len(near))
    for r in sorted(near, key=lambda r: (r["h"] / r["sp"])):
        print("     ", r["n"], r["page"], r["x"], r["y"], round(r["w"] / r["sp"], 2), round(r["h"] / r["sp"], 2), round(r["spread"], 2))


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
