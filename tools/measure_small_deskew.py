# -*- coding: utf-8 -*-
"""(아침 6) 일반 모드에 「작은 기울기 보정」을 앞단에 둘 때의 영향 — 측정만 (2026-10-13, 구현 안 함).

사본 규칙: `photo_correct.estimate_skew`(사진 모드와 같은 추정)로 각을 재고, |각| ≤ 3° **그리고** 폭 전체 밀림 > 2px(사진 모드와 같은 문턱)이면
그만큼 돌린 영상을 일반 모드로 처리한다. 잘라내기 · 안전장치는 하지 않는다(사진 모드와 다른 점).
① 깨끗한 쪽(Aoharu 3 · PDF 17): 추정 각 · 밀림 — 하나도 안 돌면 골든 711 · PDF 스냅샷 변화는 구조적으로 0
② `inputs/degraded/`에서 일반 모드가 거부한 9장: 돌린 뒤 일반 모드 처리 → 거부 여부 · 정답(같은 회전 행렬로 옮김) 채점

    python tools/measure_small_deskew.py
"""
import contextlib, io, json, math, os, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
MAX_DEG, MIN_DRIFT_PX = float(os.environ.get("DESKEW_MAX_DEG", "3.005")), 2.0   # 3° + 추정 격자 한 칸(오차 최대 0.0047°, tools/measure_skew_error.py)


def _angle(bgr):
    from modules.photo_correct import estimate_skew
    a = -estimate_skew(bgr)
    w = bgr.shape[1]
    drift = abs(math.tan(math.radians(a))) * w
    return float(a), float(drift), bool(abs(a) <= MAX_DEG and drift > MIN_DRIFT_PX)


def _clean(job):
    nm, path, pg = job
    from modules.preprocess import load_image
    a, d, rot = _angle(load_image(os.path.join(ROOT, path), pdf_page=pg))
    return dict(page=nm, angle=round(a, 3), drift_px=round(d, 2), rotate=rot)


def _deg(stem):
    import cv2
    import main as MAIN
    import score_inputs as S
    D = os.path.join(ROOT, "inputs", "degraded")
    m = next(x for x in json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8")) if x["stem"] == stem)
    bgr = cv2.imdecode(np.fromfile(os.path.join(D, m["file"]), np.uint8), cv2.IMREAD_COLOR)
    a, d, rot = _angle(bgr)
    h, w = bgr.shape[:2]
    R = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0) if rot else np.array([[1.0, 0, 0], [0, 1.0, 0]])
    out_dir = os.path.join(ROOT, "debug", "small_deskew")
    os.makedirs(out_dir, exist_ok=True)
    img = cv2.warpAffine(bgr, R, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) if rot else bgr
    p = os.path.join(out_dir, stem + ".png")
    open(p, "wb").write(cv2.imencode(".png", img)[1].tobytes())
    js = os.path.join(out_dir, stem + ".json")
    sys.argv = ["main.py", p, "--no-debug", "--output-dir", out_dir, "--save-labels", js]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            MAIN.run_page(MAIN.parse_args(), p, 0, out_dir)
    except SystemExit:
        return dict(stem=stem, angle=round(a, 3), rotated=rot, rejected=True)
    import csv
    heads = [(float(r["x"]), float(r["y"]), r["pitch"], r["eff"]) for r in csv.DictReader(open(os.path.join(D, stem + ".tsv"), encoding="utf-8"), delimiter="\t")]
    P = R @ np.array([[h[0], h[1], 1.0] for h in heads]).T
    heads = [(float(x), float(y)) + tuple(h[2:]) for (x, y), h in zip(P.T, heads)]
    doc = json.load(open(js, encoding="utf-8"))
    sp = float(np.median([s["spacing"] for s in doc["staves"]]))
    c, _b = S._score(doc, heads, sp)
    return dict(stem=stem, angle=round(a, 3), rotated=rot, rejected=False, staves=len(doc["staves"]),
                key=f"{doc['music']['key_symbol']}{doc['music']['key_count']}", counts=dict(c))


def main():
    import check_accidental_fix as C
    from concurrent.futures import ProcessPoolExecutor
    W = int(os.environ.get("MEASURE_WORKERS", "2"))
    with ProcessPoolExecutor(W) as ex:
        clean = list(ex.map(_clean, C.PAGES))
    print("① 깨끗한 쪽 20: 돌림", sum(r["rotate"] for r in clean), "· 각 최대 |°|", max(abs(r["angle"]) for r in clean), "· 밀림 최대 px", max(r["drift_px"] for r in clean))
    for r in clean:
        if r["rotate"]:
            print("   돌림", r)
    sc = json.load(open(os.path.join(ROOT, "debug", "inputs_score", "degraded.json"), encoding="utf-8"))["rows"]
    rej = [r["stem"] for r in sc if r["mode"] == "normal" and r["rejected"]]
    with ProcessPoolExecutor(W) as ex:
        deg = list(ex.map(_deg, rej))
    json.dump(dict(clean=clean, degraded=deg), open(os.path.join(ROOT, "debug", "small_deskew.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t = Counter()
    for r in deg:
        if r["rejected"]:
            print(f"   {r['stem']:14s} 각 {r['angle']:6.2f}° · 거부(회복 못 함)")
            continue
        c = r["counts"]; t.update(c); n = c["정답"]
        print(f"   {r['stem']:14s} 각 {r['angle']:6.2f}° · 보표 {r['staves']} · 조표 {r['key']} · 누락 {c.get('누락', 0) / n * 100:.1f}% · 음고 {c.get('음고 틀림', 0)} · 표기 {c.get('표기 틀림', 0)} · 유령 {c.get('유령', 0)} · 확실 {c.get('확실 맞음', 0)}/{c.get('확실', 0)}")
    print(f"② 거부 9장 중 회복 {sum(not r['rejected'] for r in deg)}", (f"· 회복분 합 누락 {t['누락'] / t['정답'] * 100:.1f}% · 확실 정밀도 {t['확실 맞음'] / max(1, t['확실']) * 100:.1f}%" if t['정답'] else ""))


if __name__ == "__main__":
    main()
