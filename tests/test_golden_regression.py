# -*- coding: utf-8 -*-
"""
골든 회귀 테스트 — RE:Aoharu 3페이지 정답 골든(711)과 PDF 17쪽 변화 감지용 스냅샷을 대조한다.

왜 필요한가: 이 프로젝트에서 회귀가 여러 번 났다. 임시표 규칙을 고치면 검출이
따라 움직이고, 라벨 배치를 고치면 겹침이 새로 생기는 식이다. 눈으로 대조하는
데는 한 페이지에 수십 분이 들어서, 고친 뒤에 그냥 넘어가기 쉽다.
그래서 확정된 결과를 파일로 박아 두고 매번 기계가 대조하게 한다.

두 층을 각각 다른 엄격도로 본다:

  1) 라벨 (tests/golden/aoharu_p*.tsv)
     음표 좌표·음이름·임시표·고정도·이동도 표기까지 **한 글자도 달라지면 실패**.
     검출과 표기는 이미 육안 전수 대조를 마친 값이라 바뀔 이유가 없다.

  1-1) 문맥 (tests/golden/aoharu_p*_context.tsv)
     보표마다 음자리표·조표·헤더 끝. **라벨 줄의 음이름만으로는 조표 변화를 못 본다** —
     조표가 바뀐 음이 페이지에 없으면 라벨은 그대로다(tests/_score_context.py).
     박자표 값은 인식하지 않으므로 헤더 끝(header_end)이 그 흔적이다. 한 글자도 달라지면 실패.

  2) 배치 품질 (아래 LAYOUT_LIMITS)
     라벨 위치는 앞으로도 다듬을 여지가 있어 좌표까지 고정하지 않는다.
     대신 '절대 나빠지면 안 되는 선'만 지킨다 — 유령 0, 화음 상하 역전 0,
     라벨끼리 겹침 0, 음표 머리 가림 0, 음표에서 30px 넘게 떨어진 라벨 5개 이하.

사용법:
    python tests/test_golden_regression.py                     # 대조 (정답 골든 실패 · 스냅샷 변화를 따로 출력)
    python tests/test_golden_regression.py --update            # 아오하루 정답 골든 갱신 (승인받은 변경일 때만)
    python tests/test_golden_regression.py --update-snapshot   # PDF 스냅샷 갱신 (바뀐 줄을 육안 판정한 뒤)

sample_images의 악보가 없으면 건너뛴다(저장소에 포함되지 않는 파일이다).
"""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts
from modules.note_namer import to_solfege_batch, resolve_tonic
from modules.verify import reverse_check, drop_beam_ghosts, drop_offstaff_ghosts
from modules.renderer import render_solfege_on_image
from _ledger_check import check as ledger_check
from _score_context import context_lines, self_check as context_self_check

ROOT = os.path.join(os.path.dirname(__file__), "..")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
PAGES = [
    ("p1", os.path.join(ROOT, "sample_images", "KakaoTalk_20260731_162400402.png")),
    ("p2", os.path.join(ROOT, "sample_images", "KakaoTalk_20260731_162400402_01.png")),
    ("p3", os.path.join(ROOT, "sample_images", "KakaoTalk_20260731_162400402_02.png")),
]

# 배치 품질의 하한선. 라벨 위치 자체는 고정하지 않되, 이 선은 넘지 않아야 한다.
LAYOUT_LIMITS = {
    "두 보표 사이 귀속 불일치": 0,
    "유령 후보": 0,
    "화음 상하 역전": 0,
    "라벨끼리 겹침": 0,
    "음표 머리 가림": 0,
    "음표에서 30px 초과": 5,
}


