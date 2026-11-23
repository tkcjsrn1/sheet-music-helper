# -*- coding: utf-8 -*-
"""실사용 대용 세트 채점 (2026-10-13 야간 큐 2(c) · 7) — 채점 전용, 문턱 유도에 쓰지 않는다.

degraded: `inputs/degraded/`(make_degraded.py) 24장을 일반 모드 · 사진 모드(`--photo`)로 각각 `main.run_page` → 정답 TSV와 1:1 짝
  (가로 0.7 · 세로 0.5sp) → 누락 · 음고 틀림 · 표기 틀림(임시표 접미) · 유령 · 「확실」 정밀도. 단계 기록: 거부(SystemExit) · 찾은 보표 수(원본 대비) ·
  음자리표 · 조표(원본 쪽 일반 모드 결과 대비).
mutopia: `inputs/mutopia/` PDF 전 쪽 일반 모드 → 정답 = PDF 머리 글리프 위치(`measure_normalize_sp.truth_at`) — 음고 정답은 없어 누락 · 유령만.

    python tools/score_inputs.py degraded     # debug/inputs_score/degraded.json + 표
    python tools/score_inputs.py mutopia      # debug/inputs_score/mutopia.json + 표
"""
import contextlib
import csv
import io
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "inputs_score")
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
NORM = {"#": "#", "b": "b", "natural": "", "": "", None: "", "flatflat": "b", "doublesharp": "#"}


