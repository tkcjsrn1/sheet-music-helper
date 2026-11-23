# -*- coding: utf-8 -*-
"""
Sheet Music Note-Name Helper - 메인 실행 스크립트

전체 파이프라인:
    1. 전처리 + 오선 검출      (modules/preprocess.py)
    2. 음표 머리 검출          (modules/notehead_detect.py)
    3. 음고 계산               (modules/pitch_calculator.py)
    4. 계이름 변환             (modules/note_namer.py)
    5. 결과 이미지 렌더링       (modules/renderer.py)

사용법:
    - 커맨드라인: python main.py <악보 이미지 또는 PDF 경로> [--page N] [--clef treble|bass]
    - exe(더블클릭): 실행 후 안내에 따라 경로를 입력하거나, 이미지 파일을 exe 아이콘 위로
      드래그 앤 드롭하면 자동으로 그 파일을 입력으로 사용한다.
"""

import argparse
import os
import sys

from modules.engine_mask_cache import clear_mask_cache, with_mask_cache
from modules.preprocess import preprocess, draw_debug_image, SheetMusicImageError, StaffNotFoundError
from modules.notehead_detect import detect_noteheads, NoteheadDetectionError
from modules.clef_keysig import analyze_staves, clef_change_suspects, alto_suspects, unknown_clef_suspects, clef_glyph_suspects, header_reopened_suspects
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts, filled_flags, unstable_accidentals, c1_flat_suspects
from modules.pitch_calculator import calculate_pitches, UnsupportedClefError
from modules.note_namer import to_solfege_batch, UnknownNoteNameError, normalize_key_override
from modules.renderer import render_solfege_on_image, RendererError, _find_korean_font
from modules.result_legend import annotation_writer, clef_warnings
from user_messages import staff_count_confirmation


def _user_text(value) -> str:
    """내부의 정확한 용어를 초보자에게 익숙한 화면 문구로 바꾼다."""
    return str(value).replace("보표별", "악보 줄마다").replace("보표", "악보 줄")