def analyze(path):
    """한 페이지를 처리해 (라벨 줄 목록, 배치 지표, 문맥 줄 목록)을 돌려준다."""
    result = preprocess(path)
    contexts = analyze_staves(result)
    noteheads = detect_noteheads(result, contexts=contexts)
    noteheads, _beam_ghosts = drop_beam_ghosts(result, noteheads)
    noteheads, _glyph_ghosts = drop_offstaff_ghosts(result, noteheads)
    notes = calculate_pitches(noteheads, result.staves,
                              clef={i: c.clef for i, c in contexts.items()})
    accidentals = annotate_accidentals(result, contexts, notes)
    notes, accidentals = remove_accidental_ghosts(notes, accidentals, result.staves)

    found = [c for c in contexts.values() if c.clef_found]
    key_letters, key_symbol = (found[0].key_letters, found[0].key_symbol) if found else ((), "")
    tonic = resolve_tonic(key_symbol, len(key_letters))
    fixed = to_solfege_batch(notes, key_letters, key_symbol, accidentals, "solfege", [], "")
    movable = to_solfege_batch(notes, key_letters, key_symbol, accidentals,
                               "solfege-movable", [], tonic)

    lines = []
    for i, (note, fixed_text) in enumerate(fixed):
        lines.append("\t".join((
            str(note.staff_index), str(int(note.x)), str(int(note.y)),
            f"{note.note_name}{note.octave}", accidentals[i] or "-",
            fixed_text, movable[i][1],
        )))
    lines.sort()

    # ---- 배치 지표 ----
    spacings = {s.index: s.spacing for s in result.staves}
    tmp = os.path.join(tempfile.gettempdir(), "_golden_layout.png")
    placed = render_solfege_on_image(
        result.original_bgr, fixed, tmp, font_size=18,
        staff_spacings=spacings, staves=result.staves, text_offset_y=22,
    )
    metrics = {k: 0 for k in LAYOUT_LIMITS}
    metrics["유령 후보"] = len(reverse_check(result, notes))
    # 두 보표 사이의 음은 어느 보표로 읽느냐에 따라 음이름이 통째로 달라진다.
    # 순방향·역방향 점검이 둘 다 통과해도 여기서 틀릴 수 있어 따로 본다.
    metrics["두 보표 사이 귀속 불일치"] = sum(1 for r in ledger_check(path) if not r["ok"])
    for i, a in enumerate(placed):
        if a["gap"] > 30:
            metrics["음표에서 30px 초과"] += 1
        for b in placed[i + 1:]:
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                metrics["라벨끼리 겹침"] += 1
    for p in placed:
        for other in (q["note"] for q in placed):
            if other is p["note"]:
                continue
            sp = spacings.get(other.staff_index, 12.0)
            if (p["x"] < other.x + sp * 0.6 and other.x - sp * 0.6 < p["x"] + p["w"]
                    and p["y"] < other.y + sp * 0.5 and other.y - sp * 0.5 < p["y"] + p["h"]):
                metrics["음표 머리 가림"] += 1
                break
    by_staff = {}
    for p in placed:
        by_staff.setdefault(p["note"].staff_index, []).append(p)
    for idx, group in by_staff.items():
        sp = spacings[idx]
        for a in group:
            for b in group:
                if a is b or abs(a["note"].x - b["note"].x) >= sp * 0.9:
                    continue
                if a["note"].y < b["note"].y and a["y"] > b["y"]:
                    metrics["화음 상하 역전"] += 1
    return lines, metrics, context_lines(contexts)


def golden_path(tag, kind=""):
    return os.path.join(GOLDEN_DIR, f"aoharu_{tag}{kind}.tsv")


# ---- PDF 17쪽 「변화 감지용 스냅샷」 (2026-09-30, TASKS [1]) ----
# 위 아오하루 골든(711개)은 **육안 전수 대조로 정답이 확인된 기준**이고, 바뀌면 곧 퇴행이다.
# 이 스냅샷은 **정답이 아니다** — 검증 PDF 17쪽(바흐 1 · 쇼팽 B♭m 6 · D♭ 6 · Em 4)의 제품 출력을 그대로 찍어 둔 것이라
# 알려진 오류(A-17 임시표 뒤바뀜, 임시표 글리프 · 빔 위 유령 라벨 등)가 들어 있다. 목적은 **변화 감지**:
# 인식 코드를 바꿨을 때 이 17쪽에서 무엇이 바뀌었는지 한 줄도 빠짐없이 드러낸다.
# 바뀌면 이 테스트는 종료 코드 1로 멈추지만 **오류 판정이 아니다** — 바뀐 줄 목록(debug/snapshot_diff.tsv)을
# 육안(또는 PDF 글리프 정답)으로 판정해 고쳐짐이면 `--update-snapshot`, 새로 틀림 · 오삭제면 그 변경을 되돌린다.
# 값은 main.py를 명령줄 그대로 실행한 라벨 JSON에서 만든다 — 위 analyze()는 제품과 경로가 달라
# (remove_accidental_ghosts에 filled를 안 넘기고 chord_rescue도 없다) 제품에서만 도는 규칙을 못 본다
# (docs/MEASUREMENT_PITFALLS.md A-3b). 근거 docs/PDF_SNAPSHOT.md
PDF_DIR = os.path.join(ROOT, "test_scores")
PDF_PAGES = ([("bach", "bach_minuet_Am.pdf", 0)]
             + [(f"bbm{i + 1}", "chopin_nocturne_Bbm.pdf", i) for i in range(6)]
             + [(f"db{i + 1}", "chopin_nocturne_Db_6-8.pdf", i) for i in range(6)]
             + [(f"em{i + 1}", "chopin_nocturne_Em.pdf", i) for i in range(4)])
