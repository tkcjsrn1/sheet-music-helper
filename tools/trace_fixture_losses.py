# -*- coding: utf-8 -*-
"""조표 픽스처에서 **음표가 어느 단계에서 사라지는지** 가른다.

측정 전용. `modules/`는 읽기만 한다.

`tools/count_fixture_notes.py`가 「15종 중 11종에서 18개가 부족하다」까지 밝혔다.
이 도구는 그 손실이 **검출 실패인지, 이후 필터의 삭제인지**를 단계별로 센다.

## 단계

| 단계 | 함수 | 손실의 뜻 |
|---|---|---|
| 1 | `detect_noteheads` | 모양·크기 게이트에서 탈락하거나 **애초에 안 잡힘** |
| 1' | 같은 함수의 `reject_log` | 모양 판정은 통과했는데 **뒤 단계에서 지워진** 것. 사유가 붙는다 |
| 2 | `drop_beam_ghosts` | 빔 위 유령으로 판정 |
| 3 | `drop_offstaff_ghosts` | 오선 밖·덧줄 없음으로 판정 |
| 4 | `remove_accidental_ghosts` | 임시표 글리프로 판정 (픽스처는 임시표 0개라 0이어야 정상) |

**정답은 168개**다(오른손 108 · 왼손 60, `count_fixture_notes.py`).
픽스처는 화음이 없어 음표 하나 = 라벨 하나가 성립한다.

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요):
    python tools/trace_fixture_losses.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts

from count_fixture_notes import count_notes, expected_key, FIX
from _score_context import context_rows

FIXTURES = [
    "01_C_major_0", "02_G_major_sharp1", "03_D_major_sharp2", "04_A_major_sharp3",
    "05_E_major_sharp4", "06_B_major_sharp5", "07_Fs_major_sharp6",
    "08_Db_major_flat5", "09_Ab_major_flat4", "10_Eb_major_flat3",
    "11_Bb_major_flat2", "12_F_major_flat1", "13_Cs_major_sharp7",
    "14_Gb_major_flat6", "15_Cb_major_flat7",
]


def trace(stem):
    """(정답, 단계별 개수 dict, reject 사유 Counter, 최종 음표 목록)"""
    pdf = os.path.join(FIX, "pdf", stem + ".pdf")
    _r, _l, truth = count_notes(os.path.join(FIX, "sources", stem + ".ly"))

    res = preprocess(pdf)
    ctxs = analyze_staves(res)
    rejects = []
    heads = detect_noteheads(res, contexts=ctxs, reject_log=rejects)
    n_det = len(heads)

    heads_b, beam_ghosts = drop_beam_ghosts(res, heads)
    heads_c, off_ghosts = drop_offstaff_ghosts(res, heads_b)
    notes = calculate_pitches(heads_c, res.staves,
                              clef={i: c.clef for i, c in ctxs.items()})
    accs = annotate_accidentals(res, ctxs, notes)
    notes2, _accs2 = remove_accidental_ghosts(notes, accs, res.staves)

    stages = {
        "정답": truth,
        "검출": n_det,
        "빔유령 제거": len(heads_b) - n_det,
        "오선밖 제거": len(heads_c) - len(heads_b),
        "임시표 제거": len(notes2) - len(notes),
        "최종": len(notes2),
        # 음표가 다 남아도 조표가 틀리면 라벨이 틀린다 — 정답 조표와 맞춘다
        "조표": context_rows(ctxs)[0]["key"] if ctxs else "-",
        "조표정답": expected_key(stem),
    }
    return truth, stages, Counter(r["reason"] for r in rejects), notes2, res, rejects


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("=" * 100)
    print("조표 픽스처 — 음표가 어느 단계에서 사라지는가. 정답 168개")
    print("=" * 100)
    print(f"{'픽스처':22s} {'검출':>5s} {'빔':>4s} {'오선밖':>6s} {'임시표':>6s} "
          f"{'최종':>5s} {'차이':>5s}  reject 사유")
    all_reasons = Counter()
    rows = []
    for stem in FIXTURES:
        truth, st, reasons, notes, res, rejects = trace(stem)
        all_reasons.update(reasons)
        diff = st["최종"] - truth
        rows.append((stem, st, diff, notes, res, rejects))
        rs = " / ".join(f"{k} {v}" for k, v in reasons.most_common()) or "-"
        key = st["조표"] + ("" if st["조표"] == st["조표정답"] else f"(정답 {st['조표정답']}) **틀림**")
        print(f"{stem:22s} {st['검출']:5d} {st['빔유령 제거']:+4d} "
              f"{st['오선밖 제거']:+6d} {st['임시표 제거']:+6d} "
              f"{st['최종']:5d} {diff:+5d}  조표 {key}  {rs}")

    print("\n" + "-" * 100)
    print("reject_log 사유 합계 (모양 판정은 통과했는데 뒤에서 지워진 것)")
    for k, v in all_reasons.most_common():
        print(f"  {k}: {v}")

    print("\n" + "-" * 100)
    det_short = sum(max(0, 168 - r[1]["검출"]) for r in rows)
    filt_drop = sum(-(r[1]["빔유령 제거"] + r[1]["오선밖 제거"] + r[1]["임시표 제거"])
                    for r in rows)
    print(f"검출 단계에서 이미 모자란 합계 : **{det_short}개**")
    print(f"검출 뒤 필터가 지운 합계       : **{filt_drop}개**")
    print("   (검출이 정답보다 많으면 유령이 섞인 것이므로 두 수의 단순 합 != 부족분)")
    return rows


if __name__ == "__main__":
    main()
