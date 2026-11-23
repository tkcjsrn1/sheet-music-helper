# -*- coding: utf-8 -*-
"""[6] 흐린 인쇄(`measure_robustness` faded — 잉크 대비 0.55)에서 사라지는 머리가 어느 단계에서 빠지나. 제품 코드 무변경.

현재 main 제품 단계를 원본 · 흐린 영상 각각에 같은 순서로 돌린다(`measure_missing_verovio._stages`와 같은 단계 — 두 검출 경로 base · rescue):
  이진화 → 머리 검출(reject_log 사유 기록) → 빔 유령 필터 → 보표 밖 유령 필터 → 음고 → 임시표 유령 필터 = 최종.
원본 최종 머리마다 흐린 쪽에서의 운명을 0.5sp 안 짝으로 가른다:
  남음 / 임시표 유령 필터 / 보표 밖 유령 필터 / 빔 유령 필터 / 검출 내부 필터(사유) / 머리 후보 없음(이진화 잉크 부족 < 0.25 · 모양 판정).
이진화 잉크 = 그 자리 ±0.4sp × ±0.55sp의 흐린 영상 이진화 잉크 비율. 원본 쪽 그 머리가 빈 머리였는지 꽉 찬 머리였는지 · 흐린 쪽 판정도 남긴다.

    python tools/measure_faded_stages.py
"""
import os
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def stages(path_png):
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from modules.notehead_detect import detect_noteheads
    from modules.chord_rescue import detect_noteheads_rescue
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts, filled_flags
    res = preprocess(path_png)
    ctx = analyze_staves(res)
    clef = {i: c.clef for i, c in ctx.items()}
    out = {}
    for tag, det in (("base", detect_noteheads), ("rescue", detect_noteheads_rescue)):
        rej = []
        heads = det(res, contexts=ctx, reject_log=rej)
        out[tag + "_det"] = [(h.x, h.y, h.filled) for h in heads]
        out[tag + "_rej"] = [(r["x"], r["y"], r["reason"]) for r in rej]
        h1, _ = drop_beam_ghosts(res, heads)
        out[tag + "_beam"] = [(h.x, h.y) for h in h1]
        h2, _ = drop_offstaff_ghosts(res, h1)
        out[tag + "_off"] = [(h.x, h.y) for h in h2]
        notes = calculate_pitches(h2, res.staves, clef=clef)
        accs = annotate_accidentals(res, ctx, notes)
        kept, _a = remove_accidental_ghosts(notes, accs, res.staves, filled=filled_flags(notes, h2), result=res)
        out[tag + "_final"] = [(n.x, n.y) for n in kept]
    out["sp"] = float(np.median([s.spacing for s in res.staves]))
    return out, res.binary


def _page(job):
    import measure_robustness as R
    from modules.preprocess import load_image
    name, path, pg = job
    src = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
    tmp = tempfile.mkdtemp(prefix="faded_")
    got = {}
    for v in ("base", "faded"):
        f = os.path.join(tmp, v + ".png")
        open(f, "wb").write(cv2.imencode(".png", R.VARIANTS[v](src))[1].tobytes())
        got[v] = stages(f)
        os.remove(f)
    os.rmdir(tmp)
    (A, _ba), (B, bb) = got["base"], got["faded"]
    sp = A["sp"]
    near = lambda lst, x, y, r=0.5: [t for t in lst if abs(t[0] - x) <= r * sp and abs(t[1] - y) <= r * sp]
    c = Counter()
    for x, y in A["base_final"] + [p for p in A["rescue_final"] if not near(A["base_final"], *p)]:
        hollow = any(not f for _x, _y, f in near(A["base_det"] + A["rescue_det"], x, y))
        if near(B["base_final"], x, y) or near(B["rescue_final"], x, y):
            fate = "남음"
        elif near(B["base_off"], x, y) or near(B["rescue_off"], x, y):
            fate = "임시표 유령 필터"
        elif near(B["base_beam"], x, y) or near(B["rescue_beam"], x, y):
            fate = "보표 밖 유령 필터"
        elif near(B["base_det"], x, y) or near(B["rescue_det"], x, y):
            d = near(B["base_det"] + B["rescue_det"], x, y)
            fate = "빔 유령 필터" + (" (흐린 쪽 빈 머리)" if any(not f for *_xy, f in d) else "")
        elif near(B["base_rej"] + B["rescue_rej"], x, y):
            fate = "검출 내부 필터(" + near(B["base_rej"] + B["rescue_rej"], x, y)[0][2] + ")"
        else:
            box = bb[int(y - 0.4 * sp):int(y + 0.4 * sp), int(x - 0.55 * sp):int(x + 0.55 * sp)]
            fate = "머리 후보 없음 · " + ("이진화 잉크 부족" if (float((box > 0).mean()) if box.size else 0) < 0.25 else "모양 판정")
        c[(fate, "원본 빈 머리" if hollow else "원본 꽉 찬 머리")] += 1
    # 흐린 쪽에서 빈 머리로 판정된 수 — 꽉 찬 머리가 빈 머리로 바뀌는 사슬
    c[("(흐린 쪽 빈 머리 판정 수)", "")] = sum(not f for *_xy, f in B["base_det"])
    c[("(원본 빈 머리 판정 수)", "")] = sum(not f for *_xy, f in A["base_det"])
    return name, c


def main():
    import measure_robustness as R
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_page, R.pages()))
    tot = {"pdf": Counter(), "verovio": Counter()}
    for name, c in res:
        tot["verovio" if name.endswith("_p1") else "pdf"].update(c)
    for st, c in tot.items():
        n = sum(v for (f, _k), v in c.items() if not f.startswith("("))
        print(f"== {st}: 원본 최종 머리 {n} · 흐린 쪽에서 사라짐 {n - sum(v for (f, _k), v in c.items() if f == '남음')}")
        for (f, k), v in sorted(c.items(), key=lambda t: -t[1]):
            if f != "남음":
                print(f"   {f} · {k}: {v}")


if __name__ == "__main__":
    main()
