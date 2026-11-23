# -*- coding: utf-8 -*-
"""`clef_keysig.system_groups`(시스템 왼쪽 연결선으로 보표 묶기) 정답 대조(2026-10-16). 정답: Verovio = SVG system, 그 밖 = 보표 두 개씩(피아노 — organ2는 3단이라 정답이 틀림).

    python tools/measure_system_groups.py
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    from modules.clef_keysig import system_groups
    from modules.preprocess import preprocess
    st, nm, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    staves = sorted(res.staves, key=lambda s: s.top)
    got = system_groups(res.binary, res.staves)
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
        if len(t["staves"]) != len(staves):
            return st, nm, None, got
        sy = [ts["system"] for ts in t["staves"]]
    else:
        sy = [i // 2 for i in range(len(staves))]
    want = [[s.index for s, g in zip(staves, sy) if g == k] for k in sorted(set(sy))]
    return st, nm, want == got, (want, got)


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(3) as ex:
        R = list(ex.map(_page, S.pages()))
    for st, nm, ok, d in R:
        if not ok:
            print("  다름" if ok is False else "  정답 없음", st, nm, d)
    print("일치", sum(r[2] is True for r in R), "/", len(R))


if __name__ == "__main__":
    main()
