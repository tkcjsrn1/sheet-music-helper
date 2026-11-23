# -*- coding: utf-8 -*-
"""제품 변경 전후 검증 20쪽을 통째로 대조한다 — 라벨(좌표·음고·표기)과 보표 문맥, 보표별 음자리표 끝.

측정 전용. 라벨 계산은 `check_accidental_fix.snapshot`(제품 경로와 같은 순서)을 그대로 쓴다.

    python tools/compare_snapshot.py save  debug/snap_before.json   # 바꾸기 전
    python tools/compare_snapshot.py diff  debug/snap_before.json   # 바꾼 뒤 — 지금 제품과 대조
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
import modules.clef_keysig as CK  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402


def take():
    snap = C.snapshot()
    for page, path, pg in C.PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctx = CK.analyze_staves(res)
        snap[page]["clef_end"] = {str(i): c.clef_end for i, c in ctx.items()}
    return snap


def diff(a, b):
    tot = dict(사라짐=0, 생김=0, 음고=0, 표기=0, 문맥=0, 음자리표끝=0)
    for page in a:
        la, lb = a[page]["labels"], b[page]["labels"]
        used, gone = set(), []
        for p in la:
            k = next((j for j, q in enumerate(lb) if j not in used
                      and abs(q["x"] - p["x"]) <= C.MATCH and abs(q["y"] - p["y"]) <= C.MATCH), None)
            if k is None:
                gone.append(p)
                continue
            used.add(k)
            if lb[k]["pitch"] != p["pitch"]:
                tot["음고"] += 1
                print(f"  {page} 음고 ({p['x']},{p['y']}) {p['pitch']}->{lb[k]['pitch']}")
            elif lb[k]["text"] != p["text"]:
                tot["표기"] += 1
                print(f"  {page} 표기 ({p['x']},{p['y']}) {p['text']}->{lb[k]['text']}")
        new = [q for j, q in enumerate(lb) if j not in used]
        for p in gone:
            print(f"  {page} 사라짐 ({p['x']},{p['y']}) {p['pitch']} {p['text']}")
        for q in new:
            print(f"  {page} 생김   ({q['x']},{q['y']}) {q['pitch']} {q['text']}")
        cd = C.rows_diff(a[page]["context"], b[page]["context"])
        for d in cd:
            print(f"  {page} 문맥 {d}")
        ce = [(i, a[page]["clef_end"][i], b[page]["clef_end"].get(i)) for i in a[page]["clef_end"]
              if a[page]["clef_end"][i] != b[page]["clef_end"].get(i)]
        for i, x, y in ce:
            print(f"  {page} 보표{i} clef_end {x}->{y}")
        tot["사라짐"] += len(gone); tot["생김"] += len(new); tot["문맥"] += len(cd); tot["음자리표끝"] += len(ce)
    print(f"→ {tot}")
    return tot


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "save":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(take(), f, ensure_ascii=False)
        print(f"저장 {path}")
    else:
        with open(path, encoding="utf-8") as f:
            diff(json.load(f), take())
