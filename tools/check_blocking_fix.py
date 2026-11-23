# -*- coding: utf-8 -*-
"""가림 규칙 수정이 올라오면 **한 번에** 대조하는 검증기.

측정 전용. `modules/`는 읽기만 한다.

## 쓰는 법

```bash
python tools/check_blocking_fix.py --save     # 수정 전 기준선 저장 (이미 저장돼 있다)
python tools/check_blocking_fix.py --with-tests  # 수정 후 대조 + 골든·전체 테스트
```

기준선은 `docs/measurements/blocking_fix_baseline.json`이다.

## 보는 것

| 항목 | 통과 조건 |
|---|---|
| **A 73건** (가짜 구멍을 옳게 막던 것) | 여전히 막혀 있고, 그 자리에 **빈 음표 라벨이 새로 생기지 않으며 기존 라벨도 사라지지 않는다** |
| **C 6건** (사라졌던 쇼팽 Em 2분음표 5개) | 그 자리에 **정답 음고로** 라벨이 생긴다 (`C_TRUTH`) |
| **유지된 라벨** | 위치가 같아도 **음고가 바뀌면 실패**다 |
| **B 16건** (저해상도에서 filled로 라벨만 남던 것) | 상태 변화를 보고만 한다. 바뀌어도 실패로 세지 않는다 |
| **채택된 구멍 592개** | 계속 채택된다. 규칙 띠에 드는 36개를 따로 센다 |
| **라벨 수·유령** | **검증 악보 20쪽 전체**에서 쪽마다 라벨 증감과 `verify.reverse_check` 유령 수. 새 라벨은 좌표까지 출력한다 (집단 A/B/C 추적은 5쪽뿐) |

`reverse_check`는 유령을 다 못 센다(2026-09-21: 새 유령 4개에 변화 0). **새 라벨은 반드시 확대해서 본다.**

**저해상도(RE:Aoharu sp 11.3)에서는 규칙이 0%다.** B 16건은 안 살아나는 것이 예상 동작이며,
그 사실이 이 검증에서 **눈에 보이게** 남는다.

## 한계

내부 값(가려졌나/채택됐나)은 `trace_hollow_path`의 **기록 사본**으로 읽는다. 수정이 그 사본의
삽입 지점(주석 문구)을 바꾸면 사본을 못 만든다. 그때는 **라벨 수준 대조만** 하고 그 사실을 크게 알린다.
"""
import argparse
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts, reverse_check

import measure_blocked_holes as M

BASELINE = os.path.join(ROOT, "docs", "measurements", "blocking_fix_baseline.json")
# 사라지는 것이 **맞는** 라벨. 쇼팽 Em (1022,2705)은 ♮ 글리프 위에 붙어 있던 유령이고,
# 그 오른쪽 진짜 2분음표가 살아나면서 없어진다(육안 확인, `docs/HOLLOW_FILLED_TRACE.md` §2).
EXPECTED_LOST = {"em1": [(1022, 2705)]}
# C 6건의 **정답 음고**. 라벨이 생겼다고 복구가 아니다 — 음고가 맞아야 복구다.
# 근거: 다섯 곳 모두 높은음자리표·♯1(E단조), 오선 맨 아랫줄(E4) 기준 반칸
# +3.94 / +3.94 / +6.00 / +0.90 / −0.15 → B4 / B4 / D5 / F4 / E4.
# 음자리표·오선 위치는 `docs/C_truth_pitches.png`에서 눈으로 확인했다.
# (642,1581)은 (640,1592)와 **같은 음표의 다른 구멍 조각**이라 정답이 같다.
C_TRUTH = {"em1": {(1934, 1045): "B4", (642, 1581): "B4", (640, 1592): "B4",
                   (1050, 2705): "D5", (1750, 2754): "F4", (2100, 2764): "E4"}}
# 라벨 대조는 **검증 악보 20쪽 전체**에서 한다. 구멍 추적(집단 A/B/C)은 `M.PAGES` 5쪽뿐이다.
# 5쪽만 보다가 B♭m 6쪽의 새 오삭제를 놓쳤다(2026-09-21, PR #53) — 목표 쪽만 보면 다른 쪽을 못 본다.
_BBM, _DB, _EM = ("test_scores/chopin_nocturne_Bbm.pdf", "test_scores/chopin_nocturne_Db_6-8.pdf",
                  "test_scores/chopin_nocturne_Em.pdf")
_AO = "sample_images/KakaoTalk_20260731_162400402"
ALL_PAGES = ([("bach", "test_scores/bach_minuet_Am.pdf", 0)]
             + [(f"bbm{i + 1}", _BBM, i) for i in range(6)]
             + [(f"db{i + 1}", _DB, i) for i in range(6)]
             + [(f"em{i + 1}", _EM, i) for i in range(4)]
             + [("aoharu1", _AO + ".png", 0), ("aoharu2", _AO + "_01.png", 0),
                ("aoharu3", _AO + "_02.png", 0)])
