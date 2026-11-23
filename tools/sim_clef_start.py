# -*- coding: utf-8 -*-
"""A-8 2단계 사본 시뮬레이션 — 음자리표 클러스터 **시작점** 수정. 제품 파일은 안 바꾼다.

> **2단계가 제품에 들어가기 전(`beab320`) 소스 기준 도구다.** 지금 소스에는 치환 위치가 없어 멈춘다 — 결과는 `docs/KEYSIG_CLEF_GAP.md` §9.

1단계 제품(변형 B) 소스를 메모리에서 고쳐 `clef_keysig._analyze_one`만 바꿔 끼운다.

- `start` : 클러스터 폭 조건(≥ 1.4sp)을 **덩어리 안에서 오선 행 밖 잉크가 끊김 없이 이어진 가장 넓은 조각**에도 건다.
            괄호(0.87sp)와 세로줄(0.26sp)이 짧은 빈칸을 사이에 두고 한 덩어리(1.48sp)로 붙어 통과하던 것을 막는다.
            새 상수 없음 — 기존 1.4sp(「음자리표 본체는 1.5sp 이상, 브레이스/바라인 조각은 걸러낸다」)를 조각 단위로 적용
- `nominw`: 빈 틈 규칙의 `xc + 2.2sp` 조건을 뗀다(변형 A 수준)
- `nocap` : 음자리표 끝 상한 `xc + 5sp`를 뗀다 — 상한에 가려진 것이 아닌지 보려고
- `old`   : 1단계 전(빈 틈 규칙 없음)을 흉내 — CLEF_GAP_SP를 무한대로

    python tools/sim_clef_start.py table            # 변형별 골든 · 20쪽 · 178보표 · 뒤집힘 표
    python tools/sim_clef_start.py golden start,nominw,nocap
"""
import io
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import modules  # noqa: E402,F401
import modules.clef_keysig as CK  # noqa: E402

PROD = CK._analyze_one
ACCEPT_OLD = "        if width >= sp * 1.4 and float(ink_cnt[cx:c2].max()) > sp * 0.8:\n"
ACCEPT_NEW = """        _run = seg_w = 0                 # [사본] 오선 행 밖 잉크가 끊김 없이 이어진 가장 넓은 조각
        for _v in off_cnt[cx:c2] > 0:
            _run = _run + 1 if _v else 0
            seg_w = max(seg_w, _run)
        if width >= sp * 1.4 and seg_w >= sp * 1.4 and float(ink_cnt[cx:c2].max()) > sp * 0.8:
"""
MINW = " and c2 - e + 1 >= cx + sp * CLEF_MIN_WIDTH_SP"
CAP_OLD = ", xc + int(sp * 5))"


def load(flags):
    src = io.open(CK.__file__, encoding="utf-8").read()
    if "start" in flags:
        assert src.count(ACCEPT_OLD) == 1
        src = src.replace(ACCEPT_OLD, ACCEPT_NEW)
    if "nominw" in flags:
        assert src.count(MINW) == 1
        src = src.replace(MINW, "")
    if "nocap" in flags:
        assert src.count(CAP_OLD) == 1
        src = src.replace(CAP_OLD, ")")
    m = types.ModuleType("modules._clef_start_sim")
    m.__package__ = "modules"
    exec(compile(src, "clef_keysig_sim.py", "exec"), m.__dict__)
    if "old" in flags:
        m.CLEF_GAP_SP = 1e9
    return m._analyze_one


def use(fn):
    CK._analyze_one = fn


def golden():
    import test_golden_regression as TG
    out = []
    for tag, path in TG.PAGES:
        want = io.open(TG.golden_path(tag), encoding="utf-8").read().splitlines()
        want_ctx = io.open(TG.golden_path(tag, "_context"), encoding="utf-8").read().splitlines()
        lines, metrics, ctx = TG.analyze(path)
        out.append(dict(tag=tag, gone=[l for l in want if l not in set(lines)],
                        new=[l for l in lines if l not in set(want)],
                        ctx=[(a, b) for a, b in zip(want_ctx, ctx) if a != b] + ([("줄 수", "")] if len(want_ctx) != len(ctx) else []),
                        ghosts=metrics["유령 후보"]))
    return out


