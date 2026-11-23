# -*- coding: utf-8 -*-
"""합성 촬영본 57장의 제품 파이프라인 결과를 PDF 글리프 정답과 대조한다.

실행: python tools/measure_synthetic_photos.py [--limit N]
중간 결과는 매 장마다 저장되므로 재실행 시 완료한 장은 건너뛴다.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from main import run_page  # noqa: E402
from modules.preprocess import preprocess  # noqa: E402
from tools.measure_omission_rate import match, pdf_glyphs, truth_pitch  # noqa: E402

OUT = ROOT / "output" / "synthetic_photos"
RESULT = OUT / "measurement.json"
EXPECTED_KEY = {"bach": ("", 0), "chopin_Db": ("♭", 5), "F_flat1": ("♭", 1)}


def truth(row):
    """검출 결과보다 먼저 PDF 원본의 일반 음표를 독립적으로 고른다."""
    res = preprocess(str(ROOT / row["source_pdf"]), pdf_page=row["source_page"])
    staves = res.staves
    glyphs = pdf_glyphs(row["source_pdf"], row["source_page"])
    clefs = []
    for glyph in (g for g in glyphs if g["name"].startswith("clefs.")):
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - glyph["cy"]))
        clefs.append(dict(glyph, staff=st.index))
    heads = []
    for glyph in (g for g in glyphs if g["name"].startswith("noteheads.")):
        if any(abs(glyph["cx"] - h["cx"]) < 2 and abs(glyph["cy"] - h["cy"]) < 2 for h in heads):
            continue
        st = min(staves, key=lambda s: abs((s.top + s.bottom) / 2 - glyph["cy"]))
        if not st.top - 6 * st.spacing <= glyph["cy"] <= st.bottom + 6 * st.spacing:
            continue
        heads.append(glyph)
    main_size = Counter(h["size"] for h in heads).most_common(1)[0][0]
    normal = [h for h in heads if abs(h["size"] - main_size) < .05]
    small = [h for h in heads if abs(h["size"] - main_size) >= .05]
    for h in normal:
        h["staff"], h["pitch"], h["step"], h["clef"] = truth_pitch(h["cx"], h["cy"], staves, clefs)
    return normal, small, float(np.median([s.spacing for s in staves])), len(staves)


def project(heads, row):
    """곡면 뒤 3×3 변환 행렬 순서로 PDF 정답 좌표를 옮긴다."""
    if not heads:
        return []
    w = row["input_size"][0]
    amp = row["curve"]["amplitude_px"]
    xy = np.array([[h["cx"], h["cy"]] for h in heads], np.float32)
    if amp:
        xy[:, 1] += amp * (1 - np.abs((xy[:, 0] - (w - 1) / 2) / ((w - 1) / 2))) ** 2
    xy = cv2.perspectiveTransform(xy.reshape(-1, 1, 2), np.array(row["forward_homography"], np.float64)).reshape(-1, 2)
    return [dict(h, cx=float(p[0]), cy=float(p[1])) for h, p in zip(heads, xy)]


def evaluate(doc, row, normal, small, sp):
    labels = doc["labels"]
    n, s = project(normal, row), project(small, row)
    pairs, matched_truth, matched_labels = match(n, labels, sp)
    extra = [labels[i] for i in range(len(labels)) if i not in matched_labels]
    _, _, small_hits = match(s, extra, sp)
    ghosts = [extra[i] for i in range(len(extra)) if i not in small_hits]
    wrong = [dict(x=labels[li]["x"], y=labels[li]["y"], expected=n[ti]["pitch"], got=labels[li]["pitch"])
             for ti, li in pairs if n[ti]["pitch"] != labels[li]["pitch"]]
    missing = [dict(x=round(h["cx"]), y=round(h["cy"]), pitch=h["pitch"])
               for i, h in enumerate(n) if i not in matched_truth]
    return dict(labels=len(labels), missing=len(missing), ghosts=len(ghosts), wrong_pitch=len(wrong),
                small_labeled=len(small_hits), missing_details=missing,
                ghost_details=[dict(x=g["x"], y=g["y"], pitch=g["pitch"], text=g["text"]) for g in ghosts],
                wrong_details=wrong)


def run(row):
    image = OUT / row["file"]
    assert hashlib.sha256(image.read_bytes()).hexdigest() == row["sha256"], image
    folder = OUT / "results" / row["score"] / row["condition"]
    folder.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(save_source=False, no_debug=True, audit=False, clef="auto", verify=False,
                              notation="solfege", font_size=18, color="#dc1414", save_labels=None,
                              key="", minor=False)
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            run_page(args, str(image), 0, str(folder))
        doc = json.loads(next(folder.glob("*_라벨.json")).read_text(encoding="utf-8"))
        return doc, None
    except (Exception, SystemExit) as exc:
        return None, dict(type=type(exc).__name__, message=str(exc), last_log=log.getvalue()[-1200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    # 요약은 추적 문서를 바로 덮지 않는다 — 사람이 확인한 뒤 docs/PHOTO_SYNTHETIC_RESULTS.md로 옮긴다
    ap.add_argument("--report", type=Path, default=ROOT / "debug" / "PHOTO_SYNTHETIC_RESULTS.md")
    a = ap.parse_args()
    rows = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["images"]
    saved = json.loads(RESULT.read_text(encoding="utf-8")) if RESULT.exists() else {}
    by_score = {}
    processed = 0
    for row in rows:
        score, case = row["score"], row["condition"]
        if score not in by_score:
            by_score[score] = truth(row)
        normal, small, sp, expected_staves = by_score[score]
        if row["source_note_count"] is not None:
            assert len(normal) == row["source_note_count"], "픽스처 소스 음표 수와 PDF 글리프가 다름"
        done = saved.get(row["file"])       # 결과 폴더가 지워졌으면 기록이 남아 있어도 다시 돈다(요약 단계가 라벨 JSON을 읽음)
        if done and (done["error"] or any((OUT / "results" / score / case).glob("*_라벨.json"))):
            continue
        doc, error = run(row)
        record = dict(score=score, condition=case, file=row["file"], expected_staves=expected_staves,
                      truth_normal=len(normal), truth_small=len(small), source_note_count=row["source_note_count"],
                      error=error)
        if doc is not None:
            key = (doc["music"]["key_symbol"], doc["music"]["key_count"])
            record.update(detected_staves=len(doc["staves"]), key_symbol=key[0], key_count=key[1],
                          key_correct=key == EXPECTED_KEY[score],
                          clefs=[s["clef"] for s in doc["staves"]], **evaluate(doc, row, normal, small, sp))
            if case == "original":
                record["clefs_same"] = True
                record["first_failure"] = "원본 기준선"
            else:
                base = saved.get(f"{score}__original.png")
                record["clefs_same"] = bool(base and record["clefs"] == base["clefs"])
                record["new_missing"] = record["missing"] - base["missing"] if base else None
                record["new_ghosts"] = record["ghosts"] - base["ghosts"] if base else None
                record["first_failure"] = (
                    "오선" if record["detected_staves"] != expected_staves else
                    "조표" if not record["key_correct"] else
                    "음자리표" if not record["clefs_same"] else
                    "음표 누락" if record["new_missing"] > 0 else
                    "유령" if record["new_ghosts"] > 0 else
                    "음고" if record["wrong_pitch"] > base["wrong_pitch"] else "악화 없음")
        else:
            record["first_failure"] = "처리 실패"
        saved[row["file"]] = record
        RESULT.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        processed += 1
        print(f"{len(saved):02d}/57 {score} {case}: {record['first_failure']}" +
              (f" 보표{record['detected_staves']}/{expected_staves} 라벨{record['labels']} 누락{record['missing']} 유령{record['ghosts']}" if doc else
               f" {error['type']} {error['last_log'][-80:]}"), flush=True)
        if a.limit and processed >= a.limit:
            break
    if len(saved) == len(rows):
        for row in rows:
            if row["condition"] == "original" or saved[row["file"]]["error"]:
                continue
            score = row["score"]
            base_path = OUT / "results" / score / "original" / f"{score}__original_라벨.json"
            case_path = OUT / "results" / score / row["condition"] / f"{Path(row['file']).stem}_라벨.json"
            base_labels = json.loads(base_path.read_text(encoding="utf-8"))["labels"]
            case_labels = json.loads(case_path.read_text(encoding="utf-8"))["labels"]
            projected = project([dict(cx=l["x"], cy=l["y"], text=l["text"]) for l in base_labels], row)
            pairs, _, _ = match(projected, case_labels, by_score[score][2])
            changed = sum(projected[i]["text"] != case_labels[j]["text"] for i, j in pairs)
            saved[row["file"]]["text_changed"] = changed
            if saved[row["file"]]["first_failure"] in ("변화 없음", "악화 없음"):
                saved[row["file"]]["first_failure"] = "최종 표기" if changed else "악화 없음"
        RESULT.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        write_report(rows, saved, a.report)


def input_digest(rows):
    """ZIP이 있으면 ZIP의 SHA-256, 없으면 57장 각 SHA-256을 파일 이름순으로 이어 붙인 묶음 해시 — 같은 입력인지 비교용."""
    archive = OUT / "synthetic_photos_57.zip"
    if archive.exists():
        return "ZIP SHA-256", hashlib.sha256(archive.read_bytes()).hexdigest()
    each = "".join(hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in sorted(r["file"] for r in rows))
    return f"ZIP 없음 — {len(rows)}장 각 SHA-256을 이름순으로 이어 붙인 묶음 SHA-256", hashlib.sha256(each.encode("ascii")).hexdigest()


def write_report(rows, saved, path):
    kind, digest = input_digest(rows)
    lines = [
        "# 합성 촬영 조건별 인식 측정 (2026-09-28)", "",
        "**합성으로 잰 값이며 실제 사진 성능은 미검증이다.** 렌즈 왜곡, 종이 질감, 촬영 거리별 초점 흐림과 카메라 색 처리 등은 포함하지 않았다.", "",
        "바흐 미뉴에트 1쪽, 쇼팽 D♭ 1쪽, F장조 ♭1 픽스처를 각각 19조건(원본 포함)으로 만들었다. "
        "기울기 0.5/1/2/3/5°, 약·중·강 원근, 약·강 책 곡면, 한쪽 그림자·전체 어둡게·형광등 얼룩, "
        "초점 흐림·가우시안 잡음·JPEG 및 2°+약한 원근+그림자+흐림을 포함한다. 조건별 파일명에 조건을 적었다.", "",
        f"- 이미지 57장 ZIP: `output/synthetic_photos/synthetic_photos_57.zip` ({kind} `{digest}`). "
        "이 저장소의 작업 PC 배포용 사본은 `dist/synthetic_photos_57_20260928.zip`에 둔다.",
        "- 각 이미지의 PDF 출처·SHA, 300dpi, 3×3 순방향 행렬, 곡면식과 진폭, "
        "조명/잡음 수치, 난수 시드, 보간법은 ZIP의 `manifest.json`에 있다. 곡면은 단일 행렬로 나타낼 수 없어 별도 식을 기록했다.",
        "- 생성: `tools/generate_synthetic_photos.py`; 측정: `tools/measure_synthetic_photos.py`. "
        "원자료: `docs/measurements/synthetic_photos_20260928.json`.", "",
        "제품 인식 코드는 바꾸지 않고 `main.run_page`를 이미지마다 실행했다. PDF의 `noteheads.*`에서 일반 크기 음표 머리를 "
        "검출 결과와 독립적으로 추출하고, manifest 변환을 정답 좌표에 적용해 라벨과 1:1 대응했다. "
        "작은 꾸밈음은 정답 누락에서 제외했고 그 자리에 붙은 라벨은 유령에서 제외했다. "
        "표의 누락/유령은 이 자동 대응의 **후보 수**다. 원본에도 있던 후보를 뺀 증가분으로 조건별 첫 악화를 분류했다. "
        "최종 표기 변화는 변환된 원본 라벨에 대응되는 라벨의 계이름 문자열을 비교했다.", "",
        "(2026-09 측정) 원본 기준선: 바흐는 일반 음표 173·라벨 185·누락 0·유령 후보 12, "
        "D♭은 일반 음표 239(+작은 머리 10)·라벨 240·누락 24·유령 후보 16, "
        "F ♭1은 소스 168음표와 PDF 일반 머리 168개가 일치하며 라벨 166·누락 2·유령 0이다.", "",
        "(2026-09 측정) 57개 중 오선 1단계 예외가 24개, 실행은 끝났으나 보표 수가 줄어든 조건이 9개다. "
        "보표 수를 유지한 상태에서 확인된 조표 오판은 바흐 0.5px 평행이동(없음→♭1)이다. "
        "보표 수가 줄어든 9조건에서는 음자리표 배열도 짧아졌으나, 보표 수가 유지된 조건의 음자리표 배열 변화는 0이다. "
        "처리된 33조건 중 16조건에서 최종 표기 문자열 변화가 있으며, 숫자는 첫 실패 단계가 아닌 전체 변화다.", "",
        "(2026-09 측정) 첫 깨짐: 기울기 0.5°에서 바흐·F ♭1은 1단계 예외, D♭은 8개 중 보표 1개만 검출. "
        "약한 원근부터 세 악보 모두 보표가 줄고, 약한 책 곡면부터 모두 1단계 예외다. "
        "조명·잡음에서는 보표와 조표가 유지돼도 누락·유령 또는 최종 표기가 바뀐다. "
        "조합 조건은 세 악보 모두 1단계에서 실패했다. 따라서 아래 수치를 안전 각도나 사진 허용치로 해석할 수 없다.", "",
        "표의 `누락/유령`은 조건의 절대 후보 수다. `첫 실패`는 오선→조표→음자리표→누락→유령→음고→최종 표기 순으로 "
        "원본보다 처음 악화한 항목이며, `악화 없음`은 라벨이 완전히 동일하다는 뜻이 아니다. "
        "`표기변화`는 원본 라벨과 좌표 대응이 된 것 중 문자열이 달라진 개수다.", "",
        "| 악보 | 조건 | 처리 | 보표 | 조표 | 음자리표 | 라벨 | 누락 | 유령 | 표기변화 | 첫 실패 |",
        "|---|---|---|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        r = saved[row["file"]]
        failed = bool(r["error"])
        key = "—" if failed else (f"{r['key_symbol']}{r['key_count']}" if r["key_count"] else "없음")
        clef = "—" if failed else ("같음" if r["clefs_same"] else "다름¹")
        vals = [r["score"], r["condition"], "1단계 실패" if failed else "완료",
                f"{r.get('detected_staves', '—')}/{r['expected_staves']}", key, clef,
                r.get("labels", "—"), r.get("missing", "—"), r.get("ghosts", "—"),
                r.get("text_changed", "—"), r["first_failure"]]
        lines.append("| " + " | ".join(map(str, vals)) + " |")
    lines += ["", "¹ 보표가 사라져 음자리표 배열 길이가 달라진 경우다. 살아남은 보표의 음자리표 자체가 틀렸다는 판정은 아니다.", "",
              "실제 사진은 별도로 촬영해 같은 항목을 측정해야 한다. PDF 글리프 자동 대응 역시 육안 전수 검증을 대신하지 않는다.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("요약:", path, f"({kind} {digest[:12]}…)")


if __name__ == "__main__":
    main()