SNAPSHOT_HEADER = ("# 변화 감지용 스냅샷 — 정답이 아니다(알려진 오류 포함). {date} main {rev} 제품 출력(main.py 명령줄) 그대로.\n"
                   "# 바뀌면 오류가 아니라 판정 대상: 바뀐 줄을 육안 판정 → 고쳐짐이면 --update-snapshot. 근거 docs/PDF_SNAPSHOT.md\n"
                   "# 열: 보표 · x · y · 음이름 · 임시표 · 표기(고정도) · 확신도\n")
SNAPSHOT_DIFF = os.path.join(ROOT, "debug", "snapshot_diff.tsv")


def snapshot_path(tag, kind=""):
    return os.path.join(GOLDEN_DIR, f"snapshot_pdf_{tag}{kind}.tsv")


def run_product(pdf, page, tmp):
    """main.py를 명령줄 그대로 한 쪽 돌려 라벨 JSON을 읽는다."""
    import json
    import subprocess
    out = os.path.join(tmp, f"{os.path.splitext(pdf)[0]}_{page}.json")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), os.path.join(PDF_DIR, pdf),
                           "--page", str(page), "--no-debug", "--output-dir", tmp, "--save-labels", out],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError(f"{pdf} {page}쪽 실행 실패: {(proc.stdout + proc.stderr).strip().splitlines()[-3:]}")
    return json.load(io.open(out, encoding="utf-8"))


def pdf_lines(doc):
    """(라벨 줄, 문맥 줄). 문맥: 보표 · 음자리표 · 조표 기호 · 조표 개수."""
    labels = sorted("\t".join((str(l["staff"]), str(int(l["x"])), str(int(l["y"])), l["pitch"],
                               l["accidental"] or "-", l["text"], l["confidence"])) for l in doc["labels"])
    m = doc["music"]
    ctx = ["\t".join((str(s["id"]), s["clef"], m["key_symbol"] or "-", str(m["key_count"]))) for s in doc["staves"]]
    return labels, ctx


def golden_workers():
    """동시에 띄우는 main.py 수 — 환경변수 AKBO_GOLDEN_WORKERS(1 ~ 4), 기본 1. 범위 밖 · 숫자 아님이면 1.
    잠금 하나 아래 main.py 4개가 동시에 돌아 메모리 부족 중지를 낳았다(MEASUREMENT_PITFALLS B-9). 결과는 워커 수와 무관하다."""
    v = os.environ.get("AKBO_GOLDEN_WORKERS", "1")
    return int(v) if v.isdigit() and 1 <= int(v) <= 4 else 1