BAND = lambda r: r["hole_h"] >= 0.93 and 1.15 <= r["hole_w"] <= 1.30


def simulate_rule(h_min=0.93, w_lo=1.15, w_hi=1.30, dx_max=0.35):
    """후보 규칙을 **사본에만** 넣는다 — 제품 파일은 건드리지 않는다.

    「가려진 구멍이 높이 ≥0.93sp이고 폭 1.15~1.30sp면 가림을 무시하고 채택」.
    이음매 판정·가림 창은 그대로 둔다(`docs/BLOCKED_HOLE_FEATURES.md` §5).
    """
    import types
    import modules.notehead_detect as ND
    src = open(ND.__file__, encoding="utf-8").read()
    a = "        hole_rects.append((hx + hw / 2.0, hy + hh / 2.0, hy, hh))\n"
    b = ("    for cx, cy, blocker, hy0, hy1 in hollow_candidates:\n"
         "        if blocker is not None and blocker not in artifacts:\n"
         "            continue  # 정상적으로 채워진 머리에 가려진 구멍 -> 무시\n")
    c = "    hole_rects: List[tuple] = []\n"
    d = "    artifacts = seam_artifacts | ring_artifacts\n"
    assert src.count(a) == 1 and src.count(b) == 1 and src.count(c) == 1 and src.count(d) == 1, \
        "삽입 지점을 못 찾았다 — 제품 코드가 바뀌었다"
    # 폭 기록은 **보표마다 비운다**. 안 비우면 다른 보표의 같은 반올림 좌표가 섞여
    # 엉뚱한 구멍이 구제된다(실측: 쇼팽 D♭에서 진짜 음표 1개가 그렇게 사라졌다).
    src = src.replace(c, "    _HW.clear()\n" + c)
    # blocker 번호는 artifact 제거 **전** raw 기준이다. 제거 뒤 raw로 읽으면 번호가 밀려
    # 엉뚱한 덩어리의 x를 쓴다(2026-09-21 발견 — 이전 5쪽 시뮬레이션의 dx가 이 버그를 안고 있었다).
    src = src.replace(d, d + "    _raw0 = list(raw)\n")
    # 폭은 **순서로** 짝짓는다. 좌표 반올림을 키로 쓰면 같은 밴드의 다른 구멍과 충돌한다
    src = src.replace(a, a.rstrip("\n") + "; _HW.append(hw / spacing)\n")
    src = src.replace(b, b.replace(
        "    for cx, cy, blocker, hy0, hy1 in hollow_candidates:\n",
        "    for _i, (cx, cy, blocker, hy0, hy1) in enumerate(hollow_candidates):\n").replace(
        "        if blocker is not None and blocker not in artifacts:\n",
        "        _w = _HW[_i] if _i < len(_HW) else 0.0\n"
        "        _dx = abs(_raw0[blocker][0] - cx) / spacing if blocker is not None else 9.0\n"
        f"        _rescue = ((hy1 - hy0) / spacing >= {h_min} and {w_lo} <= _w <= {w_hi} and _dx <= {dx_max})\n"
        "        if blocker is not None and blocker not in artifacts and not _rescue:\n"))
    mod = types.ModuleType("modules.notehead_detect")
    mod.__file__ = ND.__file__
    mod._HW = []
    exec(compile(src, "nd_sim", "exec"), mod.__dict__)
    sys.modules["modules.notehead_detect"] = mod
    for name in ("modules.verify", "modules.clef_keysig", "tools.measure_blocked_holes"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "remove_staff_lines"):
            m.remove_staff_lines = mod.remove_staff_lines
    globals()["detect_noteheads"] = mod.detect_noteheads
    return mod


def labels_of(path, page):
    res = preprocess(os.path.join(ROOT, path), pdf_page=page)
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    b, _ = drop_beam_ghosts(res, heads)
    o, _ = drop_offstaff_ghosts(res, b)
    notes = calculate_pitches(o, res.staves, clef={i: c.clef for i, c in ctx.items()})
    final, _ = remove_accidental_ghosts(notes, annotate_accidentals(res, ctx, notes), res.staves)
    filled = {(int(h.x), int(h.y)): bool(h.filled) for h in o}
    return ([dict(x=int(n.x), y=int(n.y), pitch=f"{n.note_name}{n.octave}",
                  filled=filled.get((int(n.x), int(n.y)))) for n in final],
            len(reverse_check(res, final)))


