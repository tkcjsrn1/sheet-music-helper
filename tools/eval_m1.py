# -*- coding: utf-8 -*-
"""M1(사진 입력 전처리) 검증 — Codex 합성 촬영본 57장 + 가장자리 조건 12장. 측정 전용.

각 영상을 **M1 없이**(`preprocess`) 그리고 **M1로**(`preprocess(photo=True)`) 돌려, 원본 조건(합성 전 PDF 렌더)
라벨과 좌표로 짝짓는다. 좌표 대응: 원본 → (곡면) → manifest 순방향 행렬 → (M1이면) 보정 행렬.

항목: 처리 결과(완료 · 거부 · 오선 실패) · 보표 수 · 조표 · 음자리표 배열 · 라벨 유지 · 소실 · 음고 · 표기 · 새로 생김.
짝짓기 허용 0.5sp. **자동 대응 수이지 눈으로 본 판정이 아니다.**

가장자리 조건(A-12, 이 도구가 만든다): 세 악보 × {원본, 2° 회전} × {회색 책상 배경, 복사기 검은 테두리}
- 회색 책상: 종이 밖을 밝기 140으로. 종이-배경 경계가 가로 전체 폭의 긴 선이 된다
- 검은 테두리: 종이 밖 2% 폭을 검게(복사기 유리 밖). 강한 경계

    python tools/eval_m1.py [--only 파일이름조각]
"""
import json
import math
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from modules.preprocess import preprocess, PhotoRejectedError, StaffNotFoundError  # noqa: E402
from modules.clef_keysig import analyze_staves  # noqa: E402
from modules.notehead_detect import detect_noteheads  # noqa: E402
from modules.pitch_calculator import calculate_pitches  # noqa: E402
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts  # noqa: E402
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts  # noqa: E402
from _score_context import label_texts  # noqa: E402

SYN = os.path.join(ROOT, "output", "synthetic_photos")
EDGE = os.path.join(ROOT, "output", "m1_edge")


def write(path, img):
    with open(path, "wb") as f:
        f.write(cv2.imencode(".png", img)[1].tobytes())


def labels(res):
    """골든 테스트와 같은 순서(임시표 유령 제거 포함)."""
    ctx = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctx)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
    accs = annotate_accidentals(res, ctx, notes)
    notes, accs = remove_accidental_ghosts(notes, accs, res.staves)
    texts = label_texts(notes, ctx, accs)
    found = [c for c in ctx.values() if c.clef_found]
    key = (found[0].key_symbol + str(found[0].key_count)) if found and found[0].key_count else "없음"
    clefs = [ctx[s.index].clef for s in res.staves]
    return [(n.x, n.y, f"{n.note_name}{n.octave}", t) for n, t in zip(notes, texts)], key, clefs


def run(path, photo):
    try:
        res = preprocess(path, photo=photo)
    except PhotoRejectedError as e:
        return dict(status="거부", reason=e.reason)
    except StaffNotFoundError as e:
        return dict(status="오선 실패", reason=str(e)[:30])
    labs, key, clefs = labels(res)
    m = res.photo_correction.matrix if res.photo_correction is not None else np.array([[1.0, 0, 0], [0, 1.0, 0]])
    return dict(status="완료", staves=len(res.staves), key=key, clefs=clefs, labels=labs, m=m,
                angle=res.photo_correction.angle_deg if res.photo_correction is not None else 0.0)


def forward(pts, row):
    """원본 좌표 → 합성 사진 좌표 (곡면 → 행렬)."""
    x, y = pts[:, 0].astype(float), pts[:, 1].astype(float)
    amp = row.get("curve", {}).get("amplitude_px", 0) or 0
    if amp:
        w = row["input_size"][0]
        y = y + amp * (1 - np.abs((x - (w - 1) / 2) / ((w - 1) / 2))) ** 2
    H = np.array(row["forward_homography"], float)
    p = cv2.perspectiveTransform(np.stack([x, y], 1)[None], H)[0]
    return p


