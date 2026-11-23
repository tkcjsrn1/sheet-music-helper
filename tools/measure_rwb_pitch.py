# -*- coding: utf-8 -*-
"""[3] 링 벽 B안(`claude/ring-wall-keep-b`, 라벨 debug/sim_lp/rwB)이 되찾은 머리의 음고 틀림 · 중복 경로. 제품 코드 무변경.

기준 = debug/sim_lp/nograce(지금 main과 라벨 집합 같음). 새 라벨 중
  음고 틀림: 정답 음과의 반칸 차, 라벨 y − 정답 y(sp), 그 라벨 표시(clef_changed · clef_alto 등) — 음자리표인가 좌표인가.
  중복: 같은 정답 머리에 이미 있던 라벨과의 dx · dy(sp), 그 라벨 · 새 라벨의 음 — 링 벽이 빈 머리 자기 벽인가(같은 음 · dx < 0.8sp).

    python tools/measure_rwb_pitch.py
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

DIRS = tuple(os.environ.get("RWB_DIRS", "nograce,rwB").split(","))   # 기준,변형 — 작업 프로세스도 보도록 환경 변수
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
L_ = "CDEFGAB"
step = lambda p: L_.index(p[0]) + 7 * int(p[-1])


def _one(job):
    import numpy as np
    import measure_chord_template as T
    from modules.preprocess import preprocess
    st, name, path, pg = job
    if st == "aoharu" or name == "organ2":
        return []
    rd = lambda d: json.load(open(os.path.join(ROOT, "debug", "sim_lp", d, name + ".json"), encoding="utf-8"))["labels"]
    A, B = rd(DIRS[0]), rd(DIRS[1])
    key = lambda l: (l["staff"], l["x"], l["y"], l["text"], l["pitch"])
    ka = {key(l) for l in A}
    new = [l for l in B if key(l) not in ka]
    if not new:
        return []
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    heads = T._truth(st, name, path, pg, res)
    sp = float(np.median([s.spacing for s in res.staves]))
    out = []
    for l in new:
        h = [q for q in heads if abs(q[0] - l["x"]) <= 0.7 * sp and abs(q[1] - l["y"]) <= 0.5 * sp]
        if not h:
            continue
        old = [o for o in A if abs(o["x"] - h[0][0]) <= 0.7 * sp and abs(o["y"] - h[0][1]) <= 0.5 * sp]
        if old:
            o = old[0]
            out.append(dict(kind="중복", page=name, x=l["x"], y=l["y"], dx=round((l["x"] - o["x"]) / sp, 2), dy=round((l["y"] - o["y"]) / sp, 2),
                            same=o["pitch"] == l["pitch"], new_ok=l["pitch"] == h[0][2], old_ok=o["pitch"] == h[0][2]))
        elif h[0][2] != l["pitch"]:
            out.append(dict(kind="음고", page=name, x=l["x"], y=l["y"], d=step(l["pitch"]) - step(h[0][2]),
                            dy=round((l["y"] - h[0][1]) / sp, 2), flags=",".join(f for f in (l.get("flags") or []) if f.startswith("clef")) or "-"))
    return out


def main():
    import measure_sim_ledger_pair as S
    with ProcessPoolExecutor(2) as ex:
        rows = [r for part in ex.map(_one, S.pages()) for r in part]
    pr = [r for r in rows if r["kind"] == "음고"]
    print(f"음고 틀림 {len(pr)}: 반칸 차 {dict(Counter(r['d'] for r in pr))} · 음자리표 표시 {dict(Counter(r['flags'] for r in pr))} · 쪽 {dict(Counter(r['page'][:12] for r in pr))}")
    print("  라벨 y − 정답 y(sp):", sorted(r["dy"] for r in pr))
    du = [r for r in rows if r["kind"] == "중복"]
    print(f"중복 {len(du)}: 같은 음 {sum(r['same'] for r in du)} · 새 라벨 음 맞음 {sum(r['new_ok'] for r in du)} · 원래 라벨 음 맞음 {sum(r['old_ok'] for r in du)}")
    print("  dx(sp):", sorted(r["dx"] for r in du))
    print("  dy(sp):", sorted(r["dy"] for r in du))
    for r in rows:
        print("   ", r)




def text18():
    """같은 자리(dx = dy = 0)에서 표기만 바뀐 라벨 — 실효 임시표 정답으로 고쳐짐 / 망가짐 / 틀림→틀림."""
    import measure_pdf_effective as E
    import measure_pdf_text_causes as TC
    import measure_sim_ledger_pair as S
    E.KEYS.update(moon="FCGD", rain="BEADG")      # 월광 3악장 C♯단조 ♯4 · 빗방울 D♭장조 ♭5(가운데 C♯단조 부분은 이 정답이 틀릴 수 있음)
    E.KEY_SIGN.update(moon="#", rain="b")
    norm = lambda a: {"#": "#", "b": "b", "s": "#", "f": "b", "ss": "#", "ff": "b"}.get(a or "", "")
    c = Counter()
    for st, name, path, pg in S.pages():
        if st == "aoharu" or name == "organ2":
            continue
        rd = lambda d: json.load(open(os.path.join(ROOT, "debug", "sim_lp", d, name + ".json"), encoding="utf-8"))["labels"]
        A, B = rd(DIRS[0]), rd(DIRS[1])
        pos = {(l["staff"], l["x"], l["y"]): l for l in A}
        ch = [(pos[(l["staff"], l["x"], l["y"])], l) for l in B if (l["staff"], l["x"], l["y"]) in pos and pos[(l["staff"], l["x"], l["y"])]["text"] != l["text"]]
        if not ch:
            continue
        if st == "verovio":
            t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))
            sp = 20.0
            heads = [dict(x=n["x"], y=n["y"], pitch=n["note_name"] + n["octave"], eff=n["eff"]) for n in t["notes"]]
        else:
            res, heads = E.effective(name, path, pg)
            sp = float(sum(s.spacing for s in res.staves) / len(res.staves))
        for old, new in ch:
            h = [q for q in heads if abs(q["x"] - new["x"]) <= 0.7 * sp and abs(q["y"] - new["y"]) <= 0.5 * sp]
            if not h:
                c["정답 머리 없음"] += 1
                print("    짝 없음", name, new["x"], new["y"], old["text"], "→", new["text"], [(round(q["x"]), round(q["y"]), q["pitch"], q.get("eff")) for q in heads if abs(q["x"] - new["x"]) <= 2 * sp and abs(q["y"] - new["y"]) <= 2 * sp][:4])
                continue
            truth = norm(TC.NORM.get(h[0]["eff"], h[0]["eff"]))
            o_ok = old["pitch"] == h[0]["pitch"] and norm(TC.ACC(old["text"])) == truth
            n_ok = new["pitch"] == h[0]["pitch"] and norm(TC.ACC(new["text"])) == truth
            k = "고쳐짐" if n_ok and not o_ok else "망가짐" if o_ok and not n_ok else "틀림→틀림" if not n_ok else "맞음→맞음"
            c[k] += 1
            print("   ", name, new["x"], new["y"], old["text"], "→", new["text"], "| 정답", h[0]["pitch"], h[0]["eff"] or "-", k)
    print("표기 바뀜:", dict(c))


if __name__ == "__main__":
    text18() if sys.argv[1:2] == ["text"] else main()
