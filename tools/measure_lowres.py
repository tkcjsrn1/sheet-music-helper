# -*- coding: utf-8 -*-
"""저해상도 경고 기준 유도 — 측정 전용(판정 무변경).

개발 Verovio 20쪽 · 보류(holdout) 12쪽 300dpi PNG를 250 · 200 · 175 · 150dpi 상당으로 LANCZOS 축소해
제품 main.py(명령줄 그대로, 한 쪽씩)로 돌리고, 정답 좌표 · 보표를 같은 비율로 바꿔 `measure_verovio.evaluate_page`로 채점한다
(Codex 캡처 측정 `score-captures.py`와 같은 방식). **기준값은 개발 세트로만 고르고 holdout은 채점만 한다**(DECISIONS §3 · 원칙 9).

    python tools/measure_lowres.py run [dev|holdout ...]   # 라벨 JSON → $AKBO_LOWRES_OUT/<세트>/<dpi>/<쪽>.json (있으면 건너뜀)
    python tools/measure_lowres.py score                   # 표 + 라벨별 행 → $AKBO_LOWRES_OUT/score.json
"""
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
DATA = os.environ.get("AKBO_DATA_ROOT", r"C:\Users\user\Desktop\악보헬퍼")       # 정답(debug/vrv*/truth)이 있는 곳
OUT = os.environ.get("AKBO_LOWRES_OUT", r"F:\akbo-data\tmp\lowres")
DPIS = (300, 250, 200, 175, 150)
SETS = {"dev": (os.path.join(ROOT, "test_scores", "verovio"), os.path.join(DATA, "debug", "vrv", "truth")),
        "holdout": (os.path.join(ROOT, "test_scores", "verovio_holdout"), os.path.join(DATA, "debug", "vrv_holdout", "truth"))}


def stems(name):
    src, tru = SETS[name]
    return sorted(f[:-5] for f in os.listdir(tru) if f.endswith(".json") and os.path.exists(os.path.join(src, f[:-5] + ".png")))


def image_for(name, stem, dpi):
    src = os.path.join(SETS[name][0], stem + ".png")
    if dpi == 300:
        return src
    out = os.path.join(OUT, name, str(dpi), "input", stem + ".png")
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with Image.open(src) as im:
            im.convert("RGB").resize(tuple(round(a * dpi / 300) for a in im.size), Image.Resampling.LANCZOS).save(out, dpi=(dpi, dpi))
    return out


def run(names):
    for name in names or SETS:
        for dpi in DPIS:
            for stem in stems(name):
                js = os.path.join(OUT, name, str(dpi), stem + ".json")
                if os.path.exists(js) or os.path.exists(js + ".rejected"):
                    continue
                img = image_for(name, stem, dpi)
                tmp = os.path.join(OUT, name, str(dpi), "_png")
                r = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), img, "--page", "0", "--no-debug",
                                    "--output-dir", tmp, "--save-labels", js], cwd=ROOT, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
                if not os.path.exists(js):        # 1단계 거부 등 — 결과 없음으로 남긴다
                    with open(js + ".rejected", "w", encoding="utf-8") as f:
                        f.write((r.stdout + r.stderr)[-2000:])
                print(name, dpi, stem, "ok" if os.path.exists(js) else "거부", flush=True)


def scaled_truth(t, s):
    t = json.loads(json.dumps(t))
    for n in t["notes"]:
        n["x"] *= s
        n["y"] *= s
    for st in t["staves"]:
        st["line_ys"] = [y * s for y in st["line_ys"]]
    for b in t["boxes"]:
        b["box"] = [v * s for v in b["box"]]
    return t