def label_diff(base, got):
    import check_accidental_fix as C
    tot = dict(사라짐=0, 생김=0, 음고=0, 표기=0, 문맥=0)
    detail = []
    for page in base:
        la, lb = base[page]["labels"], got[page]["labels"]
        used = set()
        for p in la:
            k = next((j for j, q in enumerate(lb) if j not in used
                      and abs(q["x"] - p["x"]) <= C.MATCH and abs(q["y"] - p["y"]) <= C.MATCH), None)
            if k is None:
                tot["사라짐"] += 1; detail.append(f"{page} 사라짐 ({p['x']},{p['y']}) {p['pitch']} {p['text']}")
                continue
            used.add(k)
            if lb[k]["pitch"] != p["pitch"]:
                tot["음고"] += 1; detail.append(f"{page} 음고 ({p['x']},{p['y']}) {p['pitch']}->{lb[k]['pitch']}")
            elif lb[k]["text"] != p["text"]:
                tot["표기"] += 1; detail.append(f"{page} 표기 ({p['x']},{p['y']}) {p['text']}->{lb[k]['text']}")
        for j, q in enumerate(lb):
            if j not in used:
                tot["생김"] += 1; detail.append(f"{page} 생김 ({q['x']},{q['y']}) {q['pitch']} {q['text']}")
        cd = C.rows_diff(base[page]["context"], got[page]["context"])
        tot["문맥"] += len(cd); detail += [f"{page} 문맥 {d}" for d in cd]
    return tot, detail


def classify_all(fns):
    """보표마다 음자리표 끝이 음자리표-조표 틈 안에 있나 — fns: {이름: _analyze_one}. 들여쓴 첫 시스템 제외."""
    import measure_clef_gap as G
    import check_accidental_fix as C
    from modules.preprocess import preprocess
    G.LINE_PAD = 2
    out = {k: [] for k in fns}
    for page, path, pg in C.PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        ctxs = {}
        for k, fn in fns.items():
            use(fn); ctxs[k] = CK.analyze_staves(res)
        use(PROD)
        ref = ctxs[next(iter(fns))]
        kc = next(iter(ref.values())).key_count
        found = [c for c in ref.values() if c.clef_found]
        thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
        bars = sorted(x for c in found for x, _ in c.bars)
        cons, i = [], 0
        while i < len(bars):
            j = i
            while j + 1 < len(bars) and bars[j + 1] - bars[i] <= 3.0:
                j += 1
            if j - i + 1 >= thr:
                cons.append(sum(bars[i:j + 1]) / (j - i + 1))
            i = j + 1
        profs = G.staff_profiles(res)
        for s in res.staves:
            indent = pg == 0 and s.index in (0, 1) and not page.startswith(("aoharu2", "aoharu3"))
            if indent or not kc or not cons or not ref[s.index].clef_found:
                continue
            p = profs[s.index]
            sp = p["sp"]
            cl = G.clef_cluster(p)          # 1단계 전 식의 xc — 틈 위치를 찾는 기준점으로만 쓴다
            xc = cl[0] if cl else 0
            first = [x for x in cons if x > xc + sp * 1.4]
            if not first:
                continue
            empty = p["off"] == 0
            gl = int(first[0])
            while gl > xc and not empty[gl - 1]:
                gl -= 1
            gr = gl
            while gr > xc and empty[gr - 1]:
                gr -= 1
            for k in fns:
                v = ctxs[k][s.index].clef_end
                out[k].append((page, s.index, gr, gl, v,
                               "틈 안" if gr - 1 <= v <= gl else ("음자리표 안" if v < gr - 1 else "조표 넘음")))
    return out


def flips(fn):
    import measure_keysig_resample as M
    tmp = os.path.join(ROOT, "debug", "keysig_resample")
    use(fn)
    res = {}
    for name in M.SCORES:
        _img, base = M._base(name, tmp)
        for deg in M.ANGLES + ("shift",):
            for m in M.METHODS:
                res[(name, deg, m)] = (base["key"], M.header(os.path.join(tmp, f"{name}_{deg}_{m}.png"))["key"])
    use(PROD)
    cnt = {m: sum(1 for (n, d, mm), (b, k) in res.items() if mm == m and d != "shift" and k != b) for m in M.METHODS}
    left = [(n, d, m, k) for (n, d, m), (b, k) in res.items() if k != b]
    return cnt, left


VARIANTS = [("1단계 전", {"old"}), ("변형 B (제품)", set()),
            ("시작점 + 최소폭 뗌 (A 수준)", {"start", "nominw"}), ("시작점 + A 수준 + 상한 뗌", {"start", "nominw", "nocap"})]


