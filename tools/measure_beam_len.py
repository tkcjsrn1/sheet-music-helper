# -*- coding: utf-8 -*-
"""[3] 빔 마스크 가로 열림 길이 2.5sp → L로 낮추면 빔 기반 판정 전체가 어떻게 바뀌나 (2026-10-12 · 측정만, 제품 코드 무변경).

배경: 16분음표 두 개를 잇는 짧은 겹빔(≈2.06~2.11sp)이 `verify.beam_mask` · `beam_mask_strict`의 가로 열림 2.5sp보다 짧아
빔 조건(`drop_beam_ghosts` 빔 위 · 빔 사이 · 한쪽만)과 G1(`sloped_beam_mask`의 바탕) · `diagnose_labels`의 빔 값이 못 본다(`docs/BEAMGAP_DYNAMIC.md`).
사본: 두 마스크 함수를 열림 길이만 L로 바꾼 같은 코드로 바꿔 끼운다(가로채기 — 제품 파일은 그대로). 라벨 = `main.run_page`.

라벨 단위(기준 = 같은 main 제품 라벨 `debug/sim_lp/<기준>`, 49쪽 · holdout 제외):
  사라진 라벨 → 정답 짝이 있던 라벨이고 그 머리에 남은 라벨이 없으면 **오삭제**, 짝 없던 라벨이면 **사라진 유령**
  새 라벨 → 정답 머리와 짝이고 기준에 그 머리 라벨이 없었으면 **되찾음**, 짝 없으면 **새 유령**
  같은 라벨의 확신도 변화는 따로 센다(빔 값이 `beam_adjacent` 등 신호에도 들어간다)

    python tools/measure_beam_len.py run 1.8        # debug/sim_lp/beamlen18/
    python tools/measure_beam_len.py judge 1.8 [기준=main1012]
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")
CUR = {}


def install(L):
    """`beam_mask` · `beam_mask_strict`를 열림 길이 L sp인 사본으로. 나머지 코드는 제품 그대로.
    BEAM_CONN=1이면 「빔에 닿음(한쪽만)」에 기둥 연결 조건을 더한 `drop_beam_ghosts` 사본도 끼운다(큐 5, 2026-10-13)."""
    if CUR.get("L") == L:
        return
    CUR["conn"] = os.environ.get("BEAM_CONN") == "1"
    import cv2
    import numpy as np
    import modules.verify as VF

    def beam_mask(binary, staves):
        sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
        no_staff = VF.remove_staff_lines(binary, staves)
        wide = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * L)), 1))
        horiz = cv2.morphologyEx(no_staff, cv2.MORPH_OPEN, wide)
        thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
        CUR["calls"] = CUR.get("calls", 0) + 1
        return cv2.morphologyEx(horiz, cv2.MORPH_OPEN, thick)

    def beam_mask_strict(binary, staves):
        sp = float(np.median([s.spacing for s in staves])) if staves else 12.0
        wide = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(sp * L)), 1))
        horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, wide)
        for staff in staves:
            for line_y in staff.line_ys:
                y0 = max(0, int(line_y) - int(sp * 0.22))
                horiz[y0:int(line_y) + int(sp * 0.22) + 1, :] = 0
        thick = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(2, int(sp * 0.35))))
        return cv2.morphologyEx(horiz, cv2.MORPH_OPEN, thick)

    VF.beam_mask, VF.beam_mask_strict = beam_mask, beam_mask_strict
    CUR["L"] = L
    if CUR.get("conn"):
        _orig = VF.drop_beam_ghosts.__wrapped__ if hasattr(VF.drop_beam_ghosts, "__wrapped__") else VF.drop_beam_ghosts

        def drop_beam_ghosts(result, noteheads):
            """「빔에 닿음(한쪽만)」으로 지워질 머리는 그 빔이 **이 머리의 것**일 때만 지운다 — 후보 자리에서 빔 쪽으로
            열마다(x ± 0.5sp) 오선 제거 영상을 따라가 잉크가 끊기지 않고(흰 틈 < 0.15sp) 좁은 빔 마스크에 닿는 열이 있어야 한다."""
            kept, dropped = _orig(result, noteheads)
            ns = VF.remove_staff_lines(result.binary, result.staves) > 0
            narrow = VF.beam_mask_strict(result.binary, result.staves) > 0
            by = {s.index: s for s in result.staves}
            back, still = [], []
            heads = {(int(h.x), int(h.y), h.staff_index): h for h in noteheads}
            for d in dropped:
                if d["reason"] != "빔에 닿음":
                    still.append(d)
                    continue
                sp = by[d["staff"]].spacing
                x, y = d["x"], d["y"]
                conn = False
                H = ns.shape[0]
                for step in (-1, 1):
                    y0, y1 = (y - int(sp * 1.3), y - int(sp * 0.2)) if step < 0 else (y + int(sp * 0.2), y + int(sp * 1.3))
                    if not narrow[max(0, y0):max(0, y1), max(0, x - int(sp * 0.5)):x + int(sp * 0.5) + 1].any():
                        continue
                    for c in range(max(0, x - int(sp * 0.5)), x + int(sp * 0.5) + 1):
                        r, gap = y, 0
                        while 0 <= r < H and abs(r - y) <= sp * 1.3:
                            if narrow[r, c]:
                                conn = True
                                break
                            gap = 0 if ns[r, c] else gap + 1
                            if gap >= max(2, int(sp * 0.15)) and abs(r - y) > sp * 0.3:
                                break
                            r += step
                        if conn:
                            break
                    if conn:
                        break
                CUR.setdefault("conn_log", []).append((x, y, conn))
                (still if conn else back).append(d)
            back_ids = {id(heads[(d["x"], d["y"], d["staff"])]) for d in back if (d["x"], d["y"], d["staff"]) in heads}
            keep_ids = {id(h) for h in kept} | back_ids
            return [h for h in noteheads if id(h) in keep_ids], still     # 원래 순서 유지
        drop_beam_ghosts.__wrapped__ = _orig
        VF.drop_beam_ghosts = drop_beam_ghosts


def name(L):
    return "beamlen" + str(L).replace(".", "") + ("c" if os.environ.get("BEAM_CONN") == "1" else "")


def _one(job):
    L, (st, nm, path, pg) = job
    install(L)
    import io
    import contextlib
    import shutil
    import main as MAIN
    js = os.path.join(LP, name(L), nm + ".json")
    if os.path.exists(js):
        return -1
    os.makedirs(os.path.dirname(js), exist_ok=True)
    tmp = os.path.join(ROOT, "debug", "_beamlen_png", nm)
    os.makedirs(tmp, exist_ok=True)
    CUR["calls"] = 0
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js]
    with contextlib.redirect_stdout(io.StringIO()):
        MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    return CUR["calls"]


def run(L):
    import measure_sim_ledger_pair as S
    L = float(L)
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        res = list(ex.map(_one, [(L, p) for p in S.pages()]))
    print(name(L), "쪽", len(res), "· 가로채기 호출 0인 쪽", sum(c == 0 for c in res), "(측정 함정 B-4: 0이면 사본이 안 걸린 것)")


def _judge(job):
    L, base, (st, nm, path, pg) = job
    import measure_sim_ledger_pair as S
    A = json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]
    Bn = json.load(open(os.path.join(LP, name(L), nm + ".json"), encoding="utf-8"))["labels"]
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"])
    KA, KB = {key(l): l for l in A}, {key(l): l for l in Bn}
    gone, new = [KA[k] for k in KA.keys() - KB.keys()], [KB[k] for k in KB.keys() - KA.keys()]
    c, items = Counter(), []
    conf = Counter((KA[k]["confidence"], KB[k]["confidence"]) for k in KA.keys() & KB.keys() if KA[k]["confidence"] != KB[k]["confidence"])
    if st == "aoharu":       # 정답 골든 — 라벨 그대로가 정답
        c["오삭제"] += len(gone)
        c["새 유령"] += len(new)
        items += [("오삭제", nm, l["x"], l["y"], l["text"]) for l in gone] + [("새 유령", nm, l["x"], l["y"], l["text"]) for l in new]
        return st, nm, c, conf, items
    heads, sp = S._truth(st, nm, path, pg)
    near = lambda l, h: abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp
    for l in gone:
        h = [q for q in heads if near(l, q)]
        if not h:
            k = "사라진 유령"
        elif any(near(m, h[0]) for m in Bn):
            k = "사라짐 · 같은 머리 다른 라벨 남음"
        else:
            k = "오삭제"
        c[k] += 1
        items.append((k, nm, l["x"], l["y"], l["text"]))
    for l in new:
        h = [q for q in heads if near(l, q)]
        k = "새 유령" if not h else ("새 라벨 · 이미 라벨 있던 머리" if any(near(m, h[0]) for m in A) else "되찾음")
        c[k] += 1
        items.append((k, nm, l["x"], l["y"], l["text"]))
    return st, nm, c, conf, items


def judge(L, base="main1012"):
    import measure_sim_ledger_pair as S
    L = float(L)
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        res = list(ex.map(_judge, [(L, base, p) for p in S.pages()]))
    tot = {}
    for st, nm, c, conf, items in res:
        tot.setdefault(st, [Counter(), Counter()])
        tot[st][0].update(c)
        tot[st][1].update(conf)
    for st, (c, conf) in tot.items():
        print(f"{st:8s} {dict(c)} · 확신도 변화 {dict(conf)}")
    allc = sum((v[0] for v in tot.values()), Counter())
    print("합계", dict(allc))
    bad = [i for _s, _n, _c, _f, it in res for i in it if i[0] == "오삭제"]
    print("오삭제 목록", bad)
    json.dump([i for _s, _n, _c, _f, it in res for i in it], open(os.path.join(ROOT, "debug", f"beamlen_{name(L)}.json"), "w", encoding="utf-8"),
              ensure_ascii=False)


if __name__ == "__main__":
    {"run": run, "judge": judge}[sys.argv[1]](*sys.argv[2:])
