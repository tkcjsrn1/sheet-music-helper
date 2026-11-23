# -*- coding: utf-8 -*-
"""TASKS [3] / A-16 고해상도 입력 축소 사본 측정 (2026-09-30, 제품 코드 무변경).

범위 밖(sp가 경계 B보다 큰) 입력만 검증된 해상도(300dpi, sp 19.4)로 줄여 제품에 넣는다. 범위 안은 원본을 그대로 넘긴다.
기각 25(4번 정규화)와 다른 점: 그것은 300dpi 입력을 sp 17~18로 **줄여** 오삭제 71을 냈다 — 여기서는 300dpi 이하를 **건드리지 않는다**.

- sp 추정: 제품 전처리 1회차(`preprocess`) sp, 실패(오선 못 찾음)면 전역 Otsu sp(`measure_normalize_sp.otsu_sp`, PDF 오차 ≤1.3%)
- 평가: `measure_normalize_sp`의 dpi 스윕과 같은 함수(`truth_at` · `evaluate` · `product_labels`) — 같은 표에 나란히 놓인다
- 축소 뒤 좌표계에서 잰다(정답도 같은 배율)

    python tools/measure_hires_downscale.py run <dpi> [<dpi>...]     → debug/hires_downscale_<dpi>.json
    python tools/measure_hires_downscale.py identity                   → 300dpi 17쪽이 원본 그대로 넘어가는지(범위 안 무변경)
    python tools/measure_hires_downscale.py report
"""
import json
import os
import sys
import tempfile

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import measure_normalize_sp as N  # noqa: E402

P, C = N.P, N.C
SP_TARGET = 19.4          # 300dpi PDF 17쪽 sp 중앙(`NORMALIZE_SP_MEASURE.md` §2) — 제품 문턱이 유도된 해상도
OUT = os.path.join(ROOT, "debug", "hires_downscale_{}.json")      # dpi별 — 병렬 실행이 한 파일을 덮지 않게
PAGES = [p for p in C.PAGES if not p[0].startswith("aoharu")]


def estimate_sp(path, pg, dpi):
    """(sp, 원본 res 또는 None, 출처)."""
    try:
        res = P.preprocess(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi)
        return N.np.median([s.spacing for s in res.staves]), res, "제품"
    except P.StaffNotFoundError:
        bgr = P.load_image(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi)
        sp, _n = N.otsu_sp(bgr)                           # (sp, 보표 수), 못 재면 (None, 0)
        if sp is None:
            raise
        return sp, None, "Otsu"


def downscaled(path, pg, dpi, bound):
    """경계 밖이면 줄인 res, 안이면 원본 res. (res, 배율, sp 원래, 출처)."""
    sp0, res0, src = estimate_sp(path, pg, dpi)
    if sp0 <= bound and res0 is not None:
        return res0, 1.0, sp0, src                       # 범위 안 — 원본 그대로(같은 객체)
    f = SP_TARGET / sp0
    bgr = res0.original_bgr if res0 is not None else P.load_image(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=dpi)
    small = cv2.resize(bgr, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    tmp = os.path.join(tempfile.gettempdir(), f"_hires_{os.getpid()}.png")
    open(tmp, "wb").write(cv2.imencode(".png", small)[1].tobytes())
    return P.preprocess(tmp), f, sp0, src


def run(dpis, bound=0.0):
    """bound=0이면 모든 입력을 줄인다(경계 유도용 — 축소가 어느 sp부터 이득인지)."""
    for dpi in dpis:
        out = OUT.format(dpi)
        done = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}
        for name, path, pg in PAGES:
            key = f"{name}@{dpi}"
            if key in done:
                continue
            try:
                res, f, sp0, src = downscaled(path, pg, dpi, bound)
            except P.StaffNotFoundError:
                heads, _c = N.truth_at(path, pg, dpi / 300.0)
                done[key] = {"오선 실패": 1, "전체 · 정답": len(heads), "전체 · 누락": len(heads), "짝 없는 라벨": 0, "라벨": 0, "보표": 0}
                print(key, "축소 뒤에도 오선 실패", flush=True)
            else:
                heads, clefs = N.truth_at(path, pg, dpi / 300.0 * f)
                done[key] = dict(N.evaluate(res, N.product_labels(res, path, pg), heads, clefs), 배율=f, sp원래=float(sp0), sp출처=src)
                print(key, "배율", round(f, 3), src, {k: v for k, v in done[key].items() if "누락" in k}, flush=True)
            json.dump(done, open(out, "w", encoding="utf-8"), ensure_ascii=False)


def identity(bound):
    """범위 안(300dpi 17쪽)은 제품에 넘기는 res가 원본 그대로인가 — 배율 1 · 같은 이진 영상 바이트."""
    bad = []
    for name, path, pg in PAGES:
        res, f, sp0, _src = downscaled(path, pg, 300, bound)
        ref = P.preprocess(os.path.join(ROOT, path), pdf_page=pg)
        same = f == 1.0 and res.binary.tobytes() == ref.binary.tobytes() and res.original_bgr.tobytes() == ref.original_bgr.tobytes()
        print(name, "sp", round(float(sp0), 2), "배율", f, "바이트 같음" if same else "다름", flush=True)
        if not same:
            bad.append(name)
    print("범위 안 무변경:", "17/17" if not bad else f"다름 {bad}")


