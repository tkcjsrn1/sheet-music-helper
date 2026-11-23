# -*- coding: utf-8 -*-
"""A-17 ♮ · ♯ 뒤바뀜 측정 (2026-09-29, 제품 코드 무변경).

1. 재현: D♭ 3쪽 ♮ (961,2897) · ♯ (1081,2906) — 판정 입력값(막대 목록 · 런 시작/끝 · 간격 · 어긋남)을 제품 함수를 가로채 그대로 기록
2. 20쪽 전수: PDF 임시표 글리프(조표 제외) → 그 글리프가 붙는 정답 머리 → 제품 최종 음표(기존 + chord_rescue 합치기)의
   **원시 판정**(마디 내 전파 전, 음표 자신의 창에서 본 것) 혼동 행렬. 「글리프 없음」 행 = 정답 글리프가 없는데 판정이 난 음표
3. 틀린 것 확대 그림 → docs/review/a17_accidental/
4. 0.25 · 0.5 · 0.75px 평행이동에서 같은 음표 판정(위상 분류용)

원시 판정은 annotate_accidentals에 **음표마다 서로 다른 옥타브를 준 사본**을 넣어 전파를 끈다(판정 창 · 후보 고르기는 제품 그대로).
판정 입력값은 `accidental_detect._find_thin_bars` · `_find_glyphs`를 원본 모듈에서 가로채 읽는다(측정 함정 A-1 · B-4).

실행: python tools/measure_a17.py [repro|all]
"""
import dataclasses
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import check_accidental_fix as C  # noqa: E402
import measure_omission_rate as M  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402
from modules.chord_rescue import detect_noteheads_rescue, merge_additive  # noqa: E402
from modules.preprocess import PreprocessResult, binarize  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "review", "a17_accidental")
# Emmentaler 이름이 두 체계로 섞여 있다(sharp = 2, flat = M2, natural = 0, flatflat = M4, doublesharp = 4). 괄호는 임시표가 아니다
KIND = {"sharp": "#", "2": "#", "flat": "b", "M2": "b", "natural": "natural", "0": "natural",
        "flatflat": "flatflat", "M4": "flatflat", "doublesharp": "doublesharp", "4": "doublesharp"}
# 제품에 없는 표기 — 틀림으로 세지 않고 따로 본다(♭♭ → b는 제품이 낼 수 있는 가장 가까운 값)
NO_PRODUCT = ("flatflat", "doublesharp")


# ------------------------------------------------------------------ 제품 경로
def pipeline_notes(res, ctx, rescue=False):
    """check_accidental_fix.snapshot_page와 같은 순서로 최종 음표(임시표 유령 제거 뒤)까지."""
    heads = (detect_noteheads_rescue if rescue else C.detect_noteheads)(res, contexts=ctx)
    heads, _ = C.drop_beam_ghosts(res, heads)
    heads, _ = C.drop_offstaff_ghosts(res, heads)
    C.FILLED.clear()
    C.FILLED.update({(h.staff_index, h.x, h.y): bool(h.filled) for h in heads})
    notes = C.calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    notes, _accs = C.accidental_stage(res, ctx, notes)
    return notes


def final_notes(path, pg):
    """기존 파이프라인 + chord_rescue(merge_additive) — main.py에 연결될 모양(FILL_ADDITIVE_MEASURE §8)."""
    full = os.path.join(ROOT, path)
    res = C.preprocess(full, pdf_page=pg)
    ctx = C.analyze_staves(res)
    base = pipeline_notes(res, ctx)
    extra = pipeline_notes(C.preprocess(full, pdf_page=pg), ctx, rescue=True)
    sp = float(np.median([s.spacing for s in res.staves]))
    added, deleted = merge_additive([(n.x, n.y) for n in base], [(n.x, n.y) for n in extra], sp)
    notes = [n for i, n in enumerate(base) if i not in set(deleted)] + [extra[j] for j in added]
    src = ["base"] * (len(base) - len(deleted)) + ["rescue"] * len(added)
    return res, ctx, sp, notes, src


def raw_judgments(res, ctx, notes):
    """전파 없는 원시 판정 — 음표마다 옥타브를 달리해 active 키가 겹치지 않게 한다."""
    uniq = [dataclasses.replace(n, octave=1000 + i) for i, n in enumerate(notes)]
    return AD.annotate_accidentals(res, ctx, uniq)