def compare(base, got, row, sp):
    if got["status"] != "완료":
        return {}
    pts = forward(np.array([(b[0], b[1]) for b in base["labels"]], float), row)
    moved = (got["m"] @ np.c_[pts, np.ones(len(pts))].T).T
    used, out = set(), dict(유지=0, 소실=0, 음고=0, 표기=0)
    for (bx, by, bp, bt), (mx, my) in zip(base["labels"], moved):
        best = None
        for j, (gx, gy, gp, gt) in enumerate(got["labels"]):
            d = math.hypot(gx - mx, gy - my)
            if j not in used and d <= sp * 0.5 and (best is None or d < best[0]):
                best = (d, j)
        if best is None:
            out["소실"] += 1
            continue
        used.add(best[1])
        out["유지"] += 1
        gp, gt = got["labels"][best[1]][2:]
        if gp != bp:
            out["음고"] += 1
        elif gt != bt:
            out["표기"] += 1
    out["새로"] = len(got["labels"]) - len(used)
    return out


def make_edges(rows):
    """가장자리 조건 12장을 만들고 manifest 형식의 행을 돌려준다."""
    os.makedirs(EDGE, exist_ok=True)
    out = []
    for r in rows:
        if r["condition"] not in ("original", "rotation_2deg"):
            continue
        img = cv2.imdecode(np.fromfile(os.path.join(SYN, r["file"]), np.uint8), cv2.IMREAD_COLOR)
        w0, h0 = r["input_size"]
        H = np.array(r["forward_homography"], float)
        pad = 0 if r["condition"] != "original" else int(max(w0, h0) * 0.08)
        if pad:                                          # 원본은 여백이 없다 — 흰 여백을 먼저 붙인다
            img = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            H = np.array([[1, 0, pad], [0, 1, pad], [0, 0, 1.0]]) @ H
        page = cv2.warpPerspective(np.full((h0, w0), 255, np.uint8), H, (img.shape[1], img.shape[0]),
                                   flags=cv2.INTER_NEAREST) > 0
        for kind in ("graydesk", "blackframe"):
            e = img.copy()
            if kind == "graydesk":
                e[~page] = 140
            else:
                # 종이 밖을 검게 하되 영상 가장자리 2% 폭만(복사기 유리 밖) — 나머지 여백은 흰색 그대로
                band = np.zeros(page.shape, bool)
                b = int(min(page.shape) * 0.02)
                band[:b, :] = band[-b:, :] = band[:, :b] = band[:, -b:] = True
                e[band & ~page] = 20
                if r["condition"] == "original":
                    e[band] = 20                       # 여백 없는 원본은 테두리가 종이 가장자리에 붙는다
            name = f"{r['score']}__{r['condition']}__{kind}.png"
            write(os.path.join(EDGE, name), e)
            nr = dict(r)
            nr.update(file=name, condition=f"{r['condition']}+{kind}", forward_homography=H.tolist(), dir=EDGE)
            out.append(nr)
    return out


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    rows = json.load(open(os.path.join(SYN, "manifest.json"), encoding="utf-8"))["images"]
    for r in rows:
        r["dir"] = SYN
    rows = rows + make_edges(rows)
    base = {}
    results = []
    for r in rows:
        if r["condition"] == "original":
            base[r["score"]] = run(os.path.join(SYN, r["file"]), False)
    for r in rows:
        if only and only not in r["file"]:
            continue
        b = base[r["score"]]
        sp = r["source_sp"]
        line = [f"{r['score']:10s} {r['condition']:44s}"]
        rec = dict(score=r["score"], condition=r["condition"])
        for photo in (False, True):
            g = run(os.path.join(r["dir"], r["file"]), photo)
            c = compare(b, g, r, sp)
            tag = "M1" if photo else "없음"
            if g["status"] == "완료":
                same_key = "조표같음" if g["key"] == b["key"] else f"조표 {b['key']}→{g['key']}"
                same_clef = "음자리표같음" if g["clefs"] == b["clefs"] else "음자리표다름"
                line.append(f"{tag}: 완료 보표 {g['staves']} {same_key} {same_clef} "
                            f"유지 {c['유지']} 소실 {c['소실']} 음고 {c['음고']} 표기 {c['표기']} 새로 {c['새로']}")
            else:
                line.append(f"{tag}: {g['status']}({g.get('reason', '')})")
            rec[tag] = dict(status=g["status"], reason=g.get("reason"), staves=g.get("staves"),
                            key=g.get("key"), clefs_same=(g.get("clefs") == b["clefs"]) if g["status"] == "완료" else None,
                            angle=g.get("angle"), **c)
        results.append(rec)
        print(" | ".join(line), flush=True)
    with open(os.path.join(ROOT, "debug", "eval_m1.json"), "w", encoding="utf-8") as f:
        json.dump(dict(base={k: dict(key=v["key"], staves=v["staves"], labels=len(v["labels"])) for k, v in base.items()},
                       results=results), f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
