# -*- coding: utf-8 -*-
"""판단 1 — `remove_accidental_ghosts`가 **전파된(실효) 임시표**를 기준으로 왼쪽 빈 후보를 지우는 구조. 제품 코드 무변경.

규칙: 임시표가 있는 음표 j의 왼쪽 0.5~1.6sp · 같은 높이(±ACCIDENTAL_GHOST_Y_SP) 빈 후보 i = 그 임시표 글리프 → 지움.
j의 임시표가 **인쇄된 것(원시)**이 아니라 같은 마디 앞 음에서 **전파된 것**이면 j 왼쪽에는 글리프가 없다 — 그래도 지운다.

측정 사본(소스 무변경, 모듈 이름공간에서 바꿔 끼움 — main이 이름으로 가져간 것까지, 측정 함정 B-4):
  `annotate_accidentals`는 원시 임시표 목록을 함께 남기고(소스 한 줄), `remove_accidental_ghosts`를 감싼다.
  record  제품과 똑같이 동작 + 지운 후보마다 원인 j가 원시인지 전파로만인지 기록
  raw     수정안 — 지울지 판단에만 원시 임시표를 쓴다(남는 음표의 임시표는 실효값 그대로)
라벨 → debug/propdrop/<모드>/<쪽>.json, 지운 후보 → debug/propdrop/<모드>_drops.json. 호출 수를 출력(0이면 측정 무효).

    python tools/measure_propagated_drop.py run record
    python tools/measure_propagated_drop.py run raw
    python tools/measure_propagated_drop.py judge          # 지운 후보 판정 + record ↔ raw 라벨 비교
    PROPDROP_PHOTO=1 python tools/measure_propagated_drop.py run raw     # 사진 51장(--photo) → debug/propdrop/raw_photo — #188 브랜치에서 돌려 사진 재판정
"""
import inspect
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "propdrop")
STATE = {"mode": "record", "drops": [], "calls": 0, "page": ""}


def install(mode):
    import main as MAIN
    import modules.accidental_detect as AD
    STATE["mode"] = mode
    if getattr(AD, "RAW_HOOK", None) is None:
        src = inspect.getsource(AD.annotate_accidentals)
        key = "    # 2) 마디 내 지속 규칙 적용\n"
        assert src.count(key) == 1
        src = src.replace(key, "    RAW_HOOK[id(pitched_notes)] = list(raw)\n" + key)
        AD.RAW_HOOK = {}
        exec(compile(src, AD.__file__, "exec"), AD.__dict__)
        AD.ORIG_RAG = AD.remove_accidental_ghosts
    orig = AD.ORIG_RAG

    def rag(pitched_notes, accidentals, staves, filled=None, flagged=None, result=None):
        STATE["calls"] += 1
        raw = AD.RAW_HOOK.get(id(pitched_notes))
        if raw is None or len(raw) != len(pitched_notes):
            raise RuntimeError("원시 임시표 기록 없음 — 측정 무효")
        sp_of = {s.index: s.spacing for s in staves}
        trig = {}
        for j, nj in enumerate(pitched_notes):
            if not accidentals[j]:
                continue
            sp = sp_of.get(nj.staff_index, 12.0)
            for i, ni in enumerate(pitched_notes):
                if (i != j and ni.staff_index == nj.staff_index and sp * 0.5 <= nj.x - ni.x <= sp * 1.6
                        and abs(ni.y - nj.y) <= sp * AD.ACCIDENTAL_GHOST_Y_SP):
                    trig.setdefault(i, []).append((bool(raw[j]), (nj.x - ni.x) / sp, (nj.y - ni.y) / sp, raw[j] or accidentals[j]))
        use = accidentals if STATE["mode"] == "record" else [a if raw[k] else "" for k, a in enumerate(accidentals)]
        # raw 모드: 판단에는 원시가 있는 음표의 임시표만(값은 실효값 — 원시가 있으면 실효 = 원시)
        kept, _accs = orig(pitched_notes, use, staves, filled=filled, flagged=flagged, result=result)
        eff_of = {id(n): a for n, a in zip(pitched_notes, accidentals)}
        kept_ids = {id(n) for n in kept}
        for i, n in enumerate(pitched_notes):
            if id(n) not in kept_ids and i in trig:
                t0 = min(trig[i], key=lambda t: abs(t[2]))          # 가장 같은 높이의 원인
                STATE["drops"].append(dict(page=STATE["page"], staff=n.staff_index, x=int(n.x), y=int(n.y),
                                           kind="원시" if any(t[0] for t in trig[i]) else "전파로만", filled=bool(filled[i]) if filled else None,
                                           dx=round(t0[1], 2), dy=round(t0[2], 2), acc=t0[3]))
        return kept, [eff_of[id(n)] for n in kept]
    AD.remove_accidental_ghosts = MAIN.remove_accidental_ghosts = rag
    MAIN.annotate_accidentals = AD.annotate_accidentals      # main이 이름으로 가져간 것도 원시를 남기는 사본으로
    return MAIN


