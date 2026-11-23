# -*- coding: utf-8 -*-
"""실제 임시표 삭제와 raw/effective 출처를 관찰한다. 제품 판정은 바꾸지 않는다.

Python 반환 이벤트에서 버려지는 raw와 글리프 좌표를 읽는다. 프로파일러는
호출 종료 시 복원하며, 파일·환경 설정에 실행 훅을 설치하지 않는다.
출력의 filled/raw는 검출기 값이지 사람의 정답 판정이 아니다.
"""

import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import accidental_detect as ad
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.pitch_calculator import calculate_pitches
from modules.preprocess import pdf_page_count, preprocess
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts


def observe_annotation(result, contexts, notes):
    """실제 호출에서 raw와 버려지는 글리프 위치 정보를 기록한다."""
    raw, evidence = [], {}
    previous = sys.getprofile()

    def observe(frame, event, value):
        if event != "return":
            return
        if frame.f_code is ad.annotate_accidentals.__code__:
            raw.extend(frame.f_locals["raw"])
        elif (frame.f_code is ad._find_glyphs.__code__
              and frame.f_back.f_code is ad.annotate_accidentals.__code__):
            local = frame.f_back.f_locals
            note = local["note"]
            ox = max(0, local["x0"])
            oy = local["top"] + local["py0"]
            evidence[id(note)] = {
                "patch_origin": [ox, oy],
                "patch_shape": list(frame.f_locals["patch"].shape),
                "bars": [[x + ox, start + oy, end + oy]
                         for x, start, end in frame.f_locals["bars"]],
                "glyphs": [[kind, y + oy] for kind, y in value],
            }

    sys.setprofile(observe)
    try:
        effective = ad.annotate_accidentals(result, contexts, notes)
    finally:
        sys.setprofile(previous)
    assert len(raw) == len(effective) == len(notes)
    return raw, effective, evidence