def pdf_snapshots(update):
    """PDF 17쪽 스냅샷 대조. (바뀐 쪽 요약 목록)을 돌려주고, 바뀐 줄 전부를 SNAPSHOT_DIFF에 쓴다."""
    from concurrent.futures import ThreadPoolExecutor
    changed, rows = [], []
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(golden_workers()) as ex:
        docs = list(ex.map(lambda p: run_product(p[1], p[2], tmp), PDF_PAGES))
    for (tag, _pdf, _pg), doc in zip(PDF_PAGES, docs):
        labels, ctx = pdf_lines(doc)
        before = len(changed)
        for kind, lines in (("", labels), ("_context", ctx)):
            gp = snapshot_path(tag, kind)
            if update:
                import datetime
                import subprocess
                rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                     cwd=ROOT).stdout.strip()
                io.open(gp, "w", encoding="utf-8", newline="\n").write(
                    SNAPSHOT_HEADER.format(date=datetime.date.today().isoformat(), rev=rev) + "\n".join(lines) + "\n")
                print(f"[스냅샷 갱신] {os.path.basename(gp)} — {len(lines)}줄")
                continue
            if not os.path.isfile(gp):                 # 없으면 멈춤 — 조용히 만들면 지워진 파일이 검사를 없앤다
                changed.append(f"{tag}{kind}: 스냅샷 파일이 없습니다 ({os.path.basename(gp)})")
                continue
            want = [l for l in io.open(gp, encoding="utf-8").read().splitlines() if not l.startswith("#")]
            if want != lines:
                only_want = [l for l in want if l not in set(lines)]
                only_got = [l for l in lines if l not in set(want)]
                rows += [f"{tag}{kind}\t사라짐\t{l}" for l in only_want] + [f"{tag}{kind}\t생김\t{l}" for l in only_got]
                changed.append(f"{tag}{kind}: {len(want)}줄 -> {len(lines)}줄 (사라짐 {len(only_want)} · 생김 {len(only_got)})")
        if not update and len(changed) == before:
            print(f"[스냅샷 같음] pdf {tag} — 라벨 {len(labels)}개 · 보표 {len(ctx)}개")
    if rows:
        os.makedirs(os.path.dirname(SNAPSHOT_DIFF), exist_ok=True)
        io.open(SNAPSHOT_DIFF, "w", encoding="utf-8", newline="\n").write(
            "쪽\t변화\t보표\tx\ty\t음이름\t임시표\t표기\t확신도\n" + "\n".join(rows) + "\n")
    return changed


# Verovio 조표 회귀 (2026-10-02, docs/KEYSIG_VOTE_FIX.md · DECISIONS §1-10). 정답은 SVG keySig.
# 다장조 4쪽: 쉼표 · 기둥 · 박자표가 같은 x라 ♭1로 읽히던 것(♭ 자리 확인) · Schumann L: 시스템 x 어긋남(보표 안 쌍 먼저)
# · 진짜 ♭ 중 자리 확인 여유가 가장 작은 쪽(Beethoven 0.57 · 0.67 — 알토 음자리표 보표 섞임, Joplin L 0.75)
VEROVIO_KEYS = [
    ("bach_bwv846_bravura_p1", "", 0), ("bach_bwv846_leipzig_p1", "", 0),
    ("mozart_k545_bravura_p1", "", 0), ("clara_polonaise_4_bravura_p1", "", 0),
    ("schumann_op48no2_piano_leipzig_p1", "♯", 3),
    ("beethoven_op18no1_bravura_p1", "♭", 1), ("beethoven_op18no1_leipzig_p1", "♭", 1),
    ("joplin_maple_leaf_leipzig_p1", "♭", 4),
]


