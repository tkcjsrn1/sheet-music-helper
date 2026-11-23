# -*- coding: utf-8 -*-
"""TASKS [4] Verovio 다른 조판 세트 측정 (2026-10-02, 제품 코드 무변경 · 측정만).

정답: `test_scores/verovio/*.tsv`는 머리 좌표 · 음이름 · **인쇄된** 임시표뿐이다. 최종 표기(조표 · 마디 안 전파 포함)와
원인 분류에 필요한 것을 얻으려고 `build_verovio_set.py`와 **같은 입력 · 같은 Verovio 옵션**으로 SVG를 다시 그려(PNG는 안 만듦)
머리마다 실효 임시표(accid / accid.ges) · 머리 글리프(SMuFL 코드) · 꾸밈음 여부, 보표마다 오선 y · 음자리표 · 조표,
그리고 기호 상자(임시표 · 조표 · 음자리표 · 쉼표 · 빔 · 꼬리 · 글자 …)를 읽는다. 다시 만든 머리 행이 TSV와 **전부 같아야** 쓴다.

라벨: 제품 `main.run_page`(명령줄과 같은 경로 — 측정 함정 A-3b)의 라벨 JSON. A-17 사본은 `measure_a17_ghost6`의 가로채기를 그대로 건다.
짝짓기: `measure_omission_rate.match`(가까운 쌍부터 1:1, 가로 0.7sp · 세로 0.5sp) — PDF 17쪽 측정과 같은 함수.

    python tools/measure_verovio.py truth                 # debug/vrv/truth/<stem>.json
    python tools/measure_verovio.py run <base|c12|c12g13h3>   # debug/vrv/<variant>/<stem>.json
    python tools/measure_verovio.py eval <variant>        # debug/vrv/eval_<variant>.json + 표
    python tools/measure_verovio.py pdf17                 # 같은 평가기로 PDF 17쪽(스냅샷 = main.py 출력)
    python tools/measure_verovio.py raw <variant> <vrv|pdf17>    # A-17 원시 판정 행렬
    python tools/measure_verovio.py diff <variant>        # 기준 대비 고쳐짐 · 새로 틀림 · 새 유령 · 사라짐(정답 기준)
"""
import csv
import json
import os
import re
import sys
import types
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

SET_DIR = os.path.join(ROOT, "test_scores", "verovio")
OUT = os.path.join(ROOT, "debug", "vrv")
NS = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}href"
SOLFEGE = dict(C="도", D="레", E="미", F="파", G="솔", A="라", B="시")
ACC = {"s": "#", "f": "b", "n": "natural", "ss": "##", "ff": "bb", "x": "##"}
HOLLOW_GLYPHS = ("E0A0", "E0A2", "E0A3")            # SMuFL 두온 · 온 · 2분 머리
FLAT_ORDER, SHARP_ORDER = "BEADGCF", "FCGDAEB"
CLEF = {"G": "treble", "F": "bass", "C": "alto"}
BOX_CLASSES = ("accid", "keySig", "clef", "meterSig", "rest", "mRest", "beam", "flag", "stem", "dot", "text", "dynam",
               "tempo", "tie", "slur", "barLine", "artic", "fermata", "trill", "turn", "mordent", "fing", "mNum",
               "dir", "harm", "pedal", "hairpin", "label", "labelAbbr", "tuplet", "tupletNum", "ledgerLines above",
               "ledgerLines below", "arpeg", "octave", "breath")


def stems():
    return sorted(f[:-4] for f in os.listdir(SET_DIR) if f.endswith("_p1.png"))


# ------------------------------------------------------------------ 정답 다시 만들기
def _builder():
    sys.modules.setdefault("cairosvg", types.ModuleType("cairosvg"))     # PNG 단계는 쓰지 않는다
    import build_verovio_set as B
    return B


def _offset(el, parents):
    dx = dy = 0.0
    a = parents.get(el)
    while a is not None:
        t = a.get("transform")
        if t:
            m = re.fullmatch(r"translate\(\s*([\d.-]+)[, ]+([\d.-]+)\s*\)", t)
            if not m:
                raise ValueError(f"지원하지 않는 SVG 변환: {t}")
            dx += float(m[1])
            dy += float(m[2])
        a = parents.get(a)
    return dx, dy


def _box(group, parents, sx, sy):
    """'<class> bounding-box' 그룹의 rect → 화소 상자 (x0, y0, x1, y1)."""
    rect = next((c for c in group.iter() if c.tag == NS + "rect"), None)
    if rect is None:
        return None
    try:
        dx, dy = _offset(rect, parents)
    except ValueError:                      # 회전된 글자(세로 글자 등) — 유령 분류용 상자라 빼도 된다
        return None
    x, y = float(rect.get("x")) + dx, float(rect.get("y")) + dy
    return (round(x * sx, 1), round(y * sy, 1), round((x + float(rect.get("width"))) * sx, 1),
            round((y + float(rect.get("height"))) * sy, 1))


def _key_alter(sig, letter):
    """조표 sig('4f' · '2s' · '0')가 이 음이름에 주는 변화."""
    m = re.fullmatch(r"(\d+)([sf]?)", sig or "0")
    if not m or not m[2]:
        return ""
    n = int(m[1])
    return ("b" if letter in FLAT_ORDER[:n] else "") if m[2] == "f" else ("#" if letter in SHARP_ORDER[:n] else "")


