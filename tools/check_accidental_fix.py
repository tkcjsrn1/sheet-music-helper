# -*- coding: utf-8 -*-
"""임시표 오삭제 수정이 올라오면 **한 번에** 대조하는 검증기.

측정 전용. `modules/`는 읽기만 한다. 형식은 `tools/check_blocking_fix.py`와 같다.

## 쓰는 법

```bash
python tools/check_accidental_fix.py --baseline     # 수정 전(현재 제품)으로 기준선 저장
python tools/check_accidental_fix.py                # 수정 후 대조
python tools/check_accidental_fix.py --with-tests   # 대조 + 골든·tests/run_all.py
```

기준선은 `docs/measurements/accidental_fix_baseline.json`, 확대 그림은 `debug/accidental_fix/`(깃 제외)에 쌓인다.

## 보는 것

| 항목 | 통과 조건 |
|---|---|
| **피해 18개** (전파 9 · 직접 9, `docs/WRONG_DELETIONS.md` §1·§2) | 4px 안 라벨의 **음이름+옥타브와 최종 표기가 정답과 같아야** 복구다. 근처에 라벨이 있기만 하면 복구가 아니다 |
| **정상 삭제 7곳** (`GLYPHS_TO_KEEP_REMOVED`) | 계속 라벨이 없어야 한다 — 유령 제거 기능 유지 |
| **20쪽 라벨** | 사라진 라벨 0. 새 라벨은 목록 + **확대 그림**(유령 검사가 못 잡는다 — 2026-09-21 새 유령 4개에 `reverse_check` 변화 0) |
| **유지된 라벨** | 음이름·옥타브·최종 표기 불변 |
| **문맥** | 쪽마다 음자리표·조표·헤더 끝 불변(`tests/_score_context.context_diff`) |
| **보호 검사 18개** | `tests/test_naturals_real.py`를 돌려 풀린 수(unexpected success)를 센다. 풀린 좌표는 표시를 지워야 한다 |

## 정답 18개의 근거 (2026-09-22)

음이름·옥타브는 **임시표 필터 전** 파이프라인 값을 오선 반칸 위치로 다시 계산해 맞췄다 — 18개 모두
맨 아랫줄 기준 반칸이 정수 ±0.25 안이고 음자리표(높은음 17 · 낮은음 1)로 계산한 음과 같다. 확대 그림으로
18개 모두 실제 음표 머리 위에 있음을 눈으로 확인했다. 표기(♮·♭)는 PR #46 보호 검사의 기대값이고,
그림의 ♮·♭ 기호와 대조했다. **마디 전체의 임시표 전파까지 독립으로 판정한 정답셋은 아니다.**
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import cv2
import numpy as np

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts, reverse_check, diagnose_labels
from modules.labels_io import confidence_of, flags_of
from _score_context import context_rows, label_texts

BASELINE = os.path.join(ROOT, "docs", "measurements", "accidental_fix_baseline.json")
CROP_DIR = os.path.join(ROOT, "debug", "accidental_fix")

_BBM, _DB, _EM = ("test_scores/chopin_nocturne_Bbm.pdf", "test_scores/chopin_nocturne_Db_6-8.pdf",
                  "test_scores/chopin_nocturne_Em.pdf")
_AO = "sample_images/KakaoTalk_20260731_162400402"
# 검증 악보 20쪽. 목표 쪽만 보면 다른 쪽의 새 오삭제를 놓친다(MEASUREMENT_PITFALLS D-3b)
PAGES = ([("bach", "test_scores/bach_minuet_Am.pdf", 0)]
         + [(f"bbm{i + 1}", _BBM, i) for i in range(6)]
         + [(f"db{i + 1}", _DB, i) for i in range(6)]
         + [(f"em{i + 1}", _EM, i) for i in range(4)]
         + [("aoharu1", _AO + ".png", 0), ("aoharu2", _AO + "_01.png", 0),
            ("aoharu3", _AO + "_02.png", 0)])

# (쪽, x, y, 음이름+옥타브, 최종 표기, 종류). 좌표·표기는 tests/test_naturals_real.py와 같다.
VICTIMS = [
    ("db2", 1303, 252, "B5", "시b", "전파"), ("db6", 690, 2676, "G5", "솔", "전파"),
    ("bbm1", 2279, 703, "B5", "시b", "전파"), ("bbm1", 915, 1466, "D5", "레", "전파"),
    ("bbm1", 1250, 1456, "E5", "미", "전파"), ("bbm1", 991, 2846, "B5", "시b", "전파"),
    ("bbm1", 1500, 2884, "E5", "미", "전파"), ("bbm4", 582, 2920, "A5", "라b", "전파"),
    ("bbm5", 985, 2996, "E5", "미", "전파"),
    ("bbm1", 522, 1417, "B5", "시b", "직접"), ("bbm1", 574, 1426, "A5", "라", "직접"),
    ("bbm1", 681, 1436, "G5", "솔", "직접"), ("bbm1", 806, 1456, "E5", "미b", "직접"),
    ("bbm2", 1276, 312, "G5", "솔b", "직접"), ("bbm6", 1378, 334, "E5", "미", "직접"),
    ("db5", 730, 2128, "B5", "시b", "직접"), ("db5", 2152, 2109, "D6", "레b", "직접"),
    ("em4", 1828, 449, "F3", "파#", "직접"),
]
# 정상 삭제(임시표 글리프·빈 자리 유령). 계속 지워져야 한다
KEEP_REMOVED = [("db2", 616, 2601), ("db4", 2000, 888), ("db6", 1664, 2020), ("em3", 2059, 260),
                ("bbm2", 1499, 2515), ("bbm2", 1880, 2524), ("bbm2", 2202, 2515)]
NEAR = 4      # 보호 검사와 같은 허용치
MATCH = 6     # 라벨 대응(사라짐·새로 생김) 허용치 — check_blocking_fix와 같다


def accidental_stage(res, ctx, notes):
    """제품의 임시표 단계(main.py와 같다). `--simulate-*`가 이 함수만 바꿔 끼운다.
    제품이 지우지 않고 넘긴 후보는 FORCE_CHECK로 — 아래에서 mark_accidental_candidates와 같은 효과."""
    flagged = []
    fl = [FILLED.get((n.staff_index, n.x, n.y), False) for n in notes]
    try:
        kept, accs = remove_accidental_ghosts(notes, annotate_accidentals(res, ctx, notes), res.staves,
                                              filled=fl, flagged=flagged)
    except TypeError:            # 수정 전 제품(기준선): filled 인자가 없다
        kept, accs = remove_accidental_ghosts(notes, annotate_accidentals(res, ctx, notes), res.staves)
    FORCE_CHECK.update(id(n) for n in flagged)
    return kept, accs


FORCE_CHECK = set()   # 시뮬레이션이 check로 올리는 음표(id)
FILLED = {}           # (보표, x, y) → 채워진 머리인가. PitchedNote에는 filled가 없어 머리 검출 값을 잇는다


def simulate_raw_limit(mode="raw"):
    """사본에만 넣는다. 제품 파일 무변경. 표기(음고 적용)는 둘 다 effective 그대로다.

    - `raw`  : 삭제 방아쇠로 전파 뒤 임시표(effective) 대신 **직접 검출한 임시표(raw)**만 쓴다
    - `keep` : 아무것도 지우지 않는다
    둘 다 「예전 규칙이면 지워졌을 후보」에 check를 붙인다."""
    import types
    import modules.accidental_detect as AD
    src = open(AD.__file__, encoding="utf-8").read()
    a = "    return effective\n"
    assert src.count(a) == 1, "삽입 지점을 못 찾았다 — 제품 코드가 바뀌었다"
    mod = types.ModuleType("accidental_detect_sim")
    mod.__file__ = AD.__file__
    mod.__package__ = "modules"            # 원본의 상대 import가 그대로 풀리게
    exec(compile(src.replace(a, "    return effective, raw\n"), "ad_sim", "exec"), mod.__dict__)

    def stage(res, ctx, notes):
        eff, raw = mod.annotate_accidentals(res, ctx, notes)
        old, _ = AD.remove_accidental_ghosts(notes, eff, res.staves)    # 예전 규칙이 남기는 것
        old_ids = {id(n) for n in old}
        if mode == "filled":
            # 예전 규칙 그대로 지우되, 지울 후보 중 **채워진 머리**는 남긴다(빈 후보는 지금처럼 지운다)
            kept = [n for n in notes if id(n) in old_ids or FILLED.get((n.staff_index, n.x, n.y), False)]
        else:
            trig = raw if mode == "raw" else [""] * len(notes)         # keep: 방아쇠 없음 = 안 지운다
            kept, _ = AD.remove_accidental_ghosts(notes, trig, res.staves)
        ids = {id(n) for n in kept}
        # 예전 규칙이면 지워졌을 후보에 check를 붙인다(채택안 · 변형안 공통)
        FORCE_CHECK.update(id(n) for n in kept if id(n) not in old_ids)
        return kept, [e for n, e in zip(notes, eff) if id(n) in ids]    # 표기 = effective
    globals()["accidental_stage"] = stage


def snapshot_page(path, pg):
    FORCE_CHECK.clear()                   # id()는 쪽이 바뀌면 재사용될 수 있다
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    FILLED.clear()
    FILLED.update({(h.staff_index, h.x, h.y): bool(h.filled) for h in heads})
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    notes, accs = accidental_stage(res, ctx, notes)
    texts = label_texts(notes, ctx, accs)
    # 확신도 — 사용자 화면의 주황 점선(check)과 같은 계산(main._confidence_values)
    diag = {(int(r["staff"]), int(r["x"]), int(r["y"])): r for r in diagnose_labels(res, notes)}
    labels = [dict(x=int(n.x), y=int(n.y), pitch=f"{n.note_name}{n.octave}", text=t,
                   filled=FILLED.get((n.staff_index, n.x, n.y)),
                   confidence="check" if id(n) in FORCE_CHECK else
                   confidence_of(flags_of(diag.get((int(n.staff_index), int(n.x), int(n.y)), {}))))
              for n, t in zip(notes, texts)]
    return dict(labels=labels, context=context_rows(ctx), ghosts=len(reverse_check(res, notes)))


def snapshot():
    out = {}
    for page, path, pg in PAGES:
        print(f"  {page} ...", flush=True)
        out[page] = snapshot_page(path, pg)
    return out


def rows_diff(a, b, tol=1):
    """`context_rows` 두 목록의 차이 — `_score_context.context_diff`와 같은 규칙을 저장된 행에 적용."""
    ra, rb = {r["staff"]: r for r in a}, {r["staff"]: r for r in b}
    out = [] if set(ra) == set(rb) else [f"보표 목록 {sorted(ra)} -> {sorted(rb)}"]
    for i in sorted(set(ra) & set(rb)):
        out += [f"보표{i} {k} {ra[i][k]}->{rb[i][k]}" for k in ("clef", "key", "letters") if ra[i][k] != rb[i][k]]
        if abs(rb[i]["header_end"] - ra[i]["header_end"]) > tol:
            out.append(f"보표{i} header_end {ra[i]['header_end']}->{rb[i]['header_end']}")
    return out


def near(labels, x, y, r):
    return [l for l in labels if abs(l["x"] - x) <= r and abs(l["y"] - y) <= r]


def victim_status(labels, x, y, pitch, text):
    lab = near(labels, x, y, NEAR)
    if any(l["pitch"] == pitch and l["text"] == text for l in lab):
        return "복구"
    if lab:
        return "음고·표기 틀림 " + ",".join(f"{l['pitch']}/{l['text']}" for l in lab)
    return "미복구"


def crop_grid(items, name):
    """(쪽, x, y, 제목) 목록을 확대해 한 장으로. 사람이 눈으로 판정하라고 만든다."""
    if not items:
        return None
    os.makedirs(CROP_DIR, exist_ok=True)
    paths = {p: (path, pg) for p, path, pg in PAGES}
    cache, tiles = {}, []
    for page, x, y, title in items:
        if page not in cache:
            cache[page] = preprocess(os.path.join(ROOT, paths[page][0]), pdf_page=paths[page][1]).original_bgr
        img = cache[page]
        r = 70
        x0, y0 = max(0, x - r), max(0, y - r)
        c = cv2.resize(img[y0:y + r, x0:x + r].copy(), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.drawMarker(c, ((x - x0) * 3, (y - y0) * 3), (255, 120, 0), cv2.MARKER_CROSS, 18, 2)
        c = cv2.copyMakeBorder(c, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(c, f"{len(tiles) + 1} {page} {title}", (4, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 2)
        tiles.append(cv2.resize(c, (420, 450)))
    while len(tiles) % 4:
        tiles.append(np.full_like(tiles[0], 255))
    grid = np.vstack([np.hstack(tiles[k:k + 4]) for k in range(0, len(tiles), 4)])
    out = os.path.join(CROP_DIR, name)
    ok, buf = cv2.imencode(".png", grid)
    buf.tofile(out)
    return out


def protection_tests():
    """보호 검사 18개를 돌려 (예상 실패 수, 예상 밖 성공 목록)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "test_naturals_real.py")],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = (r.stdout or "") + (r.stderr or "")
    xf = sum(int(n) for n in re.findall(r"expected failures=(\d+)", out))
    us = re.findall(r"(test_(?:carry|direct)_\w+) \(.*?\) \.\.\. unexpected success", out)
    return xf, us, r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", action="store_true", help="현재 제품으로 기준선 저장")
    ap.add_argument("--with-tests", action="store_true", help="끝에 tests/run_all.py(골든 포함)까지 돌린다")
    ap.add_argument("--simulate-raw", action="store_true",
                    help="raw 제한(직접 검출 임시표만 삭제 근거)을 사본에 넣어 미리 본다. 제품 파일 무변경")
    ap.add_argument("--simulate-keep", action="store_true",
                    help="임시표 유령을 하나도 지우지 않고 지웠을 후보를 check로만 표시하는 변형안을 사본에서 본다")
    ap.add_argument("--simulate-filled", action="store_true",
                    help="지울 후보 중 채워진 머리만 남기고 check로 표시하는 안을 사본에서 본다(빈 후보는 지금처럼 지운다)")
    args = ap.parse_args()
    sim = ("raw" if args.simulate_raw else "keep" if args.simulate_keep
           else "filled" if args.simulate_filled else None)
    if sim and (args.baseline or args.with_tests):
        print("--simulate-* 는 --baseline·--with-tests 와 같이 못 쓴다 (둘 다 제품 코드로 돌려야 한다)")
        return 2
    args.simulate_raw = bool(sim)          # 아래 보호 검사 분기는 두 시뮬레이션 공통
    if sim:
        simulate_raw_limit(sim)
        print(f"[시뮬레이션 {sim}] 사본에 적용했다 — 제품 파일은 그대로다. 예전 규칙이면 지워졌을 후보는 check")

    now = snapshot()
    if args.baseline:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
        print(f"\n기준선 저장: {BASELINE}")
    base = json.load(open(BASELINE, encoding="utf-8"))
    fails, new_items = [], []

    print("\n== 피해 18개 (음이름+옥타브와 최종 표기가 정답과 같아야 복구)")
    tally = {}
    for page, x, y, pitch, text, kind in VICTIMS:
        st = victim_status(now[page]["labels"], x, y, pitch, text)
        tally.setdefault(kind, []).append(st == "복구")
        print(f"  [{kind}] {page:5s} ({x},{y}) 정답 {pitch}/{text}: {st}")
        if st.startswith("음고"):
            fails.append(f"{page} ({x},{y}) 라벨은 생겼지만 {st}")
    for kind, oks in tally.items():
        print(f"  {kind}: 복구 {sum(oks)}/{len(oks)}")

    print("\n== 정상 삭제 7곳 (계속 지워져야 한다)")
    for page, x, y in KEEP_REMOVED:
        lab = near(now[page]["labels"], x, y, NEAR)
        print(f"  {page:5s} ({x},{y}): {'유지(라벨 없음)' if not lab else '되살아남 ' + str([(l['pitch'], l['text'], l.get('confidence')) for l in lab])}")
        # 기준(2026-09-22): 계속 지워지거나, 남으면 check여야 한다(tests/test_naturals_real.py와 같다)
        if any(l.get("confidence") != "check" for l in lab):
            fails.append(f"{page} ({x},{y}) 정상 삭제되던 유령이 확실한 라벨로 되살아났다")
        if lab:
            new_items.append((page, x, y, "되살아난 유령(check?)"))

    print("\n== 20쪽 라벨 · 문맥")
    victims = {(p, x, y) for p, x, y, *_ in VICTIMS}
    checks = [0, 0]   # 20쪽 check(주황 점선) 합계: 기준선, 지금
    for page, _path, _pg in PAGES:
        b, n = base[page], now[page]
        newly = [l for l in n["labels"] if not near(b["labels"], l["x"], l["y"], MATCH)]
        lost = [l for l in b["labels"] if not near(n["labels"], l["x"], l["y"], MATCH)]
        changed = []
        for l in b["labels"]:
            same = near(n["labels"], l["x"], l["y"], MATCH)
            if same and all((s["pitch"], s["text"]) != (l["pitch"], l["text"]) for s in same):
                changed.append((l["x"], l["y"], f"{l['pitch']}/{l['text']}", f"{same[0]['pitch']}/{same[0]['text']}"))
        ctxd = rows_diff(b["context"], n["context"])
        cb = sum(1 for l in b["labels"] if l.get("confidence") == "check")
        cn = sum(1 for l in n["labels"] if l.get("confidence") == "check")
        checks[0] += cb
        checks[1] += cn
        print(f"  {page:8s} 라벨 {len(b['labels'])} → {len(n['labels'])}  유령검사 {b['ghosts']} → {n['ghosts']}  "
              f"check {cb} → {cn}  새 {len(newly)} · 사라짐 {len(lost)} · 음고/표기 바뀜 {len(changed)}")
        for l in newly:
            is_victim = any(abs(l["x"] - vx) <= NEAR and abs(l["y"] - vy) <= NEAR
                            for p, vx, vy in victims if p == page)
            tag = "피해 음표 자리" if is_victim else "확인 필요"
            print(f"       새: ({l['x']},{l['y']}) {l['pitch']}/{l['text']} [{l.get('confidence', '?')}] — {tag}")
            new_items.append((page, l["x"], l["y"], f"+{l['pitch']}/{l['text']} {'V' if is_victim else '?'}"))
        for l in lost:
            print(f"       사라짐: ({l['x']},{l['y']}) {l['pitch']}/{l['text']}")
            new_items.append((page, l["x"], l["y"], f"-{l['pitch']}/{l['text']}"))
        for c in changed:
            print(f"       바뀜: {c}")
        for d in ctxd:
            print(f"       문맥: {d}")
        if lost:
            fails.append(f"{page}: 라벨 {len(lost)}개가 사라졌다")
        if changed:
            fails.append(f"{page}: 유지된 라벨 {len(changed)}개의 음고·표기가 바뀌었다")
        if ctxd:
            fails.append(f"{page}: 음자리표·조표·헤더가 바뀌었다 {ctxd}")

    print(f"  20쪽 check 합계 {checks[0]} → {checks[1]} (쪽당 평균 {checks[1] / len(PAGES):.1f})")
    grid = crop_grid(new_items, "changes.png")
    if grid:
        print(f"\n== 확대 그림 {len(new_items)}자리 → {grid}")
        print("   새 라벨은 유령 검사가 못 잡는다. **전부 눈으로 볼 것** (V = 피해 음표 자리, ? = 그 밖)")

    print("\n== 보호 검사 18개 (tests/test_naturals_real.py)")
    if args.simulate_raw:
        print("  시뮬레이션은 테스트 프로세스에 안 들어간다 — 위 18개 판정(같은 좌표·같은 기대값)으로 대신한다")
        xf, us, rc = 18 - sum(sum(v) for v in tally.values()), [], 0
    else:
        xf, us, rc = protection_tests()
    print(f"  예상 실패 {xf} · 풀림(예상 밖 성공) {len(us)}")
    for t in us:
        print(f"    풀림: {t} — 이 좌표의 @expectedFailure를 지워야 한다")
    if rc != 0 and not us:
        fails.append("test_naturals_real.py가 예상 밖 성공 없이 실패했다 — 전제 검사·정상 삭제 검사를 볼 것")

    if args.with_tests:
        print("\n== tests/run_all.py (골든 포함)")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "run_all.py")], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        print("  " + "\n  ".join([l for l in (r.stdout or "").splitlines() if l.strip()][-3:]))
        if r.returncode != 0:
            fails.append("tests/run_all.py 실패")

    print("\n== 판정")
    for f in fails:
        print("  실패:", f)
    print(f"  피해 18개 복구 {sum(sum(v) for v in tally.values())}/18 · 보호 검사 풀림 {len(us)}")
    if not fails:
        print("  대조 실패 없음 — 새 라벨 확대 그림은 사람이 따로 판정해야 한다")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