def snapshot():
    """쪽마다 (구멍 추적 결과, 최종 라벨, 유령 수). 추적이 실패하면 holes=None."""
    out = {}
    traced = {p for p, _path, _pg in M.PAGES}
    for page, path, pg in ALL_PAGES:
        rows = None
        if page in traced:
            try:
                rows = M.rows_for(page, path, pg)
            except Exception as exc:                   # 사본을 못 만들거나 내부 구조가 바뀐 경우
                print(f"  [경고] {page}: 내부 추적 실패 ({type(exc).__name__}: {exc}) — 라벨만 본다")
        labels, ghosts = labels_of(path, pg)
        out[page] = dict(holes=rows, labels=labels, ghosts=ghosts)
    return out


def near(labels, x, y, r):
    return [l for l in labels if abs(l["x"] - x) <= r and abs(l["y"] - y) <= r]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save", action="store_true", help="지금 상태를 기준선으로 저장")
    ap.add_argument("--simulate", action="store_true",
                    help="후보 규칙을 사본에 넣어 미리 돌려 본다 (제품 파일 무변경)")
    ap.add_argument("--thresh", default="0.93,1.15,1.30,0.35",
                    help="시뮬레이션 문턱: 높이하한,폭하한,폭상한,dx상한")
    ap.add_argument("--with-tests", action="store_true",
                    help="끝에 tests/run_all.py(골든 711개 포함)까지 돌린다. --simulate와는 같이 못 쓴다")
    args = ap.parse_args()

    if args.simulate and args.with_tests:
        print("--simulate 와 --with-tests 는 같이 쓸 수 없다 (골든은 제품 코드로 돌려야 한다)")
        return 2
    if args.simulate:
        simulate_rule(*[float(v) for v in args.thresh.split(",")])
        M.T.ORIG = M.T.DBG = None      # 사본 추적은 시뮬레이션과 섞이므로 라벨만 본다
        print("[시뮬레이션] 후보 규칙을 사본에 적용했다 — 제품 파일은 그대로다\n")
    now = snapshot()
    if args.save:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        json.dump(now, open(BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n = sum(len([r for r in v["holes"] or [] if r["group"] != "채택"]) for v in now.values())
        print(f"기준선 저장: {BASELINE}  (가려진 구멍 {n}건 · "
              f"채택 {sum(len([r for r in v['holes'] or [] if r['group'] == '채택']) for v in now.values())}건)")
        return 0

    base = json.load(open(BASELINE, encoding="utf-8"))
    missing = [p for p, _a, _b in ALL_PAGES if p not in base]
    if missing:
        print(f"기준선에 없는 쪽 {missing} — 제품 코드로 --save 를 먼저 다시 돌릴 것")
        return 2
    fails = []
    print("== 라벨 수 · 유령")
    for page in base:
        b, n = base[page], now[page]
        nb, nn = len(b["labels"]), len(n["labels"])
        newly = [l for l in n["labels"] if not near(b["labels"], l["x"], l["y"], 6)]
        lost = [l for l in b["labels"] if not near(n["labels"], l["x"], l["y"], 6)
                and not any(abs(l["x"] - ex) <= 6 and abs(l["y"] - ey) <= 6
                            for ex, ey in EXPECTED_LOST.get(page, ()))]
        print(f"  {page:8s} 라벨 {nb} → {nn} ({nn - nb:+d})  유령 {b['ghosts']} → {n['ghosts']}  "
              f"새 라벨 {len(newly)} · 사라진 라벨 {len(lost)}")
        for l in newly[:8]:
            print(f"       새: ({l['x']},{l['y']}) {l['pitch']} {'filled' if l['filled'] else '빈'}")
        for l in lost[:8]:
            print(f"       사라짐: ({l['x']},{l['y']}) {l['pitch']}")
        # 유지된 라벨의 **음고가 바뀌는 것**도 본다. 위치만 보면 못 잡는다
        # (조표 비교를 안 봐서 「시♭」 19개를 놓쳤던 것과 같은 계열이다).
        moved = []
        for l in b["labels"]:
            same = near(n["labels"], l["x"], l["y"], 6)
            if same and all(s["pitch"] != l["pitch"] for s in same):
                moved.append((l["x"], l["y"], l["pitch"], same[0]["pitch"]))
        if moved:
            print(f"       음고 바뀜 {len(moved)}건: {moved[:6]}")
            fails.append(f"{page}: 라벨 {len(moved)}개의 음고가 바뀌었다")
        if lost:
            fails.append(f"{page}: 라벨 {len(lost)}개가 사라졌다")
        if n["ghosts"] > b["ghosts"]:
            fails.append(f"{page}: 유령이 늘었다 {b['ghosts']} → {n['ghosts']}")

    print("\n== 집단별")
    tally = collections.Counter()
    for page in base:
        rows_b = base[page]["holes"] or []
        rows_n = {(r["x"], r["y"]): r for r in (now[page]["holes"] or [])}
        traced = now[page]["holes"] is not None
        for r in rows_b:
            g = r["group"]
            if g == "채택":
                if traced:
                    cur = rows_n.get((r["x"], r["y"]))
                    ok = cur is not None and cur["group"] == "채택"
                    tally[("채택", "유지" if ok else "바뀜")] += 1
                    if not ok and BAND(r):
                        fails.append(f"{page}: 띠 안 채택 구멍 ({r['x']},{r['y']})이 더는 채택되지 않는다")
                continue
            lab = near(now[page]["labels"], r["x"], r["y"], int(r["sp"] * 0.6))
            if g == "A":
                # 여전히 막혀야 한다 = ① 빈 음표 라벨이 새로 생기지 않고
                # ② 그 자리의 **채워진 라벨이 사라지지 않는다**.
                # ②가 중요하다 — 구멍이 구제되면 `_inside_ring`이 그 링 범위 안의 filled 항목을
                # 지운다. 실측: 후보 규칙 시뮬레이션에서 쇼팽 D♭ (2160,2844) 진짜 음표가 이렇게 사라졌다.
                new_hollow = [l for l in lab if l["filled"] is False
                              and not near(base[page]["labels"], l["x"], l["y"], 6)]
                gone = [l for l in near(base[page]["labels"], r["x"], r["y"], int(r["sp"] * 1.0))
                        if not near(now[page]["labels"], l["x"], l["y"], 6)]
                tally[("A", "유지" if not (new_hollow or gone) else "깨짐")] += 1
                if new_hollow:
                    fails.append(f"{page}: A였던 ({r['x']},{r['y']})에 빈 음표 라벨이 생겼다")
                if gone:
                    fails.append(f"{page}: A였던 ({r['x']},{r['y']}) 근처 라벨이 사라졌다 "
                                 f"{[(l['x'], l['y'], l['pitch']) for l in gone]}")
            elif g == "C":
                want = C_TRUTH.get(page, {}).get((r["x"], r["y"]))
                got = [l for l in lab if l["pitch"] == want] if want else lab
                tally[("C", "복구(음고 일치)" if got else
                       "라벨은 있으나 음고 틀림" if lab else "여전히 없음")] += 1
                if lab and not got:
                    fails.append(f"{page}: C ({r['x']},{r['y']}) 라벨은 생겼지만 음고가 "
                                 f"{[l['pitch'] for l in lab]} (정답 {want})")
            else:
                tally[("B", "라벨 있음" if lab else "라벨 없음")] += 1
    for k in sorted(tally, key=str):
        print(f"  {k[0]:4s} {k[1]:10s} {tally[k]}")

    band = [r for page in base for r in (base[page]["holes"] or []) if r["group"] == "채택" and BAND(r)]
    print(f"\n  (참고) 규칙 띠에 드는 채택 구멍 {len(band)}개 — 위 '채택' 항목에 포함")

    c_total = sum(1 for page in base for r in (base[page]["holes"] or []) if r["group"] == "C")
    if tally[("C", "복구(음고 일치)")] < c_total:
        fails.append(f"C {c_total - tally[('C', '복구(음고 일치)')]}건이 정답 음고로 복구되지 않았다 "
                     f"(라벨 없음 {tally[('C', '여전히 없음')]} · 음고 틀림 {tally[('C', '라벨은 있으나 음고 틀림')]})")
    if tally[("B", "라벨 있음")] < sum(1 for page in base for r in (base[page]["holes"] or []) if r["group"] == "B"):
        print("  [주의] B 일부가 라벨을 잃었다 — 저해상도 쪽을 눈으로 볼 것")

    if args.with_tests:
        # 골든은 **제품 코드로** 돌아야 의미가 있다. 사본 시뮬레이션과 섞지 않는다.
        import subprocess
        print("\n== tests/run_all.py (골든 711개 포함)")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "run_all.py")],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-3:]
        print("  " + "\n  ".join(tail))
        if r.returncode != 0:
            fails.append("tests/run_all.py 실패")

    print("\n== 판정")
    if fails:
        for f in fails:
            print("  실패:", f)
        print("\n골든·전체 테스트도 반드시 함께 돌릴 것: python tests/run_all.py")
        return 1
    print("  통과 — A 유지 · C 정답 음고 복구 · 채택 구멍 유지 · 라벨 손실 0 · 음고 변화 0 · 유령 증가 0")
    if not args.with_tests:
        print("  골든·전체 테스트를 함께 돌릴 것: python tests/run_all.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
