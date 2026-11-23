# -*- coding: utf-8 -*-
"""판단 3 — 사본 시뮬레이션: ① 덧줄 구역 검색 띠를 덧줄 사다리 끝까지 ② 「같은 높이 바로 옆 중복」에서 빈 + 꽉 찬 머리 쌍은 둘 다 남김. 제품 코드 무변경.

① ledger  `notehead_detect._band_margins` 사본 — 위/아래 한계를 고정 LEDGER_MARGIN_SP(5.5sp) 대신 「오선 밖으로 1sp 간격마다 덧줄(그 행 가로 잉크 런 ≥ 1.2sp,
           오선 제거 영상)이 이어지는 마지막 줄 + 1sp」로. 이웃 보표 기본 범위를 침범하지 않는 제한(기존 그대로)은 유지.
② pair    `_detect_noteheads_in_band`가 아니라 `detect_noteheads` 소스의 중복 조건에 `and a.filled == b.filled` 한 줄(빈 + 꽉 찬 쌍은 두 성부 같은 음).
both      ① + ②.
라벨 단위(정답 대조): 되찾음 = 새로 생긴 라벨이 정답 머리와 짝, 새 유령 = 새로 생긴 라벨이 짝 없음, 오삭제 = 사라진 라벨이 정답 머리와 짝이었고 그 머리에 다른 라벨이 없음.
Aoharu는 정답 골든(라벨 그대로가 정답) — 바뀐 라벨 수만 센다.

    python tools/measure_sim_ledger_pair.py run <base|ledger|pair|both|impl>     # impl = 가로채기 없이 지금 제품(구현 뒤 대조용)
    python tools/measure_sim_ledger_pair.py judge
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
OUT = os.path.join(ROOT, "debug", "sim_lp")
CUR = {}


def install(variant):
    import main as MAIN
    import modules.notehead_detect as ND
    if CUR.get("installed"):
        return MAIN          # 프로세스당 한 번 — 바꿔 끼운 함수의 소스를 다시 읽지 않게
    CUR["installed"] = True
    if variant == "hdr":             # 박자표 없는 줄 헤더 끝 = 조표 끝 + 0.5sp(`measure_header_timesig.py`)
        import measure_header_timesig as HT
        HT.MARGIN_SP = 0.5
        HT.install()
        CUR["calls"] = 1
    if variant == "nograce":         # 꾸밈음 표시(§1-24)만 끈 지금 제품 — 그 구현의 비교 기준
        import modules.verify as VF
        VF.grace_size_suspects = lambda result, notes: []
        CUR["calls"] = 1
    if variant in ("pair", "both"):
        src = inspect.getsource(ND.detect_noteheads)
        key = "                    and abs(b.y - a.y) <= sp * 0.35):"
        assert src.count(key) == 1
        src = src.replace(key, "                    and abs(b.y - a.y) <= sp * 0.35\n                    and a.filled == b.filled):")
        exec(compile(src, ND.__file__, "exec"), ND.__dict__)
        MAIN.detect_noteheads = ND.detect_noteheads
    if variant in ("ledger", "both"):
        orig_bm = ND._band_margins

        def ladder(staff, direction):
            ns = CUR["ns"]
            sp = staff.spacing
            H, W = ns.shape
            k = 0
            while True:
                y = int(round((staff.top - (k + 1) * sp) if direction < 0 else (staff.bottom + (k + 1) * sp)))
                if not (0 <= y < H):
                    break
                rows = ns[max(0, y - 1):y + 2, :]
                runs = 0
                for r in rows:
                    d = np.diff(np.concatenate(([0], r.astype(np.int8), [0])))
                    s, e = np.where(d == 1)[0], np.where(d == -1)[0]
                    if len(s) and (e - s).max() >= 1.2 * sp:
                        runs = 1
                        break
                if not runs:
                    break
                k += 1
            return (k + 1) * sp

        def bm(staff, staves):
            up, down = orig_bm(staff, staves)
            if "ns" not in CUR:
                return up, down      # 오선 제거(`remove_staff_lines`)가 부르는 경우 — 원래대로
            sp = staff.spacing
            prev = max((s for s in staves if s.bottom < staff.top), key=lambda s: s.bottom, default=None)
            nxt = min((s for s in staves if s.top > staff.bottom), key=lambda s: s.top, default=None)
            lu, ld = ladder(staff, -1), ladder(staff, 1)
            cap_u = float("inf") if prev is None else max(sp * ND.BASE_MARGIN_SP, staff.top - (prev.bottom + prev.spacing * ND.BASE_MARGIN_SP))
            cap_d = float("inf") if nxt is None else max(sp * ND.BASE_MARGIN_SP, (nxt.top - nxt.spacing * ND.BASE_MARGIN_SP) - staff.bottom)
            return max(up, min(lu, cap_u)), max(down, min(ld, cap_d))
        ND._band_margins = bm
        orig_det = ND.detect_noteheads

        def det(result, *a, **kw):
            ns = ND.remove_staff_lines(result.binary, result.staves) > 0
            CUR["ns"] = ns
            CUR["calls"] = CUR.get("calls", 0) + 1
            try:
                return orig_det(result, *a, **kw)
            finally:
                CUR.pop("ns", None)
        ND.detect_noteheads = MAIN.detect_noteheads = det
    return MAIN


def pages():
    import check_accidental_fix as C
    import measure_a17_ghost6 as G
    P = [("pdf" if p.endswith(".pdf") else "aoharu", n, p, pg) for n, p, pg in C.PAGES]
    P += [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    P += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    return P


def _one(job):
    variant, (st, name, path, pg) = job
    MAIN = install(variant)
    import tempfile
    import shutil
    import io
    import contextlib
    js = os.path.join(OUT, variant, name + ".json")
    if os.path.exists(js):
        return 1
    os.makedirs(os.path.dirname(js), exist_ok=True)
    tmp = os.path.join(tempfile.gettempdir(), "sim_lp", variant, name)
    os.makedirs(tmp, exist_ok=True)
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js]
    with contextlib.redirect_stdout(io.StringIO()):
        MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    return CUR.get("calls", 1)


def run(variant):
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        res = list(ex.map(_one, [(variant, p) for p in pages()]))
    print(variant, "쪽", len(res), "· 가로채기 호출 0인 쪽", sum(c == 0 for c in res))


def _truth(st, name, path, pg):
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        return [(n["x"], n["y"]) for n in t["notes"]], 18.0
    from measure_normalize_sp import truth_at
    from modules.preprocess import preprocess
    hs = truth_at(path, pg, 1.0)[0]
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    return [(h["cx"], h["cy"]) for h in hs], float(np.median([s.spacing for s in res.staves]))


def _judge(job):
    st, name, path, pg = job
    base = json.load(open(os.path.join(OUT, "base", name + ".json"), encoding="utf-8"))["labels"]
    out = {}
    heads, sp = (None, None) if st == "aoharu" else _truth(st, name, path, pg)
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"])
    vt = None
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        vt = [(n["x"], n["y"], n["note_name"] + n["octave"]) for n in t["notes"]]
    for v in ("ledger", "pair", "both", "impl"):
        p = os.path.join(OUT, v, name + ".json")
        if not os.path.exists(p):
            continue
        L = json.load(open(p, encoding="utf-8"))["labels"]
        A, B = {key(l): l for l in base}, {key(l): l for l in L}
        new, gone = [B[k] for k in B.keys() - A.keys()], [A[k] for k in A.keys() - B.keys()]
        c = Counter()
        if heads is None:
            c["바뀐 라벨(골든)"] = len(new) + len(gone)
        else:
            near = lambda l, h: abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp
            for l in new:
                h = [q for q in heads if near(l, q)]
                if not h:
                    c["새 유령"] += 1
                elif any(near(m, h[0]) for m in base):
                    c["새 라벨 · 이미 라벨 있던 머리"] += 1
                else:
                    c["되찾음"] += 1
            for l in gone:
                h = [q for q in heads if near(l, q)]
                if not h:
                    c["유령 사라짐"] += 1
                elif any(near(m, h[0]) for m in L):
                    c["사라짐 · 같은 머리 다른 라벨 남음"] += 1
                    if vt is not None:      # 자리 바뀜 — 같은 머리의 새 라벨과 음고 정오 비교
                        tp = [q[2] for q in vt if near(l, q)]
                        nw = [m for m in new if near(m, h[0])]
                        if tp and nw:
                            a_ok, b_ok = l["pitch"] == tp[0], nw[0]["pitch"] == tp[0]
                            c["자리 바뀜 " + ("맞음→맞음" if a_ok and b_ok else "맞음→틀림" if a_ok else "틀림→맞음" if b_ok else "틀림→틀림")] += 1
                else:
                    c["오삭제"] += 1
        out[v] = dict(c)
    return st, name, out


def judge():
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        res = list(ex.map(_judge, pages()))
    json.dump(res, open(os.path.join(OUT, "judge.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for v in ("ledger", "pair", "both", "impl"):
        print(v)
        for st in ("pdf", "aoharu", "unseen", "verovio"):
            c = Counter()
            for s, _n, o in res:
                if s == st:
                    c.update(o.get(v, {}))
            print(f"  {st:8s}", dict(c))
        bad = [(s, n, o[v]["오삭제"]) for s, n, o in res if o.get(v, {}).get("오삭제")]
        if bad:
            print("  오삭제 쪽", bad)


if __name__ == "__main__":
    run(sys.argv[2]) if sys.argv[1] == "run" else judge()