def probe(res, ctx, note):
    """음표 하나의 판정 입력값 — 원본 모듈 함수를 가로채 읽는다."""
    rec = {}
    fb, fg = AD._find_thin_bars, AD._find_glyphs

    def spy_bars(patch, sp):
        out = fb(patch, sp)
        runs = [AD._max_run_and_extent(patch[:, c] > 0)[0] for c in range(patch.shape[1])]
        rec["patch"] = patch.shape
        rec["bars"] = [dict(x=x, s=s, e=e, len_sp=round((e - s + 1) / sp, 2),
                            width_px=sum(1 for c in range(patch.shape[1])
                                         if abs(c - x) <= sp * 0.45 and sp * 1.5 <= runs[c] <= sp * 3.2)) for x, s, e in out]
        rec["long_cols"] = sum(1 for r in runs if r > sp * 3.2)          # 기둥 · 붙은 덩어리(막대 상한 초과)
        return out

    def spy_glyphs(patch, sp, **kw):                         # 정밀 판정(DECISIONS §1-12) 뒤 bars · refined 인자
        out = fg(patch, sp, **kw)
        if kw.get("bars") is not None:
            rec["bars_used"] = [(round(x, 1), s_, e_) for x, s_, e_ in kw["bars"]]
        rec["found"] = [(k, round(y, 1)) for k, y in out]
        return out

    AD._find_thin_bars, AD._find_glyphs = spy_bars, spy_glyphs
    try:
        rec["raw"] = raw_judgments(res, ctx, [note])[0]
    finally:
        AD._find_thin_bars, AD._find_glyphs = fb, fg
    st = next(s for s in res.staves if s.index == note.staff_index)
    sp = st.spacing
    top = max(0, int(st.top - sp * 3.5))                        # annotate_accidentals와 같은 밴드 · 창 원점
    nyp = note.y - top - max(0, int(note.y - top - sp * 2.0))
    rec["note_y_in_patch"] = nyp
    b = rec.get("bars", [])
    W = rec.get("patch", (0, 0))[1]
    rec["pairs"] = []
    for p, q in zip(b, b[1:]):
        if not (sp * 0.3 <= q["x"] - p["x"] <= sp * 0.95):
            continue
        rec["pairs"].append(dict(kind="natural" if (p["s"] + sp * 0.45 < q["s"] and p["e"] + sp * 0.45 < q["e"]) else "#",
                                 dx_sp=round((q["x"] - p["x"]) / sp, 2), top_off_sp=round((q["s"] - p["s"]) / sp, 2),
                                 bot_off_sp=round((q["e"] - p["e"]) / sp, 2),
                                 center_dy_sp=round(((p["s"] + p["e"] + q["s"] + q["e"]) / 4 - nyp) / sp, 2),
                                 edge_bar=q["x"] >= W - 2))       # 창 오른쪽 끝(= 음표 머리 가장자리)에 닿은 막대
    win = [p for p in rec["pairs"] if abs(p["center_dy_sp"]) <= AD.ACCIDENTAL_Y_TOL_SP]
    rec["chosen_pair"] = min(win, key=lambda p: abs(p["center_dy_sp"])) if win else None
    rec["sp"] = round(sp, 2)
    return rec


def shifted(res, d):
    bgr = res.original_bgr
    m = np.array([[1.0, 0, d], [0, 1.0, d]])
    moved = cv2.warpAffine(bgr, m, (bgr.shape[1], bgr.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    gray, binary = binarize(moved)
    return PreprocessResult(original_bgr=moved, gray=gray, binary=binary, staves=res.staves)


# ------------------------------------------------------------------ 정답
def truth(path, pg, res, ctx):
    """조표 밖 임시표 글리프와 그 글리프가 붙는 정답 머리(오른쪽 0~4sp, 원점 y ±0.3sp, 가장 가까운 것)."""
    g = M.pdf_glyphs(path, pg, ("accidentals.", "noteheads."))
    heads = [q for q in g if q["name"].startswith("noteheads.")]
    out, skipped = [], []
    for q in g:
        if not q["name"].startswith("accidentals.") or q["name"].split(".", 1)[1] not in KIND:
            continue
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - q["oy"]))
        sp = st.spacing
        if st.index in ctx and q["cx"] < ctx[st.index].header_end:
            continue                                            # 조표
        cand = [h for h in heads if 0 < h["cx"] - q["cx"] <= 4 * sp and abs(h["cy"] - q["oy"]) <= 0.3 * sp]
        if not cand:
            skipped.append(dict(name=q["name"], x=round(q["cx"]), y=round(q["oy"])))
            continue
        h = min(cand, key=lambda h: h["cx"] - q["cx"])
        out.append(dict(name=q["name"], gh_sp=round(q["h"] / sp, 2), kind=KIND[q["name"].split(".", 1)[1]], gx=q["cx"], gy=q["oy"],
                        hx=h["cx"], hy=h["cy"], sp=sp, staff=st.index))
    return out, skipped, heads


