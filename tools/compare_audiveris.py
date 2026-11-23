# -*- coding: utf-8 -*-
"""Audiveris 5.11.0 결과를 **우리와 같은 정답·같은 기준**으로 센다 — 쪽마다 따로.

정답은 `tools/measure_omission_rate.py`와 같다(PDF 음표 머리 글리프, 겹친 글리프·다른 크기 제외).
Audiveris 쪽은 `docs/measurements/omr_feasibility/`의 머리 목록(`heads.tsv`)과 음 목록(`notes.tsv`)을 읽기만 한다.
D♭ 1쪽은 PR #59(Codex), 바흐·B♭m 1쪽은 같은 설치본·같은 명령으로 CLI가 돌린 결과다(`run_bach_bbm.log`).

## 대조 방법

1. **좌표**: Audiveris 입력은 우리와 같은 300dpi 렌더라 `heads.tsv`의 x/y/w/h 중심을 그대로 쓴다.
   확인: 세 쪽 모두 중앙 어긋남 0.5px 미만
2. **짝짓기**: 우리와 같다 — 가까운 쌍부터 1:1, 가로 0.7sp · 세로 0.5sp 안
3. **음고(머리 위치)**: Audiveris 머리의 `relative_pitch`(보표 가운데 줄 0, 위가 음수, 반칸)를 음이름·옥타브로
   바꾼다. 음자리표는 **PDF 음자리표**(정답과 같은 것) — 머리를 오선 어디에 놓았는지만 본다.
   곡 중간 음자리표 변경이 있어도 틀리지 않게 하려는 것이다
3b. **음고(MusicXML)**: Audiveris의 음자리표 판독까지 들어간 최종 음 목록은 좌표가 없어 개별 대응을 못 한다.
   음이름+옥타브 **묶음**을 정답과 비교해 차이를 적는다(서로 뒤바뀐 경우는 못 잡는다)
4. **대조 불가**: 정답 머리 중 크기가 다른 것(꾸밈음·빠르기 표시)은 우리처럼 정답에서 빼고,
   거기 붙은 Audiveris 머리는 유령으로 세지 않고 따로 센다
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import numpy as np

import measure_omission_rate as R
from modules.preprocess import preprocess

OMR = os.path.join(ROOT, "docs", "measurements", "omr_feasibility")
# 쪽: (PDF, 쪽 번호, heads.tsv, notes.tsv, 우리 결과 report.json 키)
PAGES = {"db1": ("test_scores/chopin_nocturne_Db_6-8.pdf", 0, os.path.join(OMR, "heads.tsv"), os.path.join(OMR, "notes.tsv")),
         "bach": ("test_scores/bach_minuet_Am.pdf", 0, os.path.join(OMR, "bach_p1", "heads.tsv"), os.path.join(OMR, "bach_p1", "notes.tsv")),
         "bbm1": ("test_scores/chopin_nocturne_Bbm.pdf", 0, os.path.join(OMR, "chopin_Bbm_p1", "heads.tsv"), os.path.join(OMR, "chopin_Bbm_p1", "notes.tsv"))}


def run(page):
    path, pg, heads_tsv, notes_tsv = PAGES[page]
    if not os.path.isfile(heads_tsv):
        print(f"== {page}: Audiveris 머리 목록 없음({heads_tsv}) — 처리 실패로 센다")
        return None
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    g = R.pdf_glyphs(path, pg)
    clefs_pdf = []
    for c in (x for x in g if x["name"].startswith("clefs.")):
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"]))
        clefs_pdf.append(dict(c, staff=st.index))
    heads = []
    for x in (x for x in g if x["name"].startswith("noteheads.")):
        if any(abs(x["cx"] - h["cx"]) < 2 and abs(x["cy"] - h["cy"]) < 2 for h in heads):
            continue
        heads.append(x)
    main_size = Counter(h["size"] for h in heads).most_common(1)[0][0]
    truth = [h for h in heads if abs(h["size"] - main_size) < 0.05]
    other = [h for h in heads if abs(h["size"] - main_size) >= 0.05]
    for h in truth:
        h["staff"], h["pitch"], h["step"], h["clef"] = R.truth_pitch(h["cx"], h["cy"], staves, clefs_pdf)

    rows = list(csv.DictReader(open(heads_tsv, encoding="utf-8"), delimiter="	"))
    aud = []
    for r in rows:
        cx = int(r["x"]) + int(r["w"]) / 2.0
        cy = int(r["y"]) + int(r["h"]) / 2.0
        # 머리 위치 음고: 반칸(가운데 줄 = 맨 아랫줄에서 4, 위가 음수) + PDF 음자리표
        step = 4 - int(r["relative_pitch"])
        st_idx, _p, _s, kind = R.truth_pitch(cx, cy, staves, clefs_pdf)
        letter, octave = R.BOTTOM[kind]
        i = R.LETTERS.index(letter) + step
        aud.append(dict(x=cx, y=cy, staff=st_idx, pitch=f"{R.LETTERS[i % 7]}{octave + i // 7}",
                        shape=r["shape"], rp=int(r["relative_pitch"])))
    off = np.median([[min(truth, key=lambda t: (t["cx"] - a["x"]) ** 2 + (t["cy"] - a["y"]) ** 2)["cx"] - a["x"],
                      min(truth, key=lambda t: (t["cx"] - a["x"]) ** 2 + (t["cy"] - a["y"]) ** 2)["cy"] - a["y"]]
                     for a in aud], axis=0)

    pairs, used_t, used_a = R.match(truth, aud, sp)
    missing = [truth[i] for i in range(len(truth)) if i not in used_t]
    extra = [aud[i] for i in range(len(aud)) if i not in used_a]
    _p, _t, on_other = R.match(other, extra, sp)
    ghosts = [extra[i] for i in range(len(extra)) if i not in on_other]
    # 두 성부가 같은 음을 공유하면 Audiveris는 머리를 성부마다 따로 낸다 — 정답은 하나로 셌으므로 대조 불가
    shared = [a for a in ghosts if any(abs(a["x"] - t["cx"]) < 3 and abs(a["y"] - t["cy"]) < 3 for t in truth)]
    ghosts = [a for a in ghosts if a not in shared]
    wrong = [(truth[ti], aud[ai]) for ti, ai in pairs if truth[ti]["pitch"] != aud[ai]["pitch"]]
    agree = np.mean([truth[ti]["step"] == 4 - aud[ai]["rp"] for ti, ai in pairs]) if pairs else 0

    # MusicXML 음 목록(Audiveris 음자리표 판독 포함) — 음이름+옥타브 묶음 비교
    notes = list(csv.DictReader(open(notes_tsv, encoding="utf-8"), delimiter="	"))
    xml = Counter(f"{n['step']}{n['octave']}" for n in notes if n["grace"] != "True")
    tru = Counter(h["pitch"] for h in truth)

    print(f"\n== {page}  정답 {len(truth)} (다른 크기 {len(other)} 제외) · Audiveris 머리 {len(aud)} · 짝 {len(pairs)}"
          f" · 좌표 어긋남 중앙 {off.round(2).tolist()}px · 반칸 일치 {agree:.3f}")
    print(f"   오삭제 {len(missing)} ({len(missing) / len(truth):.1%}) · 유령 {len(ghosts)} · "
          f"다른 크기 머리에 붙은 것 {len(on_other)} · 성부 공유(대조 불가) {len(shared)} · 음고 오류(머리 위치) {len(wrong)}")
    print(f"   MusicXML 음 {len(notes)} (꾸밈음 표시 {sum(n['grace'] == 'True' for n in notes)}) · "
          f"정답에만 많은 음 {dict(tru - xml)} · MusicXML에만 많은 음 {dict(xml - tru)}")
    for h in missing:
        print(f"   오삭제 ({h['cx']:.0f},{h['cy']:.0f}) {h['pitch']}")
    for a in ghosts:
        print(f"   유령 ({a['x']:.0f},{a['y']:.0f}) {a['pitch']} {a['shape']}")
    for t, a in wrong:
        print(f"   음고 ({t['cx']:.0f},{t['cy']:.0f}) 정답 {t['pitch']} · Audiveris {a['pitch']} (rp {a['rp']})")
    items = ([(h["cx"], h["cy"], f"-{h['pitch']}") for h in missing]
             + [(a["x"], a["y"], f"+{a['pitch']}") for a in ghosts]
             + [(t["cx"], t["cy"], f"{t['pitch']}!={a['pitch']}") for t, a in wrong])
    os.makedirs(R.OUT, exist_ok=True)
    R.grid(res.original_bgr, items, os.path.join(R.OUT, f"audiveris_{page}_mismatch.png"))
    return dict(truth=len(truth), missing=len(missing), ghosts=len(ghosts), wrong=len(wrong))


def run_aoharu(heads_tsv, scale, label):
    """RE:Aoharu 1쪽 — PDF가 없어 정답은 골든 라벨 226개(전수 판정 + 음표 쪽 확인, `OMISSION_RATE.md`).
    확대 입력은 Audiveris 좌표를 `scale`로 나눠 원본 좌표로 되돌린다. 음자리표는 골든 문맥 파일."""
    img = "sample_images/KakaoTalk_20260731_162400402.png"
    res = preprocess(os.path.join(ROOT, img), pdf_page=0)
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    gold = os.path.join(ROOT, "tests", "golden")
    clef = {int(r[0]): r[1] for r in csv.reader(open(os.path.join(gold, "aoharu_p1_context.tsv"), encoding="utf-8"),
                                                delimiter="\t")}
    truth = [dict(cx=float(r[1]), cy=float(r[2]), pitch=r[3], staff=int(r[0]))
             for r in csv.reader(open(os.path.join(gold, "aoharu_p1.tsv"), encoding="utf-8"), delimiter="\t")]
    rows = list(csv.DictReader(open(heads_tsv, encoding="utf-8"), delimiter="\t"))
    # relative_pitch는 **Audiveris가 배정한 보표** 기준이다. 머리마다 y로 가장 가까운 보표를 고르면 두 보표 사이 음에서
    # 기준이 어긋나고(실측: 2개가 C2), 번호 순서로 대응하면 입력에 따라 보표를 더/덜 잡을 때 밀린다(2배 이진화 60개).
    # 그래서 Audiveris 보표 번호마다 **그 번호 머리들의 중앙 y**에 가장 가까운 우리 보표로 대응시킨다
    ys = {}
    for r in rows:
        ys.setdefault(r["staff"], []).append((int(r["y"]) + int(r["h"]) / 2.0) / scale)
    to_ours = {k: min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - float(np.median(v)))).index
               for k, v in ys.items()}
    aud = []
    for r in rows:
        cx = (int(r["x"]) + int(r["w"]) / 2.0) / scale
        cy = (int(r["y"]) + int(r["h"]) / 2.0) / scale
        idx = to_ours[r["staff"]]
        letter, octave = R.BOTTOM[clef.get(idx, "treble")]
        i = R.LETTERS.index(letter) + 4 - int(r["relative_pitch"])
        aud.append(dict(x=cx, y=cy, pitch=f"{R.LETTERS[i % 7]}{octave + i // 7}", rp=int(r["relative_pitch"])))
    pairs, used_t, used_a = R.match(truth, aud, sp)
    missing = [truth[i] for i in range(len(truth)) if i not in used_t]
    ghosts = [aud[i] for i in range(len(aud)) if i not in used_a]
    wrong = [(truth[ti], aud[ai]) for ti, ai in pairs if truth[ti]["pitch"] != aud[ai]["pitch"]]
    print(f"\n== aoharu1 {label}  정답 {len(truth)} · Audiveris 머리 {len(aud)} · 짝 {len(pairs)}")
    print(f"   오삭제 {len(missing)} ({len(missing) / len(truth):.1%}) · 유령 {len(ghosts)} · 음고 오류 {len(wrong)}")
    items = ([(h["cx"], h["cy"], f"-{h['pitch']}") for h in missing]
             + [(a["x"], a["y"], f"+{a['pitch']}") for a in ghosts]
             + [(t["cx"], t["cy"], f"{t['pitch']}!={a['pitch']}") for t, a in wrong])
    R.grid(res.original_bgr, items, os.path.join(R.OUT, f"audiveris_aoharu_{label}_mismatch.png"))
    return dict(truth=len(truth), missing=len(missing), ghosts=len(ghosts), wrong=len(wrong))


if __name__ == "__main__":
    if sys.argv[1:2] == ["aoharu"]:          # python tools/compare_audiveris.py aoharu <heads.tsv> <배율> <이름>
        run_aoharu(sys.argv[2], float(sys.argv[3]), sys.argv[4])
    else:
        for p in (sys.argv[1:] or list(PAGES)):
            run(p)
