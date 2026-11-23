# -*- coding: utf-8 -*-
"""라벨 대조에 **음악적 문맥**(음자리표·조표·헤더 끝)과 **최종 표기**를 함께 넣는 공용 도구.

## 왜 필요한가

음이름+옥타브만 비교하면 **조표가 바뀌어도 차이가 0이다.** 조표는 음고가 아니라 표기(♯·♭)를
바꾸기 때문이다. 실측: 바흐 미뉴에트를 x로 0.5px 옮기면 조표가 「없음 → ♭1」로 뒤집혀
B 19개가 「시♭」이 됐는데, 음이름·옥타브 대조는 그 19개를 한 건도 못 잡았다
(`docs/SUBPIXEL_SHIFT.md` §4). **조표가 바뀌면 라벨 전체가 조용히 틀린다.**

## 무엇을 비교하나

| 항목 | 출처 | 비고 |
|---|---|---|
| 음자리표 | `StaffContext.clef` (`clef_found`가 아니면 `-`) | 보표마다 |
| 조표 | `key_symbol` · `key_count` · `key_letters` | 교차 투표라 페이지 전체가 같다 |
| 헤더 끝 | `header_end` | 음자리표·조표·**박자표 구간**까지 |
| 표기 | `to_solfege_batch` 고정도 | 조표·임시표가 반영된 최종 글자 |

**박자표 값(3/4·6/8)은 파이프라인이 인식하지 않는다.** 박자표는 헤더를 넓히는 데만 쓰이므로
`header_end`가 박자표의 유일한 흔적이다. 값 비교는 할 수 없다.
"""
import os
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from modules.note_namer import to_solfege_batch  # noqa: E402


def page_key(contexts) -> Tuple[Tuple[str, ...], str]:
    """(key_letters, key_symbol). 골든과 같은 규칙 — 음자리표를 찾은 첫 보표의 값."""
    found = [c for c in contexts.values() if c.clef_found]
    return (tuple(found[0].key_letters), found[0].key_symbol) if found else ((), "")


def context_rows(contexts) -> List[Dict]:
    return [dict(staff=i,
                 clef=c.clef if c.clef_found else "-",
                 key=f"{c.key_symbol}{c.key_count}" if c.key_count else "-",
                 letters="".join(c.key_letters) or "-",
                 header_end=int(c.header_end))
            for i, c in sorted(contexts.items())]


def context_lines(contexts) -> List[str]:
    """골든 파일용 TSV 줄: 보표 · 음자리표 · 조표 · 조표 음이름 · 헤더 끝."""
    return ["\t".join(str(r[k]) for k in ("staff", "clef", "key", "letters", "header_end"))
            for r in context_rows(contexts)]


def context_summary(contexts) -> str:
    """콘솔 한 줄 요약. 예: `조표 ♭1(B) 음자리표 TBTBTBTB`"""
    letters, symbol = page_key(contexts)
    clefs = "".join({"treble": "T", "bass": "B"}.get(r["clef"], "-") for r in context_rows(contexts))
    key = f"{symbol}{len(letters)}({''.join(letters)})" if letters else "없음"
    return f"조표 {key} 음자리표 {clefs}"


def context_diff(a, b, dx: float = 0.0, tol: int = 1) -> List[str]:
    """두 run의 문맥 차이. `header_end`는 **영상 이동량 dx를 뺀 뒤** tol px 넘게 달라질 때만 센다."""
    ra = {r["staff"]: r for r in context_rows(a)}
    rb = {r["staff"]: r for r in context_rows(b)}
    out = []
    if set(ra) != set(rb):
        out.append(f"보표 목록 {sorted(ra)} -> {sorted(rb)}")
    for i in sorted(set(ra) & set(rb)):
        x, y = ra[i], rb[i]
        for k in ("clef", "key", "letters"):
            if x[k] != y[k]:
                out.append(f"보표{i} {k} {x[k]}->{y[k]}")
        if abs(y["header_end"] - x["header_end"] - dx) > tol:
            out.append(f"보표{i} header_end {x['header_end']}->{y['header_end']}")
    return out


def label_texts(notes, contexts, accidentals) -> List[str]:
    """음표마다 고정도 최종 표기. **조표를 검출값에서 읽는다** — 고정값을 넣으면 조표 오판이 안 보인다."""
    letters, symbol = page_key(contexts)
    return [t for _n, t in to_solfege_batch(notes, letters, symbol, accidentals, "solfege", [], "")]


def self_check() -> None:
    """조표만 다른 두 문맥이 차이로 잡히고, 이동량만큼의 header_end는 안 잡혀야 한다."""
    from modules.clef_keysig import StaffContext
    from modules.pitch_calculator import PitchedNote
    a = {0: StaffContext(clef="treble", clef_found=True, header_end=187)}
    b = {0: StaffContext(clef="treble", clef_found=True, header_end=188,
                         key_count=1, key_symbol="♭", key_letters=("B",))}
    assert context_diff(a, b, dx=1.0) == ["보표0 key -->♭1", "보표0 letters -->B"], context_diff(a, b, dx=1.0)
    assert context_diff(a, a) == []
    note = [PitchedNote(x=0, y=0, note_name="B", octave=4, staff_index=0)]
    assert label_texts(note, a, [""]) != label_texts(note, b, [""]), "조표가 표기에 반영돼야 한다"
    print("[성공] _score_context 자체 점검")


if __name__ == "__main__":
    self_check()
