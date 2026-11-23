# -*- coding: utf-8 -*-
"""조표 ♯의 **구조 막대**(교차 투표 통과)에서 세로 위치를 잰다. 측정 전용.

`KEYSIG_PAIR_Y_STEP = 1.75`의 유도 근거를 다시 만든다 — 「같은 글리프의 두 세로획」과
「다른 글리프」의 `|Δstep|` 분포다. 문턱을 바꾸려면 이 출력으로 바꾼다.

`tools/measure_keysig_y.py`는 보표별(per-staff) 막대로 쟀다. 판정은 **교차 투표를
통과한 구조 막대**로 하므로 그쪽에서도 같은지 확인해야 했다. **같았다** —
잔차가 양쪽 다 `0.212step = 0.106sp`. 자세한 경과는 `docs/KEYSIG_REDESIGN.md` 부록 2.

구조 막대는 x만 남은 합의값이라 y가 없다. 그래서 **보표별 막대로 되돌아가 읽는다**
(±3px, 투표 클러스터와 같은 폭). 판정 코드의 `_same_glyph`와 같은 방식이다.

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요 — `♯`이 cp949에 없다):
    python tools/measure_keysig_consensus.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from modules import clef_keysig as ck
from modules.preprocess import preprocess
from measure_keysig_y import STEP_TABLE, BASE


def analyze(path, page=0):
    """(contexts, 보표별 [(x, step)], 구조 막대 x 목록, 중앙 sp)"""
    res = preprocess(path, pdf_page=page)
    ctxs = ck.analyze_staves(res)
    rows = []
    for staff in res.staves:
        ctx = ctxs.get(staff.index)
        if ctx is None or not ctx.clef_found:
            continue
        rows.append({"i": staff.index, "clef": ctx.clef, "sp": ctx.spacing,
                     "bars": list(ctx.bars)})

    # 교차 투표 — `_vote_key_signature`와 같은 규칙
    found = [c for c in ctxs.values() if c.clef_found]
    sp = float(np.median([c.spacing for c in found])) if found else 0.0
    threshold = max(2, (len(found) + 1) // 2) if len(found) > 1 else 1
    all_x = sorted(x for c in found for x, _y in c.bars)
    cons, i = [], 0
    while i < len(all_x):
        j = i
        while j + 1 < len(all_x) and all_x[j + 1] - all_x[i] <= 3.0:
            j += 1
        if j - i + 1 >= threshold:
            cons.append(float(np.mean(all_x[i:j + 1])))
        i = j + 1
    return ctxs, rows, cons, sp


def dy_votes(rows, xa, xb):
    """구조 막대 둘의 |Δstep|을 보표마다. 두 막대가 다 있는 보표만 센다."""
    out = []
    for r in rows:
        ya = [s for x, s in r["bars"] if abs(x - xa) <= 3.0]
        yb = [s for x, s in r["bars"] if abs(x - xb) <= 3.0]
        if ya and yb:
            out.append(abs(ya[0] - yb[0]))
    return out


def pair_xonly(cons, sp):
    """**y 조건을 뺀** 쌍짓기. 가짜 쌍의 분포를 보려고 남겨 둔다."""
    out, i = [], 0
    while i < len(cons):
        if i + 1 < len(cons) and sp * 0.3 <= cons[i + 1] - cons[i] <= sp * 0.55:
            out.append((i, i + 1))
            i += 2
        else:
            i += 1
    return out


FIXTURES = [("01_C_major_0", 0, ""), ("02_G_major_sharp1", 1, "♯"),
            ("03_D_major_sharp2", 2, "♯"), ("04_A_major_sharp3", 3, "♯"),
            ("05_E_major_sharp4", 4, "♯"), ("06_B_major_sharp5", 5, "♯"),
            ("07_Fs_major_sharp6", 6, "♯"), ("13_Cs_major_sharp7", 7, "♯"),
            ("12_F_major_flat1", 1, "♭"), ("11_Bb_major_flat2", 2, "♭"),
            ("10_Eb_major_flat3", 3, "♭"), ("09_Ab_major_flat4", 4, "♭"),
            ("08_Db_major_flat5", 5, "♭"), ("14_Gb_major_flat6", 6, "♭"),
            ("15_Cb_major_flat7", 7, "♭")]
REAL = [("aoharu p1", "sample_images/KakaoTalk_20260731_162400402.png"),
        ("aoharu p2", "sample_images/KakaoTalk_20260731_162400402_01.png"),
        ("aoharu p3", "sample_images/KakaoTalk_20260731_162400402_02.png"),
        ("bach", "test_scores/bach_minuet_Am.pdf"),
        ("chopin Bbm", "test_scores/chopin_nocturne_Bbm.pdf"),
        ("chopin Db", "test_scores/chopin_nocturne_Db_6-8.pdf"),
        ("chopin Em", "test_scores/chopin_nocturne_Em.pdf")]

# ♯6·♯7에서 겹친 잉크가 만든 가짜 막대. 진짜/가짜 분포를 가르려고 여기서만 쓴다.
FAKE_X = 343.2


def main():
    print("=" * 96)
    print("1) 구조 막대 경로 잔차 — 정답 쌍만. per-staff 측정과 같은 값이 나와야 한다")
    print("=" * 96)
    resid, true_dy, fake_dy, chain_res = {}, [], [], []
    verdicts = []
    for name, n, sym in FIXTURES:
        ctxs, rows, cons, sp = analyze(f"{BASE}/{name}.pdf")
        c0 = ctxs[next(iter(ctxs))]
        verdicts.append((name, n, sym, c0.key_count, c0.key_symbol))
        if sym != "♯":
            continue
        good = [c for c in cons if abs(c - FAKE_X) >= 3.0]
        gp = pair_xonly(good, sp)
        assert len(gp) == n, (name, len(gp), n)
        for r in rows:
            tbl = STEP_TABLE[r["clef"]]
            centers = []
            for k, (a, b) in enumerate(gp):
                ya = [s for x, s in r["bars"] if abs(x - good[a]) <= 3.0]
                yb = [s for x, s in r["bars"] if abs(x - good[b]) <= 3.0]
                if not ya or not yb:
                    centers.append(None)
                    continue
                true_dy.append(abs(ya[0] - yb[0]))
                c = (ya[0] + yb[0]) / 2.0
                centers.append(c)
                resid.setdefault((r["clef"], k), []).append(c - tbl[k])
            for k in range(len(gp) - 1):
                if centers[k] is None or centers[k + 1] is None:
                    continue
                chain_res.append((centers[k + 1] - centers[k]) - (tbl[k + 1] - tbl[k]))
        for c in cons:
            if abs(c - FAKE_X) < 3.0:
                for o in cons:
                    if sp * 0.3 <= abs(o - c) <= sp * 0.55:
                        fake_dy += dy_votes(rows, min(c, o), max(c, o))

    print("음자리표 | 순번 | 음 | 기대 | 표본 | 평균오차 | 최대|오차|step | sp환산")
    worst = 0.0
    for clef in ("treble", "bass"):
        for k in range(7):
            v = resid.get((clef, k))
            if not v:
                continue
            a = np.array(v)
            mx = float(np.abs(a).max())
            worst = max(worst, mx)
            print(f"{clef:7s} | {k+1:2d} | {ck.SHARP_ORDER[k]} | {STEP_TABLE[clef][k]:3d} "
                  f"| {len(a):3d} | {a.mean():+.3f} | {mx:.3f} | **{mx/2:.3f}sp**")
    print(f"\n>> 최대 |오차| = {worst:.3f}step = **{worst/2:.3f}sp**  "
          f"(per-staff 측정도 0.212step = 0.106sp — 되돌아가 읽기가 정확도를 안 깎는다)")

    print("\n" + "=" * 96)
    print(f"2) 문턱 근거 — KEYSIG_PAIR_Y_STEP = {ck.KEYSIG_PAIR_Y_STEP}")
    print("=" * 96)
    real = {}
    for label, path in REAL:
        if not os.path.isfile(path):
            print(f"{label:12s} 파일 없음 — 건너뜀")
            continue
        real[label] = analyze(path)
        _c, rows, cons, sp = real[label]
        for a, b in pair_xonly(cons, sp):
            true_dy += dy_votes(rows, cons[a], cons[b])
    a, b = np.array(true_dy), np.array(fake_dy)
    tol = ck.KEYSIG_PAIR_Y_STEP
    print(f"같은 글리프의 두 획  n={len(a):3d}  중앙 {np.median(a):.3f}  "
          f"95% {np.percentile(a, 95):.3f}  **최대 {a.max():.3f}**")
    print(f"가짜 막대가 만든 쌍  n={len(b):3d}  **최소 {b.min():.3f}** ~ {b.max():.3f}"
          f"   (문턱을 만드는 데는 안 쓴다. 교차 확인용)")
    print(f"음악 규칙: 인접한 두 샤프의 step 차이는 -3/+4 → 다른 글리프면 최소 3step")
    print(f"기하평균 √({a.max():.3f}×3) = {np.sqrt(a.max()*3):.3f}  /  "
          f"√({a.max():.3f}×{b.min():.3f}) = {np.sqrt(a.max()*b.min()):.3f}")
    print(f">> {tol} — 진짜 최대의 {tol/a.max():.2f}배 위, 가짜 최소의 {b.min()/tol:.2f}배 아래")
    print(f"   0.5step은 못 쓴다: 진짜 쌍 중 초과 {int((a > 0.5).sum())}개 / {len(a)}")
    c = np.array(chain_res)
    print(f"\n(예비안) 사슬 조건 여유: |Δstep(k→k+1) − 표값| n={len(c)} "
          f"최대 {np.abs(c).max():.3f}step")

    print("\n" + "=" * 96)
    print("3) 판정 — 픽스처 15종")
    print("=" * 96)
    bad = 0
    fell_to_flat = 0
    for name, n, sym, got_n, got_s in verdicts:
        ok = (got_n == n and got_s == sym)
        bad += (not ok)
        # y 검사는 쌍을 **기각만** 하므로, ♯ 악보에서 쌍이 전부 기각되면 pairs가
        # 비어 ♭ 분기로 떨어진다. 이 조건이 만든 새 경로라 따로 센다.
        fell_to_flat += (sym == "♯" and got_s == "♭")
        print(f"{name:22s} 기대 {sym}{n}  판정 {got_s}{got_n}  {'통과' if ok else '**실패**'}")
    print(f"\n>> 15종 중 실패 {bad}개 · ♯이 ♭로 떨어진 것 {fell_to_flat}개")

    print("\n" + "=" * 96)
    print("4) 실제 악보 — 골든 3장 + test_scores 4개. 쌍마다 문턱까지의 여유")
    print("=" * 96)
    for label, _path in REAL:
        if label not in real:
            continue
        ctxs, rows, cons, sp = real[label]
        c0 = ctxs[next(iter(ctxs))]
        med = [float(np.median(dy_votes(rows, cons[i], cons[j])))
               for i, j in pair_xonly(cons, sp)]
        print(f"{label:12s} 보표{len(rows):2d}  판정 {c0.key_symbol}{c0.key_count:<2d} "
              f"쌍 중앙값 {[round(m, 3) for m in med]}  여유 "
              + (f"{tol/max(med):.2f}배" if med else "-"))
    return bad + fell_to_flat


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
