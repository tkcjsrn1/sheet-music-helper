# -*- coding: utf-8 -*-
"""조표 픽스처의 **정답 음표 수**를 LilyPond 소스에서 세어 파이프라인 결과와 맞춘다.

측정 전용. `modules/`는 읽기만 한다.

## 왜 이게 필요한가

지금 검증은 **라벨 → 음표** 한 방향뿐이다 — 출력된 라벨 자리에 음표 잉크가 있는지
본다(`verify.reverse_check`도 이름과 달리 라벨을 돌며 잉크를 확인한다).
**그 방향으로는 오삭제를 못 잡는다.** 지워진 음표는 라벨이 없어 대조 대상에 없다.

**음표 → 라벨** 방향은 「악보에 음표가 몇 개인가」를 알아야 하는데, 사람이 세면 비싸다.
그런데 **합성 악보는 소스가 정답이다.** `tests/fixtures/key_signatures/sources/*.ly`에
선율이 그대로 적혀 있으므로 **사람 없이** 정답 개수를 얻는다.

## 세는 방법

`rightBase = \\fixed c' { ... }` 블록 안의 음표 토큰만 센다.
`c4 d e g | f e d c | ...` 처럼 **음이름 + (옥타브 부호) + (음길이)** 꼴이다.
`|`(마디선), `\\break`, 변수 이름은 제외한다. 쉼표(`r`)는 이 픽스처에 없다.

**이 개수는 라벨 수의 상한이 아니라 정답이다** — 픽스처에 화음이 없어
음표 하나에 라벨 하나가 정확히 대응한다.

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요):
    python tools/count_fixture_notes.py
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tests"))

FIX = "tests/fixtures/key_signatures"

# 음표 토큰: 음이름 a~g + (is|es 반복) + (' 또는 , 반복) + (음길이 숫자와 점)
NOTE = re.compile(r"^[a-g](?:is|es)*[',]*\d*\.*$")


def _block(src, name):
    """`name = \\fixed <음> { ... }` 의 중괄호 안을 돌려준다."""
    i = src.index(name)
    j = src.index("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    raise ValueError(f"{name} 블록을 못 찾았다")


def count_notes(ly_path):
    """(오른손, 왼손, 합계)"""
    src = io.open(ly_path, encoding="utf-8").read()
    out = []
    for name in ("rightBase", "leftBase"):
        body = _block(src, name)
        n = 0
        for tok in body.replace("|", " ").split():
            if tok.startswith("\\"):
                continue
            if NOTE.match(tok):
                n += 1
        out.append(n)
    return out[0], out[1], out[0] + out[1]


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from test_golden_regression import analyze

    names = sorted(os.listdir(os.path.join(FIX, "sources")))
    print("=" * 92)
    print("조표 픽스처 — LilyPond 소스의 정답 음표 수 vs 파이프라인 라벨 수")
    print("=" * 92)
    print(f"{'픽스처':24s} {'오른손':>5s} {'왼손':>5s} {'정답':>5s} {'라벨':>5s} {'차이':>5s}  "
          f"{'조표(정답/검출)':14s} 판정")
    tot_miss = 0
    key_bad = 0
    for name in names:
        if not name.endswith(".ly"):
            continue
        stem = name[:-3]
        pdf = os.path.join(FIX, "pdf", stem + ".pdf")
        if not os.path.isfile(pdf):
            print(f"{stem:24s}  PDF 없음")
            continue
        r, l, truth = count_notes(os.path.join(FIX, "sources", name))
        lines, _metrics, ctx = analyze(pdf)
        got = len(lines)
        diff = got - truth
        tot_miss += max(0, -diff)
        verdict = "일치" if diff == 0 else (f"**{-diff}개 부족**" if diff < 0
                                          else f"{diff}개 더 많음")
        # 음표 수가 맞아도 조표가 틀리면 라벨 전체가 틀린다 — 조표도 정답과 맞춘다
        want_key, got_keys = expected_key(stem), {c.split("\t")[2] for c in ctx}
        key_ok = got_keys == {want_key}
        key_bad += not key_ok
        key_col = f"{want_key}/{','.join(sorted(got_keys))}" + ("" if key_ok else " **틀림**")
        print(f"{stem:24s} {r:5d} {l:5d} {truth:5d} {got:5d} {diff:+5d}  {key_col:14s} {verdict}")
    print(f"\n>> 부족분 합계 **{tot_miss}개**  "
          f"(부족 = 악보에 있는데 라벨이 없다 = **오삭제 또는 미검출**)")
    print("   이 수치는 라벨->음표 방향으로는 **영원히 안 보인다.**")
    print(f">> 조표 오판 **{key_bad}종**")


def expected_key(stem):
    """manifest.json의 정답 조표를 `_score_context` 표기(`♯2`·`♭5`·`-`)로."""
    import json
    keys = json.load(open(os.path.join(FIX, "manifest.json"), encoding="utf-8"))["keys"]
    k = next(k for k in keys if os.path.basename(k["pdf"])[:-4] == stem)
    return f"{ {'sharp': '♯', 'flat': '♭'}[k['symbol']] }{k['count']}" if k["count"] else "-"


if __name__ == "__main__":
    main()
