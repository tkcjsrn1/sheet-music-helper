# -*- coding: utf-8 -*-
"""§1-43 초안(곡 중간 조바꿈 뒤를 새 조로) 구현 검증(2026-10-16) — 기준 · 새 라벨(49쪽, `measure_sim_ledger_pair run`)의 표기 변화를 정답과 대조.

사용자 기준(10-16 18:30): 오삭제 0 · 「확실」 새로 틀림 0 · 깨끗한 세트(PDF · 보지 않은 · 아오하루)에서 조가 바뀌는 쪽 0.
같은 라벨 = (보표, x, y, 음고) 같음. 표기만 바뀐 라벨을 정답 실효 임시표로 고침 · 새로 틀림 · 둘 다 틀림으로 가른다.
정답 = Verovio SVG(eff) · PDF · 보지 않은 `measure_certain_errors._truth`. 아오하루는 골든 — 바뀐 라벨 수만.

    python tools/compare_keychange_impl.py <기준> <새>
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
LP = os.path.join(ROOT, "debug", "sim_lp")
ACC = lambda t: "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _job(job):
    base, new, (st, nm, path, pg) = job
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"])
    A = {key(l): l for l in json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))["labels"]}
    B = {key(l): l for l in json.load(open(os.path.join(LP, new, nm + ".json"), encoding="utf-8"))["labels"]}
    c = Counter(사라짐=len(A.keys() - B.keys()), 생김=len(B.keys() - A.keys()))
    changed = [(A[k], B[k]) for k in A.keys() & B.keys() if A[k]["text"] != B[k]["text"]]
    c["표기 바뀜"] = len(changed)
    if not changed or st == "aoharu":
        return st, nm, c, []
    if st == "verovio":
        t = json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))
        heads, sp = [(n["x"], n["y"], n["note_name"] + n["octave"], n["eff"] or "") for n in t["notes"]], 18.0
    else:
        from measure_certain_errors import _truth
        heads, sp = _truth("pdf", nm, path, pg)
    norm = lambda a: {"natural": "", None: ""}.get(a, a)
    rows = []
    for a, b in changed:
        h = [q for q in heads if abs(q[0] - a["x"]) <= 0.7 * sp and abs(q[1] - a["y"]) <= 0.5 * sp]
        if not h:
            k = "유령(정답 없음)"
        else:
            want = norm(h[0][3])
            ok_a, ok_b = ACC(a["text"]) == want, ACC(b["text"]) == want
            k = "고침" if ok_b and not ok_a else "새로 틀림" if ok_a and not ok_b else "둘 다 맞음" if ok_a else "둘 다 틀림"
        if k == "새로 틀림" and b["confidence"] == "certain":
            k = "새로 틀림 · 확실"
        c[k] += 1
        rows.append((k, nm, a["x"], a["y"], a["text"], b["text"], b["confidence"]))
    return st, nm, c, rows


def main(base, new):
    import measure_sim_ledger_pair as S
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_job, [(base, new, p) for p in S.pages() if p[1] != "organ2"]))
    tot = {}
    for st, nm, c, rows in R:
        tot.setdefault(st, Counter()).update(c)
        if c["표기 바뀜"]:
            print(f"  {st} {nm}: 표기 바뀜 {c['표기 바뀜']}" + (" ← 깨끗한 세트에서 조가 바뀜" if st != "verovio" else ""))
        for r in rows:
            if r[0].startswith("새로 틀림") or r[0] == "유령(정답 없음)":
                print("    ", r)
    for st, c in tot.items():
        print(f"{st:8s}", dict(c))
    json.dump([r for *_x, rows in R for r in rows], open(os.path.join(ROOT, "debug", f"compare_{new}.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:3])
