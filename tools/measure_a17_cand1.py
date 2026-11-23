# -*- coding: utf-8 -*-
"""A-17 후보 1 사본 측정 (2026-09-30, 제품 코드 무변경): 임시표 판정 창을 보표 밴드 경계에서 자르지 않기.

제품 `main.run_page` 전체(chord_rescue 연결 · 임시표 유령 제거 · 전파 · 0.5px 재판정 · 확신도)를 그대로 돌리고,
`annotate_accidentals`만 밴드를 보표 ±(3.5 + MARGIN_SP)sp로 넓힌 사본으로 가로챈다(main · accidental_detect 두 이름 모두).
밴드 여유 3.5 + 2.0 = 5.5sp ≥ 덧줄 음표(보표 밖 ≤ 3.5sp)의 창 ±2sp — 창이 밴드 밖으로 나가지 않는다.

기준 · 후보의 라벨 JSON을 20쪽 전부 대조: 사라진 라벨(→ 정답 머리 · 음고로 오삭제 판정) · 새 라벨 · 표기 바뀜 · 라벨 수.
실행: python tools/measure_a17_cand1.py
"""
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import main as MAIN  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402
from modules.preprocess import PreprocessResult  # noqa: E402
import check_accidental_fix as C  # noqa: E402

MARGIN_SP = 2.0
OUT = os.path.join(ROOT, "debug", "a17_cand1")
ORIG_ANN, ORIG_RSL, ORIG_BAR = AD.annotate_accidentals, AD.remove_staff_lines, AD._find_barlines


CALLS = [0]                 # 가로채기 호출 수 — 0이면 측정이 빈 것(측정 함정 B-4)


def wide_annotate(result, contexts, notes):
    """후보 1: annotate_accidentals가 보는 staff.top/bottom만 넓힌 사본. 오선 제거는 원래 보표로."""
    CALLS[0] += 1
    wide = [SimpleNamespace(index=s.index, spacing=s.spacing, line_ys=s.line_ys,
                            top=int(s.top - MARGIN_SP * s.spacing), bottom=int(s.bottom + MARGIN_SP * s.spacing))
            for s in result.staves]
    AD.remove_staff_lines = lambda b, _st: ORIG_RSL(b, result.staves)
    # 마디선 검출은 「오선 높이 관통」이 조건이라 넓힌 top/bottom을 주면 마디선이 사라지고 전파가 마디를 넘는다 —
    # 후보 1은 판정 창만 바꾸므로 마디선은 원래 보표로(첫 판에서 이걸 빠뜨려 표기 528 변화가 났다)
    orig_staff = {s.index: s for s in result.staves}
    AD._find_barlines = lambda ns, st, h: ORIG_BAR(ns, orig_staff[st.index], h)
    try:
        return ORIG_ANN(PreprocessResult(original_bgr=result.original_bgr, gray=result.gray, binary=result.binary, staves=wide),
                        contexts, notes)
    finally:
        AD.remove_staff_lines = ORIG_RSL
        AD._find_barlines = ORIG_BAR


def run(name, path, pg, cand):
    out = os.path.join(OUT, "cand" if cand else "base")
    os.makedirs(out, exist_ok=True)
    js = os.path.join(out, f"{name}.json")
    argv = [os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tempfile.gettempdir(), "--save-labels", js]
    sys.argv = ["main.py"] + argv
    args = MAIN.parse_args()
    MAIN.annotate_accidentals = AD.annotate_accidentals = wide_annotate if cand else ORIG_ANN
    try:
        MAIN.run_page(args, argv[0], pg, tempfile.gettempdir())
    finally:
        MAIN.annotate_accidentals = AD.annotate_accidentals = ORIG_ANN
    return json.load(open(js, encoding="utf-8"))


def key(l):
    return (l["staff"], l["x"], l["y"])