def _base_dir() -> str:
    """
    실행 기준 폴더를 반환한다.
    PyInstaller로 패키징된 exe에서는 __file__이 임시 압축 해제 폴더를 가리키므로,
    그 경우 exe 파일이 실제로 위치한 폴더(sys.executable 기준)를 사용해
    output/debug 폴더가 exe 옆에 영구적으로 생기도록 한다.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sheet Music Note-Name Helper")
    parser.add_argument("input", nargs="?", default=None, help="악보 이미지(.png/.jpg) 또는 PDF 경로")
    parser.add_argument("--page", type=int, default=0, help="PDF인 경우 페이지 번호 (기본 0)")
    parser.add_argument(
        "--all-pages", action="store_true",
        help="PDF의 모든 페이지를 한 번에 처리 (결과 파일명에 _p1, _p2... 붙음)",
    )
    parser.add_argument(
        "--clef",
        choices=["auto", "treble", "bass"],
        default="auto",
        help="음자리표 (기본 auto: 악보 줄마다 자동 인식, 실패 시 treble)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="결과물 저장 폴더 (기본: 실행 파일 옆 output 폴더)",
    )
    parser.add_argument(
        "--no-debug", action="store_true", help="오선 검출 디버그 이미지 저장 생략"
    )
    parser.add_argument(
        "--audit", action="store_true",
        help="누락 점검: 음표로 보이는데 라벨이 안 붙은 자리를 목록·이미지로 표시",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="역방향 검증: 라벨이 붙었는데 그 자리에 음표 잉크가 없는 유령을 찾아낸다",
    )
    parser.add_argument(
        "--save-source", action="store_true",
        help="계이름을 얹기 전 원본(PDF는 렌더링 결과)도 함께 저장 — 전수 대조용",
    )
    parser.add_argument(
        "--font-size", type=int, default=18,
        help="계이름 글자 크기 (18=기본, 보표 간격에 비례)"
    )
    parser.add_argument(
        "--color", default="#dc1414", help="계이름 글자 색 (hex, 기본 #dc1414)"
    )
    parser.add_argument(
        "--notation",
        choices=["solfege", "solfege-fixed", "solfege-movable", "letter"],
        default="solfege",
        help="표기 방식: solfege-fixed=고정도 도레미(기본, solfege와 같음), "
             "solfege-movable=이동도 도레미(으뜸음이 '도'), letter=영문(C D E)",
    )
    parser.add_argument(
        "--key", default="",
        help="이동도 기준 으뜸음을 직접 지정 (예: D, Bb, F#). 없으면 조표로 판단",
    )
    parser.add_argument(
        "--save-labels", default=None,
        help="라벨 목록 JSON 경로를 직접 지정 (기본: 결과 이미지 옆 <이름>_라벨.json)",
    )
    parser.add_argument(
        "--relabel", default=None,
        help="인식을 건너뛰고 라벨 JSON만으로 다시 렌더링한다 "
             "(사용자가 고친 라벨을 그대로 보존하는 것이 목적)",
    )
    parser.add_argument(
        "--minor", action="store_true",
        help="--key로 준 조성이 단조임을 알린다 (예: --key D --minor = 라단조)",
    )
    parser.add_argument(  # 사진 입력 M1 — modules/photo_correct.py
        "--photo", action="store_true",
        help="스캐너·복사기·거치대로 만든 사진: 기울기를 바로잡고 종이 밖을 잘라낸다. "
             "비스듬해 믿을 수 없으면 처리를 멈추고 다시 찍기를 안내한다",
    )
    return parser.parse_args()


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (220, 20, 20)


def _labels_output_path(save_labels, output_dir: str, base_name: str,
                        suffix: str = "") -> str:
    """여러 페이지 처리에서도 각 페이지의 JSON 경로가 겹치지 않게 만든다."""
    if not save_labels:
        return os.path.join(output_dir, f"{base_name}_라벨.json")
    if not suffix:
        return save_labels
    root, ext = os.path.splitext(save_labels)
    return f"{root}{suffix}{ext}"


def _confidence_values(diag_rows, notes_with_names) -> list:
    """진단 행을 렌더러가 받는 음표 순서의 확신도 값으로 바꾼다."""
    from modules.labels_io import confidence_of, flags_of

    by_position = {
        (int(row["staff"]), int(row["x"]), int(row["y"])): row
        for row in (diag_rows or [])
    }
    return [
        confidence_of(flags_of(by_position.get(
            (int(note.staff_index), int(note.x), int(note.y)),
            {},
        )))
        for note, _text in notes_with_names
    ]


def apply_chord_rescue(result, contexts, clef_arg, key_letters, key_symbol,
                       notation, tonic, pitched, accidentals, named, diag_rows,
                       rare_warnings, *, enable=True):
    """두 번째 검출 결과를 기존 라벨에 합친다. 사진 입력은 기존 결과를 그대로 돌려준다."""
    if not enable:
        return pitched, accidentals, named, diag_rows, 0, 0

    from statistics import median
    from modules.chord_rescue import detect_noteheads_rescue, merge_additive
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts, diagnose_labels, sloped_beam_suspects, glyph_shape_suspects, grace_size_suspects, narrow_hole_suspects, beam_gap_suspects
    from modules.labels_io import mark_accidental_candidates

    heads = detect_noteheads_rescue(result, contexts=contexts)
    heads, _ = drop_beam_ghosts(result, heads)
    heads, _ = drop_offstaff_ghosts(result, heads)
    extra = calculate_pitches(heads, result.staves, clef=clef_arg)
    extra_acc = annotate_accidentals(result, contexts, extra)
    flagged = []
    extra, extra_acc = remove_accidental_ghosts(
        extra, extra_acc, result.staves,
        filled=filled_flags(extra, heads), flagged=flagged, result=result)
    extra_warnings = []
    extra_named = to_solfege_batch(extra, key_letters, key_symbol, extra_acc,
                                   notation, extra_warnings, tonic)
    extra_rows = mark_accidental_candidates(diagnose_labels(result, extra), flagged)
    extra_rows = mark_accidental_candidates(
        extra_rows, unstable_accidentals(result, contexts, extra, extra_acc),
        "accidental_unstable")
    extra_rows = mark_accidental_candidates(extra_rows, sloped_beam_suspects(result, extra, filled_flags(extra, heads)), "beam_sloped")  # G1 기울어진 빔 → check
    extra_rows = mark_accidental_candidates(extra_rows, clef_change_suspects(result, contexts, extra), "clef_changed")  # 바뀐 음자리표 뒤 → check
    extra_rows = mark_accidental_candidates(extra_rows, alto_suspects(result, contexts, extra), "clef_alto")  # 알토 음자리표 보표 → check
    extra_rows = mark_accidental_candidates(extra_rows, unknown_clef_suspects(contexts, extra, clef_arg), "clef_unknown")  # 음자리표 못 찾은 보표 → check
    extra_rows = mark_accidental_candidates(extra_rows, clef_glyph_suspects(result, contexts, extra), "clef_glyph")  # 음자리표 글리프 안 라벨 → check
    extra_rows = mark_accidental_candidates(extra_rows, header_reopened_suspects(contexts, extra), "header_reopened")  # 헤더에서 풀려난 줄 첫 음 → check(§1-51 초안)
    extra_rows = mark_accidental_candidates(extra_rows, grace_size_suspects(result, extra), "grace_size")  # 꾸밈음 크기 → check
    extra_rows = mark_accidental_candidates(extra_rows, glyph_shape_suspects(result, extra), "glyph_shape")  # 글리프 모양 유령 → check
    extra_rows = mark_accidental_candidates(extra_rows, narrow_hole_suspects(result, extra), "narrow_hole")  # 좁은 구멍(셈여림 p · 글자 고리) → check
    extra_rows = mark_accidental_candidates(extra_rows, c1_flat_suspects(result, extra), "flat_propagated")  # 닫힘 전 영상으로만 읽은 ♭이 마디 안 전파된 음 → check
    extra_rows = mark_accidental_candidates(extra_rows, beam_gap_suspects(result, extra), "beam_gap")  # 겹빔 사이 흰 틈 → check

    added, deleted = merge_additive(
        [(n.x, n.y) for n in pitched], [(n.x, n.y) for n in extra],
        median(s.spacing for s in result.staves), enable=enable)
    removed = set(deleted)
    keep = [i for i in range(len(pitched)) if i not in removed]
    removed_keys = {(pitched[i].staff_index, int(pitched[i].x), int(pitched[i].y))
                    for i in deleted}
    added_keys = {(extra[i].staff_index, int(extra[i].x), int(extra[i].y))
                  for i in added}
    rare_warnings.extend(w for w in extra_warnings
                         if (w["staff"], int(w["x"]), int(w["y"])) in added_keys)
    rare_warnings[:] = [w for w in rare_warnings
                        if (w["staff"], int(w["x"]), int(w["y"])) not in removed_keys]
    rows = [r for r in diag_rows
            if (r["staff"], int(r["x"]), int(r["y"])) not in removed_keys]
    rows.extend(r for r in extra_rows
                if (r["staff"], int(r["x"]), int(r["y"])) in added_keys)
    rows = mark_accidental_candidates(rows, [extra[i] for i in added],
                                      "chord_rescue_added")
    return ([pitched[i] for i in keep] + [extra[i] for i in added],
            [accidentals[i] for i in keep] + [extra_acc[i] for i in added],
            [named[i] for i in keep] + [extra_named[i] for i in added],
            rows, len(added), len(deleted))


def write_audit_image(result, noteheads, reject_log, path) -> int:
    """
    누락 점검 이미지를 저장하고 의심 개수를 반환한다.

    초록 점 = 라벨이 붙은 음표, 파란 원 = 음표로 보이는데 라벨이 안 붙은 자리.
    쉼표·가사·제목처럼 애초에 음표가 아닌 것은 앞 단계에서 걸러져 여기 안 온다.
    """
    import cv2

    img = result.original_bgr.copy()
    for nh in noteheads:
        cv2.circle(img, (nh.x, nh.y), 3, (0, 170, 0), -1)

    # 같은 글리프에서 여러 번 기록된 것은 하나로 묶는다
    # 의도적 분류(유령 제거)는 '누락 의심'이 아니므로 목록에서 뺀다
    # 아래 사유들은 '누락'이 아니라 의도적 분류다. 목록에 남기면 진짜 누락이 묻힌다.
    DELIBERATE = ("잉크가 없음", "글자에서 나온 유령", "같은 높이 바로 옆의 중복",
                  "8분음표 꼬리")
    seen: list = []
    for r in sorted(reject_log or [], key=lambda r: (r["x"], r["y"])):
        if any(k in r["reason"] for k in DELIBERATE):
            continue
        if any(abs(r["x"] - s["x"]) < 8 and abs(r["y"] - s["y"]) < 8 for s in seen):
            continue
        # 이미 근처에 라벨이 있으면 누락이 아니다 (한 글리프가 여러 후보를 낳은 것).
        # 밴드 가장자리에서 잘린 덩어리는 무게중심이 안쪽으로 끌려가 라벨과 최대
        # 0.5sp 어긋나므로, 그 사유에 한해 판정 반경을 넓게 잡는다.
        near_y = 22 if "가장자리에서 잘린" in r["reason"] else 10
        if any(abs(nh.x - r["x"]) < 12 and abs(nh.y - r["y"]) < near_y
               for nh in noteheads):
            continue
        seen.append(r)

    for r in seen:
        cv2.circle(img, (int(r["x"]), int(r["y"])), 15, (255, 0, 0), 2)
        print(f"   의심 st{r['staff']:2d} x={r['x']:6.0f} y={r['y']:6.0f}  {r['reason']}")

    ok, buf = cv2.imencode(".png", img)
    if ok:
        buf.tofile(path)
    return len(seen)


def _prompt_for_input() -> str:
    """인자 없이 실행된 경우(더블클릭) 대화형으로 이미지 경로를 입력받는다."""
    print("=" * 50)
    print(" Sheet Music Note-Name Helper (악보헬퍼)")
    print("=" * 50)
    print("악보 이미지(.png/.jpg) 또는 PDF 파일의 경로를 입력하세요.")
    print("(탐색기에서 파일을 이 창으로 드래그해서 놓아도 됩니다)")
    path = input("파일 경로 > ").strip().strip('"')
    return path


def _pause_before_exit() -> None:
    """exe로 더블클릭 실행 시 콘솔 창이 바로 닫히지 않도록 대기한다."""
    # windowed exe에서 CLI 옵션으로 실행하면 입력 창이 보이지 않는데도 input()이
    # 프로세스를 붙잡을 수 있다. 실제 대화형 콘솔이 있을 때만 기다린다.
    if (getattr(sys, "frozen", False) and sys.stdin is not None
            and sys.stdin.isatty()):
        try:
            input("\n종료하려면 Enter 키를 누르세요...")
        except EOFError:
            pass  # 부모가 입력을 닫아도 완료된 변환은 정상 종료한다.


def main() -> None:
    args = parse_args()
    try:
        args.key = normalize_key_override(args.key, args.minor)
    except UnknownNoteNameError as e:
        print(f"[오류] {e}")
        raise SystemExit(1)
    base_dir = _base_dir()

    input_path = args.input
    if input_path is None:
        input_path = _prompt_for_input()
        if not input_path:
            print("[오류] 파일 경로가 입력되지 않았습니다.")
            _pause_before_exit()
            sys.exit(1)

    output_dir = args.output_dir or os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    if args.relabel:
        relabel(args, input_path, output_dir)
        _pause_before_exit()
        return

    if args.all_pages:
        from modules.preprocess import pdf_page_count
        total = pdf_page_count(input_path)
        if total <= 1:
            print("[안내] 여러 페이지가 아니므로 한 장만 처리합니다.")
        failed = 0
        for page in range(total):
            print(f"\n{'=' * 20} {page + 1}/{total} 페이지 {'=' * 20}")
            try:
                run_page(args, input_path, page, output_dir, suffix=f"_p{page + 1}")
            except SystemExit:
                failed += 1
                print(f"[건너뜀] {page + 1}페이지 처리 실패")
        print(f"\n[전체 완료] {total - failed}/{total} 페이지 성공")
        _pause_before_exit()
        return

    suffix = f"_p{args.page + 1}" if input_path.lower().endswith(".pdf") else ""
    run_page(args, input_path, args.page, output_dir, suffix=suffix)
    _pause_before_exit()


def relabel(args, input_path: str, output_dir: str) -> None:
    """인식을 돌리지 않고 라벨 JSON만으로 결과 이미지를 다시 만든다.

    사용자가 목록에서 줄을 지우면 그 라벨이 빠지고, 값을 고치면 그대로 반영된다 —
    JSON이 곧 그리는 내용이기 때문이다.
    """
    from modules.label_edits import display_confidences
    from modules.labels_io import (LabelSchemaError, check_dpi, check_source,
                                   document_notes, document_staves, load_labels)
    from modules.preprocess import load_image

    try:
        doc = load_labels(args.relabel)
    except LabelSchemaError as e:
        print(f"[오류][재렌더링] {_user_text(e)}")
        raise SystemExit(1)

    # dpi가 다르면 조용히 넘어가지 않는다 — 라벨이 통째로 어긋난다.
    warn = check_dpi(doc)
    if warn:
        print(f"[중단] {warn}")
        print("  300dpi로 다시 인식하거나, 이 파일을 300dpi에서 다시 만드세요.")
        raise SystemExit(1)

    try:
        page = int(doc.get("source", {}).get("page", 0))
    except (AttributeError, TypeError, ValueError):
        print("[오류][재렌더링] source.page가 올바른 숫자가 아닙니다.")
        raise SystemExit(1) from None
    bgr = load_image(input_path, pdf_page=page)
    source_error = check_source(doc, input_path, bgr.shape, page)
    if source_error:
        print(f"[중단][재렌더링] {_user_text(source_error)}")
        raise SystemExit(1)
    staves = document_staves(doc)
    notes_with_names = document_notes(doc)
    confidences = display_confidences(doc)
    print(f"[재렌더링] 라벨 {len(notes_with_names)}개 · 악보 줄 {len(staves)}개 "
          f"({os.path.basename(args.relabel)})")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_계이름.png")
    music = doc.get("music") or {}
    writer, annotations = annotation_writer(output_path, header=dict(
        symbol=music.get("key_symbol", ""), count=music.get("key_count", 0),
        font_path=_find_korean_font(), spacings=[s.spacing for s in staves], setting_size=args.font_size,
        user_key=(getattr(args, "key", "") if music.get("notation") == "solfege-movable" else ""),
        first_staff_top=min((s.top for s in staves), default=None), labels=doc["labels"]))
    try:
        render_solfege_on_image(
            bgr, notes_with_names, output_path,
            font_size=args.font_size, text_color=_hex_to_rgb(args.color),
            text_offset_y=max(14, args.font_size + 4),
            staff_spacings={s.index: s.spacing for s in staves},
            staves=staves,
            confidences=confidences, image_writer=writer,
        )
    except RendererError as e:
        print(f"[오류][재렌더링] {_user_text(e)}")
        raise SystemExit(1)
    for warning in clef_warnings(doc["labels"]):
        print("[주의] " + warning)
    if not annotations["header"]:
        print("[안내] 조표 표시를 넣을 빈 상단 여백을 찾지 못했습니다.")
    print(f"[재렌더링 완료] {output_path}")


def _filter_noteheads(result, noteheads):
    from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts

    noteheads, beam_ghosts = drop_beam_ghosts(result, noteheads)
    noteheads, glyph_ghosts = drop_offstaff_ghosts(result, noteheads)
    return noteheads, beam_ghosts, glyph_ghosts


def _filter_accidentals(result, contexts, pitched, noteheads):
    accidentals = annotate_accidentals(result, contexts, pitched)
    candidates = []
    pitched, accidentals = remove_accidental_ghosts(
        pitched, accidentals, result.staves,
        filled=filled_flags(pitched, noteheads), flagged=candidates, result=result)
    return pitched, accidentals, candidates


def _diagnose_named_notes(result, contexts, clef_arg, noteheads, pitched_notes, accidentals,
                          notes_with_solfege, accidental_candidates, key_letters, key_symbol,
                          notation, tonic, rare_warnings, *, photo, keep_tonic, report_rescue):
    # 진단과 구제의 순서는 GUI·CLI 양쪽에서 같은 계약을 사용한다.
    from modules.verify import diagnose_labels, sloped_beam_suspects, glyph_shape_suspects, grace_size_suspects, narrow_hole_suspects, beam_gap_suspects
    from modules.labels_io import mark_accidental_candidates
    diag_rows = mark_accidental_candidates(diagnose_labels(result, pitched_notes), accidental_candidates)
    diag_rows = mark_accidental_candidates(diag_rows, unstable_accidentals(result, contexts, pitched_notes, accidentals), "accidental_unstable")  # 임시표 0.5px 재판정 → check
    diag_rows = mark_accidental_candidates(diag_rows, sloped_beam_suspects(result, pitched_notes, filled_flags(pitched_notes, noteheads)), "beam_sloped")  # G1 기울어진 빔 → check
    diag_rows = mark_accidental_candidates(diag_rows, clef_change_suspects(result, contexts, pitched_notes), "clef_changed")  # 바뀐 음자리표 뒤 → check
    diag_rows = mark_accidental_candidates(diag_rows, alto_suspects(result, contexts, pitched_notes), "clef_alto")  # 알토 음자리표 보표 → check
    diag_rows = mark_accidental_candidates(diag_rows, unknown_clef_suspects(contexts, pitched_notes, clef_arg), "clef_unknown")  # 음자리표 못 찾은 보표 → check
    diag_rows = mark_accidental_candidates(diag_rows, clef_glyph_suspects(result, contexts, pitched_notes), "clef_glyph")  # 음자리표 글리프 안 라벨 → check
    diag_rows = mark_accidental_candidates(diag_rows, header_reopened_suspects(contexts, pitched_notes), "header_reopened")  # 헤더에서 풀려난 줄 첫 음 → check(§1-51 초안)
    diag_rows = mark_accidental_candidates(diag_rows, grace_size_suspects(result, pitched_notes), "grace_size")  # 꾸밈음 크기 → check
    diag_rows = mark_accidental_candidates(diag_rows, glyph_shape_suspects(result, pitched_notes), "glyph_shape")  # 글리프 모양 유령 → check
    diag_rows = mark_accidental_candidates(diag_rows, narrow_hole_suspects(result, pitched_notes), "narrow_hole")  # 좁은 구멍(셈여림 p · 글자 고리) → check
    diag_rows = mark_accidental_candidates(diag_rows, c1_flat_suspects(result, pitched_notes), "flat_propagated")  # 닫힘 전 영상으로만 읽은 ♭이 마디 안 전파된 음 → check
    diag_rows = mark_accidental_candidates(diag_rows, beam_gap_suspects(result, pitched_notes), "beam_gap")  # 겹빔 사이 흰 틈 → check
    pitched_notes, accidentals, notes_with_solfege, diag_rows, added, deleted = apply_chord_rescue(
        result, contexts, clef_arg, key_letters, key_symbol, notation, tonic,
        pitched_notes, accidentals, notes_with_solfege, diag_rows, rare_warnings,
        enable=not photo)
    if added or deleted:
        report_rescue(added, deleted)
    from modules.chord_rescue import apply_chord_middles
    pitched_notes, accidentals, notes_with_solfege, diag_rows, _mid = apply_chord_middles(result, contexts, clef_arg, key_letters, key_symbol, notation, tonic, pitched_notes, accidentals, notes_with_solfege, diag_rows, rare_warnings, enable=not photo)  # 3도 쌓기 화음 가운데 머리 추가
    from modules.accidental_detect import double_acc_kinds
    from modules.note_namer import apply_double_accidentals
    double_kinds = {} if photo else double_acc_kinds(result, contexts, pitched_notes)
    accidentals, notes_with_solfege = apply_double_accidentals(pitched_notes, accidentals, notes_with_solfege, double_kinds, key_letters, key_symbol, notation, tonic)
    diag_rows = mark_accidental_candidates(diag_rows, [pitched_notes[i] for i in double_kinds], "double_acc")  # 겹임시표 종류 bb/## 표기 · 재생(#388 · #391, check 유지) — apply_key_changes 앞
    from modules.clef_keysig import apply_key_changes
    notes_with_solfege, label_keys = apply_key_changes(result, contexts, pitched_notes, accidentals, notes_with_solfege, notation, tonic, keep_tonic=keep_tonic)  # 확인된 곡 중간 조바꿈 뒤를 새 조로(§1-43 초안)
    from modules.accidental_detect import double_acc_suspects
    diag_rows = mark_accidental_candidates(diag_rows, double_acc_suspects(result, contexts, pitched_notes), "double_acc")  # 겹임시표 ♭♭ · 𝄪 머리 · 같은 마디 같은 음 → check(가운데 머리 추가 뒤라 그 판정을 막지 않음)
    from modules.verify import text_row_suspects
    diag_rows = mark_accidental_candidates(diag_rows, text_row_suspects(result, pitched_notes), "text_row")  # 오선 밖 글자 줄(나타냄말 · 셈여림) → check
    from modules.verify import side_pair_suspects
    diag_rows = mark_accidental_candidates(diag_rows, side_pair_suspects(result, pitched_notes), "side_pair")  # 같은 음 옆 쌍의 얇은 쪽 → check(§1-44 초안)
    diag_rows = mark_accidental_candidates(diag_rows, [n for n in noteheads if n.wide_triple], "wide_triple")  # 3음 덩어리 분할 머리 → check(§1-48 초안)
    from modules.accidental_detect import chord_column_suspects
    diag_rows = mark_accidental_candidates(diag_rows, chord_column_suspects(result, pitched_notes), "chord_column")  # 화음 임시표 먼 열에서 읽은 임시표 · 전파 → check(§1-49 초안)
    return pitched_notes, accidentals, notes_with_solfege, diag_rows, label_keys, deleted


def _build_result_document(input_path, page, staves, named, shape, *, contexts, **options):
    from modules.labels_io import build_document

    return build_document(input_path, page, staves, named, shape,
                          clefs={idx: context.clef for idx, context in contexts.items()}, **options)


@with_mask_cache
def run_page(args, input_path: str, page: int, output_dir: str,
             suffix: str = "") -> None:
    """한 페이지(또는 이미지 한 장)를 처리한다."""
    # ---- 1단계: 전처리 + 오선 검출 ----
    try:
        result = preprocess(input_path, pdf_page=page, photo=getattr(args, "photo", False))
    except (SheetMusicImageError, StaffNotFoundError) as e:
        print(f"[오류][1단계] {_user_text(e)}")
        raise SystemExit(1)
    print(f"[1단계 완료] {staff_count_confirmation(len(result.staves))}")

    if args.save_source:
        import cv2 as _cv2
        base_name = os.path.splitext(os.path.basename(input_path))[0] + suffix
        src_path = os.path.join(output_dir, f"{base_name}_원본.png")
        ok, buf = _cv2.imencode(".png", result.original_bgr)
        if ok:
            buf.tofile(src_path)
            print(f"  -> 원본 이미지: {src_path}")
        del buf

    if not args.no_debug:
        debug_path = os.path.join(output_dir, f"1_staff_debug{suffix}.png")
        draw_debug_image(result, debug_path)
        print(f"  -> 디버그 이미지: {debug_path}")

    # ---- 1.5단계: 보표 헤더 분석 (음자리표/조표 자동 인식) ----
    contexts = analyze_staves(result)
    found = [c for c in contexts.values() if c.clef_found]
    if found:
        clef_summary = "".join("높" if c.clef == "treble" else "낮"
                               for _, c in sorted(contexts.items()))
        print(f"[헤더 분석] 음자리표: {clef_summary}", end="")
        any_ctx = found[0]
        if any_ctx.key_count > 0:
            print(f", 조표: {any_ctx.key_symbol}x{any_ctx.key_count} "
                  f"({'/'.join(any_ctx.key_letters)})")
        else:
            print(", 조표 없음")
    else:
        print("[헤더 분석] 음자리표 없음 (합성 악보로 판단)")

    # ---- 2단계: 음표 머리 검출 ----
    reject_log = [] if args.audit else None
    try:
        noteheads = detect_noteheads(result, contexts=contexts, reject_log=reject_log)
    except NoteheadDetectionError as e:
        print(f"[오류][2단계] {_user_text(e)}")
        raise SystemExit(1)
    # 빔에 얹히거나 끼어 있는 '빈 음표'는 빔 사이 흰 띠를 링으로 착각한 것이다
    # (빔은 8분음표 이하에만 붙고 그 머리는 채워져 있다).
    # 오선 밖인데 덧줄이 없는 머리는 셈여림·페달·나타냄말 같은 '글자'다.
    noteheads, beam_ghosts, glyph_ghosts = _filter_noteheads(result, noteheads)
    print(f"[2단계 완료] 음표 머리 {len(noteheads)}개 검출"
          + (f" (빔에서 온 유령 {len(beam_ghosts)}개 제외)" if beam_ghosts else "")
          + (f" (덧줄 없는 오선 밖 글리프 {len(glyph_ghosts)}개 제외)" if glyph_ghosts else ""))

    if args.audit:
        # 탐색 밴드 가장자리에서 잘려 아예 후보가 되지 못한 음표는 reject_log에도
        # 안 남아 이 점검이 영원히 못 본다 (실측: 3페이지 87·89마디 베이스 A4가
        # 그렇게 숨어 육안 대조로만 발견됐다). 그래서 여유를 넓혀 한 번 더 돌리고
        # '넓혔을 때만 나오는 음표'를 따로 보고한다 — 밴드 폭이 원인인 누락을
        # 직접 드러내는 유일한 방법이다.
        import modules.notehead_detect as _nd
        _saved = _nd.BASE_MARGIN_SP
        try:
            _nd.BASE_MARGIN_SP = _saved + 0.7
            wide = _nd.detect_noteheads(result, contexts=contexts)
        except NoteheadDetectionError:
            wide = []
        finally:
            _nd.BASE_MARGIN_SP = _saved
        for w in wide:
            if not any(abs(w.x - n.x) < 10 and abs(w.y - n.y) < 10 for n in noteheads):
                reject_log.append(dict(staff=w.staff_index, x=float(w.x),
                                       y=float(w.y), filled=w.filled,
                                       reason="탐색 범위를 넓히면 나오는 음표 (놓쳤을 수 있음)"))

        audit_path = os.path.join(output_dir, f"2_audit{suffix}.png")
        n_sus = write_audit_image(result, noteheads, reject_log, audit_path)
        print(f"[누락 점검] 의심 {n_sus}곳 -> {audit_path}")

    # ---- 3단계: 음고 계산 ----
    if args.clef == "auto":
        clef_arg = {idx: c.clef for idx, c in contexts.items()}
    else:
        clef_arg = args.clef
    try:
        pitched_notes = calculate_pitches(noteheads, result.staves, clef=clef_arg)
    except UnsupportedClefError as e:
        print(f"[오류][3단계] {_user_text(e)}")
        raise SystemExit(1)
    print(f"[3단계 완료] 음고 계산 {len(pitched_notes)}개")

    # ---- 3.5단계: 임시표(♯/♭/♮) 검출 ----
    pitched_notes, accidentals, accidental_candidates = _filter_accidentals(result, contexts, pitched_notes, noteheads)
    n_acc = sum(1 for a in accidentals if a)
    if n_acc:
        print(f"[임시표] {n_acc}개 음표에 임시표 적용")

    if args.verify:
        from modules.verify import reverse_check, draw_reverse_image
        suspects = reverse_check(result, pitched_notes)
        for s in suspects:
            print(f"   유령후보 st{s['staff']:2d} {s['measure']:2d}번째마디 "
                  f"x={s['x']:5d} y={s['y']:5d}  좌우잉크 약={s['weak']:.2f} "
                  f"강={s['strong']:.2f}")
        rev_path = os.path.join(output_dir, f"3_reverse{suffix}.png")
        draw_reverse_image(result, pitched_notes, suspects, rev_path)
        print(f"[역방향 검증] 유령 후보 {len(suspects)}곳 -> {rev_path}")

    # ---- 4단계: 계이름 변환 ----
    key_letters, key_symbol = (), ""
    if found:
        key_letters = found[0].key_letters
        key_symbol = found[0].key_symbol
    rare_warnings: list = []
    tonic = ""
    effective_minor = False
    if args.notation == "solfege-movable":
        from modules.note_namer import resolve_tonic
        key_override = str(args.key).strip()
        try:
            tonic = resolve_tonic(key_symbol, len(key_letters), key_override, args.minor)
        except UnknownNoteNameError:
            print(f"[안내] 조성 '{key_override}'을 알 수 없어 조표대로 읽습니다.")
            tonic = resolve_tonic(key_symbol, len(key_letters))
            key_override = ""
        effective_minor = bool(args.minor and key_override)
        print(f"[이동도] 으뜸음 '도' = {tonic}"
              + (f" (지정: {key_override}{'단조' if effective_minor else '장조'})"
                 if key_override else f" (조표 {key_symbol or '없음'}{len(key_letters)}개로 판단)"))
    try:
        notes_with_solfege = to_solfege_batch(
            pitched_notes, key_letters, key_symbol, accidentals, args.notation,
            rare_warnings, tonic,
        )
    except UnknownNoteNameError as e:
        print(f"[오류][4단계] {_user_text(e)}")
        raise SystemExit(1)
    print(f"[4단계 완료] 계이름 변환 {len(notes_with_solfege)}개")

    # 확신도는 JSON 저장과 화면 표시가 같은 진단 결과를 써야 한다. 여기서 한 번만
    # 계산하고 5단계 렌더링과 6단계 직렬화가 함께 재사용한다.
    pitched_notes, accidentals, notes_with_solfege, diag_rows, label_keys, _chord_removed = _diagnose_named_notes(
        result, contexts, clef_arg, noteheads, pitched_notes, accidentals, notes_with_solfege,
        accidental_candidates, key_letters, key_symbol, args.notation, tonic, rare_warnings,
        photo=getattr(args, "photo", False), keep_tonic=bool(str(args.key or "").strip()),
        report_rescue=lambda added, deleted: print(f"[붙은 화음] 라벨 {added}개 추가 · 가운데 유령 {deleted}개 제외"))
    confidences = _confidence_values(diag_rows, notes_with_solfege)

    if rare_warnings:
        # 값은 그대로 두고 목록만 남긴다. E♯/B♯/C♭/F♭은 ♭계 조성에서 정상적으로
        # 나오는 음이므로 임의로 고치면 정답을 망가뜨린다 — 사람이 확인할 목록이다.
        from modules.verify import barline_positions, measure_index
        _nx: dict = {}
        for _n in pitched_notes:
            _nx.setdefault(_n.staff_index, []).append(int(_n.x))
        bars = {s.index: barline_positions(result.binary, s, _nx.get(s.index, ()))
                for s in result.staves}
        page_tag = os.path.basename(input_path)
        if input_path.lower().endswith(".pdf"):
            page_tag += f" {page + 1}쪽"
        print(f"[확인 필요] 조표에 없는 드문 이름 {len(rare_warnings)}개 "
              f"(값은 그대로 두었습니다)")
        for w in rare_warnings:
            m = measure_index(bars.get(w["staff"], []), w["x"])
            print(f"   {page_tag} 악보 줄 {w['staff']:2d} · {m:2d}번째 마디 "
                  f"x={w['x']:5d} y={w['y']:5d}  {w['note_name']}{w['octave']}"
                  f"{w['accidental']} -> '{w['text']}' (조표 {w['key']})")

    # 인식에만 쓰는 회색·이진 배열을 렌더 버퍼를 만들기 전에 놓는다.
    original_bgr, staves = result.original_bgr, result.staves
    del result

    # ---- 5단계: 결과 렌더링 ----
    base_name = os.path.splitext(os.path.basename(input_path))[0] + suffix
    output_path = os.path.join(output_dir, f"{base_name}_계이름.png")
    # ---- 6단계: 라벨 목록 JSON ----
    # 결과 이미지와 함께 항상 남긴다. 이 구조가 앱으로 넘어가는 것이라
    # 옵션으로 두면 정작 필요할 때 없다.
    from modules.labels_io import save_labels
    labels_path = _labels_output_path(
        args.save_labels, output_dir, base_name,
        suffix if getattr(args, "all_pages", False) else "",
    )
    doc = _build_result_document(
        input_path, page, staves, notes_with_solfege,
        original_bgr.shape,
        accidentals=accidentals,
        diag_rows=diag_rows,
        contexts=contexts,
        key_symbol=key_symbol, key_letters=tuple(key_letters),
        tonic=tonic, minor=effective_minor, notation=args.notation,
        label_keys=label_keys,
    )
    writer, annotations = annotation_writer(output_path, header=dict(
        symbol=key_symbol, count=len(key_letters), font_path=_find_korean_font(),
        spacings=[s.spacing for s in staves], setting_size=args.font_size,
        user_key=(key_override if args.notation == "solfege-movable" else ""),
        first_staff_top=min((s.top for s in staves), default=None), labels=doc["labels"]))
    try:
        clear_mask_cache()
        render_solfege_on_image(
            original_bgr, notes_with_solfege, output_path,
            font_size=args.font_size, text_color=_hex_to_rgb(args.color),
            text_offset_y=max(14, args.font_size + 4),
            staff_spacings={s.index: s.spacing for s in staves},
            staves=staves,
            confidences=confidences, image_writer=writer,
        )
    except RendererError as e:
        print(f"[오류][5단계] {_user_text(e)}")
        raise SystemExit(1)
    for warning in clef_warnings(doc["labels"]):
        print("[주의] " + warning)
    if not annotations["header"]:
        print("[안내] 조표 표시를 넣을 빈 상단 여백을 찾지 못했습니다.")
    print(f"[5단계 완료] 최종 결과 이미지: {output_path}")

    save_labels(labels_path, doc)
    n_check = sum(1 for x in doc["labels"] if x["confidence"] == "check")
    n_caution = sum(1 for x in doc["labels"] if x["confidence"] == "caution")
    print(f"[6단계 완료] 라벨 목록: {labels_path} "
          f"(확실 {len(doc['labels']) - n_caution - n_check} · "
          f"주의 {n_caution} · 의심 {n_check})")


if __name__ == "__main__":
    main()