def head_rows(res, labels, heads, clefs, scale):
    """정답 머리마다 (300dpi 좌표 키, 정답 음고, 라벨 음고 또는 None, 보표, 반칸 위치 k, 머리 y의 보표 기준 반칸 잔차)."""
    M = N.M
    sp = float(N.np.median([s.spacing for s in res.staves]))
    for c in clefs:
        c["staff"] = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - c["cy"])).index
    pairs, _t, _l = M.match(heads, labels, sp)
    h2l = dict(pairs)
    out = {}
    for i, h in enumerate(heads):
        st_i, want, step, kind = M.truth_pitch(h["cx"], h["cy"], res.staves, clefs)
        st = next(s for s in res.staves if s.index == st_i)
        half = (st.line_ys[-1] - h["cy"]) / (st.spacing / 2.0)                 # 반칸 단위 위치(정수면 딱 맞음)
        got = labels[h2l[i]]["pitch"] if i in h2l else None
        key = (round(h["cx"] / scale), round(h["cy"] / scale))
        out[key] = dict(want=want, got=got, staff=st_i, k=step, resid=round(half - step, 2), sp=round(st.spacing, 2),
                        lab_y=round(labels[h2l[i]]["y"] / scale, 1) if i in h2l else None, head_y=round(h["cy"] / scale, 1),
                        hollow=h["name"] in ("noteheads.s1", "noteheads.s0"), kind=kind)
    return out


def pitchdiff(dpi):
    """고해상도 그대로는 음고가 맞고 축소하면 틀리는 머리 — 300dpi 원본에서도 틀리는지 함께(좌표는 300dpi 기준)."""
    rows = []
    for name, path, pg in PAGES:
        per = {}
        for tag, d in (("native", dpi), ("down", dpi), ("n300", 300)):
            if tag == "down":
                res, f, _sp0, _src = downscaled(path, pg, dpi, 0.0)
            else:
                res, f = P.preprocess(os.path.join(ROOT, path), pdf_page=pg, pdf_dpi=d), 1.0
            scale = d / 300.0 * f
            heads, clefs = N.truth_at(path, pg, scale)
            per[tag] = head_rows(res, N.product_labels(res, path, pg), heads, clefs, scale)
        for key, dn in per["down"].items():
            nt, n3 = per["native"].get(key), per["n300"].get(key)
            if dn["got"] is None or dn["got"] == dn["want"]:
                continue                                                   # 축소에서 음고가 틀린 머리만
            ns = "없음(정답 대응 안 됨)" if not nt else "누락" if nt["got"] is None else "맞음" if nt["got"] == nt["want"] else "틀림"
            s3 = "없음" if not n3 else "누락" if n3["got"] is None else "맞음" if n3["got"] == n3["want"] else "틀림"
            rows.append(dict(page=name, xy300=key, want=dn["want"], down_got=dn["got"], native=ns, n300=s3,
                             n300_got=n3["got"] if n3 else None, down=dn, native_row=nt))
        mine = [r for r in rows if r["page"] == name]
        print(name, "축소 음고 틀림", len(mine), "— 고해상도 그대로:",
              {k: sum(1 for r in mine if r["native"] == k) for k in ("맞음", "틀림", "누락")}, flush=True)
    json.dump(rows, open(os.path.join(ROOT, "debug", f"hires_pitchdiff_{dpi}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)


def report():
    import glob
    done = {}
    for f in glob.glob(OUT.format("*")):
        done.update(json.load(open(f, encoding="utf-8")))
    base = json.load(open(N.SWEEP_JSON, encoding="utf-8"))
    cats = ["화음", "단일", "빈 머리", "덧줄 구역", "전체"]
    b300 = {k.split("@")[0]: v["보표"] for k, v in base.items() if k.endswith("@300")}
    print("| dpi | 입력 | " + " | ".join(f"{c} 누락" for c in cats) + " | 음고 틀림 | 짝 없는 라벨 | 보표 수 다름 · 오선 실패 |")
    print("|---:|---|" + "---:|" * (len(cats) + 3))
    for dpi in sorted({int(k.split("@")[1]) for k in list(done) + list(base)}):
        for tag, src in (("그대로", base), ("축소", done)):
            rs = {k: v for k, v in src.items() if k.endswith(f"@{dpi}")}
            if not rs:
                continue
            cells = []
            for c in cats:
                m, t = sum(v.get(c + " · 누락", 0) for v in rs.values()), sum(v.get(c + " · 정답", 0) for v in rs.values())
                cells.append(f"{m / max(1, t) * 100:.1f}%")
            stv = sum(1 for k, v in rs.items() if v["보표"] != b300.get(k.split("@")[0]))
            print(f"| {dpi} | {tag} | " + " | ".join(cells) + f" | {sum(v.get('전체 · 음고', 0) for v in rs.values())} | "
                  f"{sum(v['짝 없는 라벨'] for v in rs.values())} | {stv} · {sum(v.get('오선 실패', 0) for v in rs.values())} |")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        run([int(d) for d in sys.argv[2:]])
    elif cmd == "base":                                   # 축소 없이(스윕에 없는 dpi 채우기) — measure_normalize_sp 스윕과 같은 JSON에
        N.SWEEP_DPI[:] = [int(d) for d in sys.argv[2:]]
        N.main_sweep()
    elif cmd == "pitchdiff":
        pitchdiff(int(sys.argv[2]))
    elif cmd == "identity":
        identity(float(sys.argv[2]))
    else:
        report()
