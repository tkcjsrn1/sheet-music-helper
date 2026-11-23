# -*- coding: utf-8 -*-
"""오류 총조사 (2026-10-15 · 측정만, 보류 세트 미사용) — 지금 main 라벨의 오류를 누락 · 유령 · 음고 틀림 · 표기 틀림으로 나누고 원인 유형별로 센다.

라벨: 49쪽 = `debug/sim_lp/<이름>`(지금 main과 같은 인식 코드로 만든 것), Mutopia = `debug/inputs_score/mutopia/*.json`(`score_inputs.py mutopia`).
정답: Verovio = SVG(음고 · 실효 임시표 · 적힌 임시표 · 꾸밈음 · 음자리표 바뀜 · 임시표 상자), PDF · 보지 않은 = `measure_pdf_effective`와 같은 계산
  (머리 글리프 + 적힌 임시표 + 마디선 전파 + 곡 조표) + 작은 머리(꾸밈음) + 임시표 글리프 상자. Mutopia = 머리 위치만(누락 · 유령만).
  Aoharu는 정답 골든(라벨 = 정답)이라 빼고, organ2는 정답 좌표 불일치 쪽이라 뺀다.
짝짓기: 가로 0.7sp · 세로 0.5sp 안 1:1(가까운 것부터). 「확실」 = 라벨 확신도 certain.
원인 유형은 자동 규칙(아래 `_kind_*`)이다 — 판정이 아니라 분류이고, 유형별 예시 좌표를 남겨 눈으로 확인할 수 있게 한다.

    python tools/error_census.py [라벨이름]      # 기본 flatc1u → debug/error_census.json + 표
"""
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "error_census.json")
NORM = {"natural": "", None: "", "n": "", "s": "#", "f": "b"}
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _truth_vrv(name):
    t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
    heads = [dict(x=n["x"], y=n["y"], staff=n["staff"], pitch=n["note_name"] + n["octave"], eff=NORM.get(n["eff"], n["eff"] or ""),
                  own=NORM.get(n["accidental"], n["accidental"] or ""), small=bool(n["grace"] or n["cue"]),
                  clef_changed=n.get("clef_now") != n.get("clef_start")) for n in t["notes"]]
    boxes = [tuple(n["acc_box"]) for n in t["notes"] if n["acc_box"]]
    return heads, boxes, 18.0


def _truth_pdf(name, path, pg):
    import measure_pdf_effective as E
    import measure_omission_rate as M
    rain_flat = name == "rain1"
    E.KEYS.update({"moon": "FCGD", "rain": "BEADG" if rain_flat else "FCGD"})
    E.KEY_SIGN.update({"moon": "#", "rain": "b" if rain_flat else "#"})
    res, out = E.effective(name, path, pg)
    sp = float(np.median([s.spacing for s in res.staves]))
    g = M.pdf_glyphs(path, pg, ("noteheads.", "accidentals."))
    nh = [q for q in g if q["name"].startswith("noteheads.")]
    main = Counter(q["size"] for q in nh).most_common(1)[0][0] if nh else 1.0
    small = [(q["cx"], q["cy"]) for q in nh if abs(q["size"] - main) >= 0.05]
    boxes = [(q["cx"] - q["w"] / 2, q["cy"] - q["h"] / 2, q["cx"] + q["w"] / 2, q["cy"] + q["h"] / 2) for q in g if q["name"].startswith("accidentals.")]
    heads = []
    for o in out:
        heads.append(dict(x=o["x"], y=o["y"], staff=o["staff"], pitch=o["pitch"], eff=NORM.get(o.get("eff"), o.get("eff") or ""),
                          own=NORM.get(o.get("own"), o.get("own") or ""),
                          small=any(abs(o["x"] - a) < 2 and abs(o["y"] - b) < 2 for a, b in small), clef_changed=False))
    return heads, boxes, sp


def _match(heads, labels, sp):
    pairs = sorted((abs(h["x"] - l["x"]) + abs(h["y"] - l["y"]), i, j) for i, h in enumerate(heads) for j, l in enumerate(labels)
                   if abs(h["x"] - l["x"]) <= 0.7 * sp and abs(h["y"] - l["y"]) <= 0.5 * sp)
    hi, lj, m = set(), set(), {}
    for _d, i, j in pairs:
        if i in hi or j in lj:
            continue
        hi.add(i); lj.add(j); m[i] = j
    return m


