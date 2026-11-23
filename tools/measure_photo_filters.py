# -*- coding: utf-8 -*-
"""야간 [8] 사진 51장 — 사진 모드에서 꺼 둔 필터를 하나씩 켜면 안전한가(누락 · 유령 · 표기 · 오삭제). 제품 코드 무변경.

사진 모드에서 꺼져 있고 라벨 수를 바꾸는 것 두 가지(표시만 하는 신호는 누락 · 유령을 안 바꾸므로 뺀다):
  rescue  붙은 화음 구제(두 번째 검출 경로 + 합치기) — main.apply_chord_rescue(enable=…)를 항상 True로
  g3      G3 글리프 칸 유령 제거 — remove_accidental_ghosts 뒤 `_drop_glyph_cell_ghosts`를 사진에서도
라벨 → debug/photo_filters/<변형>/ph_*.json. 판정은 `measure_photo_truth.py`(변형 pf_rescue · pf_g3)와 오삭제 대조.

    python tools/measure_photo_filters.py run <rescue|g3>
    python tools/measure_photo_filters.py gone <rescue|g3>     # 지금 사진 결과(main1006) 대비 사라진 라벨 → 유령 / 오삭제
"""
import io
import contextlib
import json
import os
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "photo_filters")
CUR = {}


def install(variant):
    import main as MAIN
    import modules.accidental_detect as AD
    if CUR.get("installed"):
        return MAIN
    CUR["installed"] = True
    if variant == "rescue":
        orig = MAIN.apply_chord_rescue

        def rescue(*a, **kw):
            CUR["calls"] = CUR.get("calls", 0) + 1
            kw["enable"] = True
            return orig(*a, **kw)
        MAIN.apply_chord_rescue = rescue
    if variant == "g3":
        orig_rag = AD.remove_accidental_ghosts

        def rag(pitched_notes, accidentals, staves, filled=None, flagged=None, result=None):
            kept, accs = orig_rag(pitched_notes, accidentals, staves, filled=filled, flagged=flagged, result=result)
            if result is not None and filled is not None and not AD._refined(result):
                CUR["calls"] = CUR.get("calls", 0) + 1
                kept, accs = AD._drop_glyph_cell_ghosts(result, staves, pitched_notes, filled, kept, accs)
            return kept, accs
        AD.remove_accidental_ghosts = MAIN.remove_accidental_ghosts = rag
    return MAIN


def _one(job):
    variant, (name, path, pg) = job
    MAIN = install(variant)
    js = os.path.join(OUT, variant, name + ".json")
    if os.path.exists(js):
        return 1
    os.makedirs(os.path.dirname(js), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="pf_")
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js, "--photo"]
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
        except SystemExit:
            pass
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return CUR.get("calls", 0)


def run(variant):
    import measure_a17_ghost6 as G
    with ProcessPoolExecutor(2) as ex:
        res = list(ex.map(_one, [(variant, p) for p in G.photo_pages()]))
    print(variant, "사진", len(res), "· 가로채기 호출 합", sum(res))


def gone(variant):
    import measure_photo_truth as T
    A = os.path.join(ROOT, "debug", "a17_cand1_photo_main1006", "base_photo")
    B = os.path.join(OUT, variant)
    truths = {s: T.truth_of(s) for s in T.SOURCES}
    c = Counter()
    for f in sorted(os.listdir(B)):
        if not os.path.exists(os.path.join(A, f)):
            continue
        La = json.load(open(os.path.join(A, f), encoding="utf-8"))["labels"]
        kb = {(l["staff"], l["x"], l["y"]) for l in json.load(open(os.path.join(B, f), encoding="utf-8"))["labels"]}
        lost = [l for l in La if (l["staff"], l["x"], l["y"]) not in kb]
        if not lost:
            continue
        src = next(s for s in T.SOURCES if f.startswith("ph_" + s + "__"))
        heads, sp = truths[src]
        P2 = T.align([(l["x"], l["y"]) for l in La], [(h["x"], h["y"]) for h in heads], sp)
        pos = {id(l): p for l, p in zip(La, P2)}
        for l in lost:
            x, y = pos[id(l)]
            h = [q for q in heads if abs(q["x"] - x) <= 0.7 * sp and abs(q["y"] - y) <= 0.5 * sp]
            other = h and any((m["staff"], m["x"], m["y"]) in kb and abs(pos[id(m)][0] - h[0]["x"]) <= 0.7 * sp and abs(pos[id(m)][1] - h[0]["y"]) <= 0.5 * sp for m in La if m is not l)
            k = "유령" if not h else "다른 라벨 남음" if other else "오삭제"
            c[k] += 1
            if k == "오삭제":
                print("  오삭제", f, l["x"], l["y"], l["text"])
    print(variant, "사라진 라벨:", dict(c))


if __name__ == "__main__":
    {"run": run, "gone": gone}[sys.argv[1]](sys.argv[2])
