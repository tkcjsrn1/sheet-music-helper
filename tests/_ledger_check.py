# -*- coding: utf-8 -*-
"""
두 보표 사이에 놓인 음표의 '보표 귀속'을 덧줄로 검증한다.

지금까지의 점검은 두 방향뿐이었다 — 순방향('음표마다 라벨이 있나')과
역방향('라벨마다 음표가 있나'). 둘 다 통과하면서도 틀릴 수 있는 자리가 있다:
두 보표 사이의 음이다. 위 보표로 읽느냐 아래 보표로 읽느냐에 따라 음이름이
통째로 달라지는데(같은 자리가 트레블 기준 C3, 베이스 기준 E4가 된다),
앞의 두 점검은 그 차이를 보지 못한다.

판정 근거는 덧줄이다. 덧줄은 자기 보표에서 뻗어 나온 것이므로
'귀속 보표 기준으로 필요한 덧줄 위치'에 실제로 덧줄이 그려져 있어야 한다.

    python tests/_ledger_check.py <악보 파일>     # 목록 보기
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from modules.preprocess import preprocess, pdf_page_count
from modules.notehead_detect import detect_noteheads
from modules.clef_keysig import analyze_staves
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.pitch_calculator import calculate_pitches, calculate_pitch
from modules.note_namer import to_solfege_batch
from modules.verify import drop_beam_ghosts, ledger_ys


# 덧줄 판정은 modules.verify로 옮겼다 — 검증 도구와 본 코드가 같은 식을 써야
# 여기서 통과한 것이 실제 실행에서도 통과한다.
def check(path, pdf_page=0):
    """두 보표 사이 음표들의 귀속 검사 결과를 목록으로 돌려준다."""
    result = preprocess(path, pdf_page=pdf_page)
    contexts = analyze_staves(result)
    noteheads = detect_noteheads(result, contexts=contexts)
    # drop_offstaff_ghosts는 일부러 걸지 않는다 — 그것이 '오선 밖인데 덧줄 없음'을
    # 지워 버리므로, 여기서 걸면 이 검사가 언제나 통과하는 껍데기가 된다.
    # 이 검사의 목적은 지우기 **전에** 귀속이 맞는지 보는 것이다.
    noteheads, _beam_ghosts = drop_beam_ghosts(result, noteheads)
    notes = calculate_pitches(noteheads, result.staves,
                              clef={i: c.clef for i, c in contexts.items()})
    accidentals = annotate_accidentals(result, contexts, notes)
    notes, accidentals = remove_accidental_ghosts(notes, accidentals, result.staves)
    found = [c for c in contexts.values() if c.clef_found]
    key_letters, key_symbol = (found[0].key_letters, found[0].key_symbol) if found else ((), "")
    pairs = to_solfege_batch(notes, key_letters, key_symbol, accidentals, "solfege", [], "")
    text_of = {id(n): t for n, t in pairs}

    staves = sorted(result.staves, key=lambda s: s.top)
    by_index = {s.index: s for s in staves}
    rows = []

    for i, upper in enumerate(staves[:-1]):
        lower = staves[i + 1]
        for note in notes:
            if not (upper.bottom < note.y < lower.top):
                continue
            own = by_index[note.staff_index]
            other = lower if note.staff_index == upper.index else upper

            # 덧줄은 '보표 가장자리와 음표 사이'에만 있다. 그 구간만 본다 —
            # 두 보표 사이 전체를 훑으면 반대편 보표의 덧줄까지 주워 온다.
            if own is upper:
                y_from, y_to = own.bottom + own.spacing * 0.5, note.y + own.spacing * 0.5
            else:
                y_from, y_to = note.y - own.spacing * 0.5, own.top - own.spacing * 0.5
            got = ledger_ys(result.binary, note.x, own, y_from, y_to)

            # 음표가 덧줄에 얹혔는지 칸에 있는지까지 반영해 필요한 덧줄 수를 센다
            # (+0.25가 '줄 위'와 '칸'을 가르는 자리)
            dist = (note.y - own.bottom) if own is upper else (own.top - note.y)
            k_max = int(dist / own.spacing + 0.25)
            sign = 1 if own is upper else -1
            base_y = own.bottom if own is upper else own.top
            need = [base_y + sign * own.spacing * k for k in range(1, k_max + 1)]

            # 화음의 더 높은 음이 덧줄을 더 그으므로 '실제가 더 많은 것'은 정상이다.
            # 필요한 덧줄이 모두 실제로 있는지만 본다.
            ok = all(any(abs(w - g) <= own.spacing * 0.45 for g in got) for w in need)

            probe = type("N", (), dict(x=note.x, y=note.y,
                                       staff_index=other.index, filled=False))()
            other_clef = contexts[other.index].clef if other.index in contexts else "treble"
            other_pitch = calculate_pitch(probe, other, clef=other_clef)

            rows.append(dict(x=int(note.x), y=int(note.y), staff=note.staff_index,
                             pitch=f"{note.note_name}{note.octave}", text=text_of[id(note)],
                             need=[int(round(v)) for v in need], got=got, ok=ok,
                             other=f"{other_pitch.note_name}{other_pitch.octave}",
                             other_staff=other.index))
    return rows


def report(path, pdf_page=0, tag="") -> int:
    rows = check(path, pdf_page)
    bad = [r for r in rows if not r["ok"]]
    print(f"## {tag or os.path.basename(path)}: 두 보표 사이 음표 {len(rows)}개, "
          f"귀속 불일치 {len(bad)}개")
    for r in sorted(rows, key=lambda r: (r["staff"], r["x"])):
        mark = "<<" if not r["ok"] else "  "
        print(f" {mark} st{r['staff']:2d} x={r['x']:5d} y={r['y']:5d} {r['pitch']:4s} "
              f"'{r['text']}'  필요덧줄{r['need']} 실제{r['got']}  "
              f"(반대 보표 st{r['other_staff']}로 읽으면 {r['other']})")
    return len(bad)


if __name__ == "__main__":
    target = sys.argv[1]
    if target.lower().endswith(".pdf"):
        total = 0
        for pg in range(pdf_page_count(target)):
            total += report(target, pg, f"{os.path.basename(target)} {pg + 1}쪽")
        print(f"\n### 전체 귀속 불일치 {total}개")
    else:
        report(target)
