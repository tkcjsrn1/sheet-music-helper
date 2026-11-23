# -*- coding: utf-8 -*-
"""(c) 안 2 — 바뀐 음자리표 뒤 음표를 「확인 필요」로: 표시 대상 수와 그중 실제 음고가 틀린 비율. 제품 코드 무변경.

검출: `measure_clef_change`(본 = 머리 음자리표, 정규화 상관 ≥ 0.6). 표시 구간: 검출된 음자리표가 **그 보표 머리 음자리표와 다른 종류**면
그 x부터 같은 보표의 다음 검출(또는 보표 끝)까지의 라벨. 라벨 = 현재 main 제품(A-25 포함) run_page JSON.
정답 음고: Verovio = SVG 머리, PDF · 보지 않은 악보 = PDF 글리프 머리 + 그 왼쪽 가장 가까운 음자리표 글리프(바뀐 것 포함).

    python tools/measure_clef_flag.py            # 측정용 본(정답 상자)
    python tools/measure_clef_flag.py product    # 제품 `clef_keysig.clef_change_regions`(본 = 머리 음자리표 검출 구간) — 구현 판정용
                                                 #   + check 총수 변화 · 정답에 없는 구간(헛표시) · 사진 세트(사진 모드 강제로 켬) 표시 정밀도
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
THR = 0.6
PRODUCT = "product" in sys.argv


def product_regions(res):
    from modules.clef_keysig import analyze_staves, clef_change_regions
    return clef_change_regions(res, analyze_staves(res))


def _tally(c, l, reg):
    c["라벨"] += 1
    c["check 전"] += l["confidence"] == "check"
    hit = any(a <= l["x"] < b for a, b in reg.get(l["staff"], []))
    c["check 후"] += l["confidence"] == "check" or hit
    return hit


def regions(cands, header_clef):
    """보표별 (시작 x, 끝 x) — 머리와 다른 종류인 구간."""
    out = {}
    by = {}
    for c in cands:
        if c["score"] >= THR:
            by.setdefault(c["si"], []).append(c)
    for si, cs in by.items():
        cs.sort(key=lambda c: c["x"])
        for k, c in enumerate(cs):
            if c["kind"] != header_clef.get(si):
                end = cs[k + 1]["x"] if k + 1 < len(cs) else 10 ** 9
                out.setdefault(si, []).append((c["x"], end))
    return out


def _vrv(stem):
    import measure_clef_change as CC
    _s, _truth, cands = CC._one(stem)
    L = json.load(open(os.path.join(ROOT, "debug", "vrv_a25impl", "base", stem + ".json"), encoding="utf-8"))
    t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", stem + ".json"), encoding="utf-8"))
    hdr = {s["id"]: s["clef"] for s in L["staves"]}
    c = Counter()
    if PRODUCT:
        from modules.preprocess import preprocess
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))
        reg = product_regions(res)
        # 정답 바뀐 음자리표(_truth: (SVG 보표 순번, x, 종류))와 맞지 않는 구간 = 헛표시 구간
        order = {st.index: i for i, st in enumerate(sorted(res.staves, key=lambda s: s.top))}
        for si, rs in reg.items():
            for a, _b in rs:
                ok = any(tr[0] == order[si] and abs(tr[1] - a) <= 18 * 1.5 for tr in _truth)
                c["구간"] += 1
                c["헛 구간"] += not ok
    else:
        reg = regions(cands, hdr)
    for l in L["labels"]:
        if not _tally(c, l, reg):
            continue
        c["표시"] += 1
        h = [n for n in t["notes"] if abs(n["x"] - l["x"]) <= 0.7 * 18 and abs(n["y"] - l["y"]) <= 0.5 * 18]
        if not h:
            c["유령"] += 1
        elif l["pitch"] != h[0]["note_name"] + h[0]["octave"]:
            c["음고 틀림"] += 1
        else:
            c["음고 맞음"] += 1
    return "verovio", c


def _pdf(job):
    import measure_clef_change as CC
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    from modules.preprocess import preprocess
    name, path, pg, lab = job
    _n, _truth, cands = CC._one_pdf((name, path, pg))
    L = json.load(open(lab, encoding="utf-8"))
    hdr = {s["id"]: s["clef"] for s in L["staves"]}
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    reg = product_regions(res) if PRODUCT else regions(cands, hdr)
    heads, clefs = truth_at(path, pg, 1.0)
    for q in clefs:
        q["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["cy"])).index
    sp = L["staves"][0]["spacing"]
    c = Counter()
    if PRODUCT:
        for si, rs in reg.items():
            for a, _b in rs:
                c["구간"] += 1
                c["헛 구간"] += not any(tr[0] == si and abs(tr[1] - a) <= sp * 1.5 for tr in _truth)
    for l in L["labels"]:
        if not _tally(c, l, reg):
            continue
        c["표시"] += 1
        h = [q for q in heads if abs(q["cx"] - l["x"]) <= 0.7 * sp and abs(q["cy"] - l["y"]) <= 0.5 * sp]
        if not h:
            c["유령"] += 1
        elif l["pitch"] != M.truth_pitch(h[0]["cx"], h[0]["cy"], res.staves, clefs)[1]:
            c["음고 틀림"] += 1
        else:
            c["음고 맞음"] += 1
    return ("unseen" if name.startswith(("moon", "rain")) else "pdf"), c


def _set_product(v):
    global PRODUCT
    PRODUCT = v


PHOTO_LABELS = "debug/a17_cand1_g1flag/base_photo"


def _photo(f):
    """사진 합성 — 사진 모드 결과(라벨 JSON)에, 같은 사진을 사진 모드로 다시 전처리해 제품 구간을 **강제로** 씌운다(지금 제품은 사진에서 끔).
    정답 = 원본 PDF 실효 정답 머리(`measure_photo_truth` 정렬)."""
    import measure_photo_truth as T
    from modules.preprocess import preprocess
    L = json.load(open(os.path.join(ROOT, PHOTO_LABELS, f), encoding="utf-8"))
    src = next(k for k in T.SOURCES if f.startswith("ph_" + k + "__"))
    path = os.path.join(ROOT, "output", "synthetic_photos", f[3:-5] + ".png")
    c = Counter()
    if not os.path.exists(path):
        path = path[:-4] + ".jpg"
    try:
        res = preprocess(path, photo=True)
    except Exception:
        return "photo", c
    if len(res.staves) != len(L["staves"]):
        c["보표 수 다름(뺌)"] += 1
        return "photo", c
    reg = product_regions(res)
    heads, sp = T.truth_of(src)
    lab = L["labels"]
    P2 = T.align([(l["x"], l["y"]) for l in lab], [(h["x"], h["y"]) for h in heads], sp) if len(lab) >= 6 else []
    for l, (x, y) in zip(lab, P2):
        if not _tally(c, l, reg):
            continue
        c["표시"] += 1
        h = [q for q in heads if abs(q["x"] - x) <= 0.7 * sp and abs(q["y"] - y) <= 0.5 * sp]
        if not h:
            c["유령"] += 1
        elif l["pitch"] != h[0]["pitch"]:
            c["음고 틀림"] += 1
        else:
            c["음고 맞음"] += 1
    c["구간"] += sum(len(v) for v in reg.values())
    return "photo", c


def main():
    import check_accidental_fix as C
    stems = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "test_scores", "verovio")) if f.endswith("_p1.png"))
    U = "output/unseen-scores-20260829/sources/"
    jobs = [(n, p, pg, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_pdf20", n + ".json")) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    jobs += [(f"moon{p + 1}", U + "moonlight-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"moon{p + 1}.json")) for p in (0, 1, 10, 17)]
    jobs += [(f"rain{p + 1}", U + "Chop-28-15-a4.pdf", p, os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", f"rain{p + 1}.json")) for p in range(4)]
    if PRODUCT:     # 오르간 2쪽 — 가로 쪽이라 PDF 정답 좌표가 영상과 안 맞아 음고 판정은 못 하고 표시 수만 센다
        from modules.preprocess import preprocess
        from modules.clef_keysig import analyze_staves, clef_change_regions
        o = U + "Ich_ruf_zu_dir2-a4.pdf"
        r = preprocess(os.path.join(ROOT, o), pdf_page=1)
        reg = clef_change_regions(r, analyze_staves(r))
        L = json.load(open(os.path.join(ROOT, "debug", "a17_cand1_a25impl", "base_unseen", "organ2.json"), encoding="utf-8"))["labels"]
        print("organ2 구간", sum(len(v) for v in reg.values()), "· 표시", sum(any(a <= l["x"] < b for a, b in reg.get(l["staff"], [])) for l in L), "/", len(L))
    with ProcessPoolExecutor(3, initializer=_set_product, initargs=(PRODUCT,)) as ex:
        res = list(ex.map(_vrv, stems)) + list(ex.map(_pdf, jobs))
        if PRODUCT:
            res += list(ex.map(_photo, sorted(f for f in os.listdir(os.path.join(ROOT, PHOTO_LABELS)) if f.startswith("ph_") and f.endswith(".json") and "_g2" not in f and "_gaps" not in f)))
    tot = {}
    for st, c in res:
        tot.setdefault(st, Counter()).update(c)
    for st, c in tot.items():
        n = c["표시"]
        print(f"{st:8s} 표시 {n} · 음고 틀림 {c['음고 틀림']} ({c['음고 틀림'] / max(1, n) * 100:.0f}%) · 음고 맞음 {c['음고 맞음']} · 유령 {c['유령']}"
              + (f" | 구간 {c['구간']} · 헛 구간 {c['헛 구간']} · 라벨 {c['라벨']} · check {c['check 전']} → {c['check 후']}" if PRODUCT else ""))


if __name__ == "__main__":
    main()