def _staff_box(doc, y):
    """y에 가장 가까운 보표(라벨 파일의 보표 — 정답 쪽 보표 번호와 다를 수 있어 높이로 고른다)."""
    s = min(doc["staves"], key=lambda s: abs((s["top"] + s["bottom"]) / 2 - y), default=None)
    return (s["top"], s["bottom"], s["spacing"]) if s else None


def _kind_missing(h, heads, sp, doc):
    if h["small"]:
        return "꾸밈음 · 작은 음표"
    same = [o for o in heads if o is not h and o["staff"] == h["staff"]]
    col = [o for o in same if abs(o["x"] - h["x"]) <= 0.6 * sp]
    if any(abs(o["y"] - h["y"]) <= 0.55 * sp and abs(o["x"] - h["x"]) <= 1.3 * sp for o in same):
        return "2도 · 유니즌 화음"
    if len(col) >= 2:
        return "3머리 이상 화음(가운데 등)"
    if col:
        return "2머리 화음(3도 이상)"
    sb = _staff_box(doc, h["y"])
    if sb and (h["y"] < sb[0] - 0.6 * sb[2] or h["y"] > sb[1] + 0.6 * sb[2]):
        return "덧줄 구역 단독"
    return "오선 안 단독"


def _kind_ghost(l, boxes, sp):
    f = set(l["flags"])
    if any(b[0] - 0.3 * sp <= l["x"] <= b[2] + 0.3 * sp and b[1] - 0.3 * sp <= l["y"] <= b[3] + 0.3 * sp for b in boxes):
        return "임시표 글리프 위"
    if f & {"clef_glyph", "clef_changed", "clef_alto", "clef_unknown"}:
        return "음자리표 글리프 · 구간"
    if f & {"beam_adjacent", "beam_sloped", "beam_gap"}:
        return "빔 · 빔 사이"
    if f & {"narrow_hole"}:
        return "글자 · 셈여림 고리"
    if "off_staff" in f:
        return "오선 밖(글자 · 숫자 · 기호)"
    if f & {"weak_side_ink", "glyph_shape"}:
        return "약한 잉크 · 글리프 모양"
    return "오선 안 기타"


def _kind_pitch(l, h):
    f = set(l["flags"])
    if h.get("clef_changed") or f & {"clef_changed", "clef_alto", "clef_unknown"}:
        return "음자리표 바뀜 · 알토 · 못 찾음 구간"
    if l["pitch"][:-1] == h["pitch"][:-1]:
        return "옥타브만 틀림"
    steps = "CDEFGAB"
    try:
        d = abs((steps.index(l["pitch"][0]) + 7 * int(l["pitch"][-1])) - (steps.index(h["pitch"][0]) + 7 * int(h["pitch"][-1])))
    except ValueError:
        d = 99
    return "한 칸(2도) 어긋남" if d == 1 else "두 칸 이상 어긋남"


def _kind_spell(l, h, boxes, sp):
    la, eff, own = ACC(l["text"]), h["eff"], h["own"]
    if own:
        if la == "":
            near = [b for b in boxes if b[2] <= h["x"] and abs((b[1] + b[3]) / 2 - h["y"]) <= 1.5 * sp and h["x"] - b[2] <= 4 * sp]
            left = min((h["x"] - b[0] for b in near), default=None)
            if left is not None and left > 2.0 * sp:
                return "자기 임시표가 창 왼끝(2sp) 밖"
            return "자기 임시표 못 읽음(창 안)"
        return "자기 임시표 종류를 다르게 읽음"
    if la and not eff:
        return "없는 임시표를 붙임(전파 · 남의 글리프)"
    if eff and not la:
        return "전파 · 조표를 놓침"
    return "전파 · 조표 종류 다름"


