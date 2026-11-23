# -*- coding: utf-8 -*-
"""A-8 사본 시뮬레이션 — 음자리표 끝 판정에 「넓은 빈 틈」 OR 규칙을 넣으면 무엇이 바뀌나.

> **1단계(변형 B)가 제품에 들어가기 전(`da41115`) 소스 기준 도구다.** 지금 소스에는 치환 위치가 없어 `load_sim`이 멈춘다 —
> 그때 결과는 `docs/KEYSIG_CLEF_GAP.md` §6에 있다. 2단계 사본은 `tools/sim_clef_start.py`.

**제품 파일은 안 바꾼다.** `modules/clef_keysig.py` 소스를 읽어 음자리표 클러스터 루프만 고친 사본을
메모리에 올리고, 실행 중에 `clef_keysig._analyze_one`만 그 사본으로 바꿔 끼운다.

`--minw`(변형 B): 음자리표 최소 폭 xc + 2.2sp 안쪽의 빈 틈에서는 멈추지 않는다.

규칙(사본): 기존 조건(열 잉크 < 0.5sp가 `max_g` 넘게)에 더해, **오선 행(선 y ±2px)을 뺀 헤더 띠에서
잉크 0인 열이 T·sp 이상 이어지면** 그 빈 연속의 시작에서 끝낸다. 둘 중 먼저 오는 쪽.
근거 `docs/KEYSIG_CLEF_GAP.md` §4 (틈 최소 0.82 / 안쪽 최대 0.36sp → 기하평균 0.54).

    python tools/sim_clef_gap_or.py [T=0.54]     # 골든 3쪽 + 검증 20쪽 대조, 보표별 음자리표 끝 변화
    python tools/sim_clef_gap_or.py flips [T]    # 재표본화 조표 뒤집힘(measure_keysig_resample sweep과 같은 조건)
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

OLD_PROFILE = "    ink_cnt = (band[r0:r1, :] > 0).sum(axis=0)\n"
NEW_PROFILE = OLD_PROFILE + """    _keep = np.ones(r1 - r0, bool)
    for _ly in staff.line_ys:                       # [사본] 오선 행 ±2px를 뺀 열 잉크
        _a = max(0, _ly - top - r0 - 2)
        _b = min(r1 - r0, _ly - top - r0 + 3)
        if _b > _a:
            _keep[_a:_b] = False
    off_cnt = (band[r0:r1, :][_keep] > 0).sum(axis=0)
"""
OLD_LOOP = """        while c2 < W and not tall_thin[c2]:
            if ink_cnt[c2] >= sp * 0.5:
                g = 0
            else:
                g += 1
                if g > max_g:
                    break
            c2 += 1
        c2 -= g
"""
NEW_LOOP = """        e = 0
        while c2 < W and not tall_thin[c2]:
            if off_cnt[c2] == 0:                    # [사본] 넓은 빈 틈 — OR
                e += 1
                # 변형 B: 음자리표 최소 폭(xc + 2.2sp, 아래 xe 하한과 같은 값) 안의 틈에서는 멈추지 않는다
                if e >= SIM_GAP_T * sp and (not SIM_MIN_W or c2 - e + 1 >= cx + sp * 2.2):
                    break
            else:
                e = 0
            if ink_cnt[c2] >= sp * 0.5:
                g = 0
            else:
                g += 1
                if g > max_g:
                    break
            c2 += 1
        if e >= SIM_GAP_T * sp and (not SIM_MIN_W or c2 - e + 1 >= cx + sp * 2.2):
            c2 = c2 - e + 1
        else:
            c2 -= g