def svg_truth(svg, tk):
    root = ET.fromstring(svg)
    inner = next(n for n in root if n.tag == NS + "svg")
    _, _, vw, vh = map(float, inner.get("viewBox").split())
    sx = float(root.get("width").removesuffix("px")) / vw
    sy = float(root.get("height").removesuffix("px")) / vh
    parents = {c: p for p in root.iter() for c in p}

    def anc(el, cls):
        a = parents.get(el)
        while a is not None:
            if a.get("class") == cls:
                return a
            a = parents.get(a)
        return None

    # 보표: 시스템 순서 · 보표 번호 n. 오선 y는 staff 그룹의 path 5개
    staves = []
    for si, system in enumerate(e for e in root.iter() if e.get("class") == "system"):
        lines = {}
        for staff in (e for e in system.iter() if e.get("class") == "staff"):
            n = tk.getElementAttr(staff.get("id")).get("n")
            ys = []
            for p in staff:
                if p.tag == NS + "path":
                    dx, dy = _offset(p, parents)
                    nums = list(map(float, re.findall(r"[-\d.]+", p.get("d"))))
                    ys.append(round((nums[1] + dy) * sy, 1))
                    xr = (round((nums[0] + dx) * sx, 1), round((nums[2] + dx) * sx, 1))
            if len(ys) == 5:
                cur = lines.setdefault(n, dict(system=si, n=n, line_ys=ys, x0=xr[0], x1=xr[1], clefs=[], keysigs=[]))
                cur["x1"] = max(cur["x1"], xr[1])
            for cls, key in (("clef", "clefs"), ("keySig", "keysigs")):
                for e in (e for e in staff.iter() if e.get("class") == cls):
                    a = tk.getElementAttr(e.get("id"))
                    b = next((_box(g, parents, sx, sy) for g in e if g.get("class") == cls + " bounding-box"), None)
                    if cls == "clef":
                        val = (CLEF.get(a["shape"], a["shape"]) + (a.get("line", "") if a["shape"] == "C" else "")
                               if a.get("shape") else "?" + json.dumps(a))
                    else:
                        val = a.get("sig", "0")
                    if b and n in lines:
                        lines[n][key].append(dict(x=b[0], val=val, dis=a.get("dis")))
        for n in sorted(lines, key=lambda k: lines[k]["line_ys"][0]):
            st = lines[n]
            st["clefs"].sort(key=lambda c: c["x"])
            st["keysigs"].sort(key=lambda c: c["x"])
            staves.append(st)

    def staff_of(y):
        return min(range(len(staves)), key=lambda i: abs(np.mean(staves[i]["line_ys"]) - y))

    # 기호 상자 — 유령 출처 분류
    boxes = []
    for g in root.iter():
        c = g.get("class") or ""
        if c.endswith(" bounding-box"):
            base = c[: -len(" bounding-box")]
            if base in BOX_CLASSES:
                b = _box(g, parents, sx, sy)
                if b:
                    boxes.append(dict(cls=base, box=b))
    for g in root.iter():                                          # 덧줄은 상자가 없어 path로
        if (g.get("class") or "").startswith("ledgerLines"):
            for p in g.iter():
                if p.tag == NS + "path":
                    dx, dy = _offset(p, parents)
                    nums = list(map(float, re.findall(r"[-\d.]+", p.get("d"))))
                    boxes.append(dict(cls="ledger", box=(round((nums[0] + dx) * sx, 1), round((nums[1] + dy) * sy - 2, 1),
                                                         round((nums[2] + dx) * sx, 1), round((nums[1] + dy) * sy + 2, 1))))

    notes = []
    for note in (e for e in root.iter() if e.get("class") == "note"):
        rect = next((c for c in note.iter() if c.tag == NS + "rect" and parents[c].get("class") == "note bounding-box"), None)
        dx, dy = _offset(rect, parents)
        x = round((float(rect.get("x")) + float(rect.get("width")) / 2 + dx) * sx, 2)
        y = round((float(rect.get("y")) + float(rect.get("height")) / 2 + dy) * sy, 2)
        nid = note.get("id")
        na = tk.getElementAttr(nid)
        printed, ges, acc_box, raw_acc = "", "", None, None
        for ch in note.iter():
            if ch.get("class") == "accid":
                a = tk.getElementAttr(ch.get("id"))
                raw_acc = a.get("accid")
                printed = ACC.get(raw_acc, "")
                ges = ACC.get(a.get("accid.ges"), "")
                acc_box = next((_box(g, parents, sx, sy) for g in ch if g.get("class") == "accid bounding-box"), None)
                break
        ges = ges or ACC.get(na.get("accid.ges"), "")
        eff = printed or ges
        eff = "" if eff == "natural" else eff
        glyph = ""
        for ch in note.iter():
            if ch.get("class") == "notehead":
                u = next((u for u in ch.iter() if u.tag == NS + "use"), None)
                if u is not None:
                    glyph = (u.get(XLINK) or u.get("href") or "#")[1:5]
        chord = anc(note, "chord")
        ca = tk.getElementAttr(chord.get("id")) if chord is not None else {}
        grace = bool(na.get("grace") or ca.get("grace"))
        cue = (na.get("cue") or ca.get("cue")) == "true"
        si = staff_of(y)
        st = staves[si]
        clef_now = next((c["val"] for c in reversed(st["clefs"]) if c["x"] < x), st["clefs"][0]["val"] if st["clefs"] else "")
        clef_start = st["clefs"][0]["val"] if st["clefs"] else ""
        key_now = next((k["val"] for k in reversed(st["keysigs"]) if k["x"] < x), "0")
        letter = note.get("data-pname", "").upper()
        notes.append(dict(id=nid, x=x, y=y, note_name=letter, octave=note.get("data-oct", ""), accidental=printed, accid_raw=raw_acc,
                          chord=int(chord is not None), eff=eff, glyph=glyph, grace=grace, cue=cue, staff=si,
                          clef_now=clef_now, clef_start=clef_start, key_now=key_now, key_alter=_key_alter(key_now, letter),
                          acc_box=acc_box))
    return dict(staves=staves, notes=notes, boxes=boxes)


