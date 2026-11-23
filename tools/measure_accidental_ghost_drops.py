# -*- coding: utf-8 -*-
"""`remove_accidental_ghosts`가 **진짜 음표를 지우는가**를 실제 악보에서 잰다.

측정 전용. `modules/`는 읽기만 한다.

## 무엇을 재는가

`accidental_detect.remove_accidental_ghosts`는 임시표를 가진 음표 `nj`의
**왼쪽 0.5~1.6sp · 세로 ±1.25sp** 안에 있는 다른 음표 `ni`를 **임시표 글리프가
음표로 잘못 잡힌 것**으로 보고 지운다.

그런데 그 창 안에 **자기 임시표를 가진 진짜 음표**가 들어올 수 있다. 임시표가
연달아 붙은 자리(♭♭, ♮♯ …)가 그렇다. 코드에는 `ni`가 진짜인지 보는 조건이 없다 —
`accidentals[i]`를 확인하지 않는다.

그래서 삭제된 것마다 **진짜 음표의 증거**를 함께 잰다.

| 증거 | 뜻 |
|---|---|
| `자기 임시표` | `ni`에도 임시표가 붙어 있었다. 임시표 글리프 자신이라면 있을 수 없다 |
| `좌우잉크` | `verify._side_ink`의 약한 쪽. 실측상 진짜 음표는 0.40 이상, 유령은 0.03~0.20 |
| `Δstep` | `ni`와 `nj`의 음고 차이(반칸). 0이면 같은 높이 = 글리프일 가능성이 높다 |

**판정하지 않고 기록만 한다.** 유형별로 세야 무엇부터 고칠지 알 수 있기 때문이다
(`verify.diagnose_labels`와 같은 태도).

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요):
    python tools/measure_accidental_ghost_drops.py
    python tools/measure_accidental_ghost_drops.py <악보경로> [PDF쪽번호]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads, remove_staff_lines
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import (annotate_accidentals, ACCIDENTAL_GHOST_Y_SP,
                                       ACCIDENTAL_Y_TOL_SP, _find_glyphs)
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts, _side_ink

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from _score_context import context_summary  # noqa: E402

# 삭제 창 — `remove_accidental_ghosts`와 **같은 값**이다. 여기서 다시 적는 이유는
# 그 함수가 무엇을 지웠는지 돌려주지 않기 때문이다(집합을 안에서 버린다).
X_LO, X_HI = 0.5, 1.6


def raw_accidentals(res, ctxs, notes):
    """**직접 검출된**(글리프가 실제로 있는) 임시표만. 마디 내 지속은 빼고 잰다.

    `annotate_accidentals`는 `raw`(글리프 검출) + `지속`을 합친 `effective`만
    돌려준다. 그런데 `remove_accidental_ghosts`는 그 `effective`를 받아
    **"이 음표 왼쪽에 임시표 글리프가 있다"**로 해석한다 — 지속된 임시표에는
    글리프가 없으므로 그 해석이 성립하지 않는다.

    두 경로를 갈라 보려면 `raw`가 필요한데 모듈이 안 돌려주므로 여기서 다시 잰다.
    **`accidental_detect.annotate_accidentals`의 1) 단계와 같은 코드**여야 한다.
    """
    no_staff = remove_staff_lines(res.binary, res.staves)
    img_h = res.binary.shape[0]
    by_idx = {s.index: s for s in res.staves}
    cache = {}

    def band_of(staff):
        if staff.index not in cache:
            sp = staff.spacing
            top = max(0, int(staff.top - sp * 3.5))
            bottom = min(img_h, int(staff.bottom + sp * 3.5))
            vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
            cache[staff.index] = (cv2.morphologyEx(no_staff[top:bottom, :],
                                                   cv2.MORPH_CLOSE, vk), top)
        return cache[staff.index]

    out = []
    for note in notes:
        staff = by_idx.get(note.staff_index)
        if staff is None:
            out.append(""); continue
        sp = staff.spacing
        band, top = band_of(staff)
        x1 = int(note.x - sp * 0.55)
        x0 = int(note.x - sp * 2.0)
        if ctxs is not None and note.staff_index in ctxs:
            x0 = max(x0, ctxs[note.staff_index].header_end + int(sp * 0.2))
        y0 = int(note.y - top - sp * 2.0)
        y1 = int(note.y - top + sp * 2.0)
        if x1 - x0 < sp * 0.6:
            out.append(""); continue
        py0 = max(0, y0)
        patch = band[py0:min(band.shape[0], y1), max(0, x0):min(band.shape[1], x1)]
        if patch.size == 0:
            out.append(""); continue
        glyphs = _find_glyphs(patch, sp)
        best = ""
        for group in (("#", "natural"), ("b",)):
            cands = [(abs((top + py0 + gy) - note.y), kind)
                     for kind, gy in glyphs if kind in group]
            if cands:
                dy, kind = min(cands)
                if dy <= sp * ACCIDENTAL_Y_TOL_SP:
                    best = kind
                    break
        out.append(best)
    return out


def survey(path, page=0):
    """(요약 dict, 삭제 건 목록). 파이프라인은 골든 테스트와 같은 순서로 돈다."""
    res = preprocess(path, pdf_page=page)
    ctxs = analyze_staves(res)
    heads = detect_noteheads(res, contexts=ctxs)
    heads, _ = drop_beam_ghosts(res, heads)
    heads, _ = drop_offstaff_ghosts(res, heads)
    notes = calculate_pitches(heads, res.staves,
                             clef={i: c.clef for i, c in ctxs.items()})
    accs = annotate_accidentals(res, ctxs, notes)
    raws = raw_accidentals(res, ctxs, notes)

    no_staff = remove_staff_lines(res.binary, res.staves)
    sp_of = {s.index: s.spacing for s in res.staves}
    grid = {s.index: (s.grid_bottom, s.spacing) for s in res.staves}

    hits = []
    for j, nj in enumerate(notes):
        if not accs[j]:
            continue
        sp = sp_of.get(nj.staff_index, 12.0)
        for i, ni in enumerate(notes):
            if i == j or ni.staff_index != nj.staff_index:
                continue
            if (sp * X_LO <= nj.x - ni.x <= sp * X_HI
                    and abs(ni.y - nj.y) <= sp * ACCIDENTAL_GHOST_Y_SP):
                gb, gsp = grid[ni.staff_index]
                weak, strong = _side_ink(no_staff, int(ni.x), int(ni.y), sp)
                hits.append({
                    "i": i, "j": j,
                    "x": int(ni.x), "y": int(ni.y), "staff": ni.staff_index,
                    "pitch": f"{ni.note_name}{ni.octave}",
                    "own_acc": accs[i],                       # 지워지는 쪽의 임시표
                    "trig_x": int(nj.x), "trig_y": int(nj.y),
                    "trig_pitch": f"{nj.note_name}{nj.octave}",
                    "trig_acc": accs[j],
                    # 방아쇠의 임시표가 **글리프에서 직접** 나온 것인가, 마디 내
                    # **지속**으로 물려받은 것인가. 지속이면 왼쪽에 글리프가 없다.
                    "trig_raw": raws[j],
                    "trig_carried": (not raws[j]) and bool(accs[j]),
                    "dx_sp": (nj.x - ni.x) / sp,
                    "dy_sp": abs(ni.y - nj.y) / sp,
                    "dstep": ((gb - ni.y) - (gb - nj.y)) / (gsp / 2.0),
                    "weak_ink": weak, "strong_ink": strong,
                })

    dropped = sorted({h["i"] for h in hits})
    summary = {
        "라벨(삭제 전)": len(notes),
        # 음자리표·조표 — 라벨 수만 비교하면 조표가 뒤집혀도 안 보인다(tests/_score_context.py)
        "문맥": context_summary(ctxs),
        "임시표": sum(1 for a in accs if a),
        # 반환 문자열은 "#", "b", "natural", "" 이다 (accidental_detect 15행)
        "♮": sum(1 for a in accs if a == "natural"),
        "♯": sum(1 for a in accs if a == "#"),
        "♭": sum(1 for a in accs if a == "b"),
        "창 발동": len(hits),
        "삭제된 음표": len(dropped),
        "삭제 중 자기임시표 있음": sum(1 for i in dropped
                                if any(h["i"] == i and h["own_acc"] for h in hits)),
        "삭제 중 좌우잉크>=0.40": sum(
            1 for i in dropped
            if max(h["weak_ink"] for h in hits if h["i"] == i) >= 0.40),
        "방아쇠가 지속(글리프 없음)": sum(1 for h in hits if h["trig_carried"]),
        "지속 방아쇠로 삭제된 음표": len({h["i"] for h in hits if h["trig_carried"]}),
    }
    return summary, hits, notes, accs


TARGETS = [
    ("aoharu p1  [골든]", "sample_images/KakaoTalk_20260731_162400402.png", 0),
    ("aoharu p2  [골든]", "sample_images/KakaoTalk_20260731_162400402_01.png", 0),
    ("aoharu p3  [골든]", "sample_images/KakaoTalk_20260731_162400402_02.png", 0),
    ("쇼팽 Db 1쪽 [전수판정]", "test_scores/chopin_nocturne_Db_6-8.pdf", 0),
    ("바흐      [전수판정]", "test_scores/bach_minuet_Am.pdf", 0),
    ("쇼팽 Db 2쪽", "test_scores/chopin_nocturne_Db_6-8.pdf", 1),
    ("쇼팽 Db 3쪽", "test_scores/chopin_nocturne_Db_6-8.pdf", 2),
    ("쇼팽 Db 4쪽", "test_scores/chopin_nocturne_Db_6-8.pdf", 3),
    ("쇼팽 Db 5쪽", "test_scores/chopin_nocturne_Db_6-8.pdf", 4),
    ("쇼팽 Db 6쪽", "test_scores/chopin_nocturne_Db_6-8.pdf", 5),
    ("쇼팽 Bbm 1쪽", "test_scores/chopin_nocturne_Bbm.pdf", 0),
    ("쇼팽 Em 1쪽", "test_scores/chopin_nocturne_Em.pdf", 0),
]


def main():
    if len(sys.argv) > 1:
        page = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        targets = [(os.path.basename(sys.argv[1]), sys.argv[1], page)]
    else:
        targets = TARGETS

    print("=" * 104)
    print("remove_accidental_ghosts 삭제 실측 — 창 0.5~1.6sp(왼쪽) × ±1.25sp")
    print("=" * 104)
    print(f"{'악보':22s} {'라벨':>5s} {'임시표':>6s} {'♮':>4s} {'창발동':>6s} "
          f"{'삭제':>5s} {'자기임시표':>9s} {'지속방아쇠':>9s} {'지속삭제':>8s}")
    all_hits = []
    for label, path, page in targets:
        if not os.path.isfile(path):
            print(f"{label:22s}  파일 없음")
            continue
        s, hits, _n, _a = survey(path, page)
        all_hits.append((label, hits))
        print(f"{label:22s} {s['라벨(삭제 전)']:5d} {s['임시표']:6d} {s['♮']:4d} "
              f"{s['창 발동']:6d} {s['삭제된 음표']:5d} "
              f"{s['삭제 중 자기임시표 있음']:9d} "
              f"{s['방아쇠가 지속(글리프 없음)']:9d} {s['지속 방아쇠로 삭제된 음표']:8d}  {s['문맥']}")

    print("\n" + "=" * 104)
    print("삭제 건 상세 — **방아쇠가 지속(글리프 없음)**인 것만. Astra 지적 1번의 경로다")
    print("=" * 104)
    n_susp = 0
    for label, hits in all_hits:
        rows = [h for h in hits if h["trig_carried"]]
        if not rows:
            continue
        print(f"\n### {label}  의심 {len(rows)}건")
        for h in rows:
            n_susp += 1
            print(f"  지워짐 x={h['x']:5d} y={h['y']:5d} {h['pitch']:4s} "
                  f"임시표={h['own_acc'] or '-':7s} 잉크={h['weak_ink']:.2f} "
                  f"| 방아쇠 x={h['trig_x']:5d} {h['trig_pitch']:4s} {h['trig_acc']}(지속) "
                  f"| dx={h['dx_sp']:.2f}sp dy={h['dy_sp']:.2f}sp Δstep={h['dstep']:+.1f}")
    if n_susp == 0:
        print("\n  없음 — 삭제된 것은 전부 자기 임시표가 없고 좌우잉크도 0.40 미만이었다.")
    print(f"\n>> 의심 건 합계 {n_susp}개")


if __name__ == "__main__":
    main()