def score():
    import measure_verovio as V
    rows, table = [], {}
    for name in SETS:
        for dpi in DPIS:
            c = Counter()
            for stem in stems(name):
                js = os.path.join(OUT, name, str(dpi), stem + ".json")
                if not os.path.exists(js):
                    c["거부 쪽"] += 1
                    continue
                t = scaled_truth(json.load(open(os.path.join(SETS[name][1], stem + ".json"), encoding="utf-8")), dpi / 300)
                doc = json.load(open(js, encoding="utf-8"))
                e = V.evaluate_page(stem, doc, t)
                sp_of = {s["id"]: s["spacing"] for s in doc["staves"]}
                for r in e["rows"]:
                    kind = "덧줄" if r["ledger"] else ("빈 머리" if r["hollow"] else "꽉 찬 머리")
                    miss = r["status"] == "누락"
                    c["정답"] += 1
                    c["누락"] += miss
                    c[f"정답 {kind}"] += 1
                    c[f"누락 {kind}"] += miss
                    if r.get("label"):
                        lab = r["label"]
                        ok = r["status"] == "맞음"
                        rows.append(dict(set=name, dpi=dpi, stem=stem, sp=sp_of.get(lab["staff"]), conf=lab["conf"], ok=ok))
                        c["확실"] += lab["conf"] == "certain"
                        c["확실 맞음"] += lab["conf"] == "certain" and ok
                for g in e["ghosts"]:
                    rows.append(dict(set=name, dpi=dpi, stem=stem, sp=None, conf=g["conf"], ok=False))
                    c["유령"] += 1
                    c["확실"] += g["conf"] == "certain"
                c["쪽 간격 합"] += e["sp"]
                c["쪽"] += 1
            table[f"{name}/{dpi}"] = dict(c)
    # 유령은 라벨 보표를 모르므로 그 쪽의 중앙 간격으로
    page_sp = defaultdict(list)
    for r in rows:
        if r["sp"] is not None:
            page_sp[(r["set"], r["dpi"], r["stem"])].append(r["sp"])
    for r in rows:
        if r["sp"] is None:
            v = page_sp.get((r["set"], r["dpi"], r["stem"]))
            r["sp"] = float(np.median(v)) if v else None
    with open(os.path.join(OUT, "score.json"), "w", encoding="utf-8") as f:
        json.dump(dict(table=table, rows=rows), f, ensure_ascii=False)

    def pct(c, a, b):
        return f"{100 * c.get(a, 0) / max(1, c.get(b, 0)):.1f}%"
    print("| 세트 | dpi | 쪽(거부) | 오선 간격 중앙(px) | 확실 정답률 | 누락 | 누락: 꽉 찬 · 빈 · 덧줄 | 유령 |")
    print("|---|---:|---:|---:|---:|---:|---|---:|")
    for k, c in table.items():
        name, dpi = k.split("/")
        print(f"| {name} | {dpi} | {c.get('쪽', 0)}({c.get('거부 쪽', 0)}) | {c.get('쪽 간격 합', 0) / max(1, c.get('쪽', 0)):.1f} | "
              f"{pct(c, '확실 맞음', '확실')} ({c.get('확실 맞음', 0)}/{c.get('확실', 0)}) | {pct(c, '누락', '정답')} | "
              f"{pct(c, '누락 꽉 찬 머리', '정답 꽉 찬 머리')} · {pct(c, '누락 빈 머리', '정답 빈 머리')} · {pct(c, '누락 덧줄', '정답 덧줄')} | "
              f"{c.get('유령', 0)} |")
    # 보표 간격 구간별 확실 정답률과 「간격 < T면 확실 → 주의」 얻음 · 잃음(세트별)
    for name in SETS:
        cert = [r for r in rows if r["set"] == name and r["conf"] == "certain" and r["sp"] is not None]
        print(f"\n[{name}] 보표 간격 구간별 확실 정답률")
        for lo in range(6, 22):
            b = [r for r in cert if lo <= r["sp"] < lo + 1]
            if b:
                good = sum(r["ok"] for r in b)
                print(f"  {lo:2d} ~ {lo + 1:2d}px  {good}/{len(b)} = {100 * good / len(b):.1f}%")
        print(f"[{name}] 「보표 간격 < T → 확실을 주의로」 얻음(틀린 확실 내림) · 잃음(맞는 확실 내림)")
        for T in range(9, 16):
            low = [r for r in cert if r["sp"] < T]
            print(f"  T={T:2d}px  얻음 {sum(not r['ok'] for r in low)} · 잃음 {sum(r['ok'] for r in low)}")
        # 쪽 경고는 쪽별 보표 간격 중앙값으로 판단한다(#584 gui와 같은 기준)
        med = {k: float(np.median(v)) for k, v in page_sp.items() if k[0] == name}
        print(f"[{name}] 쪽 중앙 간격 < T인 쪽 수(dpi별) · 그 쪽들의 확실 정답률")
        for T in (10, 10.5, 11, 11.5, 12):
            warn = {k for k, m in med.items() if m < T}
            w = [r for r in cert if (r["set"], r["dpi"], r["stem"]) in warn]
            print(f"  T={T:4}px  " + " · ".join(f"{d}:{sum(k[1] == d for k in warn)}" for d in DPIS) +
                  f"  확실 {sum(r['ok'] for r in w)}/{len(w)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"
    if cmd == "run":
        run(sys.argv[2:])
    else:
        score()