def truth():
    """세트를 만든 경로 그대로 SVG를 다시 그려 정답을 보강한다. 머리 행이 TSV와 다르면 멈춘다."""
    B = _builder()
    import verovio
    os.makedirs(os.path.join(OUT, "truth"), exist_ok=True)
    resource, mapped = B.resource_path()
    try:
        verovio.setDefaultResourcePath(resource)
        for name, rel, part in B.SCORES:
            data = B.musicxml(B.CORPUS / rel, part)
            for font in ("Bravura", "Leipzig"):
                tk = verovio.toolkit()
                tk.setOptions({"inputFrom": "musicxml", "font": font, "pageWidth": 2100, "pageHeight": 2970, "scale": 100,
                               "svgBoundingBoxes": True, "svgAdditionalAttribute": ["note@pname", "note@oct"]})
                assert tk.loadData(data)
                svg = tk.renderToSVG(1)
                t = svg_truth(svg, tk)
                stem = f"{name}_{font.lower()}_p1"
                with open(os.path.join(SET_DIR, stem + ".tsv"), encoding="utf-8") as f:
                    rows = list(csv.DictReader(f, delimiter="\t"))
                assert len(rows) == len(t["notes"]), (stem, len(rows), len(t["notes"]))
                tsv_gap = []
                for r, n in zip(rows, t["notes"]):
                    # TSV는 빌더 대응표(B.ACCIDENTALS)로 적었다 — 그 표에 없는 인쇄 임시표(겹올림 'x' 등)는 TSV에 빈 칸
                    same = (abs(float(r["x"]) - n["x"]) < 0.01 and abs(float(r["y"]) - n["y"]) < 0.01
                            and r["note_name"] == n["note_name"] and r["octave"] == n["octave"]
                            and r["accidental"] == B.ACCIDENTALS.get(n["accid_raw"], "") and int(r["chord"]) == n["chord"])
                    assert same, (stem, r, n)
                    if r["accidental"] != n["accidental"]:
                        tsv_gap.append(dict(x=n["x"], y=n["y"], tsv=r["accidental"], svg=n["accid_raw"]))
                t["tsv_gap"] = tsv_gap
                json.dump(t, open(os.path.join(OUT, "truth", stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
                c = Counter((n["grace"], n["cue"]) for n in t["notes"])
                print(stem, "머리", len(t["notes"]), "TSV 일치", f"(TSV에 빠진 인쇄 임시표 {len(tsv_gap)})", "보표", len(t["staves"]), "꾸밈음·작은", dict(c),
                      "음자리표", sorted({s["clefs"][0]["val"] for s in t["staves"] if s["clefs"]}),
                      "조표", sorted({k["val"] for s in t["staves"] for k in s["keysigs"]}), flush=True)
    finally:
        if mapped:
            import subprocess
            subprocess.run(["subst", mapped, "/D"], check=True)


# ------------------------------------------------------------------ 제품 라벨
def run(variant, pages=None):
    """run_page 라벨 JSON. variant base = 제품 그대로, 그 밖은 measure_a17_ghost6 사본(가로채기)."""
    import measure_a17_ghost6 as G
    G.set_variant(variant)
    out = os.path.join(OUT, variant)
    os.makedirs(out, exist_ok=True)
    for stem in pages or stems():
        G.HOLLOW.clear()
        G.LAST.clear()
        js = os.path.join(out, stem + ".json")
        argv = [os.path.join(SET_DIR, stem + ".png"), "--page", "0", "--no-debug", "--output-dir", os.path.join(OUT, "_png"),
                "--save-labels", js]
        os.makedirs(os.path.join(OUT, "_png"), exist_ok=True)
        sys.argv = ["main.py"] + argv
        args = G.T1.MAIN.parse_args()
        if variant in G.VARIANT_FIX:
            G.install(True)
        elif variant == "c12":
            G.T1.MAIN.annotate_accidentals = G.AD.annotate_accidentals = G.T.MODES["c12"]
        try:
            G.T1.MAIN.run_page(args, argv[0], 0, os.path.join(OUT, "_png"))
            print(variant, stem, "완료", flush=True)
        except SystemExit as e:
            print(variant, stem, "실패", e, flush=True)
        finally:
            G.install(False)


# ------------------------------------------------------------------ 평가
def load(variant, stem):
    p = os.path.join(OUT, variant, stem + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def product_key_alter(music, letter):
    if letter in (music.get("key_letters") or []):
        return {"♭": "b", "♯": "#"}.get(music.get("key_symbol"), "")
    return ""


def norm_acc(a):
    return "" if a in (None, "", "-", "natural") else a


def expected_text(n):
    return SOLFEGE[n["note_name"]] + n["eff"]


def box_hits(boxes, x, y, pad=2):
    return sorted({b["cls"] for b in boxes if b["box"][0] - pad <= x <= b["box"][2] + pad and b["box"][1] - pad <= y <= b["box"][3] + pad})


def evaluate_page(stem, js, t):
    import measure_omission_rate as M
    staves = js["staves"]
    sp = float(np.median([s["spacing"] for s in staves]))
    labels = js["labels"]
    music = js["music"]
    notes = t["notes"]
    normal = [dict(n, cx=n["x"], cy=n["y"]) for n in notes if not n["grace"] and not n["cue"]]
    small = [dict(n, cx=n["x"], cy=n["y"]) for n in notes if n["grace"] or n["cue"]]
    pairs, used_t, used_l = M.match(normal, labels, sp)
    h2l = dict(pairs)
    # 보표 대응: 정답 보표마다 가장 가까운 제품 보표(가운데 y 1sp 안)
    tmap = {}
    for i, st in enumerate(t["staves"]):
        c = np.mean(st["line_ys"])
        best = min(staves, key=lambda s: abs((s["top"] + s["bottom"]) / 2 - c)) if staves else None
        tmap[i] = best if best is not None and abs((best["top"] + best["bottom"]) / 2 - c) <= sp else None
    header = dict(truth_staves=len(t["staves"]), product_staves=len(staves),
                  staves_missing=sum(1 for v in tmap.values() if v is None),
                  clef_wrong=[dict(staff=i, truth=st["clefs"][0]["val"] if st["clefs"] else "", got=tmap[i]["clef"])
                              for i, st in enumerate(t["staves"]) if tmap[i] is not None and st["clefs"]
                              and st["clefs"][0]["val"] != tmap[i]["clef"]],
                  key_truth=sorted({k["val"] for s in t["staves"] for k in s["keysigs"]}, key=lambda v: (len(v), v)),
                  key_first=(t["staves"][0]["keysigs"][0]["val"] if t["staves"] and t["staves"][0]["keysigs"] else "0"),
                  key_got=f"{music.get('key_count', 0)}{ {'♭': 'f', '♯': 's'}.get(music.get('key_symbol'), '') }")
    header["key_ok"] = (header["key_got"] in (header["key_first"],) or (header["key_got"] == "0" and header["key_first"] == "0"))
    rows = []
    for i, h in enumerate(normal):
        chord = any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp
                    for j, q in enumerate(normal))
        st = t["staves"][h["staff"]]
        tsp = (st["line_ys"][-1] - st["line_ys"][0]) / 4
        k = int(round((h["cy"] - st["line_ys"][0]) / (tsp / 2)))
        r = dict(x=h["x"], y=h["y"], truth=f"{h['note_name']}{h['octave']}", text_truth=expected_text(h), printed=h["accidental"],
                 eff=h["eff"], key_alter=h["key_alter"], key_now=h["key_now"], clef_now=h["clef_now"], clef_start=h["clef_start"], staff=h["staff"],
                 chord=chord, hollow=h["glyph"] in HOLLOW_GLYPHS, ledger=not 0 <= k <= 8, staff_found=tmap[h["staff"]] is not None)
        if i not in h2l:
            r["status"] = "누락"
        else:
            lab = labels[h2l[i]]
            r.update(label=dict(x=lab["x"], y=lab["y"], pitch=lab["pitch"], text=lab["text"], acc=lab["accidental"],
                                conf=lab["confidence"], staff=lab["staff"]))
            if lab["pitch"] != r["truth"]:
                r["status"] = "음고"
            elif lab["text"] != r["text_truth"]:
                r["status"] = "표기"
            else:
                r["status"] = "맞음"
        rows.append(r)
    # 짝 없는 라벨: 꾸밈음 자리 라벨은 따로
    ghosts_all = [labels[i] for i in range(len(labels)) if i not in used_l]
    _p, _t, small_hit = M.match(small, ghosts_all, sp)
    ghosts = []
    for i, g in enumerate(ghosts_all):
        if i in small_hit:
            continue
        near = min(normal, key=lambda n: abs(n["cx"] - g["x"]) + abs(n["cy"] - g["y"])) if normal else None
        ghosts.append(dict(x=g["x"], y=g["y"], pitch=g["pitch"], text=g["text"], conf=g["confidence"],
                           on=box_hits(t["boxes"], g["x"], g["y"]),
                           near_head=(round((g["x"] - near["cx"]) / sp, 2), round((g["y"] - near["cy"]) / sp, 2)) if near else None))
    return dict(stem=stem, sp=round(sp, 2), header=header, rows=rows, ghosts=ghosts, small=len(small), small_labeled=len(small_hit),
                labels=len(labels))


def cause_pitch(r, header):
    """음고 틀림 원인(자동, 좌표 · 문맥 근거)."""
    if r["clef_now"] != r["clef_start"]:
        return "음자리표 바뀜(보표 중간)"
    if any(c["staff"] == r["staff"] for c in header["clef_wrong"]):
        return "음자리표 오판(머리)"
    L, T = "CDEFGAB", r["truth"]
    g = r["label"]["pitch"]
    d = (L.index(g[0]) + 7 * int(g[1:])) - (L.index(T[0]) + 7 * int(T[1:]))
    return f"반칸 {d:+d}" if abs(d) <= 2 else ("옥타브" if abs(d) in (7, 14) else f"반칸 {d:+d}")


def cause_text(r, music, header=None):
    """표기 틀림(음고는 맞음) 원인. 조표는 「쪽 머리 조표를 틀리게 읽음」과 「곡 중간 조바꿈(제품은 쪽에 한 번만 판정)」을 가른다."""
    got = norm_acc(r["label"]["acc"])
    pk = product_key_alter(music, r["truth"][0])
    if r["printed"]:
        return "인쇄된 임시표 오판" if got != norm_acc(r["printed"]) else "인쇄된 임시표 맞음 · 표기 다름"
    if got:
        return "없는 임시표(직접 오판 또는 전파)"
    if r["eff"] != r["key_alter"]:
        return "마디 안 전파 놓침"
    if pk != r["key_alter"]:
        if header is not None and r.get("key_now", header["key_first"]) != header["key_first"]:
            return "곡 중간 조바꿈"
        return "조표 오판"
    return "기타"


def summarize(evs, music_of):
    tot = Counter()
    cat = Counter()
    causes = defaultdict(Counter)
    for e in evs:
        for r in e["rows"]:
            for c in ["전체", "화음" if r["chord"] else "단일", "빈 머리" if r["hollow"] else "꽉 찬 머리"] + (["덧줄 구역"] if r["ledger"] else []):
                cat[c + " · 정답"] += 1
                cat[c + " · " + r["status"]] += 1
            if r["status"] == "음고":
                causes["음고"][cause_pitch(r, e["header"])] += 1
            elif r["status"] == "표기":
                causes["표기"][cause_text(r, music_of[e["stem"]], e["header"])] += 1
            elif r["status"] == "누락":
                causes["누락"]["보표 못 찾음" if not r["staff_found"] else
                             ("화음" if r["chord"] else "빈 머리" if r["hollow"] else "덧줄 구역" if r["ledger"] else "단일")] += 1
        for g in e["ghosts"]:
            on = [c for c in g["on"] if c not in ("ledger",)] or (["덧줄만"] if g["on"] else ["표시 없는 자리"])
            causes["유령"][on[0] if len(on) == 1 else "+".join(on[:2])] += 1
        tot["유령"] += len(e["ghosts"])
        tot["라벨"] += e["labels"]
    return cat, causes, tot


def eval_variant(variant):
    evs, music_of = [], {}
    for stem in stems():
        js = load(variant, stem)
        if js is None:
            print(stem, "라벨 없음 — 건너뜀", flush=True)
            continue
        t = json.load(open(os.path.join(OUT, "truth", stem + ".json"), encoding="utf-8"))
        e = evaluate_page(stem, js, t)
        music_of[stem] = js["music"]
        evs.append(e)
        st = Counter(r["status"] for r in e["rows"])
        h = e["header"]
        print(f"{stem:38s} sp {e['sp']:5.2f} 보표 {h['product_staves']}/{h['truth_staves']} 음자리표 틀림 {len(h['clef_wrong'])} "
              f"조표 {h['key_got']}/{h['key_first']}{'' if h['key_ok'] else ' ✗'} | 정답 {len(e['rows'])} 누락 {st['누락']} 음고 {st['음고']} "
              f"표기 {st['표기']} 유령 {len(e['ghosts'])}", flush=True)
    json.dump(evs, open(os.path.join(OUT, f"eval_{variant}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    report(evs, music_of)
    return evs


def report(evs, music_of):
    for font in ("bravura", "leipzig", ""):
        sub = [e for e in evs if font in e["stem"]]
        cat, causes, tot = summarize(sub, music_of)
        n = cat["전체 · 정답"]
        print(f"\n== {font or '합계'} {len(sub)}쪽 · 정답 머리 {n} · 라벨 {tot['라벨']}")
        for c in ("전체", "단일", "화음", "꽉 찬 머리", "빈 머리", "덧줄 구역"):
            t = cat[c + " · 정답"]
            if t:
                print(f"  {c}: 누락 {cat[c + ' · 누락']}/{t} ({cat[c + ' · 누락'] / t * 100:.1f}%) · 음고 {cat[c + ' · 음고']} "
                      f"({cat[c + ' · 음고'] / t * 100:.1f}%) · 표기 {cat[c + ' · 표기']} ({cat[c + ' · 표기'] / t * 100:.1f}%)")
        print(f"  유령(짝 없는 라벨) {tot['유령']} ({tot['유령'] / max(1, n) * 100:.1f}% of 정답)")
        for k, v in causes.items():
            print(f"  [{k}] " + " · ".join(f"{a} {b}" for a, b in v.most_common()))


# ------------------------------------------------------------------ PDF 17쪽 — 같은 평가기
def pdf17():
    """스냅샷(= main.py 명령줄 출력, tests/golden/snapshot_pdf_*.tsv)을 PDF 글리프 정답에 같은 짝짓기로 댄다.
    표기 정답은 PDF에 없다(A-11) — 누락 · 유령 · 음고만."""
    import measure_omission_rate as M
    import check_accidental_fix as C
    from modules.preprocess import preprocess
    res_all = {}
    for name, path, pg in C.PAGES:
        if not path.endswith(".pdf"):
            continue
        rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "tests", "golden", f"snapshot_pdf_{name}.tsv"),
                                                          encoding="utf-8") if not l.startswith("#")]
        labels = [dict(x=int(r[1]), y=int(r[2]), pitch=r[3], text=r[5]) for r in rows if len(r) >= 6]
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        staves = res.staves
        sp = float(np.median([s.spacing for s in staves]))
        g = M.pdf_glyphs(path, pg)
        clefs = [dict(c, staff=min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index)
                 for c in g if c["name"].startswith("clefs.")]
        heads = []
        for x in (x for x in g if x["name"].startswith("noteheads.")):
            if any(abs(x["cx"] - h["cx"]) < 2 and abs(x["cy"] - h["cy"]) < 2 for h in heads):
                continue
            st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - x["cy"]))
            if x["cy"] < st.top - 6 * st.spacing or x["cy"] > st.bottom + 6 * st.spacing:
                continue
            heads.append(x)
        main_size = Counter(x["size"] for x in heads).most_common(1)[0][0]
        normal = [h for h in heads if abs(h["size"] - main_size) < 0.05]
        small = [h for h in heads if abs(h["size"] - main_size) >= 0.05]
        pairs, used_t, used_l = M.match(normal, labels, sp)
        h2l = dict(pairs)
        cat = Counter()
        for i, h in enumerate(normal):
            chord = any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp for j, q in enumerate(normal))
            st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - h["cy"]))
            k = int(round((h["cy"] - st.top) / (st.spacing / 2.0)))
            status = "누락" if i not in h2l else ("음고" if labels[h2l[i]]["pitch"] != M.truth_pitch(h["cx"], h["cy"], staves, clefs)[1] else "맞음")
            for c in ["전체", "화음" if chord else "단일", "빈 머리" if h["name"] in ("noteheads.s1", "noteheads.s0") else "꽉 찬 머리"] \
                    + (["덧줄 구역"] if not 0 <= k <= 8 else []):
                cat[c + " · 정답"] += 1
                cat[c + " · " + status] += 1
        ghosts = [labels[i] for i in range(len(labels)) if i not in used_l]
        _p, _t, small_hit = M.match(small, ghosts, sp)
        cat["유령"] = len(ghosts) - len(small_hit)
        cat["라벨"] = len(labels)
        res_all[name] = dict(cat)
        print(name, f"sp {sp:.1f}", {k: v for k, v in cat.items() if k.startswith("전체") or k in ("유령", "라벨")}, flush=True)
    json.dump(res_all, open(os.path.join(OUT, "eval_pdf17.json"), "w", encoding="utf-8"), ensure_ascii=False)
    tot = Counter()
    for v in res_all.values():
        tot.update(v)
    n = tot["전체 · 정답"]
    print(f"\n== PDF {len(res_all)}쪽 · 정답 머리 {n} · 라벨 {tot['라벨']}")
    for c in ("전체", "단일", "화음", "꽉 찬 머리", "빈 머리", "덧줄 구역"):
        t = tot[c + " · 정답"]
        if t:
            print(f"  {c}: 누락 {tot[c + ' · 누락']}/{t} ({tot[c + ' · 누락'] / t * 100:.1f}%) · 음고 {tot[c + ' · 음고']} ({tot[c + ' · 음고'] / t * 100:.1f}%)")
    print(f"  유령(짝 없는 라벨) {tot['유령']} ({tot['유령'] / n * 100:.1f}% of 정답)")


