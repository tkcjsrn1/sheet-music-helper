# -*- coding: utf-8 -*-
"""큐 1 분석 — 화음 임시표 열 묶음 (2026-10-19 · 정답만 읽는 측정, 제품 코드 무변경).

Verovio 개발 20쪽 정답(`debug/vrv/truth`)의 인쇄 임시표 상자(acc_box)로:
  ① 창 왼끝(머리 − 2.0sp) 밖 임시표 38의 종류 — 화음 열(같은 x 화음에 다른 임시표가 있음) · 단독(괄호 · 넓은 글리프 등)
  ② 화음 임시표 묶음(같은 화음 x ± 0.3sp에 임시표 2개 이상)의 열 수 · 열 간격 · 높이 순서와 열 배치
  ③ 묶음 왼쪽 끝 ~ 화음 사이에 다른 음 머리 · 다른 임시표가 끼는 경우(기각 33 · 39의 실패 원인 — 넓힌 쪽에 남의 기호)

    python tools/measure_acc_columns.py
"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = 18.0


def main():
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    out_kind, ncol, gaps, order, intr, outside_in_group = Counter(), Counter(), [], Counter(), Counter(), Counter()
    rows = []
    for f in sorted(os.listdir(D)):
        if not f.endswith("_p1.json"):
            continue
        T = [n for n in json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"] if not (n["grace"] or n["cue"])]
        acc = [n for n in T if n["accidental"] and n["acc_box"]]
        seen = set()
        for n in acc:
            if id(n) in seen:
                continue
            grp = [m for m in acc if m["staff"] == n["staff"] and abs(m["x"] - n["x"]) <= 0.3 * SP]
            for m in grp:
                seen.add(id(m))
            if len(grp) < 2:
                continue
            # 열: 상자 오른끝 x로 묶음(0.3sp 안 = 같은 열)
            xs = sorted({round(m["acc_box"][2]) for m in grp})
            cols = []
            for x in xs:
                if cols and x - cols[-1][-1] <= 0.3 * SP:
                    cols[-1].append(x)
                else:
                    cols.append([x])
            ncol[len(cols)] += 1
            cr = [sum(c) / len(c) for c in cols]
            gaps += [round((cr[i + 1] - cr[i]) / SP, 2) for i in range(len(cr) - 1)]
            # 높이 순서: 위에서부터 머리 순서대로 놓았을 때 열 번호(0 = 머리에 가장 가까운 열)
            col_of = lambda m: len(cr) - 1 - min(range(len(cr)), key=lambda i: abs(cr[i] - m["acc_box"][2]))
            seq = tuple(col_of(m) for m in sorted(grp, key=lambda m: m["y"]))
            order[seq] += 1
            hx = max(m["x"] for m in grp)
            for m in grp:
                gap = (m["x"] - m["acc_box"][0]) / SP
                outside_in_group[gap > 2.0] += 1
            # 묶음 왼끝 ~ 머리 사이 · 묶음 높이 ±2sp에 끼는 다른 머리(앞 음)
            left = min(m["acc_box"][0] for m in grp)
            y0, y1 = min(m["y"] for m in grp) - 2 * SP, max(m["y"] for m in grp) + 2 * SP
            others = [o for o in T if o["staff"] == n["staff"] and left - 0.5 * SP <= o["x"] < hx - 0.3 * SP and y0 <= o["y"] <= y1]
            intr["묶음 안 · 앞 음 머리 있음" if others else "묶음 안 · 앞 음 머리 없음"] += 1
            rows.append(dict(page=f[:-5], x=hx, n=len(grp), cols=len(cols), seq=seq, others=len(others)))
        for n in acc:
            if (n["x"] - n["acc_box"][0]) / SP <= 2.0:
                continue
            chord = any(m is not n and m["staff"] == n["staff"] and abs(m["x"] - n["x"]) <= 0.3 * SP for m in acc)
            out_kind["화음 열" if chord else "단독"] += 1
    print("① 창 밖 임시표:", dict(out_kind))
    print("② 화음 임시표 묶음", sum(ncol.values()), "· 열 수:", sorted(ncol.items()), "· 묶음 속 임시표 창 밖:", dict(outside_in_group))
    gs = sorted(gaps)
    print("   열 간격(sp, 상자 오른끝):", gs[:3], "…", gs[-3:], "· 중앙", gs[len(gs) // 2] if gs else "-")
    print("   높이순(위 → 아래) 열 번호 상위:", order.most_common(8))
    print("③", dict(intr))
    for r in rows:
        if r["others"]:
            print("     ", r)


if __name__ == "__main__":
    main()
