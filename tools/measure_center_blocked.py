# -*- coding: utf-8 -*-
"""큐 1 후속 — 꽉 찬 덩어리에 가려진 구멍 전부(Verovio 개발 20쪽)의 위치를 진짜 빈 머리 / 가짜로 나눠 잰다 (2026-10-19 · 측정만).

가려진 구멍 = `trace_hollow_path` 기록 사본의 hollow_candidates 중 가린 항목(blocker)이 끝까지 남은 것.
진짜 = 구멍 중심 가로 0.7sp · 세로 0.5sp 안에 정답 빈 머리(E0A2 · E0A3). 값: 가린 덩어리 중심에서 구멍 중심까지 dx · dy(sp) · 덩어리 높이(sp) ·
덩어리 중심 행의 가로 런(오선 제거 영상, 덩어리 중심 ±1.5sp 안 최장 — 덧줄이면 LEDGER_RUN_SP 1.30 이상).

    python tools/measure_center_blocked.py      # → debug/center_blocked.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)


def main():
    import trace_hollow_path as T
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import remove_staff_lines
    D = os.path.join(ROOT, "debug", "vrv", "truth")
    out = []
    for f in sorted(os.listdir(D)):
        nm = f[:-5]
        tn = [n for n in json.load(open(os.path.join(D, f), encoding="utf-8"))["notes"] if n["glyph"] in ("E0A2", "E0A3")]
        res = preprocess(os.path.join(ROOT, "test_scores", "verovio", nm + ".png"))
        T.DBG._DBG.clear()
        T.DBG.detect_noteheads(res, contexts=analyze_staves(res))
        ns = remove_staff_lines(res.binary, res.staves) > 0
        for d in T.DBG._DBG:
            sp = d["sp"]
            for cx, cy, bk, h0, h1 in d["cands"]:
                if bk is None:
                    continue
                blk = d["raw_before"][bk]
                if not any(abs(r[0] - blk[0]) < 0.5 and abs(r[1] - blk[1]) < 0.5 for r in d["raw_after"]):
                    continue        # 가린 덩어리가 링 조각으로 지워짐 → 구멍 채택
                true = any(abs(n["x"] - cx) <= 0.7 * sp and abs(n["y"] - cy) <= 0.5 * sp for n in tn)
                row = ns[int(round(blk[1])), max(0, int(blk[0] - 1.5 * sp)):int(blk[0] + 1.5 * sp)]
                run = best = 0
                for v in row:
                    run = run + 1 if v else 0
                    best = max(best, run)
                out.append(dict(page=nm, x=round(cx), y=round(cy), true=true, dx=round(float(cx - blk[0]) / sp, 2),
                                dy=round(float(cy - blk[1]) / sp, 2), bh=round(float(blk[4] - blk[3]) / sp, 2), run=round(best / sp, 2)))
        print(nm, len(out), flush=True)
    json.dump(out, open(os.path.join(ROOT, "debug", "center_blocked.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for lim in (0.1, 0.2, 0.3):
        c = [o for o in out if abs(o["dx"]) <= lim and abs(o["dy"]) <= lim]
        t, fk = [o["run"] for o in c if o["true"]], [o["run"] for o in c if not o["true"]]
        print(f"중심 창 {lim}sp: 진짜 {len(t)} 런 {sorted(t)[:3]} · 가짜 {len(fk)} 런 최대 {sorted(fk)[-3:]}")


if __name__ == "__main__":
    main()