def measure_page(path, page):
    """제품 순서로 실행하고, 실제 삭제 집합과 창 집계의 일치도 확인한다."""
    with contextlib.redirect_stdout(io.StringIO()):
        result = preprocess(str(path), pdf_page=page, pdf_dpi=300)
        contexts = analyze_staves(result)
        heads = detect_noteheads(result, contexts=contexts)
        heads, _ = drop_beam_ghosts(result, heads)
        heads, _ = drop_offstaff_ghosts(result, heads)
        notes = calculate_pitches(heads, result.staves,
                                 clef={i: c.clef for i, c in contexts.items()})
        raw, effective, evidence = observe_annotation(result, contexts, notes)
        kept, _ = ad.remove_accidental_ghosts(notes, effective, result.staves)

    # 위치·순서가 달라지면 filled가 다른 음표에 대응하므로 측정을 중단한다.
    assert len(heads) == len(notes)
    assert all((h.x, h.y, h.staff_index) == (n.x, n.y, n.staff_index)
               for h, n in zip(heads, notes))
    kept_ids = {id(n) for n in kept}
    actual_drops = {i for i, n in enumerate(notes) if id(n) not in kept_ids}
    spacings = {s.index: s.spacing for s in result.staves}
    windows = {}
    for j, trigger in enumerate(notes):
        if not effective[j]:
            continue
        sp = spacings[trigger.staff_index]
        for i, victim in enumerate(notes):
            # 현재 제품의 삭제 창을 관찰용으로 열거한다. 제품 삭제 결과와 아래에서 대조.
            if (i != j and victim.staff_index == trigger.staff_index
                    and sp * 0.5 <= trigger.x - victim.x <= sp * 1.6
                    and abs(victim.y - trigger.y) <= sp * ad.ACCIDENTAL_GHOST_Y_SP):
                windows.setdefault(i, []).append(j)
    assert set(windows) == actual_drops, "제품 삭제 조건이 달라졌습니다. 측정기도 검토하십시오."

    rows = []
    for i, triggers in sorted(windows.items()):
        n = notes[i]
        rows.append({
            "source": path.relative_to(ROOT).as_posix(), "page": page + 1,
            "staff": n.staff_index, "point": [n.x, n.y],
            "pitch": f"{n.note_name}{n.octave}", "filled": bool(heads[i].filled),
            "raw": raw[i], "effective": effective[i],
            "triggers": [{"point": [notes[j].x, notes[j].y],
                          "raw": raw[j], "effective": effective[j],
                          "geometry": evidence.get(id(notes[j]))} for j in triggers],
        })
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/accidental-window-audit")
    parser.add_argument("--crops", action="store_true", help="filled 삭제 후보의 원본 대조 이미지 생성")
    args = parser.parse_args()
    pdfs = [ROOT / "test_scores" / name for name in (
        "bach_minuet_Am.pdf", "chopin_nocturne_Db_6-8.pdf",
        "chopin_nocturne_Bbm.pdf", "chopin_nocturne_Em.pdf")]
    images = sorted((ROOT / "sample_images").glob("KakaoTalk_*.png"))
    if len(images) != 3 or not all(p.is_file() for p in pdfs):
        raise SystemExit("[중단] 검증 PDF 4종과 RE:Aoharu PNG 3쪽이 필요합니다.")
    paths = pdfs + images
    pages = [(p, page) for p in paths for page in range(pdf_page_count(str(p)))]
    if len(pages) != 20:
        raise SystemExit("[중단] 예상 20쪽과 다릅니다. PDF 의존성과 입력을 확인하십시오.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows, tiles, counts = [], [], []
    for path, page in pages:
        result, found = measure_page(path, page)
        rows.extend(found)
        counts.append({"source": path.relative_to(ROOT).as_posix(), "page": page + 1,
                       "deletions": len(found), "windows": sum(len(r["triggers"]) for r in found)})
        if args.crops:
            original = Image.fromarray(result.original_bgr[:, :, ::-1])
            for row in found:
                if not row["filled"]:
                    continue
                x, y = row["point"]
                patch = original.crop((x - 60, y - 65, x + 70, y + 65)).resize((325, 325))
                tile = Image.new("RGB", (350, 380), "white")
                tile.paste(patch, (10, 45))
                draw = ImageDraw.Draw(tile)
                draw.text((3, 3), f"{path.stem} p{page + 1}", fill="black")
                direct = any(t["raw"] for t in row["triggers"])
                draw.text((3, 20), f"({x},{y}) direct={direct}", fill="black")
                draw.ellipse((155, 202.5, 165, 212.5), outline="red", width=2)
                tiles.append(tile)
        print(f"{path.name} {page + 1}쪽: 삭제 {len(found)}개", flush=True)

    for start in range(0, len(tiles), 24):
        chunk = tiles[start:start + 24]
        contact = Image.new("RGB", (1400, 380 * ((len(chunk) + 3) // 4)), "#dddddd")
        for i, tile in enumerate(chunk):
            contact.paste(tile, (350 * (i % 4), 380 * (i // 4)))
        contact.save(args.output_dir / f"filled-deletions-{start // 24 + 1}.png")
    summary = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "accidental_module_sha256": hashlib.sha256(Path(ad.__file__).read_bytes()).hexdigest(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip()),
        "module_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "modules").glob("*.py"))},
        "python": sys.version,
        "input_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "pdf_dpi": 300, "ground_truth": False, "pages": counts,
        "unique_deletions": len(rows), "windows": sum(len(r["triggers"]) for r in rows),
        "filled_deletions": sum(r["filled"] for r in rows),
        "filled_direct_deletions": sum(r["filled"] and any(t["raw"] for t in r["triggers"]) for r in rows),
    }
    for name, data in (("summary.json", summary), ("deletions.json", rows)):
        (args.output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"측정 완료: {len(pages)}쪽, 삭제 창 {summary['windows']}건, 삭제 후보 {len(rows)}개")
    print("filled/raw는 검출기 값입니다. 오삭제 여부는 원본 이미지로 별도 확인하십시오.")


if __name__ == "__main__":
    main()