# ------------------------------------------------------------------ A-17 원시 판정 행렬 — 인쇄된 임시표 정답
RAW_KIND = {"#": "#", "b": "b", "natural": "natural", "##": "doublesharp", "bb": "flatflat"}


def raw(variant):
    """`measure_a17.run_all`과 같은 원시 판정(전파 없음)을 Verovio 20쪽에. 정답은 인쇄된 임시표가 붙은 일반 머리.
    variant는 `measure_a17_ghost6.raw`와 같은 가로채기(c12 · c12g13h3 …)."""
    import measure_a17 as A
    import measure_a17_ghost6 as G
    G.set_variant(variant)
    if variant in G.VARIANT_FIX:
        G.install(True)
    saved = G._hook_module(G.T1.C, variant)
    keep_ann = G.AD.annotate_accidentals
    G.AD.annotate_accidentals = G.c12fix_annotate if variant in G.VARIANT_FIX else {"c12": G.T.MODES["c12"]}.get(variant, G.T1.ORIG_ANN)
    conf = {f: Counter() for f in ("bravura", "leipzig")}
    rows = []
    try:
        for stem in stems():
            font = "bravura" if "bravura" in stem else "leipzig"
            t = json.load(open(os.path.join(OUT, "truth", stem + ".json"), encoding="utf-8"))
            G.HOLLOW.clear()
            G.LAST.clear()
            res, ctx, sp, notes, src = A.final_notes(os.path.relpath(os.path.join(SET_DIR, stem + ".png"), ROOT), 0)
            rj = A.raw_judgments(res, ctx, notes)
            heads = [n for n in t["notes"] if not n["grace"] and not n["cue"]]
            used = set()
            for h in (h for h in heads if h["accidental"]):
                kind = RAW_KIND[h["accidental"]]
                cand = [i for i, n in enumerate(notes) if abs(n.x - h["x"]) <= 0.7 * sp and abs(n.y - h["y"]) <= 0.5 * sp]
                if not cand:
                    conf[font][(kind, "음표 없음")] += 1
                    continue
                i = min(cand, key=lambda i: abs(notes[i].x - h["x"]) + abs(notes[i].y - h["y"]))
                used.add(i)
                got = rj[i] or "없음"
                conf[font][(kind, got)] += 1
                if got != kind:
                    rows.append(dict(stem=stem, kind=kind, got=got, x=h["x"], y=h["y"], note=(notes[i].x, notes[i].y), acc_box=h["acc_box"]))
            for i, a in enumerate(rj):
                if a and i not in used:
                    n = notes[i]
                    on_head = any(abs(h["x"] - n.x) <= 0.7 * sp and abs(h["y"] - n.y) <= 0.5 * sp for h in heads)
                    conf[font][("글리프 없음 · 진짜 머리" if on_head else "글리프 없음 · 유령 머리", a)] += 1
                    rows.append(dict(stem=stem, kind="없음", got=a, x=n.x, y=n.y, on_head=on_head))
            print(variant, stem, "임시표 머리", sum(1 for h in heads if h["accidental"]), "틀림 누적", sum(1 for r in rows if r["kind"] != "없음"), flush=True)
    finally:
        G.AD.annotate_accidentals = keep_ann
        for k, v in saved.items():
            setattr(G.T1.C, k, v)
        G.install(False)
    json.dump(dict(conf={f: {f"{k[0]}|{k[1]}": v for k, v in c.items()} for f, c in conf.items()}, rows=rows),
              open(os.path.join(OUT, f"raw_{variant}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    raw_report(variant)


def raw_report(variant):
    d = json.load(open(os.path.join(OUT, f"raw_{variant}.json"), encoding="utf-8"))
    cols = ["#", "b", "natural", "없음", "음표 없음"]
    for f in ("bravura", "leipzig", "합계"):
        c = Counter()
        for ff, v in d["conf"].items():
            if f in (ff, "합계"):
                c.update({tuple(k.split("|")): n for k, n in v.items()})
        rows = ["#", "b", "natural", "doublesharp", "flatflat", "글리프 없음 · 진짜 머리", "글리프 없음 · 유령 머리"]
        print(f"\n[{variant} · {f}]\n| 정답 \\ 원시 판정 | " + " | ".join(cols) + " |\n|---|" + "---:|" * len(cols))
        for r in rows:
            if any(c[(r, k)] for k in cols):
                print(f"| {r} | " + " | ".join(str(c[(r, k)]) for k in cols) + " |")
        # A-17 §2와 같은 정의: 분모 = 음표가 있는 ♯ · ♭ · ♮(「음표 없음」은 누락이라 따로), 틀림에 놓침(없음) 포함
        glyph = sum(v for (r, k), v in c.items() if r in ("#", "b", "natural") and k != "음표 없음")
        right = sum(c[(r, r)] for r in ("#", "b", "natural"))
        extra = sum(v for (r, k), v in c.items() if r.startswith("글리프 없음"))
        print(f"음표 있는 ♯ · ♭ · ♮ {glyph} · 맞음 {right} · 틀림 {glyph - right} ({(glyph - right) / max(1, glyph) * 100:.1f}%)"
              f" · 뒤바뀜 ♮→♯ {c[('natural', '#')]} · ♯→♮ {c[('#', 'natural')]} · 놓침 {sum(c[(r, '없음')] for r in ('#', 'b', 'natural'))}"
              f" · 글리프 없는데 판정 {extra} · 음표 없음 {sum(c[(r, '음표 없음')] for r in ('#', 'b', 'natural'))}")


# ------------------------------------------------------------------ 확대 그림
REVIEW = os.path.join(ROOT, "docs", "review", "verovio_measure")
SIGN = {"#": "#", "b": "b", "natural": "nat", "##": "x", "bb": "bb", "": "", None: ""}     # cv2 글꼴에 ♯ · ♮ 가 없다


def items_of(variant, per=8, seed=0):
    """원인별 표본(쪽 · 글꼴이 고르게 섞이도록 순서대로 건너뛰며)."""
    evs = json.load(open(os.path.join(OUT, f"eval_{variant}.json"), encoding="utf-8"))
    groups = defaultdict(list)
    for e in evs:
        js = load(variant, e["stem"])
        for r in e["rows"]:
            if r["status"] == "음고":
                k = "pitch__" + cause_pitch(r, e["header"])
            elif r["status"] == "표기":
                k = "text__" + cause_text(r, js["music"], e["header"])
            elif r["status"] == "누락":
                k = "miss__" + ("staff" if not r["staff_found"] else "chord" if r["chord"] else "hollow" if r["hollow"]
                                else "ledger" if r["ledger"] else "single")
            else:
                continue
            got = r.get("label") or {}
            title = f"T {r['truth']}{SIGN.get(r['eff'], r['eff'])} pr:{SIGN.get(r['printed'], '')} | G {got.get('pitch', '-')}" \
                    f"{SIGN.get(norm_acc(got.get('acc')), '')} {got.get('conf', '')[:4]}"
            groups[k].append(dict(stem=e["stem"], x=r["x"], y=r["y"], lx=got.get("x"), ly=got.get("y"), title=title))
        for g in e["ghosts"]:
            on = [c for c in g["on"] if c != "ledger"] or (["ledger_only"] if g["on"] else ["none"])
            groups["ghost__" + "+".join(on[:2])].append(dict(stem=e["stem"], x=g["x"], y=g["y"], lx=g["x"], ly=g["y"],
                                                            title=f"ghost {g['pitch']} {SIGN.get(None)}{g['conf'][:4]}"))
    out = {}
    for k, v in groups.items():
        step = max(1, len(v) // per)
        out[k] = (len(v), v[seed::step][:per])
    return out


def crop_grid(items, path, r=54, z=3):
    import cv2
    tiles = []
    imgs = {}
    for it in items:
        im = imgs.setdefault(it["stem"], cv2.imdecode(np.fromfile(os.path.join(SET_DIR, it["stem"] + ".png"), np.uint8), cv2.IMREAD_COLOR))  # 한글 경로에서 imread는 조용히 실패
        x, y = int(round(it["x"])), int(round(it["y"]))
        x0, y0 = max(0, x - r), max(0, y - r)
        c = cv2.resize(im[y0:y + r, x0:x + r].copy(), None, fx=z, fy=z, interpolation=cv2.INTER_NEAREST)
        cv2.circle(c, (int((it["x"] - x0) * z), int((it["y"] - y0) * z)), 16, (0, 170, 0), 2)             # 정답 머리: 초록 원
        if it.get("lx") is not None:
            cv2.drawMarker(c, (int((it["lx"] - x0) * z), int((it["ly"] - y0) * z)), (0, 0, 255), cv2.MARKER_CROSS, 22, 2)  # 라벨: 빨강 +
        c = cv2.copyMakeBorder(c, 44, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        short = it["stem"].replace("_p1", "").replace("_piano", "").replace("bravura", "B").replace("leipzig", "L")
        cv2.putText(c, f"{short} ({x},{y})", (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(c, it["title"], (4, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        tiles.append(cv2.resize(c, (2 * r * z, 2 * r * z + 44)))
    if not tiles:
        return
    while len(tiles) % 4:
        tiles.append(np.full_like(tiles[0], 255))
    g = np.vstack([np.hstack(tiles[k:k + 4]) for k in range(0, len(tiles), 4)])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(cv2.imencode(".png", g)[1].tobytes())        # 한글 경로에서 imwrite가 조용히 실패한다


def crops(variant, out_dir=None, per=8):
    out_dir = out_dir or os.path.join(OUT, "crops_" + variant)
    for k, (n, items) in sorted(items_of(variant, per).items()):
        safe = re.sub(r"[^\w+.-]", "_", k)
        crop_grid(items, os.path.join(out_dir, f"{safe}.png"))
        print(k, n, "→", len(items), "칸", flush=True)


def pair_offsets():
    """인쇄된 ♮ · ♯ 머리마다 제품 판정 입력(`measure_a17.probe` — 원본 모듈 함수를 가로채 읽음)의 쌍 위 · 아래 어긋남.
    제품의 ♮ 조건: 두 막대의 위끝 · 아래끝이 **둘 다** 0.45sp 넘게 어긋남(`accidental_detect` 125행).
    쌍은 정답 글리프 상자 안의 막대 둘(막대 x = 창 왼쪽 x0 + 패치 x)만 — 기둥 · 머리 가장자리 쌍과 섞지 않는다."""
    import measure_a17 as A
    rows = []
    for stem in stems():
        t = json.load(open(os.path.join(OUT, "truth", stem + ".json"), encoding="utf-8"))
        res, ctx, sp, notes, src = A.final_notes(os.path.relpath(os.path.join(SET_DIR, stem + ".png"), ROOT), 0)
        for h in t["notes"]:
            if h["grace"] or h["cue"] or h["accidental"] not in ("#", "natural") or not h["acc_box"]:
                continue
            cand = [n for n in notes if abs(n.x - h["x"]) <= 0.7 * sp and abs(n.y - h["y"]) <= 0.5 * sp]
            if not cand:
                continue
            n = min(cand, key=lambda n: abs(n.x - h["x"]) + abs(n.y - h["y"]))
            p = A.probe(res, ctx, n)
            x0 = int(n.x - sp * 2.0)
            if n.staff_index in ctx:
                x0 = max(x0, ctx[n.staff_index].header_end + int(sp * 0.2))
            bx0, _by0, bx1, _by1 = h["acc_box"]
            own = [b for b in p.get("bars", []) if bx0 - 2 <= x0 + b["x"] <= bx1 + 2]
            rec = dict(stem=stem, kind=h["accidental"], x=h["x"], y=h["y"], bars_in_glyph=len(own), got=p["raw"] or "없음",
                       glyph_w_sp=round((bx1 - bx0) / sp, 2))
            if len(own) >= 2:
                a, b = own[0], own[-1]
                rec.update(dx_sp=round((b["x"] - a["x"]) / sp, 2), top_off_sp=round((b["s"] - a["s"]) / sp, 2),
                           bot_off_sp=round((b["e"] - a["e"]) / sp, 2))
            rows.append(rec)
        print(stem, len(rows), flush=True)
    json.dump(rows, open(os.path.join(OUT, "pair_offsets.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for f in ("bravura", "leipzig"):
        for k in ("natural", "#"):
            v = [r for r in rows if f in r["stem"] and r["kind"] == k and "top_off_sp" in r]
            if not v:
                continue
            q = lambda key, fn: round(fn([r[key] for r in v]), 2)
            print(f"{f} {k}: n={len(v)} (막대 둘 못 찾음 {sum(1 for r in rows if f in r['stem'] and r['kind'] == k and 'top_off_sp' not in r)})"
                  f" 위 어긋남 최소 {q('top_off_sp', min)} 중앙 {q('top_off_sp', np.median)} 최대 {q('top_off_sp', max)}"
                  f" · 아래 최소 {q('bot_off_sp', min)} 중앙 {q('bot_off_sp', np.median)} 최대 {q('bot_off_sp', max)}"
                  f" · 둘 다 >0.45 {sum(1 for r in v if r['top_off_sp'] > 0.45 and r['bot_off_sp'] > 0.45)}"
                  f" · 간격 중앙 {q('dx_sp', np.median)}")


def diff(variant, base="base"):
    """정답 머리 기준으로 기준 → 사본 변화를 센다(측정 함정 C-3 · C-8): 고쳐짐 · 새로 틀림 · 사라짐(오삭제) · 되찾음 · 새 유령 · 없어진 유령."""
    out = defaultdict(list)
    for stem in stems():
        t = json.load(open(os.path.join(OUT, "truth", stem + ".json"), encoding="utf-8"))
        a, b = load(base, stem), load(variant, stem)
        if a is None or b is None:
            print(stem, "라벨 없음", flush=True)
            continue
        ea, eb = evaluate_page(stem, a, t), evaluate_page(stem, b, t)
        for ra, rb in zip(ea["rows"], eb["rows"]):
            sa, sb = ra["status"], rb["status"]
            if sa == sb and (sa != "맞음" and ra.get("label", {}).get("text") == rb.get("label", {}).get("text") or sa == "맞음" or sa == "누락"):
                continue
            k = ("사라짐(오삭제)" if sb == "누락" else "되찾음" if sa == "누락" else
                 "고쳐짐" if sb == "맞음" else "새로 틀림" if sa == "맞음" else "틀린 채 바뀜")
            out[k].append(dict(stem=stem, x=ra["x"], y=ra["y"], truth=ra["text_truth"] + "/" + ra["truth"], printed=ra["printed"],
                               base=(ra.get("label") or {}).get("text"), var=(rb.get("label") or {}).get("text"),
                               lx=(rb.get("label") or ra.get("label") or {}).get("x"), ly=(rb.get("label") or ra.get("label") or {}).get("y"),
                               conf=(rb.get("label") or {}).get("conf")))
        sp = ea["sp"]
        for g in eb["ghosts"]:
            if not any(abs(g["x"] - h["x"]) <= 0.5 * sp and abs(g["y"] - h["y"]) <= 0.5 * sp for h in ea["ghosts"]):
                out["새 유령"].append(dict(stem=stem, x=g["x"], y=g["y"], lx=g["x"], ly=g["y"], var=g["text"], conf=g["conf"], on=g["on"]))
        for g in ea["ghosts"]:
            if not any(abs(g["x"] - h["x"]) <= 0.5 * sp and abs(g["y"] - h["y"]) <= 0.5 * sp for h in eb["ghosts"]):
                out["없어진 유령"].append(dict(stem=stem, x=g["x"], y=g["y"], base=g["text"], on=g["on"]))
    json.dump(out, open(os.path.join(OUT, f"diff_{variant}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    for k in ("고쳐짐", "새로 틀림", "틀린 채 바뀜", "사라짐(오삭제)", "되찾음", "새 유령", "없어진 유령"):
        v = out.get(k, [])
        by = Counter("bravura" if "bravura" in r["stem"] else "leipzig" for r in v)
        print(f"{k}: {len(v)} (Bravura {by['bravura']} · Leipzig {by['leipzig']})")
    for k in ("새로 틀림", "사라짐(오삭제)", "새 유령"):
        for r in out.get(k, []):
            print(" ", k, r["stem"], (round(r["x"]), round(r["y"])), r.get("truth"), r.get("base"), "→", r.get("var"), r.get("conf"), r.get("on", ""))
    return out


def diff_crops(variant, out_dir=None):
    d = json.load(open(os.path.join(OUT, f"diff_{variant}.json"), encoding="utf-8"))
    names = {"고쳐짐": "fixed", "새로 틀림": "newwrong", "틀린 채 바뀜": "stillwrong", "사라짐(오삭제)": "lost", "되찾음": "recovered",
             "새 유령": "newghost", "없어진 유령": "ghostgone"}
    tr = lambda s: "".join({"도": "C", "레": "D", "미": "E", "파": "F", "솔": "G", "라": "A", "시": "B"}.get(ch, ch) for ch in (s or "-"))
    for k, v in d.items():
        items = [dict(r, title=f"{tr(r.get('base'))} -> {tr(r.get('var'))}  T {(r.get('truth') or '').split('/')[-1]}") for r in v]
        for i in range(0, len(items), 24):
            crop_grid(items[i:i + 24], os.path.join(out_dir or os.path.join(OUT, "diffcrops_" + variant), f"{names[k]}_{i // 24 + 1}.png"))
        print(k, len(v))


def raw_crops(variant, per=12, out_dir=None):
    d = json.load(open(os.path.join(OUT, f"raw_{variant}.json"), encoding="utf-8"))
    groups = defaultdict(list)
    for r in d["rows"]:
        k = f"{r['kind']}_to_{r['got']}" if r["kind"] != "없음" else f"noglyph_{'head' if r.get('on_head') else 'ghost'}_{r['got']}"
        groups[k].append(dict(stem=r["stem"], x=r["x"], y=r["y"], lx=(r.get("note") or (None, None))[0], ly=(r.get("note") or (None, None))[1],
                              title=f"T {SIGN.get(r['kind'], r['kind'])} G {SIGN.get(r['got'], r['got'])}"))
    out_dir = out_dir or os.path.join(OUT, "rawcrops_" + variant)
    for k, v in sorted(groups.items()):
        step = max(1, len(v) // per)
        crop_grid(v[::step][:per], os.path.join(out_dir, re.sub(r"[^\w+.-]", "_", k) + ".png"))
        print(k, len(v), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "rawcrops":
        raw_crops(sys.argv[2])
    elif cmd == "pairs":
        pair_offsets()
    elif cmd == "diff":
        diff(sys.argv[2])
    elif cmd == "diffcrops":
        diff_crops(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    if cmd == "crops":
        crops(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "raw":
        raw(sys.argv[2])
    elif cmd == "rawreport":
        raw_report(sys.argv[2])
    if cmd == "truth":
        truth()
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3:] or None)
    elif cmd == "eval":
        eval_variant(sys.argv[2])
    elif cmd == "pdf17":
        pdf17()
