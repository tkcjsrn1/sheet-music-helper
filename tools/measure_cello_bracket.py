# -*- coding: utf-8 -*-
"""(e) 베토벤 첼로 괄호 — 「높은음으로 읽힌 보표」를 check로 내리는 표시안의 신호 측정 (2026-10-13 야간 · 측정만, 구현 안 함, 보류 세트 미사용).

틀린 두 보표(Bravura 보표 3 · 11)는 음자리표 칸이 현악 4중주 괄호에서 시작해 괄호 끝 갈고리가 「아래 꼬리」로 세어졌다(`CLEF_TAIL.md`).
높은음으로 읽힌 보표마다 값만 기록:
  below_pos  아래 꼬리 행 잉크의 가로 무게중심 — 칸 안 상대 위치(0 = 칸 왼끝, 1 = 오른끝)
  left_ext   칸 왼끝 0.3sp 열들에서 이어진 세로 잉크 최대 길이(sp) — 괄호면 보표 높이(4sp)를 크게 넘는다
  below_left 아래 꼬리 잉크 중 칸 왼쪽 25% 열에 있는 비율

    python tools/measure_cello_bracket.py
"""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def _job(job):
    import measure_clef_tail as T
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves, CLEF_MIN_WIDTH_SP
    from modules.notehead_detect import remove_staff_lines
    kind, name, path, pg = job
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves) > 0
    H = ns.shape[0]
    staves = sorted(res.staves, key=lambda s: s.top)
    kinds = T._truth_kinds(kind, name, path, pg, staves)
    out = []
    for i, st in enumerate(staves):
        c = ctx.get(st.index)
        if c is None or not c.clef_found or c.clef != "treble":
            continue
        sp = st.spacing
        xs, xe = c.clef_start, max(c.clef_end, c.clef_start + int(sp * CLEF_MIN_WIDTH_SP))
        b0, b1 = int(st.bottom + sp * 0.4), min(H, int(st.bottom + sp * 2.5))
        win = ns[b0:b1, xs:xe]
        cols = np.where(win.any(axis=0))[0]
        w = xe - xs
        below_pos = float((np.nonzero(win)[1].mean()) / w) if win.any() else None
        below_left = float(win[:, :max(1, w // 4)].sum() / max(1, win.sum()))
        left = 0
        for x in range(xs, min(xe, xs + int(sp * 0.3) + 1)):
            col = ns[:, x]
            y = int((st.top + st.bottom) / 2)
            a = b = y
            if not col[y]:
                continue
            while a > 0 and col[a - 1]: a -= 1
            while b + 1 < H and col[b + 1]: b += 1
            left = max(left, b - a + 1)
        out.append(dict(set=kind, page=name, order=i, truth=kinds[i], below_pos=None if below_pos is None else round(below_pos, 3),
                        below_left=round(below_left, 3), left_ext=round(left / sp, 2)))
    return out


if __name__ == "__main__":
    import check_accidental_fix as C, measure_a17_ghost6 as G
    jobs = [("pdf", n, p, pg) for n, p, pg in C.PAGES if p.endswith(".pdf")] + [("unseen", n, p, pg) for n, p, pg in G.UNSEEN]
    V = os.path.join("test_scores", "verovio")
    jobs += [("verovio", f[:-4], os.path.join(V, f), 0) for f in sorted(os.listdir(os.path.join(ROOT, V))) if f.endswith("_p1.png")]
    with ProcessPoolExecutor(2) as ex:
        R = [r for part in ex.map(_job, jobs) for r in part]
    json.dump(R, open(os.path.join(ROOT, "debug", "cello_bracket.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ok = [r for r in R if r["truth"] == "treble"]; bad = [r for r in R if r["truth"] == "bass"]
    for k in ("below_pos", "below_left", "left_ext"):
        v = np.array([r[k] for r in ok if r[k] is not None])
        print(f"{k}: 맞게 읽은 높은음 {len(v)} · 최소 {v.min():.2f} · 5% {np.percentile(v, 5):.2f} · 중앙 {np.median(v):.2f} · 95% {np.percentile(v, 95):.2f} · 최대 {v.max():.2f} | 틀린 보표 {[(r['page'][:22], r['order'], r[k]) for r in bad]}")
    print("정답 없음(오르간 등)", [(r["page"], r["order"]) for r in R if r["truth"] is None][:10])