# ------------------------------------------------------------------ 실행
def repro():
    path, pg = C._DB, 2
    res, ctx, sp, notes, src = final_notes(path, pg)
    rows = []
    for gx, gy, hx, want in ((961, 2897, 987, "natural"), (1081, 2906, 1110, "#")):
        n = min(notes, key=lambda n: abs(n.x - hx) + abs(n.y - gy))
        rec = probe(res, ctx, n)
        rec.update(glyph=(gx, gy), note=(n.x, n.y), note_src=src[notes.index(n)], want=want,
                   shifts={d: raw_judgments(shifted(res, d), ctx, [dataclasses.replace(n, x=round(n.x + d), y=round(n.y + d))])[0]
                           for d in (0.25, 0.5, 0.75)})
        rows.append(rec)
        print(json.dumps(rec, ensure_ascii=False, default=str), flush=True)
    return rows


def run_all():
    from collections import Counter
    conf = Counter()
    wrong, skipped_all, extra_rows = [], [], []
    for name, path, pg in C.PAGES:
        res, ctx, sp, notes, src = final_notes(path, pg)
        raw = raw_judgments(res, ctx, notes)
        if not path.endswith(".pdf"):
            n_acc = sum(1 for a in raw if a)
            print(name, "PDF 정답 없음 — 원시 판정 임시표", n_acc, flush=True)
            conf[("(정답 없음)", "판정 있음" if n_acc else "판정 없음")] += n_acc
            continue
        glyphs, skipped, heads = truth(path, pg, res, ctx)
        skipped_all += [dict(s, page=name) for s in skipped]
        used = set()
        for t in glyphs:
            cand = [i for i, n in enumerate(notes) if abs(n.x - t["hx"]) <= 0.7 * t["sp"] and abs(n.y - t["hy"]) <= 0.5 * t["sp"]]
            if not cand:
                conf[(t["kind"], "음표 없음")] += 1
                continue
            i = min(cand, key=lambda i: abs(notes[i].x - t["hx"]) + abs(notes[i].y - t["hy"]))
            used.add(i)
            got = raw[i] or "없음"
            conf[(t["kind"], got)] += 1
            if DIST is not None and t["kind"] in ("#", "natural"):
                r = probe(res, ctx, notes[i])
                own = [p for p in r["pairs"] if not p["edge_bar"]]
                DIST.append(dict(page=name, kind=t["kind"], got=got, glyph=(round(t["gx"]), round(t["gy"])), gh_sp=t["gh_sp"],
                                 src=src[i], dx_sp=round((notes[i].x - t["gx"]) / t["sp"], 2), clipped=r["note_y_in_patch"] < 2 * r["sp"] - 1,
                                 own=min(own, key=lambda p: abs(p["center_dy_sp"])) if own else None, pairs=r["pairs"]))
            if got != t["kind"] and t["kind"] not in NO_PRODUCT:
                rec = probe(res, ctx, notes[i])
                rec["shifts"] = {d: raw_judgments(shifted(res, d), ctx,
                                                  [dataclasses.replace(notes[i], x=round(notes[i].x + d), y=round(notes[i].y + d))])[0] or "없음"
                                 for d in (0.25, 0.5, 0.75)}
                wrong.append(dict(page=name, path=path, pg=pg, kind=t["kind"], got=got, gh_sp=t["gh_sp"],
                                  clipped=rec["note_y_in_patch"] < 2 * rec["sp"] - 1, glyph=(round(t["gx"]), round(t["gy"])),
                                  note=(notes[i].x, notes[i].y), src=src[i], glyph_dx_sp=round((notes[i].x - t["gx"]) / t["sp"], 2), **rec))
        # 정답 글리프가 겨냥하지 않은 음표에 판정이 난 것
        for i, a in enumerate(raw):
            if a and i not in used:
                n = notes[i]
                on_glyph = any(abs(h["cx"] - n.x) <= 0.7 * sp and abs(h["cy"] - n.y) <= 0.5 * sp for h in heads)
                conf[("글리프 없음", a)] += 1
                extra_rows.append(dict(page=name, note=(n.x, n.y), got=a, src=src[i], on_true_head=on_glyph))
        print(name, "글리프", len(glyphs), "틀림 누적", len(wrong), flush=True)
    json.dump(dict(conf={f"{k[0]}|{k[1]}": v for k, v in conf.items()}, wrong=wrong, skipped=skipped_all, extra=extra_rows),
              open(os.path.join(ROOT, "debug", "a17.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str, indent=1)
    rows = ["#", "b", "natural", "flatflat", "doublesharp", "글리프 없음", "(정답 없음)"]
    cols = ["#", "b", "natural", "없음", "음표 없음", "판정 있음"]
    print("\n| 정답 \\ 원시 판정 | " + " | ".join(cols) + " |\n|---|" + "---:|" * len(cols))
    for r in rows:
        if any(conf[(r, c)] for c in cols):
            print(f"| {r} | " + " | ".join(str(conf[(r, c)]) for c in cols) + " |")
    print("\n다른 종류:", {k: v for k, v in conf.items() if k[0] not in rows or k[1] not in cols})
    print("대상 머리 없는 글리프:", len(skipped_all), skipped_all)
    crops(wrong)


def crops(wrong):
    """틀린 것 확대 — 원본 ±3sp, 글리프 청록 네모 · 음표 주황 원."""
    import math
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    os.makedirs(OUT_DIR, exist_ok=True)
    tiles, cache = [], {}
    for k, w in enumerate(wrong):
        key = (w["path"], w["pg"])
        if key not in cache:
            cache.clear()
            cache[key] = C.preprocess(os.path.join(ROOT, w["path"]), pdf_page=w["pg"]).original_bgr
        img, sp = cache[key], w["sp"]
        cx, cy = (w["glyph"][0] + w["note"][0]) / 2, w["note"][1]
        x0, y0 = max(0, int(cx - 3 * sp)), max(0, int(cy - 3 * sp))
        c = img[y0:int(cy + 3 * sp), x0:int(cx + 3 * sp)].copy()
        cv2.circle(c, (int(w["note"][0] - x0), int(w["note"][1] - y0)), int(sp * 0.7), (0, 140, 255), 2)
        gx, gy = w["glyph"][0] - x0, w["glyph"][1] - y0
        cv2.rectangle(c, (int(gx - 0.5 * sp), int(gy - 1.4 * sp)), (int(gx + 0.5 * sp), int(gy + 1.4 * sp)), (200, 160, 0), 1)
        s = 190 / max(c.shape[:2])
        c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        t = Image.new("RGB", (230, 262), "white")
        t.paste(Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)), (20, 64))
        d = ImageDraw.Draw(t)
        d.text((3, 2), f"#{k + 1} {w['page']} ({w['glyph'][0]},{w['glyph'][1]}) {w['src']}", font=font, fill=(0, 0, 0))
        d.text((3, 19), f"정답 {w['kind']} → 판정 {w['got']}", font=font, fill=(180, 60, 0))
        d.text((3, 36), "0.25/0.5/0.75px: " + "/".join(str(v) for v in w["shifts"].values()), font=font, fill=(60, 60, 60))
        d.rectangle([0, 0, 229, 261], outline=(190, 190, 190))
        tiles.append(t)
    for s0 in range(0, len(tiles), 20):
        chunk = tiles[s0:s0 + 20]
        rows = math.ceil(len(chunk) / 5)
        sheet = Image.new("RGB", (5 * 235 + 5, rows * 267 + 5), "white")
        for i, t in enumerate(chunk):
            sheet.paste(t, (5 + (i % 5) * 235, 5 + (i // 5) * 267))
        sheet.save(os.path.join(OUT_DIR, f"wrong_{s0 // 20 + 1}.png"))


DIST = None


def run_dist():
    """맞게 · 틀리게 판정된 정답 ♯/♮ 전부의 막대쌍 값(창 끝 막대 뺀 자기 쌍) — 수정 방향 후보의 근거."""
    global DIST
    DIST = []
    run_all()
    json.dump(DIST, open(os.path.join(ROOT, "debug", "a17_dist.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


def run_sim_band(margin_sp=2.0):
    """후보 추정(제품 무변경): 임시표 밴드를 보표 ±3.5sp에서 ±(3.5+margin)sp로 — 창이 밴드 경계에서 잘리지 않게.
    annotate_accidentals가 보는 staff.top/bottom만 넓힌 사본을 주고, 오선 제거는 원래 보표로 한다(가로채기)."""
    global crops
    orig_ann, orig_rsl = AD.annotate_accidentals, AD.remove_staff_lines

    def ann(result, contexts, notes):
        from types import SimpleNamespace                      # top/bottom은 line_ys 속성이라 판정이 읽는 필드만 가진 사본
        wide = [SimpleNamespace(index=s.index, spacing=s.spacing, line_ys=s.line_ys,
                                top=int(s.top - margin_sp * s.spacing), bottom=int(s.bottom + margin_sp * s.spacing)) for s in result.staves]
        AD.remove_staff_lines = lambda b, _st: orig_rsl(b, result.staves)
        try:
            return orig_ann(PreprocessResult(original_bgr=result.original_bgr, gray=result.gray, binary=result.binary, staves=wide),
                            contexts, notes)
        finally:
            AD.remove_staff_lines = orig_rsl

    AD.annotate_accidentals = ann
    crops = lambda _w: None
    try:
        run_all()
    finally:
        AD.annotate_accidentals = orig_ann


if __name__ == "__main__":
    {"repro": repro, "all": run_all, "dist": run_dist, "sim_band": run_sim_band}[sys.argv[1] if len(sys.argv) > 1 else "all"]()
