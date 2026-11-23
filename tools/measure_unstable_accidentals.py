# -*- coding: utf-8 -*-
"""임시표 0.5px 재판정 check(`accidental_detect.unstable_accidentals`) 검증. 측정 전용.

2026-09-29 비교(기록): 음표를 고정하고 임시표만 다시 판정하는 방식은 바흐 17건 중 14 · 시간 +24%,
음표 검출부터 다시 하는 방식(지금 제품)은 17건 전부 · +130%(이 도구 기준, CLI 전체로는 +47%).

    python tools/measure_unstable_accidentals.py catch   # 회전 보정 영상에서 표기가 바뀐 라벨을 잡나(§5-7 21건)
    python tools/measure_unstable_accidentals.py load    # 검증 20쪽: 쪽당 표시 수 · 추가 시간

catch: 원본 라벨(제품 경로)과 회전 보정 영상(`debug/rot_only_*/rc*_추정.png`, `measure_photo_robustness recover`가 만든 것)의
라벨을 좌표로 짝지어 **음고는 같고 표기가 다른** 것을 찾고, 그 음표가 회전 보정 영상에서 표시됐는지 본다.
"""
import glob
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402
from modules.notehead_detect import detect_noteheads  # noqa: E402
from modules.pitch_calculator import calculate_pitches  # noqa: E402
from modules.accidental_detect import (annotate_accidentals, remove_accidental_ghosts,  # noqa: E402
                                       filled_flags, unstable_accidentals)
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts  # noqa: E402
from _score_context import label_texts  # noqa: E402


def page(path, pg=0):
    """제품 순서대로 라벨 + 불안정 표시. (라벨 [(x, y, 음, 표기, 표시)], 기존 단계 시간, 추가 시간)"""
    t0 = time.perf_counter()
    res = preprocess(path, pdf_page=pg)
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    accs = annotate_accidentals(res, ctx, notes)
    cand = []
    notes, accs = remove_accidental_ghosts(notes, accs, res.staves,
                                           filled=filled_flags(notes, heads), flagged=cand)
    texts = label_texts(notes, ctx, accs)
    t1 = time.perf_counter()
    flagged = {id(n) for n in unstable_accidentals(res, ctx, notes, accs)}
    t2 = time.perf_counter()
    return [(n.x, n.y, f"{n.note_name}{n.octave}", t, id(n) in flagged) for n, t in zip(notes, texts)], t1 - t0, t2 - t1


def catch():
    srcs = {"bach": "test_scores/bach_minuet_Am.pdf", "bbm": "test_scores/chopin_nocturne_Bbm.pdf"}
    for name, src in srcs.items():
        base, _, _ = page(os.path.join(ROOT, src))
        tot = caught = 0
        for v in sorted(glob.glob(os.path.join(ROOT, "debug", f"rot_only_{name}", "rc*_추정.png"))):
            got, _, _ = page(v)
            used = set()
            for bx, by, bp, bt, _f in base:
                k = min(range(len(got)), key=lambda j: abs(got[j][0] - bx) + abs(got[j][1] - by))
                if abs(got[k][0] - bx) + abs(got[k][1] - by) > 12 or k in used:
                    continue
                used.add(k)
                if got[k][2] == bp and got[k][3] != bt:
                    tot += 1
                    caught += got[k][4]
                    print(f"  {os.path.basename(v):18s} ({bx},{by}) {bp} {bt}→{got[k][3]}  표시 {'O' if got[k][4] else 'X'}")
            n_flag = sum(1 for g in got if g[4])
            print(f"  {os.path.basename(v):18s} 표시 {n_flag}개 / 라벨 {len(got)}")
        print(f"→ {name}: 표기 변화 {tot} 중 표시 {caught}\n")


def load():
    import check_accidental_fix as C
    tb = ta = 0.0
    for name, path, pg in C.PAGES:
        labs, t_base, t_add = page(os.path.join(ROOT, path), pg)
        tb += t_base
        ta += t_add
        with_acc = sum(1 for l in labs if l[3][-1:] in "#b")
        print(f"{name:8s} 라벨 {len(labs):3d} · 표시 {sum(1 for l in labs if l[4]):2d} · "
              f"기존 {t_base:5.1f}s · 추가 {t_add:4.1f}s", flush=True)
    print(f"→ 20쪽 기존 단계 합 {tb:.1f}s · 추가 {ta:.1f}s ({ta / tb * 100:.0f}%)")


if __name__ == "__main__":
    {"catch": catch, "load": load}[sys.argv[1]]()