def _run(path, pg, mode, js):
    """run_page — (거부 사유 또는 None, 라벨 문서). RESCORE=1이면 이미 있는 라벨 JSON을 다시 쓴다(없으면 거부로 본 것)."""
    if os.environ.get("RESCORE") == "1":
        return (None, json.load(open(js, encoding="utf-8"))) if os.path.exists(js) else ("(재채점: 이전 실행에서 거부)", None)
    import main as MAIN
    tmp = os.path.join(OUT, "_png", mode, os.path.basename(js)[:-5])
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(os.path.dirname(js), exist_ok=True)
    argv = ["main.py", path, "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js] + (["--photo"] if mode == "photo" else [])
    sys.argv = argv
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            MAIN.run_page(MAIN.parse_args(), path, pg, tmp)
    except SystemExit:
        lines = [l for l in buf.getvalue().splitlines() if "오류" in l or "다시" in l or "거부" in l]
        return (lines[-1] if lines else "SystemExit"), None
    return None, json.load(open(js, encoding="utf-8"))


def _score(doc, heads, sp):
    import measure_omission_rate as M
    L = doc["labels"]
    pairs, _ut, used_l = M.match([dict(cx=h[0], cy=h[1]) for h in heads], L, sp)
    c = Counter(정답=len(heads), 라벨=len(L))
    cert_ok = cert = 0
    bad = []
    got = dict(pairs)
    for i, h in enumerate(heads):
        if i not in got:
            c["누락"] += 1
            continue
        l = L[got[i]]
        ok = True
        if len(h) > 2 and h[2]:
            if l["pitch"] != h[2]:
                c["음고 틀림"] += 1; ok = False
            elif ACC(l["text"]) != NORM.get(h[3], h[3]):
                c["표기 틀림"] += 1; ok = False
        if l["confidence"] == "certain":
            cert += 1; cert_ok += ok
            if not ok:
                bad.append(dict(x=l["x"], y=l["y"], text=l["text"], truth=h[2] + (h[3] or ""), kind="음고 · 표기"))
    for j, l in enumerate(L):
        if j not in used_l:
            c["유령"] += 1
            if l["confidence"] == "certain":
                cert += 1
                bad.append(dict(x=l["x"], y=l["y"], text=l["text"], truth="", kind="유령"))
    c["확실"] = cert
    c["확실 맞음"] = cert_ok
    return c, bad


def _deg_job(job):
    stem, mode = job
    D = os.path.join(ROOT, "inputs", "degraded")
    m = next(x for x in json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8")) if x["stem"] == stem)
    heads = [(float(r["x"]), float(r["y"]), r["pitch"], r["eff"]) for r in csv.DictReader(open(os.path.join(D, stem + ".tsv"), encoding="utf-8"), delimiter="\t")]
    rej, doc = _run(os.path.join(D, m["file"]), 0, mode, os.path.join(OUT, "degraded", mode, stem + ".json"))
    row = dict(stem=stem, mode=mode, variant=m["variant"], page=stem.split("__")[0], rejected=rej)
    if doc is None:
        row["counts"] = dict(정답=len(heads), 누락=len(heads))
        return row
    scale = 0.6 if m["variant"] == "lowres" else 1.0
    sp = float(np.median([s["spacing"] for s in doc["staves"]])) if doc["staves"] else m["sp_source"] * scale
    frame = "열화 좌표"
    if mode == "photo" and doc["labels"]:
        # 사진 모드 라벨은 보정 · 잘라낸 영상 좌표다. 보정이 열화를 얼마나 되돌렸는지는 경우마다 달라(회전은 되돌림 · 축소는 그대로 등)
        # 정답 기준 두 가지 — 열화 좌표 그대로 · 열화 행렬의 역으로 되돌린 원본 좌표 — 에 각각 `measure_photo_truth.align`(평행이동 격자 →
        # 부분 아핀 ICP)으로 맞추고 짝(0.5sp)이 많은 쪽을 쓴다. 쓴 기준은 frame에 남긴다(채점기 쪽 선택이라 인식 결과는 바꾸지 않는다)
        from measure_photo_truth import align
        Hi = np.linalg.inv(np.array(m["H"]))
        P = Hi @ np.array([[h[0], h[1], 1.0] for h in heads]).T
        unwarped = [(float(x), float(y)) + tuple(h[2:]) for (x, y), h in zip((P[:2] / P[2]).T, heads)]
        best = None
        for nm, ref in (("열화 좌표", heads), ("원본 좌표", unwarped)):
            Q = align([(l["x"], l["y"]) for l in doc["labels"]], [(h[0], h[1]) for h in ref], sp)
            d = ((Q[:, None, :] - np.float32([(h[0], h[1]) for h in ref])[None]) ** 2).sum(-1)
            k = int((d.min(axis=1) <= (0.5 * sp) ** 2).sum())
            if best is None or k > best[0]:
                best = (k, nm, ref, Q)
        _k, frame, heads, Q = best
        doc = dict(doc, labels=[dict(l, x=float(q[0]), y=float(q[1])) for l, q in zip(doc["labels"], Q)])
    c, bad = _score(doc, heads, sp)
    row.update(counts=dict(c), certain_bad=bad, frame=frame, staves=len(doc["staves"]), clefs=[s["clef"] for s in doc["staves"]],
               key=f"{doc['music']['key_symbol']}{doc['music']['key_count']}", sp=round(sp, 2))
    return row


def degraded():
    D = os.path.join(ROOT, "inputs", "degraded")
    stems = [m["stem"] for m in json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))]
    jobs = [(s, mode) for mode in ("normal", "photo") for s in stems]
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_deg_job, jobs))
    # 기준: 원본 쪽 일반 모드(열화 없음) 보표 수 · 음자리표 · 조표
    import check_accidental_fix as C
    P = {n: (p, pg) for n, p, pg in C.PAGES}
    base = {}
    for page in sorted({r["page"] for r in R}):
        _rej, doc = _run(os.path.join(ROOT, P[page][0]), P[page][1], "normal", os.path.join(OUT, "degraded", "source", page + ".json"))
        base[page] = dict(staves=len(doc["staves"]), clefs=[s["clef"] for s in doc["staves"]], key=f"{doc['music']['key_symbol']}{doc['music']['key_count']}")
    for r in R:
        b = base[r["page"]]
        r["stage"] = ("거부" if r["rejected"] else "보표 수 다름" if r.get("staves") != b["staves"] else
                      "음자리표 다름" if r.get("clefs") != b["clefs"] else "조표 다름" if r.get("key") != b["key"] else "구조 같음")
    json.dump(dict(rows=R, base=base), open(os.path.join(OUT, "degraded.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for mode in ("normal", "photo"):
        print(f"== {mode}")
        tot = Counter()
        for r in [r for r in R if r["mode"] == mode]:
            c = r["counts"]
            tot.update(c)
            n = max(1, c.get("정답", 0))
            print(f"  {r['stem']:18s} {r['stage']:8s} 보표 {r.get('staves', '-')} · 누락 {c.get('누락', 0) / n * 100:5.1f}% · 음고 {c.get('음고 틀림', 0)} · 표기 {c.get('표기 틀림', 0)}"
                  f" · 유령 {c.get('유령', 0)} · 확실 {c.get('확실 맞음', 0)}/{c.get('확실', 0)}" + (f" · {r.get('frame')}" if mode == "photo" else "") + (f" · 거부: {r['rejected'][:40]}" if r["rejected"] else ""))
        n = max(1, tot["정답"])
        print(f"  합계: 정답 {tot['정답']} · 누락 {tot['누락']} ({tot['누락'] / n * 100:.1f}%) · 음고 {tot['음고 틀림']} · 표기 {tot['표기 틀림']} · 유령 {tot['유령']}"
              f" · 확실 정밀도 {tot['확실 맞음']}/{tot['확실']} ({tot['확실 맞음'] / max(1, tot['확실']) * 100:.1f}%) · 단계 {dict(Counter(r['stage'] for r in R if r['mode'] == mode))}")


def _mut_job(job):
    path, pg = job
    from measure_normalize_sp import truth_at
    name = os.path.splitext(os.path.basename(path))[0]
    heads = [(h["cx"], h["cy"]) for h in truth_at(os.path.relpath(path, ROOT), pg, 1.0)[0]]
    rej, doc = _run(path, pg, "normal", os.path.join(OUT, "mutopia", f"{name}_p{pg + 1}.json"))
    row = dict(stem=f"{name}_p{pg + 1}", rejected=rej)
    if doc is None:
        row["counts"] = dict(정답=len(heads), 누락=len(heads))
        return row
    sp = float(np.median([s["spacing"] for s in doc["staves"]]))
    c, bad = _score(doc, heads, sp)
    row.update(counts=dict(c), certain_ghosts=[b for b in bad if b["kind"] == "유령"], staves=len(doc["staves"]),
               key=f"{doc['music']['key_symbol']}{doc['music']['key_count']}")
    return row


def mutopia():
    import fitz
    D = os.path.join(ROOT, "inputs", "mutopia")
    jobs = [(os.path.join(D, f), p) for f in sorted(os.listdir(D)) if f.endswith(".pdf") for p in range(len(fitz.open(os.path.join(D, f))))]
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_mut_job, jobs))
    json.dump(R, open(os.path.join(OUT, "mutopia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = Counter()
    for r in R:
        c = r["counts"]
        tot.update(c)
        n = max(1, c.get("정답", 0))
        print(f"  {r['stem']:30s} 보표 {r.get('staves', '-')} · 조표 {r.get('key', '-')} · 정답 {c.get('정답')} · 누락 {c.get('누락', 0)} ({c.get('누락', 0) / n * 100:.1f}%)"
              f" · 유령 {c.get('유령', 0)} · 확실 유령 {len(r.get('certain_ghosts', []))}" + (f" · 거부 {r['rejected']}" if r["rejected"] else ""))
    n = max(1, tot["정답"])
    print(f"  합계: 정답 {tot['정답']} · 누락 {tot['누락']} ({tot['누락'] / n * 100:.1f}%) · 유령 {tot['유령']} ({tot['유령'] / n * 100:.1f}%)")


if __name__ == "__main__":
    {"degraded": degraded, "mutopia": mutopia}[sys.argv[1]]()
