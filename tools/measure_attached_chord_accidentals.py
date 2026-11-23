# -*- coding: utf-8 -*-
"""「붙은 화음 + 임시표」 자리에서 표기가 틀린 **확실** 라벨이 몇 개인가 (check84 눈 판정 후속, A-11 연결). 측정 전용.

PDF 17쪽(바흐 · B♭m 6 · D♭ 6 · Em 4). RE:Aoharu는 PDF가 없고 임시표가 0개라 뺐다.

정답(PDF 글리프):
- **붙은 화음**: 일반 크기 음표 머리 중 같은 기둥(가로 0.6sp 이내)에서 위아래 간격 1.05sp 이하로 이어진 묶음(2도 · 3도)
- **임시표 붙음**: PDF 임시표 글리프(♯ ♭ ♮ 𝄪 𝄫)가 머리 바로 왼쪽(가로 0.3~3.5sp · 세로 0.35sp 이내)에 있으면 그 머리의 정답 임시표.
  임시표 하나는 가장 가까운 머리 하나에만 준다
- **표기 정답이 있는 머리 = 임시표가 직접 붙은 머리뿐.** 조표 · 마디 안 전파로 정해지는 머리는 「표기 판정 불가」로 따로 센다(A-11)
- 음고(음이름+옥타브)는 PDF 음자리표 + 가장 가까운 보표의 오선 반칸(`measure_omission_rate.truth_pitch`)

제품 라벨: `check_accidental_fix.snapshot_page`(확신도) + `accidental_detect.unstable_accidentals`(PR #84 신호)를 좌표로 합친다.
「확실」 = 확신도 certain이고 불안정 신호도 없는 라벨(화면에서 점선 · 연한 글씨가 없는 것).

    python tools/measure_attached_chord_accidentals.py
"""
import io
import os
import sys
from collections import Counter

import fitz
import numpy as np
from fontTools.cffLib import CFFFontSet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
import measure_omission_rate as M  # noqa: E402
import measure_unstable_accidentals as U  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402

ACC = {"sharp": "#", "flat": "b", "natural": "", "doublesharp": "##", "flatflat": "bb"}


def glyphs(path, page):
    doc = fitz.open(os.path.join(ROOT, path))
    pg = doc[page]
    fonts = {}
    for f in pg.get_fonts():
        if f[1] != "cff":
            continue
        _n, _e, _t, data = doc.extract_font(f[0])
        cff = CFFFontSet()
        cff.decompile(io.BytesIO(data), None)
        fonts[f[3].split("+")[-1]] = cff[cff.fontNames[0]]
    out, k = [], 300 / 72.0
    for span in pg.get_texttrace():
        top = fonts.get(span["font"])
        if top is None:
            continue
        sc = span["size"] * top.FontMatrix[0]
        for _u, gid, o, _b in span["chars"]:
            n = top.charset[gid]
            if not n.startswith(("noteheads.", "accidentals.", "clefs.")):
                continue
            b = M._outline_bbox(top.CharStrings, n)
            if b is None:
                continue
            out.append(dict(name=n, cx=(o[0] + (b[0] + b[2]) / 2 * sc) * k,
                            cy=(o[1] - (b[1] + b[3]) / 2 * sc) * k, size=round(span["size"], 2)))
    doc.close()
    return out


def suffix(text):
    for s in ("##", "bb", "#", "b"):
        if text.endswith(s):
            return s
    return ""