def _page(job):
    st, name, path, pg, lab = job
    doc = json.load(open(lab, encoding="utf-8"))
    L = doc["labels"]
    if st == "verovio":
        heads, boxes, sp = _truth_vrv(name)
    else:
        heads, boxes, sp = _truth_pdf(name, path, pg)
    m = _match(heads, L, sp)
    rows = []
    used = set(m.values())
    for i, h in enumerate(heads):
        if i not in m:
            rows.append(dict(kind="누락", cause=_kind_missing(h, heads, sp, doc), certain=False, page=name, x=round(h["x"]), y=round(h["y"])))
            continue
        l = L[m[i]]
        if l["pitch"] != h["pitch"]:
            rows.append(dict(kind="음고 틀림", cause=_kind_pitch(l, h), certain=l["confidence"] == "certain", page=name, x=l["x"], y=l["y"]))
        elif ACC(l["text"]) != h["eff"]:
            rows.append(dict(kind="표기 틀림", cause=_kind_spell(l, h, boxes, sp), certain=l["confidence"] == "certain", page=name, x=l["x"], y=l["y"],
                             own=h["own"], eff=h["eff"], label=l["text"]))
    for j, l in enumerate(L):
        if j not in used:
            dup = any(abs(h["x"] - l["x"]) <= 0.7 * sp and abs(h["y"] - l["y"]) <= 0.5 * sp for h in heads)
            rows.append(dict(kind="유령", cause="같은 머리에 라벨 2개(중복)" if dup else _kind_ghost(l, boxes, sp), certain=l["confidence"] == "certain", page=name, x=l["x"], y=l["y"]))
    return dict(set=st, page=name, heads=len(heads), labels=len(L), rows=rows)


def _mutopia():
    import glob
    from measure_normalize_sp import truth_at
    out = []
    for lab in sorted(glob.glob(os.path.join(ROOT, "debug", "inputs_score", "mutopia", "*.json"))):
        stem = os.path.basename(lab)[:-5]
        f, p = stem.rsplit("_p", 1)
        path = os.path.join("inputs", "mutopia", f + ".pdf")
        doc = json.load(open(lab, encoding="utf-8"))
        L = doc["labels"]
        sp = float(np.median([s["spacing"] for s in doc["staves"]]))
        hs, _clefs = truth_at(path, int(p) - 1, 1.0)
        heads = [dict(x=h["cx"], y=h["cy"], staff=-1, pitch="", eff="", own="", small=False, clef_changed=False) for h in hs]
        m = _match(heads, L, sp)
        rows = [dict(kind="누락", cause="(Mutopia — 원인 미분류)", certain=False, page=stem, x=round(h["x"]), y=round(h["y"])) for i, h in enumerate(heads) if i not in m]
        used = set(m.values())
        rows += [dict(kind="유령", cause=_kind_ghost(l, [], sp), certain=l["confidence"] == "certain", page=stem, x=l["x"], y=l["y"])
                 for j, l in enumerate(L) if j not in used]
        out.append(dict(set="mutopia", page=stem, heads=len(heads), labels=len(L), rows=rows))
    return out


def main(name="flatc1u"):
    import measure_sim_ledger_pair as S
    jobs = [(st, n, p, pg, os.path.join(ROOT, "debug", "sim_lp", name, n + ".json")) for st, n, p, pg in S.pages()
            if st != "aoharu" and n != "organ2"]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        P = list(ex.map(_page, jobs))
    P += _mutopia()
    json.dump(P, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(P)


def report(P=None):
    P = P or json.load(open(OUT, encoding="utf-8"))
    sets = Counter()
    for p in P:
        sets[p["set"]] += p["heads"]
    print("정답 머리:", dict(sets))
    rows = [r | dict(set=p["set"]) for p in P for r in p["rows"]]
    for kind in ("누락", "유령", "음고 틀림", "표기 틀림"):
        R = [r for r in rows if r["kind"] == kind]
        print(f"== {kind} {len(R)} (확실 {sum(r['certain'] for r in R)})")
        by = defaultdict(list)
        for r in R:
            by[r["cause"]].append(r)
        for cause, rr in sorted(by.items(), key=lambda kv: -len(kv[1])):
            s = Counter(r["set"] for r in rr)
            ex = [(r["page"], r["x"], r["y"]) for r in rr if r["certain"]][:3] or [(r["page"], r["x"], r["y"]) for r in rr][:2]
            print(f"   {cause:28s} {len(rr):5d} · 확실 {sum(r['certain'] for r in rr):4d} · {dict(s)} · 예 {ex}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["report"]:
        report()
    else:
        main(*sys.argv[1:2])
