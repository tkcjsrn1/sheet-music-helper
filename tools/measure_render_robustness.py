# -*- coding: utf-8 -*-
"""렌더 흔들림 시험 — 같은 PDF를 다른 렌더(PDFium dpi · 안티앨리어싱 조합)나 1px 이동 · 1% 크기로 넣었을 때
라벨이 기준(PyMuPDF 300dpi, 제품 PDF 경로)과 얼마나 달라지나. 측정 전용 — 제품 코드 무변경(main.py 명령줄 그대로).
근거 · 결과 표: docs/RENDER_ROBUSTNESS.md

    python tools/measure_render_robustness.py run [변형 ...]   # debug/render_robust/out/<변형>/<쪽>.json (워커 1, 있으면 건너뜀)
    python tools/measure_render_robustness.py                 # 비교 → debug/render_robust/compare.json + 표 출력
    python tools/measure_render_robustness.py clean <변형>     # 그 변형 결과만 지운다(코드가 바뀐 뒤 다시 잴 때)

PDFium 변형은 pypdfium2가 필요하다. 이 venv에 없으면 환경변수 AKBO_PDFIUM_PATH에 pypdfium2가 든 폴더를 준다.
300dpi가 아닌 PDFium 렌더는 Codex #504와 같이 300dpi PDFium 쪽 크기로 LANCZOS 리샘플한다.

**지표는 일치도다(정답 아님).** 기준에도 알려진 오류가 있어 「기준에만」에는 기준 유령이 사라진 것(좋아짐)도 섞인다.
「확실」 차이가 0이면 렌더가 바뀌어도 「확실」 라벨은 그대로라는 뜻이다. 진짜 손실 여부는 격자 육안 판정으로 따로 본다.
"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
# 판정 후보를 잴 때: AKBO_CODE_ROOT = 후보 worktree(그 main.py로 실행), AKBO_RUN_TAG = 결과 폴더 이름(debug/render_robust_<태그>)
CODE = os.environ.get("AKBO_CODE_ROOT", ROOT)
OUT = os.path.join(ROOT, "debug", "render_robust" + (f"_{os.environ['AKBO_RUN_TAG']}" if os.environ.get("AKBO_RUN_TAG") else ""))
PY = sys.executable
PDF_DIR = os.path.join(ROOT, "test_scores")

PAGES = ([("bach", "bach_minuet_Am.pdf", 0)]
         + [(f"bbm{i + 1}", "chopin_nocturne_Bbm.pdf", i) for i in range(6)]
         + [(f"db{i + 1}", "chopin_nocturne_Db_6-8.pdf", i) for i in range(6)]
         + [(f"em{i + 1}", "chopin_nocturne_Em.pdf", i) for i in range(4)])

SAME_PX = 2          # 1~2px 차이는 같은 라벨(사용자 기준)
MOVE_PX = 6          # 같은 음이름이 이 안이면 「이동」 — 같은 음표로 본다


def _variants():
    v = {"mupdf_png": ("mupdf", 0, 0, 1.0)}     # 대조군: 기준과 같은 그림을 PNG로 — 차이 0이어야 한다
    for dx, dy, n in ((1, 0, "dx+1"), (-1, 0, "dx-1"), (0, 1, "dy+1"), (0, -1, "dy-1")):
        v[n] = ("mupdf", dx, dy, 1.0)
    # 짝홀 확인(±1이 방향과 무관하게 같았다 — 2026-11-17) · 0.5px 리샘플 이동(선형 보간, 사용자 지시)
    for dx, dy, n in ((2, 0, "dx+2"), (0, 2, "dy+2"), (0.5, 0, "dx+0.5"), (0, 0.5, "dy+0.5"), (0.5, 0.5, "dxy+0.5")):
        v[n] = ("mupdf", dx, dy, 1.0)
    v["scale+1"] = ("mupdf", 0, 0, 1.01)
    v["scale-1"] = ("mupdf", 0, 0, 0.99)
    for dpi in (300, 315, 360):
        for t in (1, 0):
            for p in (1, 0):
                for i in (1, 0):
                    v[f"pdfium{dpi}_t{t}p{p}i{i}"] = ("pdfium", dpi, (t, p, i), None)
    return v


VARIANTS = _variants()
BASE = "base_mupdf_pdf"


def _pdfium():
    try:
        import pypdfium2 as pdfium
    except ImportError:
        sys.path.insert(0, os.environ.get("AKBO_PDFIUM_PATH", ""))
        import pypdfium2 as pdfium
    return pdfium


def _render(v, pdf, pg):
    kind = VARIANTS[v][0]
    if kind == "mupdf":
        from modules.preprocess import load_image
        im = load_image(os.path.join(PDF_DIR, pdf), pdf_page=pg)
        _k, dx, dy, s = VARIANTS[v]
        h, w = im.shape[:2]
        if s != 1.0:
            im = cv2.warpAffine(im, np.float32([[s, 0, 0], [0, s, 0]]), (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
        if dx or dy:
            im = cv2.warpAffine(im, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
        return im
    from PIL import Image
    pdfium = _pdfium()
    _k, dpi, (t, p, i), _ = VARIANTS[v]
    doc = pdfium.PdfDocument(os.path.join(PDF_DIR, pdf))
    try:
        page = doc[pg]
        size = page.render(scale=300 / 72).to_pil().size
        im = page.render(scale=dpi / 72, draw_annots=True, no_smoothtext=not t, no_smoothpath=not p,
                         no_smoothimage=not i).to_pil().convert("RGB")
        if dpi != 300:
            im = im.resize(size, Image.LANCZOS)
    finally:
        doc.close()
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def _to_base(v, x, y):
    """변형 좌표 → 기준 좌표."""
    if VARIANTS[v][0] != "mupdf":
        return x, y
    _k, dx, dy, s = VARIANTS[v]
    return (x - dx) / s, (y - dy) / s


def _main(src, js, tmp, extra=()):
    main = os.environ.get("AKBO_MAIN_WRAPPER")     # 측정 전용 래퍼(예: 렌더 종류 표시를 다는 것) — `python <래퍼> <코드 루트> <인자...>`
    head = [PY, main, CODE] if main else [PY, os.path.join(CODE, "main.py")]
    r = subprocess.run([*head, src, *extra, "--no-debug", "--output-dir", tmp, "--save-labels", js],
                       cwd=CODE, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode != 0 or not os.path.exists(js):
        print("   실패", js, (r.stdout + r.stderr).strip().splitlines()[-1:], flush=True)


def run(names):
    for v in [BASE] + names:
        for tag, pdf, pg in PAGES:
            js = os.path.join(OUT, "out", v, tag + ".json")
            if os.path.exists(js):
                continue
            os.makedirs(os.path.dirname(js), exist_ok=True)
            tmp = os.path.join(OUT, "tmp", v, tag)
            os.makedirs(tmp, exist_ok=True)
            try:
                if v == BASE:
                    _main(os.path.join(PDF_DIR, pdf), js, tmp, ("--page", str(pg)))
                else:
                    img = os.path.join(tmp, tag + ".png")
                    open(img, "wb").write(cv2.imencode(".png", _render(v, pdf, pg))[1].tobytes())
                    _main(img, js, tmp)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)       # 영상 · 결과 PNG는 바로 지운다(디스크)
        print(v, "끝", flush=True)


def _labels(path):
    d = json.load(open(path, encoding="utf-8"))
    return d, [dict(staff=int(l["staff"]), x=float(l["x"]), y=float(l["y"]), pitch=l["pitch"],
                    text=l["text"], conf=l["confidence"]) for l in d["labels"]]


def compare_page(v, tag):
    """(Counter, 상세) — 기준 라벨마다 변형 라벨 하나를 짝짓는다."""
    A_doc, A = _labels(os.path.join(OUT, "out", BASE, tag + ".json"))
    B_doc, B = _labels(os.path.join(OUT, "out", v, tag + ".json"))
    for b in B:
        b["x"], b["y"] = _to_base(v, b["x"], b["y"])
    c, detail = Counter(), dict(only_base=[], only_var=[], changed=[], conf=[])
    km = lambda d: (d["music"].get("key_symbol"), d["music"].get("key_count"))
    c["조표 바뀜"] += km(A_doc) != km(B_doc)
    c["보표 수 바뀜"] += len(A_doc["staves"]) != len(B_doc["staves"])
    used = set()
    pending = []
    for a in A:                           # 1차: 1~2px = 같은 라벨
        m = [(abs(b["x"] - a["x"]) + abs(b["y"] - a["y"]), j) for j, b in enumerate(B)
             if j not in used and b["staff"] == a["staff"] and abs(b["x"] - a["x"]) <= SAME_PX and abs(b["y"] - a["y"]) <= SAME_PX]
        if m:
            used.add(min(m)[1])
            pending.append((a, B[min(m)[1]]))
        else:
            pending.append((a, None))
    pairs = []
    for a, b in pending:                  # 2차: 같은 음이름 6px 안 = 이동
        if b is None:
            m = [(abs(x["x"] - a["x"]) + abs(x["y"] - a["y"]), j) for j, x in enumerate(B)
                 if j not in used and x["staff"] == a["staff"] and x["pitch"] == a["pitch"]
                 and abs(x["x"] - a["x"]) <= MOVE_PX and abs(x["y"] - a["y"]) <= MOVE_PX]
            if m:
                used.add(min(m)[1])
                b = B[min(m)[1]]
                c["이동"] += 1
        pairs.append((a, b))
    c["라벨"] = len(A)
    for a, b in pairs:
        if b is None:
            c["기준에만"] += 1
            c[f"기준에만·{a['conf']}"] += 1
            detail["only_base"].append(a)
            continue
        if (b["pitch"], b["text"]) != (a["pitch"], a["text"]):
            c["음고·표기 바뀜"] += 1
            if b["conf"] == "certain":
                c["확실 바뀜"] += 1
            detail["changed"].append([a, b])
        elif b["conf"] != a["conf"]:
            c["확신도 바뀜"] += 1
            c[f"확신도 {a['conf']}→{b['conf']}"] += 1
            detail["conf"].append([a, b])
        else:
            c["같음"] += 1
    for j, b in enumerate(B):
        if j not in used:
            c["변형에만"] += 1
            c[f"변형에만·{b['conf']}"] += 1
            detail["only_var"].append(b)
    return c, detail


KEYS = ("라벨", "같음", "이동", "기준에만", "기준에만·certain", "변형에만", "변형에만·certain",
        "음고·표기 바뀜", "확실 바뀜", "확신도 바뀜", "조표 바뀜", "보표 수 바뀜")


def compare():
    res, rows = {}, []
    for v in VARIANTS:
        tot, pages, detail = Counter(), {}, {}
        for tag, _pdf, _pg in PAGES:
            if not all(os.path.exists(os.path.join(OUT, "out", x, tag + ".json")) for x in (BASE, v)):
                continue
            c, d = compare_page(v, tag)
            tot += c
            tot["쪽"] += 1
            pages[tag] = dict(c)
            detail[tag] = d
        if not tot:
            continue
        res[v] = dict(total=dict(tot), pages=pages, detail=detail)
        # 「확실」 흔들림 = 기준 확실 라벨이 사라짐 + 변형에서 확실로 새로 생김 + 확실인데 음고 · 표기가 바뀜
        shake = tot["기준에만·certain"] + tot["변형에만·certain"] + tot["확실 바뀜"]
        rows.append((v, tot["쪽"], shake, tot))
    json.dump(res, open(os.path.join(OUT, "compare.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("변형 · 쪽 · 확실 흔들림 · " + " · ".join(KEYS))
    for v, n, shake, t in rows:
        print(f"{v:18s} {n:2d} {shake:4d} " + " ".join(f"{t[k]:4d}" for k in KEYS))
    return rows


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        run(a[1:] or [v for v in VARIANTS])
    elif a and a[0] == "clean":
        for v in a[1:]:
            d = os.path.join(OUT, "out", v)
            if os.path.isdir(d) and (v in VARIANTS or v == BASE):
                shutil.rmtree(d, ignore_errors=True)
                print("지움", d)
    else:
        compare()