def compare(cand="cand", out_json="diff.json", base="base"):
    """기준 · 후보 JSON 대조 + PDF 정답 머리로 오삭제 · 복구 판정."""
    import measure_omission_rate as M
    from measure_normalize_sp import truth_at
    from collections import Counter
    tot, rows, lost, gained = Counter(), [], [], []
    for name, path, pg in C.PAGES:
        fb, fc = os.path.join(OUT, base, f"{name}.json"), os.path.join(OUT, cand, f"{name}.json")
        if not (os.path.exists(fb) and os.path.exists(fc)):      # M1이 거부한 사진 등 — 양쪽 다 있어야 대조
            tot["건너뜀(JSON 없음)"] += 1
            continue
        b = json.load(open(fb, encoding="utf-8"))["labels"]
        c = json.load(open(os.path.join(OUT, cand, f"{name}.json"), encoding="utf-8"))["labels"]
        B, Cd = {key(l): l for l in b}, {key(l): l for l in c}
        removed = [B[k] for k in B if k not in Cd]
        added = [Cd[k] for k in Cd if k not in B]
        changed = [(B[k], Cd[k]) for k in B if k in Cd and (B[k]["text"], B[k]["accidental"]) != (Cd[k]["text"], Cd[k]["accidental"])]
        conf = [(B[k], Cd[k]) for k in B if k in Cd and B[k]["confidence"] != Cd[k]["confidence"]]
        tot["라벨 전"] += len(b)
        tot["라벨 후"] += len(c)
        tot["사라짐"] += len(removed)
        tot["새로 생김"] += len(added)
        tot["표기 바뀜"] += len(changed)
        tot["확신도만 바뀜"] += sum(1 for x, y in conf if (x["text"], x["accidental"]) == (y["text"], y["accidental"]))
        for l in removed:
            rows.append(dict(page=name, path=path, pg=pg, kind="사라짐", x=l["x"], y=l["y"], before=l["text"], after="(없음)", conf=l["confidence"]))
        for l in added:
            rows.append(dict(page=name, path=path, pg=pg, kind="새로 생김", x=l["x"], y=l["y"], before="(없음)", after=l["text"], conf=l["confidence"]))
        for x, y in changed:
            rows.append(dict(page=name, path=path, pg=pg, kind="표기 바뀜", x=x["x"], y=x["y"], before=x["text"], after=y["text"],
                             conf=f"{x['confidence']}→{y['confidence']}"))
        if path.endswith(".pdf") and (removed or added):
            res = C.preprocess(os.path.join(ROOT, path), pdf_page=pg)
            sp = float(np.median([s.spacing for s in res.staves]))
            heads, clefs = truth_at(path, pg, 1.0)
            for q in clefs:
                q["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["cy"])).index
            tp = [M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1] for h in heads]
            ok = {}
            for tag, L in (("b", b), ("c", c)):
                pairs, _t, _l = M.match(heads, L, sp)
                ok[tag] = {ti for ti, li in pairs if L[li]["pitch"] == tp[ti]}
            lost += [(name, round(heads[t]["cx"]), round(heads[t]["cy"]), tp[t]) for t in ok["b"] - ok["c"]]
            gained += [(name, round(heads[t]["cx"]), round(heads[t]["cy"]), tp[t]) for t in ok["c"] - ok["b"]]
        print(name, len(b), "→", len(c), "사라짐", len(removed), "새로", len(added), "표기", len(changed), flush=True)
    print("\n합계", dict(tot))
    print("오삭제(기준에서 맞는 음 라벨이 있던 정답 머리가 후보에서 잃음):", len(lost), lost)
    print("복구(후보에서 새로 맞는 음 라벨을 얻은 정답 머리):", len(gained), gained)
    json.dump(rows, open(os.path.join(OUT, out_json), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rows


REVIEW = os.path.join(ROOT, "docs", "review", "a17_candidate1")
SIGN = {"#": "#", "b": "b", "natural": "natural", "flatflat": "bb", "doublesharp": "x"}   # 맑은 고딕에 ♯ · ♮ 글꼴이 없다


def crops(rows_json="diff.json", review=REVIEW, prefix=""):
    """바뀐 라벨 전부 확대(원본 ±3sp): 주황 원 = 음표, 청록 네모 = 그 음표를 겨냥한 PDF 임시표 글리프(있으면)."""
    import math
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    import measure_a17 as A
    rows = json.load(open(os.path.join(OUT, rows_json), encoding="utf-8"))
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    os.makedirs(review, exist_ok=True)
    tiles, cache = [], {}
    for k, r in enumerate(rows):
        key_ = (r["path"], r["pg"])
        if key_ not in cache:
            cache.clear()
            photo = "synthetic_photos" in r["path"] or "m1_edge" in r["path"]     # 사진 모드 라벨 좌표는 보정 뒤 영상 기준
            res = C.preprocess(os.path.join(ROOT, r["path"]), pdf_page=r["pg"], photo=photo)
            glyphs = A.truth(r["path"], r["pg"], res, C.analyze_staves(res))[0] if r["path"].endswith(".pdf") else []
            cache[key_] = (res.original_bgr, float(np.median([s.spacing for s in res.staves])), glyphs)
        img, sp, glyphs = cache[key_]
        g = [q for q in glyphs if abs(q["hx"] - r["x"]) <= 0.7 * sp and abs(q["hy"] - r["y"]) <= 0.5 * sp]
        r["truth"] = SIGN.get(g[0]["kind"], g[0]["kind"]) if g else "없음"
        x0, y0 = max(0, int(r["x"] - 4 * sp)), max(0, int(r["y"] - 3 * sp))
        c = img[y0:int(r["y"] + 3 * sp), x0:int(r["x"] + 2 * sp)].copy()
        cv2.circle(c, (int(r["x"] - x0), int(r["y"] - y0)), int(sp * 0.7), (0, 140, 255), 2)
        for q in g:
            gx, gy = q["gx"] - x0, q["gy"] - y0
            cv2.rectangle(c, (int(gx - 0.5 * sp), int(gy - 1.4 * sp)), (int(gx + 0.5 * sp), int(gy + 1.4 * sp)), (200, 160, 0), 1)
        s_ = 190 / max(c.shape[:2])
        c = cv2.resize(c, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA)
        t = Image.new("RGB", (230, 262), "white")
        t.paste(Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)), (20, 64))
        d = ImageDraw.Draw(t)
        d.text((3, 2), f"#{k + 1} {r['page']} ({r['x']},{r['y']}) {r['kind']}", font=font, fill=(0, 0, 0))
        d.text((3, 19), f"{r['before']} → {r['after']}", font=font, fill=(180, 60, 0))
        d.text((3, 36), f"글리프 {r['truth']} · {r['conf']}", font=font, fill=(60, 60, 60))
        d.rectangle([0, 0, 229, 261], outline=(190, 190, 190))
        tiles.append(t)
    for s0 in range(0, len(tiles), 20):
        chunk = tiles[s0:s0 + 20]
        n_rows = math.ceil(len(chunk) / 5)
        sheet = Image.new("RGB", (5 * 235 + 5, n_rows * 267 + 5), "white")
        for i, t in enumerate(chunk):
            sheet.paste(t, (5 + (i % 5) * 235, 5 + (i // 5) * 267))
        sheet.save(os.path.join(review, f"{prefix}changed_{s0 // 20 + 1}.png"))
    json.dump(rows, open(os.path.join(OUT, rows_json), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("그림", len(tiles), "칸 →", review)


def golden():
    """골든 대조(tests/test_golden_regression.py)를 후보 판정으로 — 모듈이 이름으로 가져온 함수를 가로챈다."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_golden_regression as G
    G.annotate_accidentals = AD.annotate_accidentals = wide_annotate
    sys.argv = ["test_golden_regression.py"]
    try:
        G.main()
    except SystemExit as e:
        print("골든 종료 코드", e.code)
    print("후보 판정 호출 수", CALLS[0])


if __name__ == "__main__":
    if sys.argv[1:2] == ["compare"]:
        compare()
        sys.exit()
    if sys.argv[1:2] == ["crops"]:
        crops()
        sys.exit()
    if sys.argv[1:2] == ["golden"]:
        golden()
        sys.exit()
    pages = C.PAGES if len(sys.argv) < 2 else [p for p in C.PAGES if p[0] in sys.argv[1:]]
    for name, path, pg in pages:
        for cand in (False, True):
            run(name, path, pg, cand)
        print(name, "완료 · 후보 판정 호출 누적", CALLS[0], flush=True)
