# -*- coding: utf-8 -*-
"""겹임시표 종류 반환(`double_acc_kinds`, ♭♭ → "bb" · 𝄪 → "##", 직접 · 전파 + 같은 마디 취소) 측정 (2026-10-18, 49쪽 · 보류 세트 미사용).

제품(main.run_page) 그대로 돌리며 `double_acc_suspects`가 불리는 자리에서 `double_acc_kinds`도 같이 계산해 좌표로 남긴다.
정답 = 머리의 실효 임시표(PDF 글리프 · Verovio SVG, `error_census`) — 겹임시표만 "bb" · "##", 나머지는 "".
  종류 정확도: 반환한 라벨 중 정답 종류와 같은 비율(직접 · 전파 따로)
  전파 범위: 정답이 「전파된 겹임시표」인 라벨을 전파로 잡았나 · 반환한 전파가 정답에서도 겹임시표인가 · 옛 check 전파(취소 없음)와 차이
  표기 영향(배열에 덮어 쓴다면): 고침(지금 표기 틀림 → 맞음) · 새로 틀림(지금 맞음 → 틀림, 확실 따로)

    python tools/measure_double_acc_kinds.py            (돌리기 + 보고)
    python tools/measure_double_acc_kinds.py report
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(ROOT, "debug", "double_acc_kinds.json")
DBL = {"flatflat": "bb", "ff": "bb", "bb": "bb", "doublesharp": "##", "##": "##", "x": "##", "ss": "##"}
ACC = lambda t: "##" if t.endswith("##") else "bb" if t.endswith("bb") else "#" if t.endswith("#") else "b" if t.endswith("b") else ""


def _job(job):
    import contextlib
    import io
    import shutil
    import tempfile
    import main as MAIN
    import modules.accidental_detect as AD
    import error_census as EC
    st, name, path, pg = job
    got, calls = {}, [0]
    orig = AD.double_acc_suspects

    def spy(result, contexts, notes):
        calls[0] += 1
        old = orig(result, contexts, notes)
        for i, (k, src) in AD.double_acc_kinds(result, contexts, notes).items():
            n = notes[i]
            got[(n.staff_index, int(n.x), int(n.y))] = (k, src)
        for n in old:
            got.setdefault((n.staff_index, int(n.x), int(n.y)), None)   # 옛 check 전파에만 걸린 라벨
        return old
    AD.double_acc_suspects = spy
    tmp = tempfile.mkdtemp(prefix="dak_")
    js = os.path.join(tmp, "l.json")
    sys.argv = ["main.py", os.path.join(ROOT, path), "--page", str(pg), "--no-debug", "--output-dir", tmp, "--save-labels", js]
    with contextlib.redirect_stdout(io.StringIO()):
        MAIN.run_page(MAIN.parse_args(), os.path.join(ROOT, path), pg, tmp)
    L = json.load(open(js, encoding="utf-8"))["labels"]
    shutil.rmtree(tmp, ignore_errors=True)
    if st == "verovio":
        heads, _b, sp = EC._truth_vrv(name)
        raw = {(n["x"], n["y"]): n for n in json.load(open(os.path.join(ROOT, "debug", "vrv", "truth", name + ".json"), encoding="utf-8"))["notes"]}
        for h in heads:
            r = raw.get((h["x"], h["y"]), {})
            h["eff"], h["own"] = DBL.get(r.get("eff"), h["eff"]), DBL.get(r.get("accidental"), h["own"])
    else:
        heads, _b, sp = EC._truth_pdf(name, path, pg)
        for h in heads:
            h["eff"], h["own"] = DBL.get(h["eff"], h["eff"]), DBL.get(h["own"], h["own"])
    m = {j: heads[i] for i, j in EC._match(heads, L, sp).items()}
    rows = []
    for j, l in enumerate(L):
        h = m.get(j)
        key = (l["staff"], l["x"], l["y"])
        t = h["eff"] if h is not None and h["eff"] in ("bb", "##") and h["pitch"] == l["pitch"] else ""
        if key not in got and not t:
            continue
        p = got.get(key)
        rows.append(dict(x=l["x"], y=l["y"], staff=l["staff"], pitch=l["pitch"], text=l["text"], conf=l["confidence"],
                         pred=p[0] if p else "", src=p[1] if p else "", old_check=key in got,
                         truth=t, truth_src=("" if not t else "직접" if h["own"] == t else "전파"),
                         ghost=h is None, now_ok=h is not None and h["pitch"] == l["pitch"] and ACC(l["text"]) == (h["eff"] or "")))
    return dict(set=st, page=name, calls=calls[0], rows=rows)


def main():
    import measure_sim_ledger_pair as S
    from concurrent.futures import ProcessPoolExecutor
    jobs = [p for p in S.pages() if p[0] != "aoharu" and p[1] != "organ2"]
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "3"))) as ex:
        P = list(ex.map(_job, jobs))
    json.dump(P, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    report(P)


def report(P=None):
    P = P or json.load(open(OUT, encoding="utf-8"))
    zero = [p["page"] for p in P if not p["calls"]]
    if zero:                                              # MEASUREMENT_PITFALLS B-4 — 가로채기가 비면 분류하지 않는다
        raise SystemExit(f"가로채기 호출 0인 쪽: {zero}")
    rows = [dict(r, page=p["page"], set=p["set"]) for p in P for r in p["rows"]]
    print("쪽", len(P), "· 정답 겹임시표 라벨", sum(1 for r in rows if r["truth"]),
          dict(Counter((r["truth"], r["truth_src"]) for r in rows if r["truth"])))
    for src in ("직접", "전파"):
        R = [r for r in rows if r["src"] == src]
        ok = sum(r["pred"] == r["truth"] for r in R)
        print(f"  반환 {src} {len(R)} · 종류 맞음 {ok} ({ok / max(1, len(R)) * 100:.0f}%) · 틀림",
              dict(Counter(f"{r['pred']}→정답{r['truth'] or '없음'}" for r in R if r["pred"] != r["truth"])))
    for src in ("직접", "전파"):
        T = [r for r in rows if r["truth_src"] == src]
        print(f"  정답 {src} {len(T)} · 잡음 {sum(r['pred'] == r['truth'] for r in T)} · 놓침 {sum(not r['pred'] for r in T)}"
              f" · 반대 종류 {sum(bool(r['pred']) and r['pred'] != r['truth'] for r in T)}")
    cut = [r for r in rows if r["old_check"] and not r["pred"]]
    print("  옛 check에만 걸림(취소 · 종류 미상으로 뺌)", len(cut), "· 그중 정답 겹임시표", sum(bool(r["truth"]) for r in cut))
    c = Counter()
    for r in rows:
        if not r["pred"]:
            continue
        if r["pred"] == r["truth"]:
            c["고침" if not r["now_ok"] else "이미 맞음"] += 1
        elif r["now_ok"]:
            c["새로 틀림 · " + r["conf"]] += 1
        else:
            c["유령" if r["ghost"] else "둘 다 틀림"] += 1
    print("  표기 영향(배열에 덮어 쓴다면)", dict(c))
    for r in rows:
        if r["pred"] and r["pred"] != r["truth"] and r["now_ok"]:
            print("    새로 틀림", r["page"], r["staff"], r["x"], r["y"], r["pitch"], r["text"], r["pred"], r["src"], r["conf"])


if __name__ == "__main__":
    report() if sys.argv[1:2] == ["report"] else main()
