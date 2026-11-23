"""기준 커밋과 현재 헤더 함수만 교체해 같은 입력의 제품 PNG·JSON을 대조한다.

python tools/measure_header_symbol_regression.py --extra-root <검증자료가 있는 체크아웃>
사진 대조 입력은 --photo-dir로 지정한다. 정답 파일·제품 문턱을 갱신하지 않는다.
"""
import argparse
import ast
import contextlib
import csv
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import main as CLI
import modules.clef_keysig as CK
from measure_sim_ledger_pair import pages
from modules.preprocess import preprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-ref", default="38274707a3e98ecb2e69cc7443fc002901eb4bdb")
    p.add_argument("--extra-root", type=Path)
    p.add_argument("--photo-dir", type=Path)
    p.add_argument("--photos-only", action="store_true")
    p.add_argument("--reuse-baseline-dir", type=Path)
    p.add_argument("--output-dir", type=Path, default=ROOT / "output/header-symbols/matrix")
    args = p.parse_args()
    source = subprocess.check_output(["git", "show", f"{args.baseline_ref}:modules/clef_keysig.py"], cwd=ROOT).decode("utf-8")
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "analyze_staves")
    node.name = "baseline_analyze_staves"
    exec(compile(ast.Module(body=[node], type_ignores=[]), "baseline", "exec"), CK.__dict__)
    current = CK.analyze_staves
    if args.photos_only and not args.photo_dir:
        p.error("--photos-only에는 --photo-dir가 필요합니다")
    jobs = [] if args.photos_only else [(kind, name, Path(path), pg, False) for kind, name, path, pg in pages()]
    if args.photo_dir:
        jobs += [("photo", f.stem, f.resolve(), 0, True) for f in sorted(args.photo_dir.iterdir()) if f.suffix.lower() in (".png", ".jpg")]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    reusable = set()
    if args.reuse_baseline_dir:
        saved = json.loads((args.reuse_baseline_dir / "report.json").read_text(encoding="utf-8"))
        assert saved["baseline"] == args.baseline_ref, "기준 커밋이 다른 자료는 재사용하지 않습니다"
        reusable = {r["name"] for r in saved["rows"] if r["status"].get("before") == "완료"}
    for kind, name, path, page, photo in jobs:
        full = ROOT / path
        if not full.exists() and args.extra_root:
            full = args.extra_root / path
        if not full.exists():
            raise FileNotFoundError(full)
        documents, pngs, status = {}, {}, {}
        for version, func in (("before", CK.baseline_analyze_staves), ("after", current)):
            if version == "before" and name in reusable:
                cached = args.reuse_baseline_dir / "before" / name
                doc = json.loads((cached / "labels.json").read_text(encoding="utf-8"))
                assert doc["source"]["sha256"] == hashlib.sha256(full.read_bytes()).hexdigest(), "기준 입력 SHA 불일치"
                assert doc["source"]["page"] == page, "기준 쪽 번호 불일치"
                documents[version] = doc
                pngs[version] = next(cached.glob("*_계이름*.png")).read_bytes()
                status[version] = "완료"
                continue
            out = args.output_dir / version / name
            out.mkdir(parents=True, exist_ok=True)
            js = out / "labels.json"
            argv = ["main.py", str(full), "--page", str(page), "--no-debug", "--output-dir", str(out), "--save-labels", str(js)] + (["--photo"] if photo else [])
            CK.analyze_staves = CLI.analyze_staves = func
            log = io.StringIO()
            try:
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(log):
                    CLI.run_page(CLI.parse_args(), str(full), page, str(out))
                documents[version] = json.loads(js.read_text(encoding="utf-8"))
                pngs[version] = next(out.glob("*_계이름*.png")).read_bytes()
                status[version] = "완료"
            except SystemExit as e:
                status[version] = f"거부:{e.code}"
            finally:
                CK.analyze_staves = CLI.analyze_staves = current
                (out / "source.log").write_text(log.getvalue(), encoding="utf-8")
        row = dict(kind=kind, name=name, status=status)
        if len(documents) == 2:
            a, b = documents["before"], documents["after"]
            key = lambda r: (r["staff"], r["x"], r["y"], r["pitch"], r["text"])
            old, new = {key(r):r for r in a["labels"]}, {key(r):r for r in b["labels"]}
            removed = [old[k] for k in old.keys()-new.keys()]
            added = [new[k] for k in new.keys()-old.keys()]
            possible_loss = []
            if removed and kind == "verovio":
                truth = list(csv.DictReader(full.with_suffix(".tsv").open(encoding="utf-8"), delimiter="\t"))
                result = preprocess(str(full))
                for r in removed:
                    sp = result.staves[r["staff"]].spacing
                    near = [t for t in truth if abs(float(t["x"])-r["x"])<=.7*sp and abs(float(t["y"])-r["y"])<=.5*sp]
                    if near: possible_loss.append(dict(label=r, truth=near))
            elif removed and kind != "photo":
                raise AssertionError(f"{name}: 예상 밖 라벨 삭제를 정답으로 판정해야 합니다: {removed}")
            row.update(before_count=len(a["labels"]), after_count=len(b["labels"]), added=added, removed=removed,
                       retained_value_changes=[dict(before=old[k],after=new[k]) for k in old.keys()&new.keys() if old[k]!=new[k]],
                       json_equal=a==b, png_equal=pngs["before"]==pngs["after"], music_equal=a["music"]==b["music"],
                       possible_true_note_loss=possible_loss)
        rows.append(row)
        (args.output_dir / "report.json").write_text(json.dumps(dict(baseline=args.baseline_ref, clef_keysig_sha256=hashlib.sha256(Path(CK.__file__).read_bytes()).hexdigest(), rows=rows), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(name, status, f"{row.get('before_count','-')}→{row.get('after_count','-')}", "변화없음" if row.get("json_equal") else "대조 필요", flush=True)
        if row.get("possible_true_note_loss") or status.get("before") != status.get("after"):
            raise AssertionError(f"{name}: 정답 음표 소실 후보 또는 처리 상태 변화 — 채택 중단")
    print("대조 완료", len(rows), "쪽", flush=True)


if __name__ == "__main__":
    main()