def page(name, path, pg):
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    g = glyphs(path, pg)
    clefs = []
    for c in (q for q in g if q["name"].startswith("clefs.")):
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"]))
        clefs.append(dict(c, staff=st.index))
    heads = []
    for q in (q for q in g if q["name"].startswith("noteheads.")):
        if any(abs(q["cx"] - h["cx"]) < 2 and abs(q["cy"] - h["cy"]) < 2 for h in heads):
            continue
        heads.append(q)
    main = Counter(h["size"] for h in heads).most_common(1)[0][0]
    heads = [h for h in heads if abs(h["size"] - main) < 0.05]
    for h in heads:
        _si, h["pitch"], _st, _cl = M.truth_pitch(h["cx"], h["cy"], staves, clefs)
        h["acc"] = None
    # 임시표 → 가장 가까운 머리 하나
    accs = []
    for a in (q for q in g if q["name"].startswith("accidentals.")):
        kind = a["name"].split(".")[1]
        if kind not in ACC:
            continue
        cand = [h for h in heads if 0.3 * sp < h["cx"] - a["cx"] < 3.5 * sp and abs(h["cy"] - a["cy"]) <= 0.35 * sp]
        if cand:
            h = min(cand, key=lambda h: h["cx"] - a["cx"])
            if h["acc"] is None:
                h["acc"] = ACC[kind]
                h["acc_glyph"] = a
            accs.append((a, h))
    # 붙은 화음 묶음
    heads.sort(key=lambda h: (h["cx"], h["cy"]))
    groups, used = [], set()
    for i, h in enumerate(heads):
        if i in used:
            continue
        grp = [i]
        changed = True
        while changed:
            changed = False
            for j, q in enumerate(heads):
                if j in grp:
                    continue
                if any(abs(q["cx"] - heads[k]["cx"]) <= 0.6 * sp and abs(q["cy"] - heads[k]["cy"]) <= 1.05 * sp for k in grp):
                    grp.append(j)
                    changed = True
        used.update(grp)
        if len(grp) >= 2:
            groups.append(grp)
    target = [grp for grp in groups if any(heads[k]["acc"] is not None for k in grp)]

    labels = C.snapshot_page(path, pg)["labels"]
    flagged, _a, _b = U.page(os.path.join(ROOT, path), pg)
    unst = [(x, y) for x, y, _p, _t, f in flagged if f]
    for l in labels:
        l["unstable"] = any(abs(l["x"] - x) <= 1 and abs(l["y"] - y) <= 1 for x, y in unst)
        l["grade"] = "check" if (l.get("confidence") == "check" or l["unstable"]) else (
            "주의" if l.get("confidence") == "caution" else "확실")
    pairs, _ut, used_l = M.match(heads, labels, sp)
    h2l = {ti: li for ti, li in pairs}

    c = Counter()
    rows = []
    for grp in target:
        c["자리"] += 1
        xs = [heads[k]["cx"] for k in grp]
        ys = [heads[k]["cy"] for k in grp]
        for k in grp:
            h = heads[k]
            c["머리"] += 1
            li = h2l.get(k)
            if li is None:
                c["누락"] += 1
                rows.append((name, round(h["cx"]), round(h["cy"]), h["pitch"], h["acc"], "누락", "-", "-"))
                continue
            l = labels[li]
            if l["pitch"] != h["pitch"]:
                c[f"음고 틀림 · {l['grade']}"] += 1
                rows.append((name, round(h["cx"]), round(h["cy"]), h["pitch"], h["acc"], "음고 틀림", l["text"], l["grade"]))
                continue
            if h["acc"] is None:
                c["표기 판정 불가"] += 1
                continue
            ok = suffix(l["text"]) == h["acc"]
            c[f"표기 {'맞음' if ok else '틀림'} · {l['grade']}"] += 1
            if not ok:
                rows.append((name, round(h["cx"]), round(h["cy"]), h["pitch"], h["acc"], "표기 틀림", l["text"], l["grade"]))
        # 이 화음 머리에 붙은 임시표 글리프 **자리**에 라벨이 있나 = 임시표 글리프를 머리로 잡은 유령
        #   (check84 눈 판정 #1 · #3 · #4의 「♯ 빠진 레·솔」은 이것이었다 — 진짜 머리가 아니라 ♯ 글리프 자리)
        for k in grp:
            a = heads[k].get("acc_glyph")
            if a is None:
                continue
            for li, l in enumerate(labels):
                if li not in used_l and abs(l["x"] - a["cx"]) <= 0.6 * sp and abs(l["y"] - a["cy"]) <= 0.5 * sp:
                    c[f"임시표 자리 유령 · {l['grade']}"] += 1
                    rows.append((name, l["x"], l["y"], heads[k]["pitch"], heads[k]["acc"], "임시표 자리 유령", l["text"], l["grade"]))
        # 화음 자리 안의 라벨 중 어느 머리와도 짝이 안 된 것 = 중간 유령
        for li, l in enumerate(labels):
            if li in used_l:
                continue
            if min(xs) - 0.7 * sp <= l["x"] <= max(xs) + 0.7 * sp and min(ys) - 0.5 * sp <= l["y"] <= max(ys) + 0.5 * sp:
                c[f"자리 안 유령 · {l['grade']}"] += 1
                rows.append((name, l["x"], l["y"], "-", None, "유령", l["text"], l["grade"]))
    return c, rows


def main():
    total, allrows = Counter(), []
    print("| 쪽 | 자리 | 머리 | 누락 | 음고 틀림(확실/주의/check) | 표기 틀림(확실/주의/check) | 표기 맞음 | 표기 판정 불가 | 자리 안 유령(확실/주의/check) | 임시표 자리 유령(확실/주의/check) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, path, pg in C.PAGES:
        if name.startswith("aoharu"):
            continue
        c, rows = page(name, path, pg)
        total.update(c)
        allrows += rows

        def tri(k):
            return f"{c[k + ' · 확실']}/{c[k + ' · 주의']}/{c[k + ' · check']}"
        ok = c["표기 맞음 · 확실"] + c["표기 맞음 · 주의"] + c["표기 맞음 · check"]
        print(f"| {name} | {c['자리']} | {c['머리']} | {c['누락']} | {tri('음고 틀림')} | {tri('표기 틀림')} | {ok} | {c['표기 판정 불가']} | {tri('자리 안 유령')} | {tri('임시표 자리 유령')} |", flush=True)
    c = total

    def tri(k):
        return f"{c[k + ' · 확실']}/{c[k + ' · 주의']}/{c[k + ' · check']}"
    ok = c["표기 맞음 · 확실"] + c["표기 맞음 · 주의"] + c["표기 맞음 · check"]
    print(f"| **합계** | {c['자리']} | {c['머리']} | {c['누락']} | {tri('음고 틀림')} | {tri('표기 틀림')} | {ok} | {c['표기 판정 불가']} | {tri('자리 안 유령')} | {tri('임시표 자리 유령')} |")
    print(f"\n**표기가 틀린 확실 라벨: {c['표기 틀림 · 확실']}**  (음고 틀린 확실 라벨 {c['음고 틀림 · 확실']}, 자리 안 확실 유령 {c['자리 안 유령 · 확실']}, 임시표 자리 확실 유령 {c['임시표 자리 유령 · 확실']})")
    print("\n문제 목록 (쪽, x, y, 정답 음고, 정답 임시표, 종류, 라벨 표기, 등급):")
    for r in allrows:
        print("  ", r)


if __name__ == "__main__":
    main()
