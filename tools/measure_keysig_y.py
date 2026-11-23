# -*- coding: utf-8 -*-
"""조표 ♯·♭ 글리프의 **세로 위치**를 잰다. 측정 전용 — 인식 경로에 안 붙어 있다.

왜 이 방식인가 — 조표 글리프는 서로 겹친다. 글리프 하나를 x범위로 오려내
잉크 무게중심을 재면 **옆 글리프의 가로획이 섞여** 값이 흔들린다
(실측 잔차 -0.02 / -0.06 / -2.89step, 방향이 제각각이었다).

그래서 자르지 않는다. `clef_keysig._find_bars`가 **이미 찾아 둔 세로막대**를 쓴다.

- **♯** — 세로획이 둘이고 위아래로 어긋나 있다. 어긋난 만큼이 상쇄되므로
  **쌍의 중심이 곧 글리프 중심**이다(전제 자체를 ♯1에서 먼저 검증했다).
- **♭** — 세로획이 하나뿐이라 중심이 표기 위치가 아니다. **표기 위치에서 얼마나
  떨어져 있고 그 값이 일정한가**를 잰다. 실측 오프셋 `+1.170step` ±0.040.
  이때 **닫기(0.4sp) 이미지로 재면 안 된다** — 오선 제거 잔여 잉크를 막대에
  이어붙여 위끝이 0.5step까지 흔들린다. `flat_runs`가 원시 프로파일을 쓴다.

조표 막대를 고르는 것도 판정 코드와 같다 — **교차 투표 + `KEYSIG_GAP_SP` 간격 규칙**.

출력 단위는 `step`(반칸)이다. step = (grid_bottom - y) / (spacing/2). 1step = 0.5sp.

사용법 (Windows는 `PYTHONIOENCODING=utf-8` 필요 — `♯`이 cp949에 없다):
    python tools/measure_keysig_y.py --summary
    python tools/measure_keysig_y.py <PDF경로> <기대 개수>
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from modules.preprocess import preprocess
from modules.notehead_detect import remove_staff_lines
from modules import clef_keysig as ck

# 조표 ♯의 고정 위치 (SHARP_ORDER = "FCGDAEB" 순서, step = 맨 아랫줄 기준 반칸 수)
#   treble 맨 아랫줄 E4 → F5=8, C5=5, G5=9, D5=6, A4=3, E5=7, B4=4
#   bass   맨 아랫줄 G2 → F3=6, C3=3, G3=7, D3=4, A2=1, E3=5, B2=2
STEP_TABLE = {
    "treble": [8, 5, 9, 6, 3, 7, 4],
    "bass":   [6, 3, 7, 4, 1, 5, 2],
}

# 조표 ♭의 고정 위치 (FLAT_ORDER = "BEADGCF" 순서)
#   treble 맨 아랫줄 E4 → B4=4, E5=7, A4=3, D5=6, G4=2, C5=5, F4=1
#   bass   맨 아랫줄 G2 → B2=2, E3=5, A2=1, D3=4, G2=0, C3=3, F2=-1
FLAT_TABLE = {
    "treble": [4, 7, 3, 6, 2, 5, 1],
    "bass":   [2, 5, 1, 4, 0, 3, -1],
}


def _bar_runs(band, sp, x0, x1, r0, r1, margin_sp=1.2):
    """막대 x는 **검출 코드 그대로**(r0~r1) 얻고, 세로 런만 **넓힌 창**에서 잰다.

    검출 창 `r0 = 맨윗줄 - 1.5sp`는 오선 위로 0.5sp 나가 있는 `G♯`(treble 3번째)의
    글리프 윗부분을 잘라 중심을 아래로 민다(실측 -0.45step). 검출 조건은 건드리지
    않고 **측정 창만** 위아래로 `margin_sp`만큼 넓힌다.
    """
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(sp * 0.4)) | 1))
    seg_det = cv2.morphologyEx(band[r0:r1, x0:x1], cv2.MORPH_CLOSE, vk)
    m0 = max(0, int(r0 - sp * margin_sp))
    m1 = min(band.shape[0], int(r1 + sp * margin_sp))
    seg = cv2.morphologyEx(band[m0:m1, x0:x1], cv2.MORPH_CLOSE, vk)
    H, W = seg.shape

    def longest_run(col):
        best = (0, -1, -1)
        run = 0
        for i, v in enumerate(col):
            if v:
                run += 1
                if run > best[0]:
                    best = (run, i - run + 1, i)
            else:
                run = 0
        return best

    starts, ends = [], []
    for c in range(W):
        n, a, b = longest_run(seg[:, c] > 0)
        starts.append(a); ends.append(b)
    det_runs = np.array([longest_run(seg_det[:, c] > 0)[0] for c in range(W)])
    is_bar_col = (det_runs >= sp * 1.6) & (det_runs <= sp * 3.4)

    bars, _ = ck._find_bars(band, sp, x0, x1, r0, r1)   # (x, band지역 y) 목록
    out = []
    for bx, _by in bars:
        c = int(round(bx - x0))
        c = min(max(c, 0), W - 1)
        lo = hi = c
        while lo - 1 >= 0 and is_bar_col[lo - 1]:
            lo -= 1
        while hi + 1 < W and is_bar_col[hi + 1]:
            hi += 1
        cols = [i for i in range(lo, hi + 1) if is_bar_col[i]] or [c]
        a = float(np.median([starts[i] for i in cols]))
        b = float(np.median([ends[i] for i in cols]))
        # ♭의 '배'(고리) 무게중심 — 막대 오른쪽 0.20~0.60sp 슬라이스.
        # 자르는 게 아니라 **이미 검출된 막대**를 기준점으로 삼는다. 이웃 ♭의
        # 막대는 0.95sp 밖, 이웃의 배는 왼쪽으로 0.35sp 못 미쳐 안 섞인다.
        q0 = int(round(c + sp * 0.20)); q1 = int(round(c + sp * 0.60))
        q0, q1 = max(0, min(q0, W)), max(0, min(q1, W))
        bowl = None
        if q1 > q0:
            ink = seg[:, q0:q1] > 0
            rows = ink.sum(axis=1)
            if rows.sum() > 0:
                bowl = m0 + float((np.arange(len(rows)) * rows).sum() / rows.sum())
        out.append({"x": bx, "y0": m0 + a, "y1": m0 + b, "yc": m0 + (a + b) / 2.0,
                    "h": (b - a + 1) / sp, "w": len(cols), "bowl": bowl})
    return out


def flat_runs(band, sp, bars, x0):
    """♭ 막대의 세로 런을 **닫기 없이 원시 프로파일에서** 잰다.

    ♭는 세로획이 하나뿐이라 ♯의 '쌍 평균'을 못 쓴다. 그런데 닫기(0.4sp)를 건 상태로
    재면 **오선 제거 잔여 잉크와 막대가 이어붙어** 위끝이 0.5step까지 흔들린다
    (실측: 같은 B♭이 보표마다 7.58 / 7.83 / 8.12).

    세로획은 오선 제거가 잘 안 지우므로 **원시 프로파일에서도 대개 안 끊긴다.**
    끊긴 열은 런이 짧아지므로 `1.6sp` 이상인 열만 골라 중앙값을 쓴다.
    """
    out = []
    for b in bars:
        c = int(round(b["x"] - x0))
        cols = []
        for cc in range(max(0, c - 2), min(band.shape[1] - x0, c + 3)):
            col = band[:, x0 + cc] > 0
            best = (0, -1, -1); run = 0
            for i, v in enumerate(col):
                if v:
                    run += 1
                    if run > best[0]:
                        best = (run, i - run + 1, i)
                else:
                    run = 0
            if best[0] >= sp * 1.6:
                cols.append(best)
        if not cols:
            out.append(None)
            continue
        a = float(np.median([x[1] for x in cols]))
        z = float(np.median([x[2] for x in cols]))
        out.append({"y0": a, "y1": z, "h": (z - a + 1) / sp, "n": len(cols)})
    return out


def measure(path, page=0):
    res = preprocess(path, pdf_page=page)
    no_staff = remove_staff_lines(res.binary, res.staves)
    img_h = res.binary.shape[0]
    ctxs = ck.analyze_staves(res)

    rows = []
    for staff in res.staves:
        ctx = ctxs.get(staff.index)
        if ctx is None or not ctx.clef_found:
            continue
        sp = staff.spacing
        top = max(0, int(staff.top - sp * 3))
        bottom = min(img_h, int(staff.bottom + sp * 3))
        band = no_staff[top:bottom, :]
        H, W = band.shape
        r0 = max(0, int((staff.top - top) - sp * 1.5))
        r1 = min(H, int((staff.bottom - top) + sp * 1.5) + 1)

        # 조표 시작: 음자리표 끝 뒤 첫 잉크. 끝: 넉넉히 12sp (창 문제를 배제하고 잰다)
        ink_cnt = (band[r0:r1, :] > 0).sum(axis=0)
        x = ctx.clef_end
        while x < min(W, ctx.clef_end + int(sp * 1.5)) and ink_cnt[x] == 0:
            x += 1
        x0, x1 = x, min(W, x + int(sp * 12))

        bars = _bar_runs(band, sp, x0, x1, r0, r1)
        raws = flat_runs(band, sp, bars, x0)
        for b in bars:                       # band 지역좌표 → 절대 y → step
            b["abs_y"] = top + b["yc"]
            b["step"] = (staff.grid_bottom - b["abs_y"]) / (sp / 2.0)
            b["step_top"] = (staff.grid_bottom - (top + b["y0"])) / (sp / 2.0)
            b["step_bot"] = (staff.grid_bottom - (top + b["y1"])) / (sp / 2.0)
            rw = raws[bars.index(b)]
            b["raw_top"] = None if rw is None else (staff.grid_bottom - (top + rw["y0"])) / (sp / 2.0)
            b["raw_bot"] = None if rw is None else (staff.grid_bottom - (top + rw["y1"])) / (sp / 2.0)
            b["raw_h"] = None if rw is None else rw["h"]
            b["step_bowl"] = (None if b["bowl"] is None
                              else (staff.grid_bottom - (top + b["bowl"])) / (sp / 2.0))

        # 쌍 만들기 (검출 코드와 같은 규칙 0.3~0.55sp)
        pairs, singles, i = [], [], 0
        while i < len(bars):
            if i + 1 < len(bars) and sp * 0.3 <= bars[i + 1]["x"] - bars[i]["x"] <= sp * 0.55:
                l, r = bars[i], bars[i + 1]
                pairs.append({"x": (l["x"] + r["x"]) / 2.0,
                              "step": (l["step"] + r["step"]) / 2.0,
                              "step_L": l["step"], "step_R": r["step"],
                              "dx": r["x"] - l["x"], "h_L": l["h"], "h_R": r["h"]})
                i += 2
            else:
                singles.append(bars[i]); i += 1
        rows.append({"staff": staff.index, "clef": ctx.clef, "sp": sp,
                     "bars": bars, "pairs": pairs, "singles": singles,
                     "key_count": ctx.key_count, "key_symbol": ctx.key_symbol})
    return rows


def pair_bars(bars, sp, y_tol=1.0):
    """막대를 ♯ 글리프 단위로 묶는다. x 간격(0.3~0.55sp)에 더해 **y 일치**를 본다.

    같은 글리프의 두 세로획은 y가 0.2~0.55step밖에 안 벌어진다. 겹친 잉크가 만든
    가짜 막대나 옆 글리프의 획을 잘못 묶으면 2.7step 넘게 벌어진다. y 조건을 같이
    걸면 탐욕적 쌍짓기가 한 칸씩 밀리는 것을 막는다.
    """
    pairs, leftover, i = [], [], 0
    while i < len(bars):
        l = bars[i]
        r = bars[i + 1] if i + 1 < len(bars) else None
        if (r is not None and sp * 0.3 <= r["x"] - l["x"] <= sp * 0.55
                and abs(l["step"] - r["step"]) <= y_tol):
            pairs.append({"x": (l["x"] + r["x"]) / 2.0,
                          "step": (l["step"] + r["step"]) / 2.0,
                          "step_L": l["step"], "step_R": r["step"],
                          "dx": r["x"] - l["x"], "h_L": l["h"], "h_R": r["h"]})
            i += 2
        else:
            leftover.append(l)
            i += 1
    return pairs, leftover


def summarize(paths, y_tol=1.0):
    """(음자리표, 조표 순번)별 잔차. 글리프 수가 기대와 다른 보표는 **빼고 따로 센다**.

    순번 대응이 깨진 보표의 잔차를 섞으면 ±3step짜리가 들어가 표가 틀린 것처럼
    보인다 - 이번 측정 실패의 원인이 그것이다.
    """
    agg, mismatch = {}, []
    for path, expect in paths:
        for r in measure(path):
            tbl = STEP_TABLE[r["clef"]]
            pairs, leftover = pair_bars(r["bars"], r["sp"], y_tol)
            if len(pairs) < expect:
                mismatch.append((os.path.basename(path), r["staff"], r["clef"],
                                 expect, len(pairs), len(leftover)))
                continue
            for k, p in enumerate(pairs[:expect]):
                agg.setdefault((r["clef"], k), []).append(p["step"] - tbl[k])
    return agg, mismatch


def main_summary():
    base = "tests/fixtures/key_signatures/pdf"
    paths = [(f"{base}/02_G_major_sharp1.pdf", 1), (f"{base}/03_D_major_sharp2.pdf", 2),
             (f"{base}/04_A_major_sharp3.pdf", 3), (f"{base}/05_E_major_sharp4.pdf", 4),
             (f"{base}/06_B_major_sharp5.pdf", 5), (f"{base}/07_Fs_major_sharp6.pdf", 6),
             (f"{base}/13_Cs_major_sharp7.pdf", 7)]
    agg, mismatch = summarize(paths)
    print("음자리표 | 순번 | 음 | 기대step | 표본 | 평균오차 | 최소 | 최대")
    for clef in ("treble", "bass"):
        for k in range(7):
            v = agg.get((clef, k))
            if not v:
                continue
            a = np.array(v)
            print(f"{clef:7s} | {k+1:2d} | {ck.SHARP_ORDER[k]} | {STEP_TABLE[clef][k]:2d} "
                  f"| {len(a):3d} | {a.mean():+.3f} | {a.min():+.3f} | {a.max():+.3f}")
    print(f"\n글리프 수가 기대에 못 미친 보표 {len(mismatch)}개")
    for name, st, clef, exp, got, left in mismatch:
        print(f"  {name} 보표{st} {clef} 기대 {exp} -> 쌍 {got} 남은막대 {left}")


SHARP_PDFS = [("02_G_major_sharp1", 1), ("03_D_major_sharp2", 2), ("04_A_major_sharp3", 3),
              ("05_E_major_sharp4", 4), ("06_B_major_sharp5", 5), ("07_Fs_major_sharp6", 6),
              ("13_Cs_major_sharp7", 7)]
FLAT_PDFS = [("12_F_major_flat1", 1), ("11_Bb_major_flat2", 2), ("10_Eb_major_flat3", 3),
             ("09_Ab_major_flat4", 4), ("08_Db_major_flat5", 5), ("14_Gb_major_flat6", 6),
             ("15_Cb_major_flat7", 7)]
BASE = "tests/fixtures/key_signatures/pdf"


def collect_sharp(y_tol=1.0):
    """♯: 쌍의 y 중심 = 글리프 중심. (clef, 순번) -> 실측 step 목록."""
    agg, mismatch = {}, []
    for name, expect in SHARP_PDFS:
        for r in measure(f"{BASE}/{name}.pdf"):
            pairs, leftover = pair_bars(r["bars"], r["sp"], y_tol)
            if len(pairs) < expect:
                mismatch.append((name, r["staff"], r["clef"], expect, len(pairs)))
                continue
            for k, p in enumerate(pairs[:expect]):
                agg.setdefault((r["clef"], k), []).append(p["step"])
    return agg, mismatch


def keysig_group(rows):
    """조표 막대의 x를 **교차 투표 + 간격 규칙**으로 고른다 — 판정 코드와 같은 방식.

    낮은음자리표 글리프의 잔여 조각(x=235, 보표 8개 중 2개)이나 박자표·음표 기둥이
    섞이는 것을 막는다. 조표는 모든 보표에서 같은 x에 있으므로 투표로 갈린다.
    """
    if not rows:
        return []
    sp = float(np.median([r["sp"] for r in rows]))
    all_x = sorted(b["x"] for r in rows for b in r["bars"])
    threshold = max(2, (len(rows) + 1) // 2)
    consensus, i = [], 0
    while i < len(all_x):
        j = i
        while j + 1 < len(all_x) and all_x[j + 1] - all_x[i] <= 3.0:
            j += 1
        if j - i + 1 >= threshold:
            consensus.append(float(np.mean(all_x[i:j + 1])))
        i = j + 1
    if not consensus:
        return []
    group = [consensus[0]]
    for c in consensus[1:]:
        if c - group[-1] > sp * ck.KEYSIG_GAP_SP:
            break
        group.append(c)
    return group


def collect_flat():
    """♭: 막대 하나가 글리프 하나. **원시 프로파일** 세로 런의 중심을 모은다."""
    agg, mismatch = {}, []
    for name, expect in FLAT_PDFS:
        rows = measure(f"{BASE}/{name}.pdf")
        group = keysig_group(rows)
        if len(group) != expect:
            mismatch.append((name, -1, "-", expect, len(group)))
            continue
        for r in rows:
            for k, gx in enumerate(group):
                hit = [b for b in r["bars"] if abs(b["x"] - gx) <= 3.0]
                if not hit or hit[0]["raw_top"] is None:
                    mismatch.append((name, r["staff"], r["clef"], k + 1, 0))
                    continue
                b = hit[0]
                agg.setdefault((r["clef"], k), []).append(
                    ((b["raw_top"] + b["raw_bot"]) / 2.0, b["raw_top"], b["raw_bot"]))
    return agg, mismatch


def _stat(vals, exp):
    a = np.array(vals, dtype=float) - exp
    return len(a), a.mean(), np.abs(a).max()


def main_summary():
    print("=" * 78)
    print("♯ — 세로막대 쌍의 y 중심. 단위: step(반칸) / sp. 1step = 0.5sp")
    print("=" * 78)
    sag, smis = collect_sharp()
    print("음자리표 | 순번 | 음 | 기대step | 표본 | 평균오차step | 최대|오차|step | 최대|오차|sp")
    for clef in ("treble", "bass"):
        for k in range(7):
            v = sag.get((clef, k))
            if not v:
                continue
            n, m, mx = _stat(v, STEP_TABLE[clef][k])
            print(f"{clef:7s} | {k+1:2d} | {ck.SHARP_ORDER[k]} | {STEP_TABLE[clef][k]:3d} "
                  f"| {n:3d} | {m:+.3f} | {mx:.3f} | **{mx/2:.3f}**")
    print(f"글리프 수 부족 보표 {len(smis)}개: " +
          ", ".join(f"{n}/보표{s}({c} {e}→{g})" for n, s, c, e, g in smis))

    print()
    print("=" * 78)
    print("♭ — **원시 프로파일**(닫기 없이) 세로 런의 중심. ♭는 막대가 하나뿐이라")
    print("     글리프 중심이 아니다. 표기 위치에서 얼마나 떨어져 있고 그 값이")
    print("     **일정한가**를 본다. 일정하면 상수 하나로 표에 붙는다.")
    print("=" * 78)
    fag, fmis = collect_flat()
    print("음자리표 | 순번 | 음 | 기대step | 표본 | 런중심-기대 | 표준편차 | 폭 | 런높이")
    off_all = []
    for clef in ("treble", "bass"):
        for k in range(7):
            v = fag.get((clef, k))
            if not v:
                continue
            exp = FLAT_TABLE[clef][k]
            ctr = np.array([a for a, _, _ in v]) - exp
            hh = np.array([t - b for _, t, b in v])
            off_all += list(ctr)
            print(f"{clef:7s} | {k+1:2d} | {ck.FLAT_ORDER[k]} | {exp:3d} | {len(v):3d} "
                  f"| {ctr.mean():+.3f} | ±{ctr.std():.3f} "
                  f"| {ctr.min():+.3f}~{ctr.max():+.3f} | {hh.mean():.2f}step")
    off_all = np.array(off_all)
    print(f"\n전체 {len(off_all)}개: 오프셋 {off_all.mean():+.4f}step ±{off_all.std():.4f} "
          f"(폭 {off_all.min():+.3f}~{off_all.max():+.3f})")
    print(f"오프셋을 상수 {off_all.mean():.3f}로 놓았을 때 최대 잔차 "
          f"**{np.abs(off_all - off_all.mean()).max():.3f}step = "
          f"{np.abs(off_all - off_all.mean()).max()/2:.3f}sp**")
    if fmis:
        print(f"막대/글리프 불일치 {len(fmis)}건: " +
              ", ".join(f"{n}/보표{s}({c} {e}→{g})" for n, s, c, e, g in fmis))
    else:
        print("막대/글리프 불일치 0건")

    print()
    print("=" * 78)
    print("낮은음자리표 = 높은음자리표 - 2step(한 칸)? — 표를 안 쓰고 실측끼리 뺀다")
    print("=" * 78)
    print("기호 | 순번 | 음 | treble실측 | bass실측 | 차이(step) | 기대 2.000")
    for label, agg, order, getter in (("♯", sag, ck.SHARP_ORDER, lambda v: v),
                                      ("♭", fag, ck.FLAT_ORDER, lambda v: [a for a, _, _ in v])):
        for k in range(7):
            t, b = agg.get(("treble", k)), agg.get(("bass", k))
            if not t or not b:
                continue
            tm, bm = np.mean(getter(t)), np.mean(getter(b))
            print(f"  {label}  | {k+1:2d} | {order[k]} | {tm:7.3f} | {bm:7.3f} "
                  f"| **{tm - bm:.3f}** |")


if __name__ == "__main__":
    if sys.argv[1] == "--summary":
        main_summary()
        sys.exit(0)
    target = sys.argv[1]
    expect = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    flat = "flat" in os.path.basename(target)
    rows = measure(target)
    print(f"# {os.path.basename(target)}  기대 {expect}개  판정 {rows[0]['key_symbol']}{rows[0]['key_count']}")
    for r in rows:
        tbl = FLAT_TABLE[r["clef"]] if flat else STEP_TABLE[r["clef"]]
        print(f"\n[보표 {r['staff']}] {r['clef']} sp={r['sp']:.2f} 막대 {len(r['bars'])}개")
        if flat:
            for k, b in enumerate(r["bars"]):
                exp = tbl[k] if k < len(tbl) else None
                bw = b["step_bowl"]
                print(f"   ♭{k+1} x={b['x']:7.2f} 아래끝={b['step_bot']:6.2f} "
                      f"위끝={b['step_top']:6.2f} 배={bw:6.2f} 기대={exp} "
                      f"배오차={bw - exp:+.2f}" if exp is not None else "")
        else:
            pairs, leftover = pair_bars(r["bars"], r["sp"])
            for k, p in enumerate(pairs):
                exp = tbl[k] if k < len(tbl) else None
                err = (p["step"] - exp) if exp is not None else float("nan")
                print(f"   ♯{k+1} x={p['x']:7.2f} dx={p['dx']:5.2f} step={p['step']:6.2f} "
                      f"(L {p['step_L']:6.2f} / R {p['step_R']:6.2f}) 기대={exp} 오차={err:+.2f}")
            for s in leftover:
                print(f"   남은막대 x={s['x']:7.2f} step={s['step']:6.2f} h={s['h']:.2f}")
