# -*- coding: utf-8 -*-
"""수정 방향 4 「입력 크기 정규화」 사본 측정 — 제품 코드 무변경.

방식(측정 대상): 전역 이진화(Otsu)로 sp를 먼저 추정 → 허용 범위를 넘으면 축소(PDF는 dpi를 낮춰 재렌더, 이미지는 INTER_AREA)
→ 기존 파이프라인 그대로.

    python tools/measure_normalize_sp.py sp       # 1. 전역 이진화 sp vs 현재 sp (20쪽 + Aoharu + 사진 합성 69장)
    python tools/measure_normalize_sp.py sweep    # 2. PDF 17쪽 × dpi 13단계 — 범주별 누락 · 음고 · 짝 없는 라벨 (이어 돌리기 가능)
"""
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_accidental_fix as C  # noqa: E402
from modules import preprocess as P  # noqa: E402
from modules.photo_correct import correct_photo  # noqa: E402

SYN = os.path.join(ROOT, "output", "synthetic_photos")
EDGE = os.path.join(ROOT, "output", "m1_edge")


def otsu_sp(bgr):
    """전역 Otsu 이진화 → 제품과 같은 오선 검출 · 보표 묶기 → sp 중앙값. 못 재면 None."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _t, b = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    try:
        st = P.group_into_staves(P.detect_staff_lines(b), row_sum=P.staff_line_profile(b))
    except P.StaffNotFoundError:
        return None, 0
    if not st:
        return None, 0
    return float(np.median([s.spacing for s in st])), len(st)


def cur_sp(path, pg=0, photo=False):
    try:
        res = P.preprocess(path, pdf_page=pg, photo=photo)
    except (P.StaffNotFoundError, P.PhotoRejectedError) as e:
        return None, 0, type(e).__name__
    return float(np.median([s.spacing for s in res.staves])), len(res.staves), "완료"


def main_sp():
    rows = []
    for name, path, pg in C.PAGES:
        full = os.path.join(ROOT, path)
        c, n, _s = cur_sp(full, pg)
        o, no = otsu_sp(P.load_image(full, pdf_page=pg))
        rows.append(("검증 20쪽", name, c, n, o, no))
    files = sorted(os.listdir(SYN)) + sorted(os.listdir(EDGE))
    for f in files:
        if not f.lower().endswith((".png", ".jpg")):
            continue
        full = os.path.join(SYN if os.path.exists(os.path.join(SYN, f)) else EDGE, f)
        bgr = P.load_image(full)
        c, n, st = cur_sp(full)
        o, no = otsu_sp(bgr)
        rows.append(("합성 · M1 없이", f, c, n, o, no))
        c, n, st = cur_sp(full, photo=True)
        if st == "완료":
            try:
                cb, _corr = correct_photo(bgr)
            except Exception as e:                      # 제품이 통과시켰으면 여기서도 통과해야 한다
                cb = None
                print("  보정 재현 실패", f, e)
            o, no = otsu_sp(cb) if cb is not None else (None, 0)
        else:
            o, no = None, 0
        rows.append(("합성 · M1(사진 모드)", f, c, n, o, no if st == "완료" else st))
    print("| 세트 | 입력 | 현재 sp · 보표 | Otsu sp · 보표 | 차이(%) |\n|---|---|---|---|---:|")
    diffs = {}
    for s, f, c, n, o, no in rows:
        d = (o - c) / c * 100 if (c and o) else None
        diffs.setdefault(s, []).append(d)
        print(f"| {s} | {f} | {c and round(c, 2)} · {n} | {o and round(o, 2)} · {no} | {'—' if d is None else f'{d:+.1f}'} |")
    print("\n| 세트 | 입력 | 둘 다 잼 | |차이| 최대(%) | |차이| > 3% | 현재만 잼 | Otsu만 잼 |\n|---|---:|---:|---:|---:|---:|---:|")
    for s in diffs:
        rs = [r for r in rows if r[0] == s]
        both = [abs((r[4] - r[2]) / r[2] * 100) for r in rs if r[2] and r[4]]
        print(f"| {s} | {len(rs)} | {len(both)} | {max(both) if both else 0:.1f} | {sum(1 for d in both if d > 3)} | "
              f"{sum(1 for r in rs if r[2] and not r[4])} | {sum(1 for r in rs if r[4] and not r[2])} |")
    json.dump([list(r) for r in rows], open(os.path.join(ROOT, "debug", "normalize_sp_otsu.json"), "w", encoding="utf-8"),
              ensure_ascii=False, default=str)


# ---------------------------------------------------------------- 2. dpi 촘촘히 — 허용 sp 구간 유도
import measure_omission_rate as M  # noqa: E402

SWEEP_DPI = [150, 165, 177, 190, 200, 220, 240, 260, 280, 300, 350, 400, 600]
SWEEP_JSON = os.environ.get("NSP_SWEEP_JSON") or os.path.join(ROOT, "debug", "normalize_sp_sweep.json")   # 다시 잴 때 새 파일로(예: debug/normalize_sp_sweep_1005.json)


def product_labels(res, path, pg):
    """골든 · 오삭제 측정과 같은 제품 경로(`check_accidental_fix.snapshot_page`)를 이미 만든 res로 돈다."""
    orig = C.preprocess
    C.preprocess = lambda *_a, **_k: res
    try:
        return C.snapshot_page(path, pg)["labels"]
    finally:
        C.preprocess = orig


def truth_at(path, pg, scale):
    """PDF 글리프 정답(300dpi 좌표)을 scale배. 일반 크기 머리만, 겹친 글리프 하나로."""
    g = M.pdf_glyphs(path, pg)
    for q in g:
        q["cx"] *= scale
        q["cy"] *= scale
    heads = []
    for q in (q for q in g if q["name"].startswith("noteheads.")):
        if not any(abs(q["cx"] - h["cx"]) < 2 * scale and abs(q["cy"] - h["cy"]) < 2 * scale for h in heads):
            heads.append(q)
    from collections import Counter
    main = Counter(h["size"] for h in heads).most_common(1)[0][0]
    return [h for h in heads if abs(h["size"] - main) < 0.05], [q for q in g if q["name"].startswith("clefs.")]


def evaluate(res, labels, heads, clefs):
    """정답 머리 범주별 누락 · 음고 틀림 · 짝 없는 라벨(유령 후보)."""
    staves = res.staves
    sp = float(np.median([s.spacing for s in staves]))
    for c in clefs:
        c["staff"] = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
    pairs, used_t, used_l = M.match(heads, labels, sp)
    h2l = dict(pairs)
    out = {}

    def add(k, v=1):
        out[k] = out.get(k, 0) + v
    for i, h in enumerate(heads):
        chord = any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp for j, q in enumerate(heads))
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - h["cy"]))
        k = int(round((h["cy"] - st.top) / (st.spacing / 2.0)))
        cats = ["전체", "화음" if chord else "단일",
                "빈 머리" if h["name"] in ("noteheads.s1", "noteheads.s0") else "꽉 찬 머리"]
        if not 0 <= k <= 8:
            cats.append("덧줄 구역")
        for c in cats:
            add(c + " · 정답")
            if i not in h2l:
                add(c + " · 누락")
            elif labels[h2l[i]]["pitch"] != M.truth_pitch(h["cx"], h["cy"], staves, clefs)[1]:
                add(c + " · 음고")
    out["짝 없는 라벨"] = len(labels) - len(used_l)
    out["라벨"] = len(labels)
    out["보표"] = len(staves)
    out["sp"] = sp
    return out


def main_sweep():
    done = json.load(open(SWEEP_JSON, encoding="utf-8")) if os.path.exists(SWEEP_JSON) else {}
    pages = [p for p in C.PAGES if not p[0].startswith("aoharu")]
    for dpi in SWEEP_DPI:
        for name, path, pg in pages:
            key = f"{name}@{dpi}"
            if key in done:
                continue
            heads, clefs = truth_at(path, pg, dpi / 300.0)
            try:
                res = P.preprocess(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi)
            except P.StaffNotFoundError:              # 제품이 오선을 못 찾음 — 그 쪽 음표 전부 누락으로 센다
                done[key] = {"오선 실패": 1, "전체 · 정답": len(heads), "전체 · 누락": len(heads), "짝 없는 라벨": 0,
                             "라벨": 0, "보표": 0, "sp": float("nan")}
                json.dump(done, open(SWEEP_JSON, "w", encoding="utf-8"), ensure_ascii=False)
                print(key, "오선 실패", flush=True)
                continue
            done[key] = evaluate(res, product_labels(res, path, pg), heads, clefs)
            json.dump(done, open(SWEEP_JSON, "w", encoding="utf-8"), ensure_ascii=False)
            print(key, {k: v for k, v in done[key].items() if "누락" in k or k in ("sp", "짝 없는 라벨")}, flush=True)
    report_sweep(done)


def report_sweep(done):
    cats = ["화음", "단일", "빈 머리", "덧줄 구역", "전체"]
    print("\n| dpi | sp 중앙 | " + " | ".join(f"{c} 누락" for c in cats) + " | 음고 틀림(전체) | 짝 없는 라벨 | 보표 수 다름 · 오선 실패 |")
    print("|---:|---:|" + "---:|" * (len(cats) + 3))
    base = {k.split("@")[0]: v["보표"] for k, v in done.items() if k.endswith("@300")}
    for dpi in SWEEP_DPI:
        rs = [v for k, v in done.items() if k.endswith(f"@{dpi}")]
        if not rs:
            continue
        sps = sorted(v["sp"] for v in rs if v["sp"] == v["sp"]) or [float("nan")]
        cells = []
        for c in cats:
            m, t = sum(v.get(c + " · 누락", 0) for v in rs), sum(v.get(c + " · 정답", 0) for v in rs)
            cells.append(f"{m}/{t} ({m / max(1, t) * 100:.1f}%)")
        wrong = sum(v.get("전체 · 음고", 0) for v in rs)
        ghost = sum(v["짝 없는 라벨"] for v in rs)
        stv = sum(1 for k, v in done.items() if k.endswith(f"@{dpi}") and v["보표"] != base.get(k.split("@")[0]))
        print(f"| {dpi} | {sps[len(sps) // 2]:.1f} | " + " | ".join(cells) + f" | {wrong} | {ghost} | {stv} · {sum(v.get('오선 실패', 0) for v in rs)} |")


# ---------------------------------------------------------------- 3. 머리 단위 평가 — 현재(300dpi) 대비 사라진 라벨 · 새 유령 · 음고 변화
EVAL_DIR = os.path.join(ROOT, "docs", "review", "normalize_sp")


def fill_dark_detect(res):
    """3번 사본: 음표 머리 검출에 넘기는 영상만 어두운 화소(흐림 뒤 gray < 128)로 보강. 다른 단계는 제품 이진화 그대로."""
    import modules.notehead_detect as ND
    dark = cv2.GaussianBlur(res.gray, (3, 3), 0) < 128

    def dn(r, **kw):
        b = r.binary
        r.binary = np.where(dark, 255, b).astype(np.uint8)
        try:
            return ND.detect_noteheads(r, **kw)
        finally:
            r.binary = b
    return dn


BLOCK_PER_SP = 25 / 11.5          # Aoharu(sp 11.5)에서 지금 창 25px과 같아지게


def block_for(sp):
    return max(3, int(round(BLOCK_PER_SP * sp)) | 1)


def block_preprocess(full, pg=0, photo=False):
    """1번 사본: 제품 전처리로 sp를 잰 뒤, 창 = BLOCK_PER_SP × sp(홀수)로 이진화만 바꿔 다시 전처리."""
    sp = float(np.median([s.spacing for s in P.preprocess(full, pdf_page=pg, photo=photo).staves]))
    orig = P.binarize
    b = block_for(sp)

    def binarize(bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        return gray, cv2.adaptiveThreshold(cv2.GaussianBlur(gray, (3, 3), 0), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY_INV, blockSize=b, C=10)
    P.binarize = binarize
    try:
        return P.preprocess(full, pdf_page=pg, photo=photo)
    finally:
        P.binarize = orig


# ---------------------------------------------------------------- 3번 좁힘: 닫힌 구멍 중 원본에서 안쪽이 어두운 것만 채움
HOLE_T = 101      # `holes` 실측: 뚫린 꽉 찬 머리 구멍 평균 최대 0.0 · 빈 머리 최소 202.6 → 틈 가운데 (PDF 렌더만 잼)


def closed_holes(binary):
    """이진화 결과의 닫힌 구멍: 배경(0)의 4연결 성분 중 영상 가장자리에 안 닿는 것. (라벨 영상, 통계)"""
    bg = (binary == 0).astype(np.uint8)
    n, lab, st, _c = cv2.connectedComponentsWithStats(bg, connectivity=4)
    h, w = binary.shape
    edge = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist())
    return lab, st, [i for i in range(1, n) if i not in edge]


def hole_means(res):
    """구멍마다 원본 회색(흐림 전 gray) 평균."""
    lab, st, ids = closed_holes(res.binary)
    sums = np.bincount(lab.ravel(), weights=res.gray.ravel().astype(float), minlength=st.shape[0])
    return lab, st, {i: sums[i] / st[i, cv2.CC_STAT_AREA] for i in ids}


def hole_fill_detect(res, T):
    """3번 좁힘 사본: 음표 머리 검출에 넘기는 영상만, 원본 평균 회색 < T인 닫힌 구멍을 채움. 구멍 밖 화소는 안 더함."""
    import modules.notehead_detect as ND
    lab, _st, means = hole_means(res)
    dark_ids = np.array([i for i, m in means.items() if m < T], dtype=np.int64)
    fill = np.isin(lab, dark_ids) if dark_ids.size else np.zeros(lab.shape, bool)

    def dn(r, **kw):
        b = r.binary
        r.binary = np.where(fill, 255, b).astype(np.uint8)
        try:
            return ND.detect_noteheads(r, **kw)
        finally:
            r.binary = b
    return dn, int(fill.sum()), len(dark_ids)


HOLLOW_PAGES = [("hollow16", "debug/hollow_fixture/hollow_16.pdf", 0), ("hollow20", "debug/hollow_fixture/hollow_20.pdf", 0),
                ("hollow24", "debug/hollow_fixture/hollow_24.pdf", 0)]


def main_holes():
    """문턱 유도: 정답 머리 중심을 품은 닫힌 구멍의 원본 회색 평균 — 꽉 찬 머리(s2, 뚫린 것) vs 빈 머리(s1 · s0)."""
    pages = [p for p in C.PAGES if not p[0].startswith("aoharu")] + HOLLOW_PAGES
    vals = {"꽉 찬 머리(뚫림)": [], "빈 머리": []}
    for name, path, pg in pages:
        res = P.preprocess(os.path.join(ROOT, path), pdf_page=pg)
        heads, _cl = truth_at(path, pg, 1.0)
        lab, st, means = hole_means(res)
        for h in heads:
            x, y = int(round(h["cx"])), int(round(h["cy"]))
            win = lab[y - 2:y + 3, x - 2:x + 3].ravel()
            ids = [i for i in set(win.tolist()) if i in means]
            if not ids:
                continue
            i = max(ids, key=lambda i: (win == i).sum())
            kind = "빈 머리" if h["name"] in ("noteheads.s1", "noteheads.s0") else "꽉 찬 머리(뚫림)"
            vals[kind].append((means[i], name, x, y, int(st[i, cv2.CC_STAT_AREA])))
        print(name, {k: len(v) for k, v in vals.items()}, flush=True)
    for k, v in vals.items():
        g = sorted(m for m, *_ in v)
        if g:
            print(f"\n{k}: n={len(g)} · 최소 {g[0]:.1f} · 10% {g[len(g) // 10]:.1f} · 중앙 {g[len(g) // 2]:.1f} · 90% {g[(len(g) * 9) // 10]:.1f} · 최대 {g[-1]:.1f}")
            hist = np.histogram(g, bins=17, range=(0, 255))[0]
            print("  15단위 히스토그램 0~255:", hist.tolist())
    f = max(m for m, *_ in vals["꽉 찬 머리(뚫림)"])
    e = min(m for m, *_ in vals["빈 머리"])
    print(f"\n꽉 찬 머리 최대 {f:.1f} · 빈 머리 최소 {e:.1f} · 틈 {e - f:.1f} → {'겹침 — 기각' if e <= f else f'문턱 후보(틈 가운데) {(e + f) / 2:.1f}'}")
    print("빈 머리 가장 어두운 5:", sorted(vals["빈 머리"])[:5])
    print("꽉 찬 머리 가장 밝은 5:", sorted(vals["꽉 찬 머리(뚫림)"])[-5:])


def variant_labels(variant, path, pg, sp300):
    """변형별 라벨(300dpi 좌표로 환산)과 그 결과의 sp."""
    full = os.path.join(ROOT, path)
    if variant.startswith("norm"):
        T = float(variant[4:])
        dpi = 300.0 * T / sp300 if sp300 > T else 300.0
        res = P.preprocess(full, pdf_page=pg, pdf_dpi=dpi)
        labs = product_labels(res, path, pg)
        k = 300.0 / dpi
        for l in labs:
            l["x"], l["y"] = l["x"] * k, l["y"] * k
        return labs
    if variant == "block":
        return product_labels(block_preprocess(full, pg), path, pg)
    res = P.preprocess(full, pdf_page=pg)
    if variant in ("fill", "holefill"):
        orig = C.detect_noteheads
        C.detect_noteheads = fill_dark_detect(res) if variant == "fill" else hole_fill_detect(res, HOLE_T)[0]
        try:
            return product_labels(res, path, pg)
        finally:
            C.detect_noteheads = orig
    return product_labels(res, path, pg)


def main_eval(variants, out_dir=None, pages=None):
    global EVAL_DIR
    EVAL_DIR = out_dir or EVAL_DIR
    os.makedirs(EVAL_DIR, exist_ok=True)
    pages = pages or [p for p in C.PAGES if not p[0].startswith("aoharu")]
    total = {v: {} for v in variants}
    events = {v: [] for v in variants}
    for name, path, pg in pages:
        res = P.preprocess(os.path.join(ROOT, path), pdf_page=pg)
        sp = float(np.median([s.spacing for s in res.staves]))
        heads, clefs = truth_at(path, pg, 1.0)
        for c in clefs:
            c["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
        base = product_labels(res, path, pg)
        bp, _bt, bl = M.match(heads, base, sp)
        b_h2l = dict(bp)
        b_ghost = [base[i] for i in range(len(base)) if i not in bl]
        for v in variants:
            labs = variant_labels(v, path, pg, sp)
            vp, _vt, vl = M.match(heads, labs, sp)
            v_h2l = dict(vp)
            t = total[v]
            for i, h in enumerate(heads):
                tp = M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1]
                a, b = b_h2l.get(i), v_h2l.get(i)
                if a is not None and b is None:
                    kind = "사라진 라벨"
                    grp = [q for q in heads if abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp]
                    if len(grp) >= 2:
                        xs, ys = [q["cx"] for q in grp], [q["cy"] for q in grp]

                        def inside(L):
                            return sum(1 for l in L if min(xs) - 0.7 * sp <= l["x"] <= max(xs) + 0.7 * sp
                                       and min(ys) - 0.5 * sp <= l["y"] <= max(ys) + 0.5 * sp)
                        nb, na = inside(base), inside(labs)
                        sub_kind = "화음 · 자리만 바뀜" if na >= nb else "화음 · 머리 수 감소"
                    else:
                        sub_kind, nb, na = "화음 아님", None, None
                elif a is None and b is not None:
                    kind = "새로 찾음"
                elif a is not None and b is not None and base[a]["pitch"] != labs[b]["pitch"]:
                    kind = "음고 좋아짐" if labs[b]["pitch"] == tp else ("음고 나빠짐" if base[a]["pitch"] == tp else "음고 다르게 틀림")
                else:
                    continue
                t[kind] = t.get(kind, 0) + 1
                events[v].append(dict(page=name, path=path, pg=pg, x=h["cx"], y=h["cy"], kind=kind, truth=tp, sp=sp,
                                      sub=sub_kind if kind == "사라진 라벨" else None,
                                      n_before=nb if kind == "사라진 라벨" else None, n_after=na if kind == "사라진 라벨" else None,
                                      before=base[a]["text"] if a is not None else "-", after=labs[b]["text"] if b is not None else "-"))
            for j, l in enumerate(labs):
                if j in vl:
                    continue
                if not any(abs(g["x"] - l["x"]) <= 0.7 * sp and abs(g["y"] - l["y"]) <= 0.5 * sp for g in b_ghost):
                    t["새 유령"] = t.get("새 유령", 0) + 1
                    events[v].append(dict(page=name, path=path, pg=pg, x=l["x"], y=l["y"], kind="새 유령", truth="-", sp=sp,
                                          before="-", after=l["text"]))
            t["유령(짝 없는 라벨)"] = t.get("유령(짝 없는 라벨)", 0) + len(labs) - len(vl)
            t["현재 유령"] = t.get("현재 유령", 0) + len(b_ghost)
            print(name, v, {k: t[k] for k in t}, flush=True)
    kinds = ["사라진 라벨", "새로 찾음", "음고 좋아짐", "음고 나빠짐", "음고 다르게 틀림", "새 유령", "유령(짝 없는 라벨)", "현재 유령"]
    print("\n| 변형 | " + " | ".join(kinds) + " |\n|---|" + "---:|" * len(kinds))
    for v in variants:
        print(f"| {v} | " + " | ".join(str(total[v].get(k, 0)) for k in kinds) + " |")
    json.dump(events, open(os.path.join(ROOT, "debug", f"eval_{'_'.join(variants)}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for v in variants:
        for e in events[v]:
            if e["kind"] == "사라진 라벨":
                print(f"  {v} 사라진 라벨 {e['page']} ({int(e['x'])},{int(e['y'])}) {e['sub']} 라벨 {e['n_before']}→{e['n_after']} · 정답 {e['truth']} · {e['before']}")
    redo_crops(events)


ORDER = ("사라진 라벨", "음고 나빠짐", "새 유령")


def redo_crops(events=None):
    """그림만 다시 — 종류별로 정렬(사라진 라벨 → 음고 나빠짐 → 새 유령)."""
    events = events or json.load(open(os.path.join(ROOT, "debug", "normalize_sp_eval.json"), encoding="utf-8"))
    for v, evs in events.items():
        crops(v, sorted((e for e in evs if e["kind"] in ORDER), key=lambda e: (ORDER.index(e["kind"]), e["page"], e["y"], e["x"])))


def crops(variant, evs, out_dir=None):
    """사라진 라벨 · 새 유령 · 음고 나빠짐 확대(원본 300dpi ±3sp, 주황 원) — 한 장 24칸.
    e["img"]가 있으면 그 영상에서 자른다(사진 모드 — 라벨 좌표가 보정 뒤 영상 기준)."""
    import math
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 13)
    cache, tiles = {}, []
    for e in evs:
        key = (e["path"], e["pg"])
        if "img" not in e and key not in cache:
            cache.clear()
            cache[key] = P.load_image(os.path.join(ROOT, e["path"]), pdf_page=e["pg"])
        img, sp = e.get("img", cache.get(key)), e["sp"]
        x0, y0 = max(0, int(e["x"] - 3 * sp)), max(0, int(e["y"] - 3 * sp))
        c = img[y0:int(e["y"] + 3 * sp), x0:int(e["x"] + 3 * sp)].copy()
        cv2.circle(c, (int(e["x"] - x0), int(e["y"] - y0)), int(sp * 0.8), (0, 140, 255), 2)
        k = 150 / max(c.shape[:2])
        c = cv2.resize(c, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        t = Image.new("RGB", (190, 215), "white")
        t.paste(Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)), (20, 58))
        d = ImageDraw.Draw(t)
        d.text((3, 2), f"{e['page']} ({int(e['x'])},{int(e['y'])})", font=font, fill=(0, 0, 0))
        d.text((3, 19), e["kind"], font=font, fill=(180, 60, 0))
        d.text((3, 36), f"정답 {e['truth']} · {e['before']} → {e['after']}", font=font, fill=(60, 60, 60))
        d.rectangle([0, 0, 189, 214], outline=(190, 190, 190))
        tiles.append(t)
    for s in range(0, len(tiles), 24):
        chunk = tiles[s:s + 24]
        rows = math.ceil(len(chunk) / 6)
        sheet = Image.new("RGB", (6 * 195 + 5, rows * 220 + 5), "white")
        for i, t in enumerate(chunk):
            sheet.paste(t, (5 + (i % 6) * 195, 5 + (i // 6) * 220))
        sheet.save(os.path.join(out_dir or EVAL_DIR, f"{variant}_{s // 24 + 1}.png"))


# ---------------------------------------------------------------- 「추가」 방식: 기존 라벨은 그대로, 좁힌 보강에서만 나온 라벨을 check로 더함
ADD_DIR = os.path.join(ROOT, "docs", "review", "fill_additive")


def additive(path, pg):
    """기존 라벨(제품 그대로) + 좁힌 보강 파이프라인 라벨 중 기존 라벨 ±0.5sp(가로 · 세로) 안에 짝이 없는 것.
    두 파이프라인을 **따로** 끝까지 돌리므로 기존 라벨은 구조적으로 안 바뀐다 — 아래에서 실제 비교로도 확인."""
    full = os.path.join(ROOT, path)
    res = P.preprocess(full, pdf_page=pg)
    sp = float(np.median([s.spacing for s in res.staves]))
    base = product_labels(res, path, pg)
    res2 = P.preprocess(full, pdf_page=pg)
    orig = C.detect_noteheads
    C.detect_noteheads = hole_fill_detect(res2, HOLE_T)[0]
    try:
        fill = product_labels(res2, path, pg)
    finally:
        C.detect_noteheads = orig
    base_again = product_labels(P.preprocess(full, pdf_page=pg), path, pg)
    same = [(l["x"], l["y"], l["pitch"], l["text"], l["confidence"]) for l in base] == \
           [(l["x"], l["y"], l["pitch"], l["text"], l["confidence"]) for l in base_again]
    add = [dict(l, confidence="check") for l in fill
           if not any(abs(l["x"] - b["x"]) <= 0.5 * sp and abs(l["y"] - b["y"]) <= 0.5 * sp for b in base)]
    return res, sp, base, add, same


def main_additive():
    os.makedirs(ADD_DIR, exist_ok=True)
    pdf = [p for p in C.PAGES if not p[0].startswith("aoharu")]
    tot = {"기존 라벨 그대로(쪽)": 0, "추가": 0, "진짜 머리": 0, "진짜 머리 · 음고 맞음": 0, "유령": 0, "중복": 0,
           "화음 정답": 0, "화음 누락 전": 0, "화음 누락 후": 0, "단일 누락 전": 0, "단일 누락 후": 0}
    evs = []
    for name, path, pg in C.PAGES:
        res, sp, base, add, same = additive(path, pg)
        tot["기존 라벨 그대로(쪽)"] += int(same)
        tot["추가"] += len(add)
        if name.startswith("aoharu"):
            print(name, "추가", len(add), "· 기존 그대로", same, flush=True)
            for l in add:
                evs.append(dict(page=name, path=path, pg=pg, x=l["x"], y=l["y"], kind="추가 · 정답 없음(Aoharu)", truth="-", sp=sp,
                                before="-", after=l["text"]))
            continue
        heads, clefs = truth_at(path, pg, 1.0)
        for c in clefs:
            c["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
        bp, bt, _bl = M.match(heads, base, sp)
        rest = [i for i in range(len(heads)) if i not in bt]
        ap, at, al = M.match([heads[i] for i in rest], add, sp)
        a2h = {li: rest[ti] for ti, li in ap}
        for li, l in enumerate(add):
            if li in a2h:
                h = heads[a2h[li]]
                tp = M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1]
                kind = "진짜 머리"
                tot[kind] += 1
                tot["진짜 머리 · 음고 맞음"] += int(l["pitch"] == tp)
                if l["pitch"] != tp:
                    kind = "진짜 머리 · 음고 틀림"
            else:
                near = [i for i, h in enumerate(heads) if i in bt and abs(h["cx"] - l["x"]) <= 0.7 * sp and abs(h["cy"] - l["y"]) <= 0.5 * sp]
                kind = "중복" if near else "유령"
                tot[kind] += 1
                tp = "-"
                if near:                           # 그 머리의 기존 라벨과 비교 — 같은 음이 두 번인가, 기존 라벨이 틀렸나
                    b2l = dict(bp)
                    h = heads[near[0]]
                    tp = M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1]
                    b = base[b2l[near[0]]]
                    sub = ("같은 음 두 번" if b["pitch"] == l["pitch"] else
                           "기존 틀림 · 추가 맞음" if l["pitch"] == tp and b["pitch"] != tp else
                           "기존 맞음 · 추가 틀림" if b["pitch"] == tp else "둘 다 틀림")
                    tot["중복 · " + sub] = tot.get("중복 · " + sub, 0) + 1
                    tot.setdefault("중복 · 기존 라벨 세로 어긋남(sp)", []).append(round((b["y"] - h["cy"]) / sp, 2))
                    kind = "중복 · " + sub
            evs.append(dict(page=name, path=path, pg=pg, x=l["x"], y=l["y"], kind=kind, truth=tp, sp=sp, before="-", after=l["text"]))
        _p, t_all, _l = M.match(heads, base + add, sp)
        for i, h in enumerate(heads):
            chord = any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp for j, q in enumerate(heads))
            k = "화음" if chord else "단일"
            if chord:
                tot["화음 정답"] += 1
            tot[f"{k} 누락 전"] += int(i not in bt)
            tot[f"{k} 누락 후"] += int(i not in t_all)
        print(name, "추가", len(add), "· 기존 그대로", same, {k: tot[k] for k in ("진짜 머리", "유령", "중복")}, flush=True)
    print("\n", tot)
    print(f"\n붙은 화음 누락: {tot['화음 누락 전']}/{tot['화음 정답']} ({tot['화음 누락 전'] / tot['화음 정답'] * 100:.1f}%) → "
          f"{tot['화음 누락 후']}/{tot['화음 정답']} ({tot['화음 누락 후'] / tot['화음 정답'] * 100:.1f}%) · 단일 누락 {tot['단일 누락 전']} → {tot['단일 누락 후']}")
    json.dump(evs, open(os.path.join(ROOT, "debug", "fill_additive.json"), "w", encoding="utf-8"), ensure_ascii=False)
    global EVAL_DIR
    EVAL_DIR = ADD_DIR
    order = ("유령", "중복 · 같은 음 두 번", "중복 · 기존 틀림 · 추가 맞음", "중복 · 기존 맞음 · 추가 틀림", "중복 · 둘 다 틀림",
             "진짜 머리 · 음고 틀림", "추가 · 정답 없음(Aoharu)", "진짜 머리")
    for f in os.listdir(ADD_DIR):
        os.remove(os.path.join(ADD_DIR, f))
    crops("added", sorted(evs, key=lambda e: (order.index(e["kind"]), e["page"], e["y"], e["x"])))


# ---------------------------------------------------------------- 「추가」 후속: 2(끼인 기존 라벨 → check) · 2b(중점이면 삭제)
V2B_DIR = os.path.join(ROOT, "docs", "review", "fill_additive_2b")


def sandwich(L, add, sp):
    """기존 라벨 L을 위아래로 끼는 추가 라벨 쌍(가로 0.6sp 안, 둘 사이 세로 ≤1.6sp) 중 L과 가장 가까운 것. 없으면 None."""
    col = [a for a in add if abs(a["x"] - L["x"]) <= 0.6 * sp]
    up = [a for a in col if a["y"] < L["y"]]
    lo = [a for a in col if a["y"] > L["y"]]
    if not up or not lo:
        return None
    u = max(up, key=lambda a: a["y"])
    d = min(lo, key=lambda a: a["y"])
    if d["y"] - u["y"] > 1.6 * sp:
        return None
    return u, d


def mid_dev(L, u, d, sp):
    """중점 조건의 어긋남(sp): 위 · 아래 추가 라벨까지 거리가 각각 0.5sp에서 벗어난 양 중 큰 것."""
    return max(abs((L["y"] - u["y"]) / sp - 0.5), abs((d["y"] - L["y"]) / sp - 0.5))


def main_v2():
    os.makedirs(V2B_DIR, exist_ok=True)
    pdf = [p for p in C.PAGES if not p[0].startswith("aoharu")]
    pages = []
    ghost_dev, real_dev = [], []                 # 허용오차 유도용
    for name, path, pg in pdf:
        res, sp, base, add, _same = additive(path, pg)
        heads, clefs = truth_at(path, pg, 1.0)
        for c in clefs:
            c["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
        tp = [M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1] for h in heads]
        bp, _bt, _bl = M.match(heads, base, sp)
        l2h = {li: ti for ti, li in bp}
        for li, L in enumerate(base):
            L["_ok"] = li in l2h and L["pitch"] == tp[l2h[li]]
            L["_head"] = l2h.get(li)
        # (가) 합쳐진 유령: 추가 라벨 쌍에 끼인, 음이 틀린 기존 라벨의 중점 어긋남
        for L in base:
            s = sandwich(L, add, sp)
            if s and not L["_ok"]:
                ghost_dev.append((mid_dev(L, *s, sp), name, L["x"], L["y"]))
        # (나) 3화음 진짜 가운데 음: 정답 머리 위 · 아래 ±1sp(0.8~1.2)에 같은 기둥 머리가 있고, 기존 라벨이 맞는 음
        for li, L in enumerate(base):
            if not L["_ok"]:
                continue
            h = heads[L["_head"]]
            nb = [q for q in heads if abs(q["cx"] - h["cx"]) <= 0.6 * sp]
            up = [q for q in nb if 0.8 * sp <= h["cy"] - q["cy"] <= 1.2 * sp]
            lo = [q for q in nb if 0.8 * sp <= q["cy"] - h["cy"] <= 1.2 * sp]
            if up and lo:
                u = dict(x=up[0]["cx"], y=up[0]["cy"])
                d = dict(x=lo[0]["cx"], y=lo[0]["cy"])
                real_dev.append((mid_dev(L, u, d, sp), name, L["x"], L["y"]))
        pages.append((name, path, pg, res, sp, base, add, heads, tp))
        print(name, "유령", len(ghost_dev), "진짜 가운데", len(real_dev), flush=True)

    g = sorted(v for v, *_ in ghost_dev)
    r = sorted(v for v, *_ in real_dev)
    print(f"\n(가) 합쳐진 유령 중점 어긋남 n={len(g)}: 최소 {g[0]:.3f} · 중앙 {g[len(g) // 2]:.3f} · 최대 {g[-1]:.3f}")
    print(f"(나) 3화음 진짜 가운데 음 n={len(r)}: " + (f"최소 {r[0]:.3f} · 중앙 {r[len(r) // 2]:.3f} · 최대 {r[-1]:.3f}" if r else "없음"))
    print("  (가) 큰 쪽 5:", sorted(ghost_dev)[-5:])
    print("  (나) 작은 쪽 5:", sorted(real_dev)[:5])
    tol = (g[-1] + r[0]) / 2 if r and r[0] > g[-1] else None
    print("허용오차:", "겹침 — 2b 기각" if tol is None else f"{tol:.3f}sp (틈 {g[-1]:.3f} ~ {r[0]:.3f}의 가운데)")

    # 모든 맞는 기존 라벨(진짜 라벨)도 끼임 · 중점 조건에 걸리는지 — 사라진 진짜 라벨 후보
    real_hit = []
    for name, path, pg, res, sp, base, add, heads, tp in pages:
        for L in base:
            s = sandwich(L, add, sp)
            if s and L["_ok"]:
                real_hit.append((round(mid_dev(L, *s, sp), 3), name, L["x"], L["y"], L["pitch"]))
    print("\n맞는 기존 라벨 중 추가 라벨 쌍에 끼인 것:", real_hit)
    print("  em2 (1006,1824) 「같은 음 두 번」:", [h for h in real_hit if h[1] == "em2" and abs(h[2] - 1006) < 15])

    # 평가
    import math
    from collections import Counter
    rows, evs = {}, []
    for v in ("추가만", "2", "2b"):
        t = Counter()
        per_chord = Counter()
        for name, path, pg, res, sp, base, add, heads, tp in pages:
            labs = [dict(L) for L in base]
            for L in labs:
                s = sandwich(L, add, sp)
                if s is None:
                    continue
                if v == "2" and L["confidence"] != "check":
                    L["confidence"] = "check"
                    t["check로 올림"] += 1
                    t["check로 올림 · " + ("맞는 라벨" if L["_ok"] else "틀린 라벨")] += 1
                if v == "2b" and tol is not None and mid_dev(L, *s, sp) <= tol:
                    L["_del"] = True
                    t["삭제"] += 1
                    t["삭제 · " + ("진짜 라벨(맞는 음)" if L["_ok"] else "유령(틀린 음 · 정답 없음)")] += 1
                    evs.append(dict(page=name, path=path, pg=pg, x=L["x"], y=L["y"], sp=sp, truth=tp[L["_head"]] if L["_head"] is not None else "-",
                                    kind="2b 삭제 · " + ("진짜" if L["_ok"] else "유령"), before=L["text"], after="삭제"))
            final = [L for L in labs if not L.get("_del")] + add
            _p, t_all, _l = M.match(heads, final, sp)
            ok_before = {L["_head"] for L in base if L["_ok"]}
            pp, _t, _l = M.match(heads, final, sp)
            ok_after = {ti for ti, li in pp if final[li]["pitch"] == tp[ti]}
            t["사라진 진짜 라벨"] += len(ok_before - ok_after)
            t["check 전"] += sum(1 for L in base if L["confidence"] == "check")
            t["check 후"] += sum(1 for L in final if L["confidence"] == "check")
            for i, h in enumerate(heads):
                grp = [q for q in heads if abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp]
                if len(grp) >= 2:
                    t["화음 정답"] += 1
                    t["화음 누락"] += int(i not in t_all)
            # 화음당 check 개수: 붙은 화음 묶음마다 자리 안 check 라벨 수
            seen = set()
            for i, h in enumerate(heads):
                grp = sorted(j for j, q in enumerate(heads) if abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp)
                if len(grp) < 2 or tuple(grp) in seen:
                    continue
                seen.add(tuple(grp))
                xs, ys = [heads[j]["cx"] for j in grp], [heads[j]["cy"] for j in grp]
                n = sum(1 for L in final if L["confidence"] == "check" and min(xs) - 0.7 * sp <= L["x"] <= max(xs) + 0.7 * sp
                        and min(ys) - 0.5 * sp <= L["y"] <= max(ys) + 0.5 * sp)
                per_chord[min(n, 4)] += 1
        rows[v] = (t, per_chord)
    print("\n| 변형 | 사라진 진짜 라벨 | 지운 유령 | check로 올림(맞는/틀린) | check 전→후(증가) | 붙은 화음 누락 | 화음당 check 0/1/2/3/4+ |")
    print("|---|---:|---:|---|---|---|---|")
    for v, (t, pc) in rows.items():
        print(f"| {v} | {t['사라진 진짜 라벨']} | {t['삭제 · 유령(틀린 음 · 정답 없음)']} | {t['check로 올림']} ({t['check로 올림 · 맞는 라벨']}/{t['check로 올림 · 틀린 라벨']}) | "
              f"{t['check 전']}→{t['check 후']} (+{t['check 후'] - t['check 전']}) | {t['화음 누락']}/{t['화음 정답']} ({t['화음 누락'] / t['화음 정답'] * 100:.1f}%) | "
              f"{'/'.join(str(pc[k]) for k in range(5))} |")
    print("2b 삭제 중 진짜 라벨:", rows["2b"][0]["삭제 · 진짜 라벨(맞는 음)"])
    global EVAL_DIR
    EVAL_DIR = V2B_DIR
    for f in os.listdir(V2B_DIR):
        os.remove(os.path.join(V2B_DIR, f))
    crops("deleted", sorted(evs, key=lambda e: (e["kind"], e["page"], e["y"], e["x"])))
    json.dump(evs, open(os.path.join(ROOT, "debug", "fill_additive_2b.json"), "w", encoding="utf-8"), ensure_ascii=False)


# ---------------------------------------------------------------- 병합 전 보고: 제품 모듈(modules/chord_rescue)로 두 번 돌려 합치기 재현
def rescue_page(path, pg=0, photo=False):
    """main.py가 할 연결을 재현: 기존 파이프라인 + 보강 파이프라인(머리 검출만 detect_noteheads_rescue) → merge_additive."""
    from modules.chord_rescue import detect_noteheads_rescue, merge_additive
    full = os.path.join(ROOT, path)
    res = P.preprocess(full, pdf_page=pg, photo=photo)
    sp = float(np.median([s.spacing for s in res.staves]))
    base = product_labels(res, path, pg)
    res2 = P.preprocess(full, pdf_page=pg, photo=photo)
    orig = C.detect_noteheads
    C.detect_noteheads = detect_noteheads_rescue
    try:
        extra = product_labels(res2, path, pg)
    finally:
        C.detect_noteheads = orig
    added, deleted = merge_additive([(l["x"], l["y"]) for l in base], [(l["x"], l["y"]) for l in extra], sp)
    final = [l for i, l in enumerate(base) if i not in set(deleted)] + [dict(extra[j], confidence="caution", _added=True) for j in added]
    return res, sp, base, final, added, deleted


def main_rescue():
    from collections import Counter
    out = {}
    tot = Counter()
    per_page = []
    lost_list, del_rows = [], []
    for name, path, pg in C.PAGES:
        res, sp, base, final, added, deleted = rescue_page(path, pg)
        cb = sum(1 for l in base if l["confidence"] == "check")
        cf = sum(1 for l in final if l["confidence"] == "check")
        per_page.append((name, len(base), len(final), len(added), len(deleted), cb, cf))
        tot["check 전"] += cb
        tot["check 후"] += cf
        if name.startswith("aoharu"):
            tot["Aoharu 추가"] += len(added)
            tot["Aoharu 삭제"] += len(deleted)
            print(name, "추가", len(added), "삭제", len(deleted), flush=True)
            continue
        heads, clefs = truth_at(path, pg, 1.0)
        for c in clefs:
            c["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
        tp = [M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)[1] for h in heads]
        bp, bt, _bl = M.match(heads, base, sp)
        fp, ft, _fl = M.match(heads, final, sp)
        ok_b = {ti for ti, li in bp if base[li]["pitch"] == tp[ti]}
        ok_f = {ti for ti, li in fp if final[li]["pitch"] == tp[ti]}
        for ti in ok_b - ok_f:
            lost_list.append((name, round(heads[ti]["cx"]), round(heads[ti]["cy"]), tp[ti]))
        tot["매칭 머리 전"] += len(bt)
        tot["매칭 머리 후"] += len(ft)
        # 추가 라벨 분류(정답 대조)
        rest = [i for i in range(len(heads)) if i not in bt]
        adds = [l for l in final if l.get("_added")]
        ap, _at, _al = M.match([heads[i] for i in rest], adds, sp)
        a_real = {li for _ti, li in ap}
        for li, l in enumerate(adds):
            if li in a_real:
                tot["추가 · 진짜 머리"] += 1
            elif any(abs(h["cx"] - l["x"]) <= 0.7 * sp and abs(h["cy"] - l["y"]) <= 0.5 * sp for i, h in enumerate(heads) if i in bt):
                tot["추가 · 중복(기존 라벨 있는 머리)"] += 1
            else:
                tot["추가 · 유령"] += 1
        for i in deleted:
            L = base[i]
            li_ok = any(li == i and base[li]["pitch"] == tp[ti] for ti, li in bp)
            tot["삭제 · 맞는 음" if li_ok else "삭제 · 틀린 음(유령)"] += 1
            del_rows.append((name, L["x"], L["y"], L["text"], "맞는 음" if li_ok else "유령"))
        for i, h in enumerate(heads):
            if any(j != i and abs(q["cx"] - h["cx"]) <= 0.6 * sp and abs(q["cy"] - h["cy"]) <= 1.05 * sp for j, q in enumerate(heads)):
                tot["화음 정답"] += 1
                tot["화음 누락 전"] += int(i not in bt)
                tot["화음 누락 후"] += int(i not in ft)
        print(name, "추가", len(added), "삭제", len(deleted), "check", cb, "→", cf, flush=True)
    print("\n## 20쪽\n")
    print("| 쪽 | 라벨 전 → 후 | 추가 | 삭제 | check 전 → 후 |\n|---|---|---:|---:|---|")
    for name, nb, nf, na, nd, cb, cf in per_page:
        print(f"| {name} | {nb} → {nf} | {na} | {nd} | {cb} → {cf} |")
    print("\n", dict(tot))
    print("\n오삭제(맞는 음 라벨이 있던 정답 머리가 잃음):", lost_list)
    print("2b 삭제 목록:", del_rows)
    print(f"붙은 화음 누락: {tot['화음 누락 전']}/{tot['화음 정답']} → {tot['화음 누락 후']}/{tot['화음 정답']}")

    # 빈 음표 픽스처
    print("\n## 빈 음표 픽스처\n")
    for name, path, pg in HOLLOW_PAGES:
        res, sp, base, final, added, deleted = rescue_page(path, pg)
        heads, _cl = truth_at(path, pg, 1.0)
        hol = [h for h in heads if h["name"] in ("noteheads.s1", "noteheads.s0")]
        _p, tb, _l = M.match(hol, base, sp)
        _p, tf, _l = M.match(hol, final, sp)
        print(f"{name}: 빈 머리 {len(hol)} · 검출 {len(tb)} → {len(tf)} · 추가 {len(added)} · 삭제 {len(deleted)}", flush=True)

    # 사진 합성 세트(사진 모드) — 거부는 전처리에서 나므로 두 파이프라인이 같다. 통과분의 추가 · 삭제 수
    print("\n## 사진 합성 세트 (사진 모드)\n")
    st = Counter()
    photo_dels = []
    for f in sorted(os.listdir(SYN)) + sorted(os.listdir(EDGE)):
        if not f.lower().endswith((".png", ".jpg")):
            continue
        full = os.path.join(SYN if os.path.exists(os.path.join(SYN, f)) else EDGE, f)
        rel = os.path.relpath(full, ROOT)
        try:
            res, sp, base, final, added, deleted = rescue_page(rel, 0, photo=True)
        except (P.PhotoRejectedError, P.StaffNotFoundError):
            st["거부 · 오선 실패"] += 1
            continue
        st["통과"] += 1
        st["추가"] += len(added)
        st["삭제"] += len(deleted)
        st["check 전"] += sum(1 for l in base if l["confidence"] == "check")
        st["check 후"] += sum(1 for l in final if l["confidence"] == "check")
        img = cv2.cvtColor(res.gray, cv2.COLOR_GRAY2BGR)       # 보정 뒤 영상 — 라벨 좌표가 이 기준
        photo_dels += [dict(path=rel, pg=0, img=img, sp=sp, page=f[:18], x=base[i]["x"], y=base[i]["y"],
                            kind="2b 삭제(사진)", truth="?", before=base[i]["text"], after="삭제") for i in deleted]
    print(dict(st))
    # 사진 모드 2b 삭제 확대(정답 없음 — 사진 모드 활성화 판단 자료, DECISIONS 1-9)
    out = os.path.join(ROOT, "docs", "review", "chord_rescue_photo")
    os.makedirs(out, exist_ok=True)
    crops("deleted", photo_dels, out_dir=out)
    print("사진 2b 삭제 그림:", len(photo_dels), "칸 →", out)


if __name__ == "__main__":
    if sys.argv[1] == "rescue":
        main_rescue()
        sys.exit()
    if sys.argv[1] == "v2":
        main_v2()
        sys.exit()
    if sys.argv[1] == "additive":
        main_additive()
        sys.exit()
    if sys.argv[1] == "holes":
        main_holes()
        sys.exit()
    if sys.argv[1] == "crops":
        redo_crops()
        sys.exit()
    if sys.argv[1] == "eval":
        main_eval(sys.argv[2:])
        sys.exit()
    if sys.argv[1] == "narrow":            # 3번 좁힘 — 3번(fill)과 함께 돌려 사라진 13의 화음 단위 분류도 낸다
        main_eval(["fill", "holefill"], out_dir=os.path.join(ROOT, "docs", "review", "fill_narrow"))
        sys.exit()
    {"sp": main_sp, "sweep": main_sweep, "report": lambda: report_sweep(json.load(open(SWEEP_JSON, encoding="utf-8")))}[sys.argv[1]]()
