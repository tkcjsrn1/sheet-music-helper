# -*- coding: utf-8 -*-
"""겹임시표 bb/## 연결(#388 + Codex #391) 검증 — 기준 · 새 라벨(49쪽, `measure_sim_ledger_pair run`) 대조 (2026-10-18).

  생김 · 사라짐 = (보표, x, y, 음고) 집합 차 — 0이어야 한다(오삭제 0)
  표기 바뀜 = 같은 라벨의 text 변화를 정답 실효 임시표(겹임시표는 bb · ##)와 대조 → 고침 · 새로 틀림(확실 따로) · 둘 다 틀림 · 유령
  확신도 바뀜 = 0이어야 한다(겹임시표 라벨은 이미 double_acc check)
  schema = 새 문서 schema 2인 쪽 수(겹임시표가 든 쪽만이어야 함)

    python tools/compare_double_conn.py <기준> <새>

쪽마다 결과를 debug/compare_double_conn/<새>/<쪽>.json에 바로 쓰고, 이미 있는 쪽은 건너뛴다(중간에 죽어도 이어서 돌림).
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
DBL = {"flatflat": "bb", "ff": "bb", "bb": "bb", "doublesharp": "##", "##": "##", "x": "##", "ss": "##"}
ACC = lambda t: "##" if t.endswith("##") else "bb" if t.endswith("bb") else "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _job(job):
    base, new, (st, nm, path, pg) = job
    out = os.path.join(ROOT, "debug", "compare_double_conn", new, nm + ".json")
    if os.path.exists(out):
        st, nm, c, rows = json.load(open(out, encoding="utf-8"))
        return st, nm, Counter(c), rows
    st, nm, c, rows = _judge(base, new, st, nm, path, pg)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    json.dump([st, nm, dict(c), rows], open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, out)                       # 쓰다 죽으면 .tmp만 남아 다음에 다시 잰다
    return st, nm, c, rows


def _judge(base, new, st, nm, path, pg):
    import error_census as EC
    load = lambda v: json.load(open(os.path.join(LP, v, nm + ".json"), encoding="utf-8"))
    DA, DB = load(base), load(new)
    key = lambda l: (l["staff"], l["x"], l["y"], l["pitch"])
    A = {key(l): l for l in DA["labels"]}
    B = {key(l): l for l in DB["labels"]}
    c = Counter(생김=len(B.keys() - A.keys()), 사라짐=len(A.keys() - B.keys()))
    c["schema2"] = int(DB["schema"] == 2)
    c["겹임시표 라벨"] = sum(l["accidental"] in ("bb", "##") for l in DB["labels"])
    c["겹임시표 라벨 check 아님"] = sum(l["accidental"] in ("bb", "##") and l["confidence"] != "check" for l in DB["labels"])
    c["확신도 바뀜"] = sum(A[k]["confidence"] != B[k]["confidence"] for k in A.keys() & B.keys())
    changed = [(A[k], B[k]) for k in A.keys() & B.keys() if A[k]["text"] != B[k]["text"]]
    c["표기 바뀜"] = len(changed)
    rows = []
    if changed and st != "aoharu":
        if st == "verovio":
            heads, _b, sp = EC._truth_vrv(nm)
            raw = {(n["x"], n["y"]): n for n in json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", nm + ".json"), encoding="utf-8"))["notes"]}
            for h in heads:
                h["eff"] = DBL.get(raw.get((h["x"], h["y"]), {}).get("eff"), h["eff"])
        else:
            heads, _b, sp = EC._truth_pdf(nm, path, pg)
            for h in heads:
                h["eff"] = DBL.get(h["eff"], h["eff"])
        L = DB["labels"]
        m = {j: heads[i] for i, j in EC._match(heads, L, sp).items()}
        idx = {key(l): j for j, l in enumerate(L)}
        for a, b in changed:
            h = m.get(idx[key(b)])
            if h is None or h["pitch"] != b["pitch"]:
                k = "유령(정답 없음)"
            else:
                ok_a, ok_b = ACC(a["text"]) == h["eff"], ACC(b["text"]) == h["eff"]
                k = "고침" if ok_b and not ok_a else "새로 틀림" if ok_a and not ok_b else "둘 다 맞음" if ok_a else "둘 다 틀림"
                if k == "새로 틀림" and b["confidence"] == "certain":
                    k = "새로 틀림 · 확실"
            c[k] += 1
            rows.append((k, nm, b["staff"], b["x"], b["y"], b["pitch"], a["text"], b["text"], b["confidence"]))
    return st, nm, c, rows


def main(base, new):
    import measure_sim_ledger_pair as S
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "2"))) as ex:
        R = list(ex.map(_job, [(base, new, p) for p in S.pages()]))
    tot = Counter()
    for st, nm, c, rows in R:
        tot.update(c)
        if c["표기 바뀜"] or c["생김"] or c["사라짐"] or c["확신도 바뀜"] or c["schema2"]:
            print(f"  {st} {nm}: " + ", ".join(f"{k} {v}" for k, v in c.items() if v))
        for r in rows:
            if r[0] != "고침":
                print("    ", r)
    print("합계", dict(tot))


if __name__ == "__main__":
    main(*sys.argv[1:3])
