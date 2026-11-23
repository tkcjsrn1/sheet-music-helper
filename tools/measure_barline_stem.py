# -*- coding: utf-8 -*-
"""A-25 마디선 오검출 — 진짜 마디선과 기둥을 가르는 성질을 잰다. 제품 코드 무변경.

제품 마디선 후보 = `accidental_detect._find_barlines`(임시표 전파 경계 · 라벨 배치가 쓰는 그 함수) 출력 전부.
정답: PDF(LilyPond) = 벡터 세로 사각형(두께 > 0.5pt 마디선 · 0.23pt 기둥), Verovio = SVG barLine · stem 상자, Aoharu = 정답 없음(그림 판정).

성질(기보 규칙 후보):
  ext_top / ext_bot  그 열의 세로 잉크(오선 제거 + 제품과 같은 세로 닫힘)가 맨윗줄 위 · 맨아랫줄 아래로 뻗은 길이(sp, 음수 = 안쪽에서 끝남)
  joins              위 · 아래 이웃 보표 맨아랫줄 · 맨윗줄까지 이어지는가(큰보표 관통)
  blob_top / blob_bot 세로 잉크 양 끝 ±0.3sp 띠의 가로 잉크 폭(sp) — 머리 · 빔이 붙었는가

    python tools/measure_barline_stem.py collect | report
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "debug", "barline_stem")


def pdf_verticals(path, page, dpi=300):
    """PDF 세로 사각형 · 세로 선 → [(x, y0, y1, kind)] px. 두께 > 0.5pt 마디선, 그 밖 기둥."""
    import fitz
    k = dpi / 72.0
    out = []
    for dr in fitz.open(path)[page].get_drawings():
        for it in dr["items"]:
            if it[0] == "re" and it[1].height > it[1].width * 3 and it[1].height > 5:
                r = it[1]
                out.append(((r.x0 + r.x1) / 2 * k, r.y0 * k, r.y1 * k, "barline" if r.width > 0.5 else "stem"))
            elif it[0] == "l" and abs(it[1].x - it[2].x) < 0.5 and abs(it[1].y - it[2].y) > 5:
                # E단조 PDF는 마디선을 사각형이 아니라 굵기 0.93pt 세로 선으로 그린다(2026-10-06 — 이것을 빠뜨려 그 4쪽 정답 전파가 마디를 넘었다)
                y0, y1 = sorted((it[1].y, it[2].y))
                out.append((it[1].x * k, y0 * k, y1 * k, "barline" if (dr.get("width") or 0) > 0.5 else "stem"))
    return out


def pages():
    import check_accidental_fix as C
    P = [("pdf", n, os.path.join(ROOT, p), pg) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    P += [("aoharu", n, os.path.join(ROOT, p), pg) for n, p, pg in C.PAGES if not p.endswith(".pdf")]
    V = os.path.join(ROOT, "test_scores", "verovio")
    P += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    return P


def _one(job):
    import cv2
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules import accidental_detect as AD
    st_, name, path, pg = job
    res = preprocess(path, pdf_page=pg) if path.endswith(".pdf") else preprocess(path)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    if st_ == "pdf":
        truth = pdf_verticals(path, pg)
    elif st_ == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        truth = [((b["box"][0] + b["box"][2]) / 2, b["box"][1], b["box"][3], {"barLine": "barline", "stem": "stem"}[b["cls"]])
                 for b in t["boxes"] if b["cls"] in ("barLine", "stem")]
    else:
        truth = None
    staves = sorted(res.staves, key=lambda s: s.top)
    rows = []
    closed = {}
    for i, s in enumerate(staves):
        sp = s.spacing
        vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
        y0, y1 = 0, H                                       # 쪽 전체 — 8sp 창은 쇼팽 큰보표 사이(> 8sp)를 못 담았다(측정 함정 A-6)
        band = closed.setdefault(vk.shape[0], cv2.morphologyEx(ns, cv2.MORPH_CLOSE, vk))
        for x in AD._find_barlines(ns, s, H):
            # 오선 가운데 행을 지나는 세로 잉크 런(±1열 중 가장 긴 것)
            best = None
            for c in (x - 1, x, x + 1):
                col = band[:, c] > 0
                mid = int((s.top + s.bottom) / 2) - y0
                if not col[mid]:
                    continue
                a = mid
                while a > 0 and col[a - 1]:
                    a -= 1
                b = mid
                while b < len(col) - 1 and col[b + 1]:
                    b += 1
                if best is None or b - a > best[1] - best[0]:
                    best = (a, b, c)
            if best is None:
                continue
            a, b, c = best
            top, bot = y0 + a, y0 + b
            prev_ = staves[i - 1] if i > 0 else None
            next_ = staves[i + 1] if i + 1 < len(staves) else None

            def blob(yc):
                r0, r1 = max(0, int(yc - y0 - 0.3 * sp)), int(yc - y0 + 0.3 * sp) + 1
                row = (band[r0:r1, max(0, c - int(2 * sp)):c + int(2 * sp) + 1] > 0).any(axis=0)
                # 막대 열에서 이어진 가로 잉크 폭
                k = int(2 * sp) if c >= int(2 * sp) else c
                l = k
                while l > 0 and row[l - 1]:
                    l -= 1
                r = k
                while r < len(row) - 1 and row[r + 1]:
                    r += 1
                return (r - l + 1) / sp
            kind = None
            if truth is not None:
                hit = [k for tx, ty0, ty1, k in truth if abs(tx - x) <= 0.5 * sp and ty0 <= s.bottom and ty1 >= s.top]
                kind = "barline" if "barline" in hit else "stem" if "stem" in hit else "other"
            # 양 끝이 오선 경계에 맞는가 — 위끝은 어느 보표 맨윗줄, 아래끝은 어느 보표 맨아랫줄까지의 최소 거리(sp)
            end_top = min(abs(top - q.top) for q in staves) / sp
            end_bot = min(abs(bot - q.bottom) for q in staves) / sp
            rows.append(dict(set=st_, page=name, staff=s.index, x=int(x), sp=sp, truth=kind, top=int(top), bot=int(bot),
                             end_top=end_top, end_bot=end_bot,
                             ext_top=(s.top - top) / sp, ext_bot=(bot - s.bottom) / sp,
                             joins_up=bool(prev_ and top <= prev_.bottom + 0.3 * sp),
                             joins_down=bool(next_ and bot >= next_.top - 0.3 * sp),
                             blob_top=blob(top), blob_bot=blob(bot)))
    return rows


def collect():
    os.makedirs(OUT, exist_ok=True)
    with ProcessPoolExecutor(2) as ex:                      # (c) 평가와 겹쳐 2개만
        rows = [r for part in ex.map(_one, pages()) for r in part]
    json.dump(rows, open(os.path.join(OUT, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("후보", len(rows), Counter((r["set"], r["truth"]) for r in rows))


def report_ends():
    """「양 끝이 오선 경계」 E = max(end_top, end_bot) 분포 — 마디선 최대 vs 기둥 최소, 문턱별 놓침 · 가짜."""
    rows = json.load(open(os.path.join(OUT, "candidates.json"), encoding="utf-8"))
    for font in ("pdf", "verovio"):
        for kind in ("barline", "stem", "other"):
            a = np.array([max(r["end_top"], r["end_bot"]) for r in rows if r["set"] == font and r["truth"] == kind])
            if len(a):
                print(f"{font:7s} {kind:7s} n {len(a):4d} E 최소 {a.min():.2f} 1% {np.percentile(a, 1):.2f} 중앙 {np.median(a):.2f} 99% {np.percentile(a, 99):.2f} 최대 {a.max():.2f}")
    for t in (0.1, 0.15, 0.2, 0.25, 0.3, 0.4):
        c = Counter((r["set"], r["truth"], max(r["end_top"], r["end_bot"]) <= t) for r in rows if r["set"] != "aoharu")
        print(f"E ≤ {t}: 마디선 놓침 PDF {c[('pdf', 'barline', False)]}/{c[('pdf', 'barline', False)] + c[('pdf', 'barline', True)]}"
              f" · Verovio {c[('verovio', 'barline', False)]}/{c[('verovio', 'barline', False)] + c[('verovio', 'barline', True)]}"
              f" | 기둥 남음 PDF {c[('pdf', 'stem', True)]} · Verovio {c[('verovio', 'stem', True)]} | other 남음 PDF {c[('pdf', 'other', True)]} · Verovio {c[('verovio', 'other', True)]}")


def report():
    rows = json.load(open(os.path.join(OUT, "candidates.json"), encoding="utf-8"))
    for font in ("pdf", "verovio"):
        for kind in ("barline", "stem", "other"):
            v = [r for r in rows if r["set"] == font and r["truth"] == kind]
            if not v:
                continue
            def q(k, vv=None):
                a = np.array([r[k] for r in (v if vv is None else vv)], float)
                return f"{a.min():.2f}/{np.median(a):.2f}/{a.max():.2f}"
            out = [r for r in v if not (r["joins_up"] or r["joins_down"])]
            print(f"{font:7s} {kind:7s} n {len(v):4d} | 큰보표 관통 {sum(r['joins_up'] or r['joins_down'] for r in v):4d} | "
                  f"관통 안 하는 것 {len(out)}: 위 뻗음 {q('ext_top', out) if out else '-'} · 아래 {q('ext_bot', out) if out else '-'} | "
                  f"끝 덩어리 위 {q('blob_top')} 아래 {q('blob_bot')}")



# ------------------------------------------------------------------ 규칙 비교
def _label_xs(st_, name):
    """제품 라벨(run_page) 음표 x — 보표별. PDF · Aoharu = debug/a17_cand1_cmp/base_pdf20, Verovio = debug/vrv/plain_base."""
    p = (os.path.join(ROOT, "debug", "vrv", "plain_base", name + ".json") if st_ == "verovio"
         else os.path.join(ROOT, "debug", "a17_cand1_cmp", "base_pdf20", name + ".json"))
    out = {}
    for l in json.load(open(p, encoding="utf-8"))["labels"]:
        out.setdefault(l["staff"], []).append(int(l["x"]))
    return out


def _rules_one(job):
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules import accidental_detect as AD
    from modules.verify import barline_positions
    st_, name, path, pg = job
    res = preprocess(path, pdf_page=pg) if path.endswith(".pdf") else preprocess(path)
    ns = remove_staff_lines(res.binary, res.staves)
    H = res.binary.shape[0]
    xs = _label_xs(st_, name)
    if st_ == "pdf":
        truth = pdf_verticals(path, pg)
        truth = [(x, a, b, "barline" if (k == "barline" or x < 300) else k) for x, a, b, k in truth]   # 시스템 첫머리선(0.23pt)도 마디선
    elif st_ == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        truth = [((b["box"][0] + b["box"][2]) / 2, b["box"][1], b["box"][3], {"barLine": "barline", "stem": "stem"}[b["cls"]])
                 for b in t["boxes"] if b["cls"] in ("barLine", "stem")]
    else:
        truth = None
    cand = [r for r in json.load(open(os.path.join(OUT, "candidates.json"), encoding="utf-8")) if r["set"] == st_ and r["page"] == name]
    rows = []
    for s in res.staves:
        sp = s.spacing
        nx = xs.get(s.index, [])
        if len(nx) < 2:
            continue
        lo, hi = min(nx), max(nx)
        p0 = [x for x in AD._find_barlines(ns, s, H) if lo < x < hi]
        mine = [r for r in cand if r["staff"] == s.index]
        joined_staff = any(r["joins_up"] or r["joins_down"] for r in mine)
        r1 = [x for x in p0 if not joined_staff or any(r["x"] == x and (r["joins_up"] or r["joins_down"]) for r in mine)]
        r2 = barline_positions(res.binary, s, nx)
        row = dict(set=st_, page=name, staff=s.index, sp=sp, p0=p0, r1=r1, r2=r2, joined=joined_staff)
        if truth is not None:
            real = sorted({round(x) for x, a, b, k in truth if k == "barline" and a <= s.bottom and b >= s.top and lo < x < hi})
            row["real"] = real
            for k in ("p0", "r1", "r2"):
                row[k + "_miss"] = [x for x in real if not any(abs(x - y) <= 0.5 * sp for y in row[k])]
                row[k + "_fake"] = [y for y in row[k] if not any(abs(x - y) <= 0.5 * sp for x in real)]
        rows.append(row)
    return rows


def rules():
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_rules_one, pages()) for r in part]
    json.dump(rows, open(os.path.join(OUT, "rules.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for st_ in ("pdf", "verovio"):
        v = [r for r in rows if r["set"] == st_]
        n_real = sum(len(r["real"]) for r in v)
        for k, nm in (("p0", "제품 _find_barlines"), ("r1", "보표 단위 관통 규칙"), ("r2", "barline_positions(음표 x 제외)")):
            miss = sum(len(r[k + "_miss"]) for r in v)
            fake = sum(len(r[k + "_fake"]) for r in v)
            print(f"{st_:7s} {nm:28s} 진짜 마디선 {n_real} 중 놓침 {miss} · 가짜(기둥 등) {fake}")
    a = [r for r in rows if r["set"] == "aoharu"]
    print("aoharu  (정답 없음) 검출 수 — 제품", sum(len(r["p0"]) for r in a), "· 관통 규칙", sum(len(r["r1"]) for r in a),
          "· barline_positions", sum(len(r["r2"]) for r in a))

if __name__ == "__main__":
    {"collect": collect, "report": report, "ends": report_ends, "rules": rules}[sys.argv[1]]()
