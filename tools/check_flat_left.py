# -*- coding: utf-8 -*-
"""[B] ♭ 판정 「막대가 고리 왼쪽」(§1-21 후보) 구현 판정 — 직전 main(`debug/sim_lp/gshape`) ↔ 구현 뒤(`debug/sim_lp/flatleft`). 제품 코드 무변경.

정답: Verovio SVG(음고 · 실효 임시표), PDF · 보지 않은 악보 = `measure_pdf_effective`(`measure_certain_errors._truth`). 오르간 2쪽은 정답 좌표가 안 맞아 수만 센다.
  사라진 라벨 → 진짜 머리(다른 라벨 없음) = 오삭제 / 유령
  새 라벨 → 진짜 머리(그 머리에 라벨 없었음) = 되살아남 / 유령 = 새 유령 — 격자 그림 docs/review/flat_left/new_labels.png
  같은 자리 라벨의 표기 변화 → 고쳐짐(틀림 → 맞음) / 망가짐(맞음 → 틀림) / 틀림 → 틀림
  2도 빈 머리 쌍(정답 빈 머리 둘 · |dx| ≤ 1.5sp · |dy| 0.35~0.65sp) 13곳 — 구현 뒤 두 머리 모두 라벨이 있나

    python tools/check_flat_left.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""
HOLLOW_V = ("E0A3", "E0A2", "E0A0")


def _one(job):
    import measure_sim_ledger_pair as S
    from measure_certain_errors import _truth
    st, name, path, pg = job
    A = json.load(open(os.path.join(S.OUT, "gshape", name + ".json"), encoding="utf-8"))["labels"]
    B = json.load(open(os.path.join(S.OUT, "flatleft", name + ".json"), encoding="utf-8"))["labels"]
    pos = lambda l: (l["staff"], l["x"], l["y"])
    Ap, Bp = {pos(l): l for l in A}, {pos(l): l for l in B}
    c, pics = Counter(), []
    gone, new = [Ap[k] for k in Ap.keys() - Bp.keys()], [Bp[k] for k in Bp.keys() - Ap.keys()]
    if st == "aoharu" or name == "organ2":
        c["사라짐(정답 없음)"] += len(gone)
        c["생김(정답 없음)"] += len(new)
        c["표기 바뀜(정답 없음)"] += sum(ACC(Ap[k]["text"]) != ACC(Bp[k]["text"]) for k in Ap.keys() & Bp.keys())
        return st, name, c, pics, []
    heads, sp = _truth("verovio" if st == "verovio" else "pdf", name, path, pg)
    near = lambda l, h: abs(h[0] - l["x"]) <= 0.7 * sp and abs(h[1] - l["y"]) <= 0.5 * sp
    for l in gone:
        h = [q for q in heads if near(l, q)]
        c["사라짐 · 유령" if not h else "사라짐 · 같은 머리 다른 라벨" if any(near(m, h[0]) for m in B) else "오삭제"] += 1
        if h and not any(near(m, h[0]) for m in B):
            pics.append(dict(name=name, st=st, x=l["x"], y=l["y"], kind="오삭제"))
    for l in new:
        h = [q for q in heads if near(l, q)]
        k = "새 유령" if not h else "새 라벨 · 이미 라벨 있던 머리" if any(near(m, h[0]) for m in A) else "되살아남"
        c[k] += 1
        pics.append(dict(name=name, st=st, x=l["x"], y=l["y"], kind=k))
    for k in Ap.keys() & Bp.keys():
        a, b = Ap[k], Bp[k]
        if ACC(a["text"]) == ACC(b["text"]):
            continue
        h = [q for q in heads if near(a, q)]
        if not h:
            c["표기 바뀜 · 유령"] += 1
            continue
        ok_a = a["pitch"] == h[0][2] and ACC(a["text"]) == h[0][3]
        ok_b = b["pitch"] == h[0][2] and ACC(b["text"]) == h[0][3]
        c["표기 고쳐짐" if ok_b and not ok_a else "표기 망가짐" if ok_a and not ok_b else "표기 틀림 → 틀림"] += 1
    # 2도 빈 머리 쌍
    pairs = []
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
        hol = [(n["x"], n["y"]) for n in t["notes"] if n["glyph"] in HOLLOW_V]
    else:
        from measure_normalize_sp import truth_at
        hol = [(h["cx"], h["cy"]) for h in truth_at(path, pg, 1.0)[0] if h["name"] in ("noteheads.s1", "noteheads.s0")]
    for i, a in enumerate(hol):
        for b in hol[i + 1:]:
            if abs(a[0] - b[0]) <= 1.5 * sp and 0.35 * sp <= abs(a[1] - b[1]) <= 0.65 * sp:
                has = [any(near(m, q) for m in B) for q in (a, b)]
                had = [any(near(m, q) for m in A) for q in (a, b)]
                pairs.append(dict(name=name, a=[round(a[0]), round(a[1])], b=[round(b[0]), round(b[1])], before=had, after=has))
    return st, name, c, pics, pairs


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(3) as ex:
        res = list(ex.map(_one, S.pages()))
    tot = Counter()
    pics, pairs = [], []
    for st, name, c, p, q in res:
        tot.update({f"{st} {k}": v for k, v in c.items()})
        pics += p
        pairs += q
    for k in sorted(tot):
        print(k, tot[k])
    print("2도 빈 머리 쌍", len(pairs))
    for q in pairs:
        print("  ", q["name"], q["a"], q["b"], "전", q["before"], "→ 후", q["after"])
    for p in pics:
        if p["kind"] in ("오삭제", "되살아남", "새 유령"):
            print("  ", p["kind"], p["name"], p["x"], p["y"])
    json.dump(dict(tot=dict(tot), pics=pics, pairs=pairs), open(os.path.join(ROOT, "debug", "flat_left.json"), "w", encoding="utf-8"), ensure_ascii=False)
    _grid([p for p in pics if p["kind"] in ("되살아남", "새 유령", "오삭제")])


def _grid(pics):
    import cv2
    import numpy as np
    import measure_sim_ledger_pair as S
    from modules.preprocess import load_image
    P = {n: (st, p, g) for st, n, p, g in S.pages()}
    tiles = []
    for p in pics[:40]:
        st, path, pg = P[p["name"]]
        im = load_image(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else cv2.imdecode(np.fromfile(os.path.join(ROOT, path), np.uint8), cv2.IMREAD_COLOR)
        R = 44
        x, y = p["x"], p["y"]
        t = im[max(0, y - R):y + R, max(0, x - R):x + R].copy()
        t = cv2.copyMakeBorder(t, 0, 2 * R - t.shape[0], 0, 2 * R - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.circle(t, (R, R), 10, (0, 160, 0) if p["kind"] == "되살아남" else (0, 0, 255), 1)
        t = cv2.copyMakeBorder(cv2.resize(t, (150, 150)), 14, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(t, {"되살아남": "REVIVED", "새 유령": "NEW GHOST", "오삭제": "WRONG DEL"}[p["kind"]] + " " + p["name"][:12], (2, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 0, 0), 1)
        tiles.append(t)
    if not tiles:
        return
    while len(tiles) % 6:
        tiles.append(np.full_like(tiles[0], 255))
    os.makedirs(os.path.join(ROOT, "docs", "review", "flat_left"), exist_ok=True)
    g = np.vstack([np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)])
    open(os.path.join(ROOT, "docs", "review", "flat_left", "new_labels.png"), "wb").write(cv2.imencode(".png", g)[1].tobytes())


if __name__ == "__main__":
    main()