"""

_ORIG = CK._analyze_one
MIN_W = "--minw" in sys.argv                 # 변형 B 켜기
if MIN_W:
    sys.argv.remove("--minw")


def load_sim(T, min_w=None):
    src = io.open(CK.__file__, encoding="utf-8").read()
    assert src.count(OLD_PROFILE) == 1 and src.count(OLD_LOOP) == 1, "제품 소스가 바뀌었다 — 사본 치환 위치 확인"
    src = src.replace(OLD_PROFILE, NEW_PROFILE).replace(OLD_LOOP, NEW_LOOP)
    m = types.ModuleType("modules._clef_keysig_sim")
    m.__package__ = "modules"
    m.SIM_GAP_T = T
    m.SIM_MIN_W = MIN_W if min_w is None else min_w
    exec(compile(src, "clef_keysig_sim.py", "exec"), m.__dict__)
    return m._analyze_one


def use(fn):
    CK._analyze_one = fn


def staff_table(path, pg):
    from modules.preprocess import preprocess
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
    ctx = CK.analyze_staves(res)
    return {i: (c.clef_end, c.header_end, c.clef, c.key_symbol + str(c.key_count)) for i, c in ctx.items()}


def golden(T):
    import test_golden_regression as TG
    out = []
    for tag, path in TG.PAGES:
        want = io.open(TG.golden_path(tag), encoding="utf-8").read().splitlines()
        want_ctx = io.open(TG.golden_path(tag, "_context"), encoding="utf-8").read().splitlines()
        lines, metrics, ctx = TG.analyze(path)
        gone = [l for l in want if l not in set(lines)]
        new = [l for l in lines if l not in set(want)]
        cgone = [l for l in want_ctx if l not in set(ctx)]
        cnew = [l for l in ctx if l not in set(want_ctx)]
        out.append((tag, len(want), gone, new, cgone, cnew, metrics))
    return out


def main(T):
    import check_accidental_fix as C
    sim = load_sim(T)
    print(f"== 규칙 T={T}sp\n")
    print("## 보표별 음자리표 끝 (clef_end · header_end) — 바뀐 보표만")
    changed = 0
    for page, path, pg in C.PAGES:
        use(_ORIG); a = staff_table(path, pg)
        use(sim); b = staff_table(path, pg)
        for i in sorted(a):
            if a[i] != b[i]:
                changed += 1
                print(f"  {page} 보표{i}: clef_end {a[i][0]}->{b[i][0]}  header_end {a[i][1]}->{b[i][1]}"
                      + (f"  음자리표 {a[i][2]}->{b[i][2]}" if a[i][2] != b[i][2] else "")
                      + (f"  조표 {a[i][3]}->{b[i][3]}" if a[i][3] != b[i][3] else ""))
    print(f"  → 바뀐 보표 {changed}\n")

    print("## 골든 (RE:Aoharu 3쪽, 라벨 711)")
    use(sim)
    for tag, n, gone, new, cgone, cnew, metrics in golden(T):
        print(f"  {tag}: 라벨 {n} — 사라짐 {len(gone)} · 생김 {len(new)} · 문맥 변화 {len(cgone)}")
        for l in gone[:10]:
            print(f"      - {l}")
        for l in new[:10]:
            print(f"      + {l}")
        for l in cgone:
            print(f"      문맥 골든: {l}")
        for l in cnew:
            print(f"      문맥 사본: {l}")
    print()

    print("## 검증 20쪽 — 라벨 대조")
    use(_ORIG); base = C.snapshot()
    use(sim); got = C.snapshot()
    use(_ORIG)
    tot = dict(사라짐=0, 생김=0, 음고=0, 표기=0, 문맥=0)
    for page in base:
        la, lb = base[page]["labels"], got[page]["labels"]
        used, gone = set(), []
        for p in la:
            k = next((j for j, q in enumerate(lb) if j not in used
                      and abs(q["x"] - p["x"]) <= C.MATCH and abs(q["y"] - p["y"]) <= C.MATCH), None)
            if k is None:
                gone.append(p)
                continue
            used.add(k)
            if lb[k]["pitch"] != p["pitch"]:
                tot["음고"] += 1; print(f"  {page} 음고 ({p['x']},{p['y']}) {p['pitch']}->{lb[k]['pitch']}")
            elif lb[k]["text"] != p["text"]:
                tot["표기"] += 1; print(f"  {page} 표기 ({p['x']},{p['y']}) {p['text']}->{lb[k]['text']}")
        new = [q for j, q in enumerate(lb) if j not in used]
        cd = C.rows_diff(base[page]["context"], got[page]["context"])
        tot["사라짐"] += len(gone); tot["생김"] += len(new); tot["문맥"] += len(cd)
        for p in gone:
            print(f"  {page} 사라짐 ({p['x']},{p['y']}) {p['pitch']} {p['text']}")
        for q in new:
            print(f"  {page} 생김   ({q['x']},{q['y']}) {q['pitch']} {q['text']}")
        for d in cd:
            print(f"  {page} 문맥 {d}")
    print(f"  → {tot}")


def flips(T):
    import measure_keysig_resample as M
    sim = load_sim(T)
    tmp = os.path.join(ROOT, "debug", "keysig_resample")
    res = {}
    for name in M.SCORES:
        use(_ORIG); _img, base_o = M._base(name, tmp)
        use(sim); _img, base_s = M._base(name, tmp)
        for deg in M.ANGLES + ("shift",):
            for m in M.METHODS:
                p = os.path.join(tmp, f"{name}_{deg}_{m}.png")
                use(_ORIG); ko = M.header(p)["key"]
                use(sim); ks = M.header(p)["key"]
                res[(name, deg, m)] = (base_o["key"], ko, base_s["key"], ks)
    use(_ORIG)
    print(f"== 규칙 T={T}sp — 재표본화 조표 뒤집힘 (기존 → 사본)")
    for m in M.METHODS:
        o = sum(1 for (n, d, mm), (bo, ko, bs, ks) in res.items() if mm == m and d != "shift" and ko != bo)
        s = sum(1 for (n, d, mm), (bo, ko, bs, ks) in res.items() if mm == m and d != "shift" and ks != bs)
        sh = [(n, ko, ks) for (n, d, mm), (bo, ko, bs, ks) in res.items() if mm == m and d == "shift" and (ko != bo or ks != bs)]
        print(f"  {m:9s} 16각 48회: {o} → {s}   0.5px 이동(기존판정, 사본판정): {sh}")
    left = [(n, d, m, ks) for (n, d, m), (bo, ko, bs, ks) in res.items() if ks != bs]
    print(f"  사본에서 남은 뒤집힘 {len(left)}: {left}")
    print(f"  원본 판정 기존/사본: " + ", ".join(f"{n} {v[0]}/{v[2]}" for (n, d, m), v in res.items() if d == 'shift' and m == 'linear'))



def classify(T=0.54):
    """보표마다 음자리표 끝이 **음자리표-조표 틈 안**에 있나 — 기존과 사본.

    틈 = 오선 행 밖 잉크 0인 열 연속 중 첫 구조 막대 바로 왼쪽의 것(`measure_clef_gap.gap_stats`와 같은 정의).
    분류: 틈 안(맞음) / 음자리표 안(틈보다 왼쪽) / 조표 넘음(틈보다 오른쪽). 들여쓴 첫 시스템은 따로 표시.
    """
    import measure_clef_gap as G
    import check_accidental_fix as C
    from modules.preprocess import preprocess
    sim = load_sim(T)
    G.LINE_PAD = 2
    tally = {}
    rows = []
    for page, path, pg in C.PAGES:
        res = preprocess(os.path.join(ROOT, path), pdf_page=pg)
        use(_ORIG); a = CK.analyze_staves(res)
        use(sim); b = CK.analyze_staves(res)
        use(_ORIG)
        kc = next(iter(a.values())).key_count
        found = [c for c in a.values() if c.clef_found]
        thr = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
        bars = sorted(x for c in found for x, _ in c.bars)
        cons, i = [], 0
        while i < len(bars):
            j = i
            while j + 1 < len(bars) and bars[j + 1] - bars[i] <= 3.0:
                j += 1
            if j - i + 1 >= thr:
                cons.append(float(sum(bars[i:j + 1]) / (j - i + 1)))
            i = j + 1
        profs = G.staff_profiles(res)
        for s in res.staves:
            if not a[s.index].clef_found or not kc or not cons:
                continue
            p = profs[s.index]
            sp = p["sp"]
            indent = (pg == 0 and s.index in (0, 1) and not page.startswith(("aoharu2", "aoharu3")))
            cl = G.clef_cluster(p)
            xc = cl[0] if cl else 0
            first = [x for x in cons if x > xc + sp * 1.4]
            if indent or not first:
                continue
            empty = p["off"] == 0
            gl = int(first[0])
            while gl > xc and not empty[gl - 1]:
                gl -= 1
            gr = gl
            while gr > xc and empty[gr - 1]:
                gr -= 1

            def cat(v):
                return "틈 안" if gr - 1 <= v <= gl else ("음자리표 안" if v < gr - 1 else "조표 넘음")
            ca, cb = cat(a[s.index].clef_end), cat(b[s.index].clef_end)
            tally[(ca, cb)] = tally.get((ca, cb), 0) + 1
            if a[s.index].clef_end != b[s.index].clef_end:
                rows.append(f"  {page} 보표{s.index}: 틈 [{gr},{gl}]  기존 {a[s.index].clef_end}({ca}) → 사본 {b[s.index].clef_end}({cb})")
    print(f"== T={T}: 음자리표 끝 위치 (기존 → 사본), 들여쓴 첫 시스템 제외")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {k[0]:6s} → {k[1]:6s} : {v}")
    print("\n".join(rows))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "classify":
        classify(float(args[1]) if len(args) > 1 else 0.54)
    elif args and args[0] == "flips":
        flips(float(args[1]) if len(args) > 1 else 0.54)
    else:
        main(float(args[0]) if args else 0.54)