def verovio_keys():
    from modules.preprocess import preprocess
    from modules.clef_keysig import analyze_staves
    from _score_context import page_key
    bad = []
    for stem, sym, cnt in VEROVIO_KEYS:
        letters, got = page_key(analyze_staves(preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png"))))
        if (got, len(letters)) != (sym, cnt):
            bad.append(f"{stem}: 조표 {got}{len(letters)} (정답 {sym or '없음'}{cnt or ''})")
        else:
            print(f"[조표 일치] {stem} — {sym or '없음'}{cnt or ''}")
    return bad


# 짧은 시스템 추가 검출 회귀 (2026-10-02, docs/SHORT_LAST_SYSTEM.md · DECISIONS §1-11).
# 진짜: Verovio 양끝 맞춤 안 한 마지막 시스템 — 보표 수. 가짜: 보표로 잡히면 실패 —
# D♭ 6쪽 페달 괄호선(x 겹침 −0.72), 회전 0.5° 합성 사진(--photo 없이) 오선 조각(최대 0.33)
SHORT_STAFF_PAGES = [("mozart_k545_leipzig_p1", 8), ("schumann_op48no2_piano_leipzig_p1", 6)]


def short_staves():
    import cv2
    import numpy as np
    from modules import preprocess as PP
    bad = []
    for stem, n in SHORT_STAFF_PAGES:
        got = len(preprocess(os.path.join(ROOT, "test_scores", "verovio", stem + ".png")).staves)
        if got != n:
            bad.append(f"{stem}: 보표 {got} (정답 {n}) — 짧은 마지막 시스템")
        else:
            print(f"[보표 일치] {stem} — {n}")

    def added(binary):
        # 보표 묶기가 실패하면 제품도 보표를 하나도 내지 않는다 — 조각이 추가될 수 없다(§1-15 평평한 꼭대기 뒤 회전 0.5° 원시 영상이 이 경우)
        try:
            base = PP.group_into_staves(PP.detect_staff_lines(binary), row_sum=PP.staff_line_profile(binary))
        except PP.StaffNotFoundError:
            return 0
        return len(PP._add_short_staves(binary, base)) - len(base)

    db6 = preprocess(os.path.join(PDF_DIR, "chopin_nocturne_Db_6-8.pdf"), pdf_page=5)
    if added(db6.binary):
        bad.append("D♭ 6쪽: 페달 괄호선이 보표로 잡혔습니다")
    else:
        print("[오검출 없음] D♭ 6쪽 페달선")
    sys.path.insert(0, ROOT)
    from tools.generate_synthetic_photos import image_case
    src = preprocess(os.path.join(PDF_DIR, "chopin_nocturne_Db_6-8.pdf"), pdf_page=0)
    data, _ext, _h, _sz, _c = image_case(src.original_bgr, float(np.median([s.spacing for s in src.staves])), {"rot": 0.5}, 0)
    _gray, binary = PP.binarize(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR))
    if added(binary):
        bad.append("회전 0.5° 합성 사진: 기울어진 오선 조각이 보표로 잡혔습니다")
    else:
        print("[오검출 없음] 회전 0.5° 사진 오선 조각")
    return bad


# 굵은 오선 한 줄의 평평한 꼭대기 회귀 (2026-10-04, docs/STAFF_PEAKS.md · DECISIONS §1-15). 600dpi에서 오선 한 줄이 봉우리 둘이 되어
# 보표가 빠지던 쪽(바뀌기 전: 바흐 보표 묶기 실패 · B♭m 3쪽 8 · D♭ 5쪽 9). (악보, 쪽, 정답 보표 수)
HIRES_STAFF_PAGES = [("bach_minuet_Am.pdf", 0, 8), ("chopin_nocturne_Bbm.pdf", 2, 10), ("chopin_nocturne_Db_6-8.pdf", 4, 10)]


def hires_staves():
    bad = []
    for f, pg, n in HIRES_STAFF_PAGES:
        try:
            got = len(preprocess(os.path.join(PDF_DIR, f), pdf_page=pg, pdf_dpi=600).staves)
        except Exception as e:
            got = type(e).__name__
        if got != n:
            bad.append(f"{f} {pg + 1}쪽 600dpi: 보표 {got} (정답 {n}) — 굵은 오선 한 줄이 두 줄로")
        else:
            print(f"[보표 일치] {f} {pg + 1}쪽 600dpi — {n}")
    return bad


# 임시표 정밀 판정 회귀 (2026-10-02, docs/NATURAL_SHARP.md · DECISIONS §1-12). 그 좌표에 음표를 직접 두고 **원시 판정**(전파 없음)만 본다 —
# 머리 검출이 바뀌어도 판정 규칙 자체를 지킨다. (쪽, 경로, pdf 쪽, 음표 x, y, 기대)
ACCIDENTAL_CASES = [
    ("Clara 3 Bravura ♮ — 예전 조건에서 ♯", "verovio/clara_polonaise_3_bravura_p1.png", 0, 715, 1382, "natural"),
    ("Clara 3 Leipzig ♮ — 두 획 어긋남 합 0.50(♮ 최소)", "verovio/clara_polonaise_3_leipzig_p1.png", 0, 620, 701, "natural"),
    ("Clara 3 Leipzig ♯ — 합 0.06(♯ 최대, 경계에 가장 가까움)", "verovio/clara_polonaise_3_leipzig_p1.png", 0, 1929, 2529, "#"),
    ("D♭ 3쪽 ♮ — A-17 재현", "chopin_nocturne_Db_6-8.pdf", 2, 987, 2897, "natural"),
    ("D♭ 3쪽 ♯ — A-17 재현", "chopin_nocturne_Db_6-8.pdf", 2, 1110, 2906, "#"),
]


def accidental_cases():
    from modules.pitch_calculator import PitchedNote
    bad, cache = [], {}
    for label, rel, pg, x, y, want in ACCIDENTAL_CASES:
        if (rel, pg) not in cache:
            res = preprocess(os.path.join(PDF_DIR, rel), pdf_page=pg)
            cache[(rel, pg)] = (res, analyze_staves(res))
        res, ctx = cache[(rel, pg)]
        st = min(res.staves, key=lambda s: abs((s.top + s.bottom) / 2 - y))
        got = annotate_accidentals(res, ctx, [PitchedNote(x=x, y=y, note_name="X", octave=0, staff_index=st.index)])[0]
        if got != want:
            bad.append(f"{label}: 원시 판정 {got or '없음'} (기대 {want})")
        else:
            print(f"[임시표 일치] {label}")
    return bad


# 임시표 전파 경계 회귀 (2026-10-03, A-25 · docs/A25_BARLINE.md §7 · DECISIONS §1-14). 머리 검출부터 전파까지 제품 순서로 돌려
# 그 자리 음표의 **전파 뒤** 임시표를 본다. (설명, 경로, pdf 쪽, x, y, 기대)
PROPAGATION_CASES = [
    ("바흐 Bravura B3 — 같은 마디 앞 ♭이 기둥을 넘어 전파", "verovio/bach_bwv846_bravura_p1.png", 0, 1794, 1559, "b"),
    ("바흐 Bravura B3 — 같은 마디 둘째", "verovio/bach_bwv846_bravura_p1.png", 0, 1908, 1559, "b"),
    ("Schumann Bravura E4 — 마디선 위 라벨에도 진짜 마디선 유지(흰 틈)", "verovio/schumann_op48no2_piano_bravura_p1.png", 0, 1523, 689, ""),
    ("B♭m 6쪽 F4 — 진짜 마디선 바로 옆 음표, 앞 마디 ♭이 넘어오면 실패", "chopin_nocturne_Bbm.pdf", 5, 1994, 1100, ""),
]


# 바뀐 음자리표 뒤 「확인 필요」 회귀 (2026-10-04, docs/CLEF_CHANGE.md · DECISIONS §1-16). (이름, 경로, pdf 쪽, 보표 순번(위에서), x, 구간 안이어야 하는가)
CLEF_CHANGE_CASES = [
    ("B♭m 2쪽 높은음자리표로 바뀐 뒤 C3 → 정답 A4", "chopin_nocturne_Bbm.pdf", 1, 1, 1428, True),
    ("B♭m 2쪽 바뀌기 전 음표", "chopin_nocturne_Bbm.pdf", 1, 1, 1300, False),
    ("Clara 1 Bravura 보표 9 — 낮은음자리표로 돌아온 뒤(x 1052)는 표시 안 함", "verovio/clara_polonaise_1_bravura_p1.png", 0, 9, 1100, False),
    ("Clara 1 Bravura 보표 9 — 높은음자리표 구간", "verovio/clara_polonaise_1_bravura_p1.png", 0, 9, 600, True),
]


def clef_change_cases():
    from modules.clef_keysig import clef_change_regions
    bad = []
    for name, rel, pg, order, x, want in CLEF_CHANGE_CASES:
        res = preprocess(os.path.join(PDF_DIR, rel), pdf_page=pg)
        st = sorted(res.staves, key=lambda s: s.top)[order]
        reg = clef_change_regions(res, analyze_staves(res))
        got = any(a <= x < b for a, b in reg.get(st.index, ()))
        if got != want:
            bad.append(f"{name}: 구간 안 {got} (기대 {want})")
        else:
            print(f"[음자리표 바뀜 일치] {name}")
    return bad


# 알토 음자리표 → 보표 전체 check 회귀 (2026-10-04, docs/ALTO_CLEF.md · DECISIONS §1-17). (경로, 보표 순번(위에서), 알토인가)
ALTO_CASES = [("verovio/beethoven_op18no1_bravura_p1.png", 2, True), ("verovio/beethoven_op18no1_bravura_p1.png", 0, False),
              ("verovio/beethoven_op18no1_bravura_p1.png", 3, False), ("chopin_nocturne_Db_6-8.pdf", 1, False)]


def alto_cases():
    from modules.clef_keysig import is_alto
    from modules.notehead_detect import remove_staff_lines
    bad = []
    for rel, order, want in ALTO_CASES:
        res = preprocess(os.path.join(PDF_DIR, rel), pdf_page=0)
        ctx = analyze_staves(res)
        st = sorted(res.staves, key=lambda s: s.top)[order]
        got = is_alto(remove_staff_lines(res.binary, res.staves), st, ctx[st.index])
        if got != want:
            bad.append(f"{rel} 보표 {order}: 알토 {got} (기대 {want})")
        else:
            print(f"[알토 판정 일치] {rel} 보표 {order} — {want}")
    return bad


# 덧줄 사다리 띠 회귀 (2026-10-04, DECISIONS §1-19). (경로, 보표 순번, 위 띠가 넘어야 할 sp) — 덧줄 5~6개 높은 음이 있는 보표
LADDER_CASES = [("verovio/clara_polonaise_3_bravura_p1.png", 6, 8.0), ("verovio/clara_polonaise_3_bravura_p1.png", 8, 8.0)]


def ladder_cases():
    from modules import notehead_detect as ND
    bad = []
    for rel, order, need in LADDER_CASES:
        res = preprocess(os.path.join(PDF_DIR, rel))
        st = sorted(res.staves, key=lambda s: s.top)[order]
        up = ND._band_margins(st, res.staves, ND.remove_staff_lines(res.binary, res.staves))[0] / st.spacing
        if up < need:
            bad.append(f"{rel} 보표 {order}: 위 검색 띠 {up:.1f}sp (≥ {need} 필요) — 덧줄 5~6개 높은 음이 잘린다")
        else:
            print(f"[덧줄 사다리 일치] {rel} 보표 {order} — 위 띠 {up:.1f}sp")
    return bad


def unknown_clef_cases():
    """음자리표 못 찾은 보표 → check(2026-10-05, DECISIONS §1-22). 베토벤 Bravura 첼로 보표 7은 표시, 음자리표를 직접 지정하면 표시 안 함."""
    from types import SimpleNamespace
    from modules.clef_keysig import unknown_clef_suspects
    res = preprocess(os.path.join(PDF_DIR, "verovio/beethoven_op18no1_bravura_p1.png"))
    ctx = analyze_staves(res)
    st = sorted(res.staves, key=lambda s: s.top)
    notes = [SimpleNamespace(staff_index=st[7].index), SimpleNamespace(staff_index=st[6].index)]
    bad = []
    auto = unknown_clef_suspects(ctx, notes, {i: c.clef for i, c in ctx.items()})
    if [n.staff_index for n in auto] != [st[7].index]:
        bad.append(f"베토벤 B: 자동 인식에서 표시 보표 {[n.staff_index for n in auto]} (기대 [{st[7].index}])")
    if unknown_clef_suspects(ctx, notes, "bass"):
        bad.append("베토벤 B: 음자리표를 직접 지정했는데 표시됨")
    if not bad:
        print("[음자리표 못 찾음 표시 일치] 베토벤 B 보표 7 · 직접 지정 시 표시 없음")
    return bad


def propagation_cases():
    from modules.notehead_detect import detect_noteheads
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
    from modules.pitch_calculator import calculate_pitches
    bad, cache = [], {}
    for label, rel, pg, x, y, want in PROPAGATION_CASES:
        if (rel, pg) not in cache:
            res = preprocess(os.path.join(PDF_DIR, rel), pdf_page=pg)
            ctx = analyze_staves(res)
            heads = detect_noteheads(res, contexts=ctx)
            heads, _ = drop_beam_ghosts(res, heads)
            heads, _ = drop_offstaff_ghosts(res, heads)
            notes = calculate_pitches(heads, res.staves, clef={i: c.clef for i, c in ctx.items()})
            cache[(rel, pg)] = (notes, annotate_accidentals(res, ctx, notes))
        notes, accs = cache[(rel, pg)]
        i = min(range(len(notes)), key=lambda i: abs(notes[i].x - x) + abs(notes[i].y - y))
        if abs(notes[i].x - x) + abs(notes[i].y - y) > 6:
            bad.append(f"{label}: 그 자리 음표를 못 찾음")
        elif accs[i] != want:
            bad.append(f"{label}: 전파 뒤 {accs[i] or '없음'} (기대 {want or '없음'})")
        else:
            print(f"[전파 일치] {label}")
    return bad


def main() -> None:
    update = "--update" in sys.argv                      # 아오하루 정답 골든만(승인 대상)
    update_snapshot = "--update-snapshot" in sys.argv    # PDF 스냅샷만(바뀐 줄 육안 판정 뒤)
    missing = [p for _t, p in PAGES if not os.path.isfile(p)]
    if missing:
        print(f"[건너뜀] 검증용 악보가 없습니다: {os.path.basename(missing[0])} 등 {len(missing)}개")
        return

    os.makedirs(GOLDEN_DIR, exist_ok=True)
    context_self_check()
    failures = []
    for tag, path in PAGES:
        lines, metrics, ctx = analyze(path)
        gp = golden_path(tag)

        if update or not os.path.isfile(gp):
            io.open(gp, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
            print(f"[갱신] {os.path.basename(gp)} — 라벨 {len(lines)}개")
        else:
            want = io.open(gp, encoding="utf-8").read().splitlines()
            if want != lines:
                only_want = [l for l in want if l not in set(lines)]
                only_got = [l for l in lines if l not in set(want)]
                failures.append(
                    f"{tag}: 라벨이 달라졌습니다 (골든 {len(want)}개 -> 현재 {len(lines)}개)\n"
                    + "".join(f"      - 사라짐: {l}\n" for l in only_want[:10])
                    + "".join(f"      + 생김:   {l}\n" for l in only_got[:10])
                )
            else:
                print(f"[일치] {tag} — 라벨 {len(lines)}개")

        # 문맥 골든은 없으면 **실패**다. 라벨 골든처럼 조용히 새로 만들면 지워진 파일이 검사를 없앤다
        cp = golden_path(tag, "_context")
        if update:
            io.open(cp, "w", encoding="utf-8", newline="\n").write("\n".join(ctx) + "\n")
            print(f"[갱신] {os.path.basename(cp)} — 보표 {len(ctx)}개")
        elif not os.path.isfile(cp):
            failures.append(f"{tag}: 문맥 골든이 없습니다 ({os.path.basename(cp)})")
        else:
            want_ctx = io.open(cp, encoding="utf-8").read().splitlines()
            if want_ctx != ctx:
                failures.append(
                    f"{tag}: 음자리표·조표·헤더 끝이 달라졌습니다 (보표 · 음자리표 · 조표 · 음이름 · 헤더 끝)\n"
                    + "".join(f"      - 골든: {l}\n" for l in want_ctx if l not in set(ctx))
                    + "".join(f"      + 현재: {l}\n" for l in ctx if l not in set(want_ctx)))
            else:
                print(f"       문맥 일치 — 보표 {len(ctx)}개, 조표 {ctx[0].split(chr(9))[2]}")

        over = {k: v for k, v in metrics.items() if v > LAYOUT_LIMITS[k]}
        if over:
            failures.append(f"{tag}: 배치 품질이 한도를 넘었습니다 — "
                            + ", ".join(f"{k} {v}개(한도 {LAYOUT_LIMITS[k]})"
                                        for k, v in over.items()))
        else:
            print(f"       배치 지표 통과 — " +
                  ", ".join(f"{k} {v}" for k, v in metrics.items()))

    changed = pdf_snapshots(update_snapshot)
    key_bad = verovio_keys() + short_staves() + hires_staves() + accidental_cases() + propagation_cases() + clef_change_cases() + alto_cases() + ladder_cases() + unknown_clef_cases()

    if failures:
        print("\n[실패] 정답 골든(아오하루 711)이 달라졌습니다 — 퇴행입니다:")
        for f in failures:
            print("   " + f)
        print("\n정답이 바뀌는 의도한 변경이라면 승인을 받은 뒤 `python tests/test_golden_regression.py --update`로 갱신하세요.")
    if changed:
        print("\n[판정 필요] PDF 변화 감지용 스냅샷이 바뀌었습니다 — 오류가 아니라 판정 대상입니다(정답이 아닌 스냅샷):")
        for c in changed:
            print("   " + c)
        print(f"   바뀐 줄 전부: {os.path.relpath(SNAPSHOT_DIFF, ROOT)}")
        print("   바뀐 줄을 육안(또는 PDF 글리프 정답)으로 판정해 고쳐짐이면 "
              "`python tests/test_golden_regression.py --update-snapshot`, 새로 틀림 · 오삭제면 변경을 되돌리세요.")
    if key_bad:
        print("\n[실패] Verovio 조표 · 보표 · 임시표 · 전파 검사가 다릅니다 — 퇴행입니다(docs/KEYSIG_VOTE_FIX.md · docs/SHORT_LAST_SYSTEM.md):")
        for b in key_bad:
            print("   " + b)
    if failures or changed or key_bad:
        raise SystemExit(1)
    print(f"\n[성공] 골든 회귀 테스트 통과 — 정답 골든 711 일치 · PDF 스냅샷 17쪽 같음 · Verovio 조표 {len(VEROVIO_KEYS)}쪽 · 짧은 시스템 · 보표 오검출 · 임시표 {len(ACCIDENTAL_CASES)}건 · 전파 {len(PROPAGATION_CASES)}건 통과")


if __name__ == "__main__":
    main()
