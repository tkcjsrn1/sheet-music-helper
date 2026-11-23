# -*- coding: utf-8 -*-
"""(d) 줄 중간 조표 증거를 「다음 시스템 머리 조표」로 확인하면 오검출이 얼마나 남나. 제품 코드 무변경.

증거 = `measure_midline_keysig._page`(간격 창, KEY_CHANGE.md §4). 확인 = 같은 쪽 다음 시스템 보표들의 머리 막대(`analyze_staves`)를
제품 `_vote_key_signature`로 읽은 값이 증거 값과 같음. 근거: 조표는 바뀐 뒤 시스템마다 머리에 다시 찍히지만,
마디 첫 임시표(오검출 대부분, §4)는 다음 시스템 머리에 없다. 라벨을 안 쓰므로 §5의 글리프 유령 순환과 무관.
다음 시스템이 없으면(쪽 마지막 시스템) 확인 불가 = 기각.
「바뀜」 = 증거 값이 그 시스템 머리 조표와도 다름(같으면 조가 안 바뀐 것 — em ♯1 · 베토벤 op18 ♭1의 마디 첫 임시표).

    python tools/measure_keychange_confirm.py
"""
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _page(job):
    import json
    import measure_midline_keysig as K
    import modules.clef_keysig as CK
    from modules.preprocess import preprocess
    kind, name, path, pg, lab, mins = job
    K.MIN_STAVES = mins
    _k, _n, truth, found = K._page(job[:5])
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = CK.analyze_staves(res)
    staves = sorted(res.staves, key=lambda s: s.top)
    if kind == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        if len(t["staves"]) != len(staves):
            return kind, name, [], []
        sys_of = {s.index: ts["system"] for s, ts in zip(staves, t["staves"])}
    else:
        sys_of = {s.index: i // 2 for i, s in enumerate(staves)}
    head = {}
    for sy in set(sys_of.values()):
        kc, ks, _r = CK._vote_key_signature({i: ctx[i] for i, g in sys_of.items() if g == sy and i in ctx})
        head[sy] = f"{kc}{'s' if ks == '♯' else 'f'}" if kc else "0"
    found = [f + (head.get(f[0] + 1), head.get(f[0])) for f in found]
    return kind, name, truth, found


def main():
    import measure_midline_keysig as K
    import check_accidental_fix as C
    base = [("pdf", n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES]
    U = "output/unseen-scores-20260829/sources/"
    base += [("unseen", f"moon{p + 1}", U + "moonlight-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"moon{p + 1}.json")) for p in (0, 1, 10, 17)]
    base += [("unseen", f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"rain{p + 1}.json")) for p in range(4)]
    V = os.path.join(ROOT, "test_scores", "verovio")
    base += [("verovio", f[:-4], os.path.join("test_scores", "verovio", f), 0, os.path.join(ROOT, "debug", "vrv_a25impl", "base", f[:-4] + ".json"))
             for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    for mins in (1, 2):
        with ProcessPoolExecutor(3) as ex:
            res = list(ex.map(_page, [b + (mins,) for b in base]))
        c = Counter()
        for kind, name, truth, found in res:
            used = set()
            for sy, x, val in truth:
                near = [f for f in found if f[0] == sy and x - 4 * 18 <= f[1] <= x]
                hit = [f for f in near if f[2] == val]
                c[(kind, "정답")] += 1
                c[(kind, "검출")] += bool(hit)
                c[(kind, "검출+확인")] += any(f[5] == val for f in hit)
                c[(kind, "검출+확인+바뀜")] += any(f[5] == val != f[6] for f in hit)
                used.update(id(f) for f in near)
                if hit and not any(f[5] == val for f in hit):
                    print(f"  [{mins}] 확인 실패(진짜)", name, sy, x, val, "다음 시스템 머리", [f[5] for f in hit])
            for f in found:
                if id(f) in used:
                    continue
                c[(kind, "오검출")] += 1
                if f[5] == f[2]:
                    c[(kind, "오검출+확인")] += 1
                    c[(kind, "오검출+확인+바뀜")] += f[2] != f[6]
                    print(f"  [{mins}] 확인 통과(오검출)", kind, name, f)
        for kind in ("verovio", "pdf", "unseen"):
            g = lambda k: c[(kind, k)]
            print(f"동의 ≥ {mins} {kind}: 조바꿈 {g('정답')} 검출 {g('검출')} → 확인 뒤 {g('검출+확인')} → +바뀜 {g('검출+확인+바뀜')}"
                  f" | 오검출 {g('오검출')} → 확인 뒤 {g('오검출+확인')} → +바뀜 {g('오검출+확인+바뀜')}")


if __name__ == "__main__":
    main()
