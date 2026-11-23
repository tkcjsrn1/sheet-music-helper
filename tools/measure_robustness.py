# -*- coding: utf-8 -*-
"""[3](d) 실제 사용 입력 내구성 — PDF 17쪽(300dpi 렌더) + Verovio 20쪽에 흐림 · JPEG · 잡음 · 밝기 · 1~2px 이동을 주고
변형 없는 결과와 비교해 라벨(사라짐 · 생김) · 음고 · 표기 · 조표 · 보표 수가 얼마나 흔들리나. 제품 코드 무변경(main.py 명령줄 그대로).

    python tools/measure_robustness.py run      # 변형 영상을 그때그때 만들어 main.py --save-labels → debug/robust/out/<변형>/<쪽>.json (3개 병렬, 영상 · 결과 PNG는 바로 지움)
    python tools/measure_robustness.py          # 비교
"""
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "robust")
PY = os.path.join(ROOT, "venv", "Scripts", "python.exe")


def _jpeg(im, q):
    return cv2.imdecode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)


def _shift(im, d):
    return cv2.warpAffine(im, np.float32([[1, 0, d], [0, 1, d]]), (im.shape[1], im.shape[0]), borderValue=(255, 255, 255))


VARIANTS = {
    "base": lambda im: im,
    "blur": lambda im: cv2.GaussianBlur(im, (0, 0), 1.0),
    "jpeg35": lambda im: _jpeg(im, 35),
    "noise": lambda im: np.clip(im.astype(np.int16) + np.random.default_rng(0).normal(0, 12, im.shape).astype(np.int16), 0, 255).astype(np.uint8),
    "dark": lambda im: (im.astype(np.float32) * 0.6).astype(np.uint8),
    "faded": lambda im: (255 - (255 - im.astype(np.float32)) * 0.55).astype(np.uint8),     # 흐린 인쇄(잉크가 회색)
    "shift1": lambda im: _shift(im, 1),
    "shift2": lambda im: _shift(im, 2),
}
SHIFT = {"shift1": 1, "shift2": 2}


def pages():
    import check_accidental_fix as C
    P = [(n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")]
    V = os.path.join(ROOT, "test_scores", "verovio")
    P += [(f[:-4], os.path.join("test_scores", "verovio", f), 0) for f in sorted(os.listdir(V)) if f.endswith("_p1.png")]
    return P


def make():
    from modules.preprocess import load_image
    for name, path, pg in pages():
        src = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
        for v, f in VARIANTS.items():
            d = os.path.join(OUT, "img", v)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, name + ".png"), "wb").write(cv2.imencode(".png", f(src))[1].tobytes())


def _run(job):
    """영상은 실행 직전에 만들고 끝나면 지운다 — 296장을 미리 만들면 약 0.8GB라 디스크가 찼다(2026-10-04)."""
    v, name, path, pg = job
    js = os.path.join(OUT, "out", v, name + ".json")
    if os.path.exists(js):
        return
    from modules.preprocess import load_image
    os.makedirs(os.path.dirname(js), exist_ok=True)
    tmp = os.path.join(OUT, "tmp", v, name)
    os.makedirs(tmp, exist_ok=True)
    src = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
    img = os.path.join(tmp, name + ".png")
    open(img, "wb").write(cv2.imencode(".png", VARIANTS[v](src))[1].tobytes())
    try:
        subprocess.run([PY, os.path.join(ROOT, "main.py"), img, "--no-debug", "--output-dir", tmp, "--save-labels", js],
                       cwd=ROOT, capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def run():
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(_run, [(v, n, p, g) for v in VARIANTS for n, p, g in pages()]))


def compare():
    acc = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
    tot = {}
    for v in VARIANTS:
        if v == "base":
            continue
        c = Counter()
        for name, path, _pg in pages():
            st = "verovio" if "verovio" in path else "pdf"
            a, b = (os.path.join(OUT, "out", x, name + ".json") for x in ("base", v))
            if not os.path.exists(a):
                continue
            c[(st, "쪽")] += 1
            if not os.path.exists(b):
                c[(st, "실패(결과 없음)")] += 1
                continue
            A, B = (json.load(open(x, encoding="utf-8")) for x in (a, b))
            d = SHIFT.get(v, 0)
            sp = float(np.median([s["spacing"] for s in A["staves"]])) if A["staves"] else 18.0
            c[(st, "보표 수 바뀜")] += len(A["staves"]) != len(B["staves"])
            ka, kb = (x.get("music", {}) for x in (A, B))
            c[(st, "조표 바뀜")] += (ka.get("key_symbol"), ka.get("key_count")) != (kb.get("key_symbol"), kb.get("key_count"))
            used = set()
            c[(st, "라벨")] += len(A["labels"])
            for la in A["labels"]:
                m = [(abs(lb["x"] - d - la["x"]) + abs(lb["y"] - d - la["y"]), j) for j, lb in enumerate(B["labels"])
                     if j not in used and abs(lb["x"] - d - la["x"]) <= 0.5 * sp and abs(lb["y"] - d - la["y"]) <= 0.4 * sp]
                if not m:
                    c[(st, "사라짐")] += 1
                    continue
                j = min(m)[1]
                used.add(j)
                lb = B["labels"][j]
                if lb["pitch"] != la["pitch"]:
                    c[(st, "음고 바뀜")] += 1
                elif acc(lb["text"]) != acc(la["text"]):
                    c[(st, "표기 바뀜")] += 1
            c[(st, "생김")] += len(B["labels"]) - len(used)
        tot[v] = c
    json.dump({v: {f"{k[0]}|{k[1]}": n for k, n in c.items()} for v, c in tot.items()}, open(os.path.join(OUT, "compare.json"), "w", encoding="utf-8"), ensure_ascii=False)
    keys = ("쪽", "실패(결과 없음)", "보표 수 바뀜", "조표 바뀜", "라벨", "사라짐", "생김", "음고 바뀜", "표기 바뀜")
    for st in ("pdf", "verovio"):
        print(st)
        for v, c in tot.items():
            print(f"  {v:7s} " + " · ".join(f"{k} {c[(st, k)]}" for k in keys))


if __name__ == "__main__":
    {"make": make, "run": run}.get(sys.argv[1] if len(sys.argv) > 1 else "", compare)()
