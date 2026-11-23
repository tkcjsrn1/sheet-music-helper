# -*- coding: utf-8 -*-
"""임시표 0.5px 재판정(`accidental_unstable`)으로 **새로 check가 된 라벨** 전수 분류 — PR #84 병합 조건. 측정 전용.

검증 20쪽. 라벨·기존 확신도는 `check_accidental_fix.snapshot_page`(제품 경로, 이 신호 없음), 새 신호는
`accidental_detect.unstable_accidentals`(제품 함수)로 따로 얻어 좌표로 합친다.

정답(음이름+옥타브):
- PDF 17쪽: PDF 음표 머리 글리프 + PDF 음자리표 + 오선 반칸(`measure_omission_rate.run_pdf`와 같은 규칙 — 같은 자리 중복 ·
  빠르기 표시 속 음표 제외, 가장 흔한 글자 크기만 일반 머리). 짝짓기 가로 0.7sp · 세로 0.5sp
- RE:Aoharu 3쪽: 골든(전수 판정) 라벨

분류: 이미 check였음 / **새 check — 음고 틀림 · 음고 맞음(check만) · 머리 없음(유령 · 꾸밈음 자리)**.
**임시표 표기의 정답은 없다**(A-11) — 음고가 맞는 라벨의 표기가 맞는지는 이 도구가 가르지 못한다.

    python tools/classify_unstable_checks.py
"""
import io
import os
import sys
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
import measure_omission_rate as M  # noqa: E402
import measure_unstable_accidentals as U  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402


def pdf_truth(path, pg):
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    g = M.pdf_glyphs(path, pg)
    clefs = []
    for c in (x for x in g if x["name"].startswith("clefs.")):
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"]))
        clefs.append(dict(c, staff=st.index))
    heads = []
    for x in (x for x in g if x["name"].startswith("noteheads.")):
        if any(abs(x["cx"] - h["cx"]) < 2 and abs(x["cy"] - h["cy"]) < 2 for h in heads):
            continue
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - x["cy"]))
        if x["cy"] < st.top - 6 * st.spacing or x["cy"] > st.bottom + 6 * st.spacing:
            continue
        heads.append(x)
    main = Counter(x["size"] for x in heads).most_common(1)[0][0]
    normal = [h for h in heads if abs(h["size"] - main) < 0.05]
    for h in normal:
        _si, h["pitch"], _st, _cl = M.truth_pitch(h["cx"], h["cy"], staves, clefs)
    return normal, sp


def golden_truth(tag):
    rows = io.open(os.path.join(ROOT, "tests", "golden", f"aoharu_{tag}.tsv"), encoding="utf-8").read().splitlines()
    out = []
    for r in rows:
        f = r.split("\t")
        out.append(dict(cx=float(f[1]), cy=float(f[2]), pitch=f[3]))
    return out, 11.6


def main():
    total = Counter()
    db1_wrong = []
    lines = []
    new_rows = []
    for page, path, pg in C.PAGES:
        snap = C.snapshot_page(path, pg)["labels"]
        flagged, _t0, _t1 = U.page(os.path.join(ROOT, path), pg)
        unst = [(x, y) for x, y, _p, _t, f in flagged if f]
        truth, sp = golden_truth(f"p{page[-1]}") if page.startswith("aoharu") else pdf_truth(path, pg)
        pairs, _ut, _ul = M.match(truth, snap, sp)
        lab2truth = {li: truth[ti] for ti, li in pairs}
        c = Counter()
        for li, l in enumerate(snap):
            is_unst = any(abs(l["x"] - x) <= 1 and abs(l["y"] - y) <= 1 for x, y in unst)
            before = l.get("confidence")
            if before == "check":
                c["check 전"] += 1
            if not is_unst:
                continue
            if before == "check":
                c["이미 check"] += 1
                continue
            t = lab2truth.get(li)
            if t is None:
                kind = "머리 없음"
            elif t["pitch"] != l["pitch"]:
                kind = "음고 틀림"
            else:
                kind = "음고 맞음"
            c[kind] += 1
            new_rows.append((page, l["x"], l["y"], l["pitch"], l["text"], kind, t["pitch"] if t else "-"))
        if page == "db1":                                   # 기존 음고 오류(OMISSION_RATE §3)와 대조
            db1_wrong = [(l["x"], l["y"], lab2truth[li]["pitch"], l["pitch"]) for li, l in enumerate(snap)
                         if li in lab2truth and lab2truth[li]["pitch"] != l["pitch"]]
        new = c["음고 틀림"] + c["음고 맞음"] + c["머리 없음"]
        lines.append(f"| {page} | {len(snap)} | {c['check 전']} | **{c['check 전'] + new}** (+{new}) | "
                     f"{c['음고 틀림']} | {c['음고 맞음']} | {c['머리 없음']} | {c['이미 check']} |")
        total.update(c)
        total["라벨"] += len(snap)
        print(lines[-1], flush=True)
    new = total["음고 틀림"] + total["음고 맞음"] + total["머리 없음"]
    print(f"| **합계** | {total['라벨']} | {total['check 전']} | **{total['check 전'] + new}** (+{new}) | "
          f"{total['음고 틀림']} | {total['음고 맞음']} | {total['머리 없음']} | {total['이미 check']} |")
    print("\n새 check 전체:")
    for r in new_rows:
        print("  ", r)
    print(f"\nD♭ 1쪽 기존 음고 오류 {len(db1_wrong)}건:", db1_wrong)
    over = [r for r in new_rows if r[0] == "db1" and any(abs(r[1] - x) <= 2 and abs(r[2] - y) <= 2 for x, y, _a, _b in db1_wrong)]
    print(f"그중 새 check와 겹침 {len(over)}:", over)


if __name__ == "__main__":
    main()
