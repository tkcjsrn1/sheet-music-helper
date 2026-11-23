# -*- coding: utf-8 -*-
"""보류(holdout) 세트 채점 — 채점만 한다. 이 결과로 문턱을 고르거나 시뮬레이션을 판정하지 않는다(DECISIONS §3 · 원칙 9).

라벨: 지금 제품 `main.run_page`(명령줄과 같은 경로, 측정 함정 A-3b) → debug/vrv_holdout/<이름>/<stem>.json
채점: `measure_verovio.evaluate_page`(Verovio 20쪽 측정과 같은 평가기 · 짝짓기 가로 0.7sp · 세로 0.5sp 1:1).
「확실」 정밀도 = 확신도 certain 라벨 중 맞음(음고 · 표기 모두) / certain 라벨 전체(유령 포함).
비교 기준: 같은 채점기로 개발 세트 Verovio 20쪽(`debug/sim_lp/<이름>` 라벨, 같은 main).

    python tools/score_holdout.py run main1012
    python tools/score_holdout.py score main1012
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
SET = os.path.join(ROOT, "test_scores", "verovio_holdout")
OUT = os.path.join(ROOT, "debug", "vrv_holdout")


def stems():
    return [m["stem"] for m in json.load(open(os.path.join(SET, "manifest.json"), encoding="utf-8"))]


def _one(job):
    variant, stem = job
    import io
    import contextlib
    import shutil
    import main as MAIN
    js = os.path.join(OUT, variant, stem + ".json")
    if os.path.exists(js):
        return stem
    os.makedirs(os.path.dirname(js), exist_ok=True)
    tmp = os.path.join(OUT, "_png", stem)
    os.makedirs(tmp, exist_ok=True)
    src = os.path.join(SET, stem + ".png")
    sys.argv = ["main.py", src, "--page", "0", "--no-debug", "--output-dir", tmp, "--save-labels", js]
    with contextlib.redirect_stdout(io.StringIO()):
        MAIN.run_page(MAIN.parse_args(), src, 0, tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    return stem


def run(variant):
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        print(variant, "완료", len(list(ex.map(_one, [(variant, s) for s in stems()]))), "쪽")


def _score(pairs):
    """pairs: (stem, 라벨 JSON 경로, 정답 JSON 경로). 쪽별 줄과 합계."""
    import measure_verovio as V
    tot = Counter()
    per = []
    for stem, lab, tru in pairs:
        js = json.load(open(lab, encoding="utf-8"))
        e = V.evaluate_page(stem, js, json.load(open(tru, encoding="utf-8")))
        c = Counter(r["status"] for r in e["rows"])
        c["정답"] = len(e["rows"])
        c["유령"] = len(e["ghosts"])
        c["라벨"] = e["labels"]
        cert = [r for r in e["rows"] if r.get("label") and r["label"]["conf"] == "certain"]
        c["확실"] = len(cert) + sum(g["conf"] == "certain" for g in e["ghosts"])
        c["확실 맞음"] = sum(r["status"] == "맞음" for r in cert)
        c["확실 유령"] = sum(g["conf"] == "certain" for g in e["ghosts"])
        tot.update(c)
        per.append((stem, c))
    return per, tot


def line(name, c):
    n = max(1, c["정답"])
    return (f"{name:38s} 정답 {c['정답']:5d} · 누락 {c['누락']:4d} ({c['누락'] / n * 100:4.1f}%) · 음고 {c['음고']:4d} ({c['음고'] / n * 100:4.1f}%)"
            f" · 표기 {c['표기']:4d} ({c['표기'] / n * 100:4.1f}%) · 유령 {c['유령']:4d} ({c['유령'] / n * 100:4.1f}%)"
            f" · 확실 정밀도 {c['확실 맞음']}/{c['확실']} ({c['확실 맞음'] / max(1, c['확실']) * 100:.1f}%) · 확실 유령 {c['확실 유령']}")


def score(variant):
    import measure_verovio as V
    per, tot = _score([(s, os.path.join(OUT, variant, s + ".json"), os.path.join(OUT, "truth", s + ".json")) for s in stems()])
    print("== 보류 세트 (holdout, 채점 전용)")
    for s, c in per:
        print(line(s, c))
    for font in ("bravura", "leipzig"):
        sub = Counter()
        for s, c in per:
            if f"_{font}_" in s:
                sub.update(c)
        print(line(f"  [{font}]", sub))
    print(line("합계 holdout", tot))
    dev = [(s, os.path.join(ROOT, "debug", "sim_lp", variant, s + ".json"), os.path.join(V.OUT, "truth", s + ".json")) for s in V.stems()]
    dev = [d for d in dev if os.path.exists(d[1])]
    _p, dtot = _score(dev)
    print(line(f"비교: 개발 Verovio {len(dev)}쪽", dtot))
    json.dump(dict(holdout=[(s, dict(c)) for s, c in per], holdout_total=dict(tot), dev_total=dict(dtot)),
              open(os.path.join(OUT, f"score_{variant}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    {"run": run, "score": score}[sys.argv[1]](sys.argv[2])
