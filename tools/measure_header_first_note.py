# -*- coding: utf-8 -*-
"""줄 첫 음이 header_end 안에 잡혀 빠지는 문제 — 49쪽 전수 (2026-10-26 · 측정만, 제품 코드 무변경).

보표마다 정답 머리 중 음자리표 끝보다 오른쪽이면서 머리 검출이 버리는 자리(꽉 찬 머리 중심 < header_end,
빈 머리 < header_end + 0.6sp — `notehead_detect`)에 있는 것을 센다. 기준 라벨은 debug/sim_lp/<기준>.
분류: 「조표·박자표 뒤」 = 머리 왼끝(x − 0.6sp)이 조표 끝(마지막 조표 막대 + 0.5sp, 조표 없으면 음자리표 끝)과
그 뒤 박자표 숫자 끝(`_timesig_span_end`)보다 오른쪽 — 고칠 대상. 나머지 = 「헤더 기호와 겹침」.
Aoharu는 정답 머리가 없어(골든 = 라벨) 뺀다.

    python tools/measure_header_first_note.py [기준=main1019]
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


def _one(job):
    import modules.clef_keysig as CK
    from modules.notehead_detect import remove_staff_lines
    from modules.preprocess import preprocess
    import measure_header_timesig as HT
    base_tag, (st, name, path, pg) = job
    heads = HT._heads(st, name, path, pg)
    if heads is None:
        return []
    res = preprocess(os.path.join(ROOT, path), pdf_page=pg) if path.endswith(".pdf") else preprocess(os.path.join(ROOT, path))
    ctx = CK.analyze_staves(res)
    ns = remove_staff_lines(res.binary, res.staves)
    lp = os.path.join(ROOT, "debug", "sim_lp", base_tag, name + ".json")
    labs = json.load(open(lp, encoding="utf-8"))["labels"] if os.path.exists(lp) else []
    out = []
    for x, y in heads:
        s = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))
        c = ctx.get(s.index)
        sp = s.spacing
        if c is None or not c.clef_found or x <= c.clef_end or x >= c.header_end + 0.6 * sp:
            continue
        key_end = max(c.clef_end, int(max(b for b, _y in c.bars) + 0.5 * sp)) if (c.key_count and c.bars) else c.clef_end
        ts_end = CK._timesig_span_end(ns, s, key_end)
        sym_end = max(key_end, ts_end)
        has = any(abs(l["x"] - x) <= 0.7 * sp and abs(l["y"] - y) <= 0.5 * sp for l in labs)
        out.append(dict(page=name, set=st, staff=s.index, x=round(x), y=round(y), header_end=int(c.header_end),
                        key_end=int(key_end), ts_end=int(ts_end), timesig=ts_end > key_end,
                        kind="조표·박자표 뒤" if x - 0.6 * sp > sym_end else "헤더 기호와 겹침",
                        gap_sp=round((x - 0.6 * sp - sym_end) / sp, 2), over_sp=round((c.header_end - sym_end) / sp, 2),
                        label=has))
    return out


def main():
    import measure_sim_ledger_pair as S
    tag = sys.argv[1] if len(sys.argv) > 1 else "main1019"
    with ProcessPoolExecutor(int(os.environ.get("MEASURE_WORKERS", "1"))) as ex:
        rows = [r for part in ex.map(_one, [(tag, p) for p in S.pages()]) for r in part]
    json.dump(rows, open(os.path.join(ROOT, "debug", "header_first_note.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    c = Counter((r["kind"], "라벨 있음" if r["label"] else "라벨 없음") for r in rows)
    print("== 49쪽(Aoharu 제외) 헤더 안쪽 정답 머리:", dict(c))
    for k in ("조표·박자표 뒤", "헤더 기호와 겹침"):
        rs = [r for r in rows if r["kind"] == k]
        print(f"[{k}] 쪽별:", Counter(r["page"] for r in rs).most_common())
        print("   박자표 있는 보표:", sum(r["timesig"] for r in rs), "· 헤더 끝 − 기호 끝(sp) 분포:", sorted(r["over_sp"] for r in rs))
        print("   머리 왼끝 − 기호 끝(sp):", sorted(r["gap_sp"] for r in rs))
    for r in rows:
        print("  ", r)


if __name__ == "__main__":
    main()
