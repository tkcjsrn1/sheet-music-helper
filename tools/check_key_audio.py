# -*- coding: utf-8 -*-
"""#383 후속: 49쪽 라벨마다 「표시 글자를 고정도로 읽은 음높이」와 「재생 pitch_to_midi」가 같은지 전수 대조.

    python tools/check_key_audio.py <기준 변형> <새 변형>     (debug/sim_lp/<변형>/*.json, measure_sim_ledger_pair run 결과)
기준 · 새 라벨 집합(보표, x, y, 음고, 표기, 확신도)이 같은지도 본다 — 오삭제 0 확인.
"""
import glob
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from modules.label_audio import pitch_to_midi

LP = os.path.join(ROOT, "debug", "sim_lp")
KEY = lambda l: (l["staff"], l["x"], l["y"], l["pitch"], l["text"], l["confidence"])


def main(base, new):
    c = Counter()
    for js in sorted(glob.glob(os.path.join(LP, new, "*.json"))):
        nm = os.path.basename(js)[:-5]
        B = json.load(open(js, encoding="utf-8"))
        A = json.load(open(os.path.join(LP, base, nm + ".json"), encoding="utf-8"))
        a, b = Counter(map(KEY, A["labels"])), Counter(map(KEY, B["labels"]))
        c["사라짐"] += sum((a - b).values()); c["생김"] += sum((b - a).values())
        fixed = dict(B["music"], notation="solfege")   # 표시 글자를 고정도 이름으로 읽는다
        for l in B["labels"]:
            c["라벨"] += 1
            c["구간 조표"] += "key" in l
            try:
                shown = pitch_to_midi(dict(l, edited=True), fixed)
            except ValueError:
                c["표기 해석 불가"] += 1
                continue
            if pitch_to_midi(l, B["music"]) != shown:
                c["불일치"] += 1
                print("  불일치", nm, l["staff"], l["x"], l["y"], l["pitch"], l["accidental"], l["text"], l.get("key"))
    print(dict(c))


if __name__ == "__main__":
    main(*sys.argv[1:3])