def table(part="all"):
    """part: golden20 · cls · flips · all — 메모리가 모자라면 나눠 돌린다(2026-09-28 한 번에 돌리다 시스템이 멈춰 세웠다)."""
    import check_accidental_fix as C
    fns = {name: load(fl) if fl else PROD for name, fl in VARIANTS}
    report = []
    if part in ("golden20", "all"):
        use(fns["1단계 전"]); base = C.snapshot()
    for name, _fl in (VARIANTS if part in ("golden20", "all") else []):
        use(fns[name])
        g = golden()
        snap = C.snapshot()
        tot, detail = label_diff(base, snap)
        use(PROD)
        report.append((name, g, tot, detail))
    if part in ("golden20", "all"):
        _print_golden20(report)
    if part in ("cls", "all"):
        _print_cls(classify_all(fns))
    if part in ("flips", "all"):
        _print_flips(fns)


def _print_golden20(report):
    print("\n## 골든 711 (골든 파일 대비) · 검증 20쪽 (1단계 전 대비)")
    for name, g, tot, detail in report:
        gs = " / ".join(f"{x['tag']} 사라짐 {len(x['gone'])} 생김 {len(x['new'])} 문맥 {len(x['ctx'])} 유령후보 {x['ghosts']}" for x in g)
        print(f"- {name}: 골든 [{gs}]  20쪽 {tot}")
        for x in g:
            for l in x["gone"][:5]:
                print(f"      골든 {x['tag']} - {l}")
            for l in x["new"][:8]:
                print(f"      골든 {x['tag']} + {l}")
            for a, b in x["ctx"]:
                print(f"      골든 {x['tag']} 문맥 {a} → {b}")
        for d in detail[:20]:
            print(f"      20쪽 {d}")


def _print_cls(cls):
    print("\n## 178보표 음자리표 끝 (1단계 전 → 변형)")
    base_c = cls["1단계 전"]
    for name, _fl in VARIANTS[1:]:
        pairs = {}
        worse = []
        for a, b in zip(base_c, cls[name]):
            pairs[(a[5], b[5])] = pairs.get((a[5], b[5]), 0) + 1
            if a[5] == "틈 안" and b[5] != "틈 안":
                worse.append(f"{b[0]} 보표{b[1]} 틈[{b[2]},{b[3]}] {a[4]}→{b[4]}({b[5]})")
        good = sum(v for (x, y), v in pairs.items() if x != "틈 안" and y == "틈 안")
        bad = sum(v for (x, y), v in pairs.items() if x == "틈 안" and y != "틈 안")
        still = sum(v for (x, y), v in pairs.items() if x != "틈 안" and y != "틈 안")
        print(f"- {name}: n={len(base_c)} 틈 안 유지 {pairs.get(('틈 안', '틈 안'), 0)} · 좋아짐 {good} · 나빠짐 {bad} · 여전히 틀림 {still}")
        for w in worse[:20]:
            print(f"      나빠짐 {w}")
        if still:
            print("      여전히 틀림: " + ", ".join(f"{b[0]}#{b[1]} {b[4]}({b[5]})" for a, b in zip(base_c, cls[name]) if a[5] != "틈 안" and b[5] != "틈 안"))


def _print_flips(fns):
    print("\n## 재표본화 조표 뒤집힘 (16각 48회: LINEAR / NEAREST / CUBIC / LANCZOS4 / 2배)")
    for name, _fl in VARIANTS:
        cnt, left = flips(fns[name])
        print(f"- {name}: " + " / ".join(str(cnt[m]) for m in ("linear", "nearest", "cubic", "lanczos4", "up2"))
              + f"   남은 LINEAR·LANCZOS4·이동: {[x for x in left if x[2] in ('linear', 'lanczos4') or x[1] == 'shift']}")


def golden_only(flags):
    use(load(flags))
    for x in golden():
        print(f"{x['tag']}: 사라짐 {len(x['gone'])} · 생김 {len(x['new'])} · 문맥 {len(x['ctx'])} · 유령후보 {x['ghosts']}")
        for l in x["new"]:
            print(f"   + {l}")
        for a, b in x["ctx"]:
            print(f"   문맥 {a} → {b}")
    use(PROD)


if __name__ == "__main__":
    if sys.argv[1] == "table":
        table(sys.argv[2] if len(sys.argv) > 2 else "all")
    else:
        golden_only(set(sys.argv[2].split(",")))
