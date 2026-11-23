# -*- coding: utf-8 -*-
"""재표본화(회전 보정 등) 뒤 **임시표 표기가 표시 없이 바뀌는 것**을 해부한다. 측정 전용.

원본과 변형 이미지를 같은 제품 경로(`check_accidental_fix.snapshot_page` — 확신도까지)로 돌려
라벨을 좌표(±6px)로 짝짓고, **음고는 같은데 최종 표기가 다른** 라벨마다

- 방향: 생김(임시표 없음 → 있음) · 사라짐 · 바뀜(♯→♭ 등). 조표를 뺀 **임시표 성분**으로 본다
- 단계: 직접(그 음표 자신의 글리프 검출이 달라짐) · 전파(자기 글리프는 같고 마디 안 앞 음표의 임시표나 마디선이 달라짐)
- 확신도: 변형 쪽 라벨에 check(주황 점선)가 붙었나

    python tools/measure_resample_accidentals.py <원본> <쪽> <변형 png>...   # 변형은 원본과 같은 좌표계(되돌린 이미지)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402
import modules.accidental_detect as A  # noqa: E402
from modules.notehead_detect import remove_staff_lines  # noqa: E402

ACC = {"#": "♯", "b": "♭"}


def acc_part(text):
    """표기에서 임시표 성분(계이름 뒤 #/b/♮). 조표 반영분과 섞여 있으므로 원본과의 **차이**로만 쓴다."""
    for s in ("##", "bb", "#", "b"):
        if text.endswith(s):
            return s
    return ""


def internals(path, page):
    """(음표, raw 임시표, 유효 임시표, 보표별 마디선) — 제품과 같은 순서로 다시 계산."""
    res = preprocess(path, pdf_page=page)
    ctxs = analyze_staves(res)
    from modules.notehead_detect import detect_noteheads
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    heads = detect_noteheads(res, contexts=ctxs)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctxs.items()})
    eff = A.annotate_accidentals(res, ctxs, notes)
    # raw = 음표 하나씩 넣으면 전파가 없다
    raw = [A.annotate_accidentals(res, ctxs, [n])[0] for n in notes]
    ns = remove_staff_lines(res.binary, res.staves)
    bars = {s.index: A._find_barlines(ns, s, res.binary.shape[0]) for s in res.staves}
    return notes, raw, eff, bars


def near(notes, x, y, r=6):
    best = None
    for i, n in enumerate(notes):
        d = abs(n.x - x) + abs(n.y - y)
        if d <= 2 * r and (best is None or d < best[0]):
            best = (d, i)
    return None if best is None else best[1]


def analyze(src, page, variants):
    base = C.snapshot_page(src, page)
    bi = internals(os.path.join(ROOT, src), page)
    total = {"생김": 0, "사라짐": 0, "바뀜": 0}
    rows = []
    for v in variants:
        got = C.snapshot_page(v, 0)
        vi = None
        used = set()
        for p in base["labels"]:
            k = next((j for j, q in enumerate(got["labels"]) if j not in used
                      and abs(q["x"] - p["x"]) <= C.MATCH and abs(q["y"] - p["y"]) <= C.MATCH), None)
            if k is None:
                continue
            used.add(k)
            q = got["labels"][k]
            if q["pitch"] != p["pitch"] or q["text"] == p["text"]:
                continue
            a0, a1 = acc_part(p["text"]), acc_part(q["text"])
            direction = "생김" if not a0 and a1 else ("사라짐" if a0 and not a1 else "바뀜")
            if vi is None:
                vi = internals(os.path.join(ROOT, v), 0)
            ib, iv = near(bi[0], p["x"], p["y"]), near(vi[0], q["x"], q["y"])
            if ib is None or iv is None:
                stage = "대응 실패"
            elif bi[1][ib] != vi[1][iv]:
                stage = f"직접(raw {bi[1][ib] or '-'}→{vi[1][iv] or '-'})"
            else:
                n = bi[0][ib]
                bb = [b for b in bi[3].get(n.staff_index, []) if abs(b - n.x) < 400]
                vb = [b for b in vi[3].get(vi[0][iv].staff_index, []) if abs(b - n.x) < 400]
                bar_changed = sorted(bb) != sorted(vb) and (len(bb) != len(vb) or max(abs(a - b) for a, b in zip(sorted(bb), sorted(vb))) > 3)
                stage = f"전파(유효 {bi[2][ib] or '-'}→{vi[2][iv] or '-'}{', 마디선 달라짐' if bar_changed else ''})"
            total[direction] += 1
            rows.append(f"{os.path.basename(v):22s} ({p['x']},{p['y']}) {p['pitch']:4s} {p['text']}→{q['text']:5s} "
                        f"{direction:3s} {stage:34s} 확신도 {p['confidence']}→{q['confidence']}")
    print("\n".join(rows))
    print(f"→ {os.path.basename(src)} p{page}: 변형 {len(variants)}개, 표기 변화 {sum(total.values())} {total} · "
          f"check 붙은 것 {sum(1 for r in rows if r.endswith('check'))}")




def effective(path, page, shift=None):
    """(음표, 유효 임시표). shift=(dx, dy)면 원본을 그만큼 평행이동(INTER_LINEAR)한 영상으로 판정한다."""
    import cv2
    import numpy as np
    from modules.preprocess import binarize, PreprocessResult
    from modules.notehead_detect import detect_noteheads
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    res = preprocess(path, pdf_page=page)
    if shift:
        m = np.array([[1.0, 0, shift[0]], [0, 1.0, shift[1]]])
        bgr = cv2.warpAffine(res.original_bgr, m, (res.original_bgr.shape[1], res.original_bgr.shape[0]),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        gray, binary = binarize(bgr)
        res = PreprocessResult(original_bgr=bgr, gray=gray, binary=binary, staves=res.staves)  # 보표는 그대로 — 임시표만 흔든다
    ctxs = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctxs)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctxs.items()})
    return notes, A.annotate_accidentals(res, ctxs, notes)


def selfcheck(src, page, variants):
    """후보: 같은 영상을 (0.5, 0.5)px 옮겨 임시표를 다시 판정해 **다르면 check**.
    - 잡음: 원본 대비 표기가 바뀐 음표 중 이 검사가 표시한 수
    - 헛경보: 표시했지만 원본과 같은 음표 수, 그리고 임시표가 붙은 음표 대비 비율"""
    bn, be = effective(os.path.join(ROOT, src), page)
    rows = []
    for v in [os.path.join(ROOT, src)] + variants:
        pg = page if v.endswith(src) else 0
        vn, ve = effective(v, pg)
        sn, se = effective(v, pg, shift=(0.5, 0.5))
        flagged = set()
        for i, n in enumerate(vn):
            j = near(sn, n.x + 0.5, n.y + 0.5)
            if j is not None and se[j] != ve[i]:
                flagged.add(i)
        changed, caught = 0, 0
        for i, n in enumerate(vn):
            k = near(bn, n.x, n.y)
            if k is not None and bn[k].note_name == n.note_name and bn[k].octave == n.octave and be[k] != ve[i]:
                changed += 1
                caught += i in flagged
        with_acc = sum(1 for a in ve if a)
        rows.append(f"{os.path.basename(v):34s} 표기 변화 {changed} · 그중 표시 {caught} | 표시 {len(flagged)} "
                    f"(임시표 붙은 음표 {with_acc}개, 전체 {len(vn)}개)")
    print("\n".join(rows))


if __name__ == "__main__":
    if sys.argv[1] == "--selfcheck":
        selfcheck(sys.argv[2], int(sys.argv[3]), sys.argv[4:])
    else:
        analyze(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
