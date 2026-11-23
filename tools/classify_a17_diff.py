# -*- coding: utf-8 -*-
"""A-17 사본 대조 결과(diff_*.json)의 칸별 자동 판정 (2026-09-30).

- 기대 표기: 그 음표를 겨냥한 PDF 임시표 글리프 → 없으면 같은 음 높이 · 같은 마디 앞 글리프(마디 내 전파, 마디선은 제품
  `_find_barlines`, 음 높이 ±0.25sp = 반 칸 — ±0.35sp는 D♭ 3쪽 (1241,2900) B에 옆 A의 ♯을 전파했다 · 첫 판의 「앞 20sp」는 월광 1쪽 ♮ 전파를 놓쳐 맞은 칸을 「새로 틀림」으로 셌다) → 없으면 조표
  (조표는 제품이 읽은 `music.key_letters`). 음 높이 변화량(♯ +1 · ♭ −1 · ♮ 0 · 표시 없음 = 조표)으로 비교한다
- 새로 생김 / 사라짐: PDF 정답 머리(가로 0.7 · 세로 0.5sp)와 대응 — 없으면 유령
- 정답을 못 쓰는 입력(회전된 PDF 쪽 · 사진)은 「눈 판정」으로 남긴다
실행: python tools/classify_a17_diff.py <diff json 이름> <기준 폴더> <후보 폴더>
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import check_accidental_fix as C  # noqa: E402
import measure_a17 as A  # noqa: E402
import measure_omission_rate as M  # noqa: E402
from modules import accidental_detect as AD  # noqa: E402

OUT = os.path.join(ROOT, "debug", "a17_cand1")
ALT = {"#": 1, "b": -1, "natural": 0, "flatflat": -2, "doublesharp": 2}
NO_TRUTH = {"organ2"}          # /Rotate 걸린 쪽 — PDF 글리프 좌표가 렌더 영상과 안 맞는다


def classify(diff_name, base_dir, cand_dir):
    rows = json.load(open(os.path.join(OUT, diff_name), encoding="utf-8"))
    cache = {}
    cnt = Counter()
    for r in rows:
        page = r["page"]
        if page in NO_TRUTH or not r["path"].endswith(".pdf"):
            r["auto"] = "눈 판정"
            cnt[r["auto"]] += 1
            continue
        if page not in cache:
            res = C.preprocess(os.path.join(ROOT, r["path"]), pdf_page=r["pg"])
            ctx = C.analyze_staves(res)
            glyphs = A.truth(r["path"], r["pg"], res, ctx)[0]
            allg = [q for q in M.pdf_glyphs(r["path"], r["pg"], ("accidentals.",)) if q["name"].split(".", 1)[1] in A.KIND]
            heads = [q for q in M.pdf_glyphs(r["path"], r["pg"], ("noteheads.",))]
            sp = float(np.median([s.spacing for s in res.staves]))
            no_staff = AD.remove_staff_lines(res.binary, res.staves)
            bars = {s.index: (s, AD._find_barlines(no_staff, s, res.binary.shape[0])) for s in res.staves}
            lab = {}
            for d in (base_dir, cand_dir):
                j = json.load(open(os.path.join(OUT, d, f"{page}.json"), encoding="utf-8"))
                lab[d] = ({(l["x"], l["y"]): l for l in j["labels"]}, set(j["music"]["key_letters"]), j["music"]["key_symbol"])
            cache[page] = (glyphs, allg, heads, sp, lab, bars)
        glyphs, allg, heads, sp, lab, bars = cache[page]
        xy = (r["x"], r["y"])
        on_head = any(abs(h["cx"] - r["x"]) <= 0.7 * sp and abs(h["cy"] - r["y"]) <= 0.5 * sp for h in heads)
        if r["kind"] == "새로 생김":
            r["auto"] = "진짜 머리 라벨 생김" if on_head else "새 유령"
        elif r["kind"] == "사라짐":
            r["auto"] = "진짜 머리 라벨 사라짐" if on_head else "유령 제거"
        elif not on_head:
            r["auto"] = "유령 라벨 글자만"
        elif r["before"] == r["after"]:
            r["auto"] = "표기 같음"
        else:
            b, c = lab[base_dir][0][xy], lab[cand_dir][0][xy]
            letter = b["pitch"][0]
            keys, ksym = lab[base_dir][1], lab[base_dir][2]
            key_alt = (1 if ksym == "♯" else -1) if letter in keys else 0
            g = [q for q in glyphs if abs(q["hx"] - r["x"]) <= 0.7 * sp and abs(q["hy"] - r["y"]) <= 0.5 * sp]
            if g:
                exp, why = ALT[g[0]["kind"]], "글리프"
            else:
                st, bl = bars[b["staff"]]
                left = max([x for x in bl if x < r["x"]], default=0)
                prev = [q for q in allg if abs(q["oy"] - r["y"]) <= 0.25 * sp and left < q["cx"] < r["x"]
                        and st.top - 6 * sp <= q["oy"] <= st.bottom + 6 * sp]
                if prev:
                    q = max(prev, key=lambda q: q["cx"])
                    exp, why = ALT[A.KIND[q["name"].split(".", 1)[1]]], "같은 마디 앞 글리프"
                else:
                    exp, why = key_alt, "조표"

            def alt(l):
                return ALT[l["accidental"]] if l["accidental"] else key_alt
            ob, oc = alt(b) == exp, alt(c) == exp
            r["auto"] = "고쳐짐" if (oc and not ob) else "새로 틀림" if (ob and not oc) else "틀린 채 바뀜" if not (ob or oc) else "표기 같음"
            r["why"] = f"{why} 기대{exp:+d}"
        cnt[r["auto"]] += 1
    json.dump(rows, open(os.path.join(OUT, diff_name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(diff_name, dict(cnt))
    for i, r in enumerate(rows, 1):
        if r["auto"] in ("새로 틀림", "새 유령", "진짜 머리 라벨 사라짐", "틀린 채 바뀜", "눈 판정"):
            print(f"  #{i}", r["page"], (r["x"], r["y"]), r["kind"], r["before"], "→", r["after"], r["auto"], r.get("why", ""))
    return cnt


if __name__ == "__main__":
    classify(*sys.argv[1:4])