def pages():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    if os.environ.get("PROPDROP_PHOTO"):
        return [("photo", n, p, pg) for n, p, pg in G.photo_pages()]
    P = [("pdf" if p.endswith(".pdf") else "aoharu", n, p, pg) for n, p, pg in C.PAGES]
    P += [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    P += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    return P


def _one(job):
    mode, (st, name, path, pg) = job
    MAIN = install(mode)
    import tempfile
    photo = st == "photo"
    js = os.path.join(OUT, mode + ("_photo" if photo else ""), name + ".json")
    os.makedirs(os.path.dirname(js), exist_ok=True)
    STATE["page"], STATE["drops"], STATE["calls"] = name, [], 0
    tmp = os.path.join(tempfile.gettempdir(), "propdrop", mode, name)       # 같은 PDF의 여러 쪽이 같은 결과 파일 이름으로 동시에 쓰지 않게
    os.makedirs(tmp, exist_ok=True)
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js] + (["--photo"] if photo else [])
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
        except SystemExit:
            pass            # 사진 모드가 거부한 사진
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return STATE["calls"], STATE["drops"]


def run(mode):
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one, [(mode, p) for p in pages()]))
    print("가로채기 호출", sum(c for c, _d in res), "· 쪽", len(res), "· 호출 0인 쪽", sum(c == 0 for c, _d in res))
    tag = mode + ("_photo" if os.environ.get("PROPDROP_PHOTO") else "")
    json.dump([d for _c, ds in res for d in ds], open(os.path.join(OUT, f"{tag}_drops.json"), "w", encoding="utf-8"), ensure_ascii=False)


def _truth(st, name, path, pg):
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"]) for n in t["notes"]], 18.0
    if st == "aoharu":
        return None, None
    from measure_normalize_sp import truth_at
    from modules.preprocess import preprocess
    hs = truth_at(path, pg, 1.0)[0]
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    return [(h["cx"], h["cy"]) for h in hs], float(np.median([s.spacing for s in res.staves]))


def _judge_page(job):
    st, name, path, pg, drops = job
    heads, sp = _truth(st, name, path, pg)
    L = json.load(open(os.path.join(OUT, "record", name + ".json"), encoding="utf-8"))["labels"]
    out = []
    for d in drops:
        if heads is None:
            out.append(dict(d, set=st, verdict="그림 판정(정답 없음)"))
            continue
        h = [q for q in heads if abs(q[0] - d["x"]) <= 0.7 * sp and abs(q[1] - d["y"]) <= 0.5 * sp]
        other = h and any(abs(l["x"] - h[0][0]) <= 0.7 * sp and abs(l["y"] - h[0][1]) <= 0.5 * sp for l in L)
        out.append(dict(d, set=st, verdict="유령" if not h else "진짜 머리 · 다른 라벨 남음" if other else "진짜 머리 — 오삭제"))
    return out


def judge():
    P = {name: (st, name, path, pg) for st, name, path, pg in pages()}
    drops = json.load(open(os.path.join(OUT, "record_drops.json"), encoding="utf-8"))
    by = {}
    for d in drops:
        by.setdefault(d["page"], []).append(d)
    with ProcessPoolExecutor(3) as ex:
        rows = [r for part in ex.map(_judge_page, [P[k] + (v,) for k, v in by.items()]) for r in part]
    json.dump(rows, open(os.path.join(OUT, "record_judged.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for kind in ("원시", "전파로만"):
        v = [r for r in rows if r["kind"] == kind]
        print(f"{kind}: 지움 {len(v)} · " + " · ".join(f"{k} {n}" for k, n in Counter(r["verdict"] for r in v).most_common())
              + " | 세트 " + str(dict(Counter(r["set"] for r in v))))
    for r in rows:
        if r["verdict"].endswith("오삭제"):
            print("  오삭제", r["set"], r["page"], r["staff"], r["x"], r["y"], r["kind"])
    # record ↔ raw 라벨 비교
    c = Counter()
    for name in P:
        a, b = (os.path.join(OUT, m, name + ".json") for m in ("record", "raw"))
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        A = {(l["staff"], l["x"], l["y"]) for l in json.load(open(a, encoding="utf-8"))["labels"]}
        B = {(l["staff"], l["x"], l["y"]) for l in json.load(open(b, encoding="utf-8"))["labels"]}
        c[(P[name][0], "살아남(raw에만)")] += len(B - A)
        c[(P[name][0], "사라짐(record에만)")] += len(A - B)
    print("record → raw 라벨:", {f"{k[0]} {k[1]}": n for k, n in sorted(c.items())})


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        judge()
