"""조표·3/4 박자표 유령의 고정 재현. 제품 판정/라벨은 변경하지 않는다.

python tools/check_header_symbols.py
python tools/check_header_symbols.py --check  # 기호 유령 또는 첫 F4/파 소실이면 종료1
python tools/check_header_symbols.py --shift-x 0.5 --check --output-dir output/phase-check
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INPUT = ROOT / 'test_scores/verovio/beethoven_op18no1_bravura_p1.png'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--shift-x', type=float, choices=(0, 0.25, 0.5, 0.75), default=0,
                        help='원본을 가로로 실제 재표본화한 뒤 최종 음고까지 검사')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/header-symbols')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    input_path = INPUT
    if args.shift_x:
        import cv2
        import numpy as np
        from modules.preprocess import load_image
        original = load_image(str(INPUT))
        moved = cv2.warpAffine(original, np.float32([[1,0,args.shift_x],[0,1,0]]),
                               (original.shape[1],original.shape[0]),
                               flags=cv2.INTER_LINEAR, borderValue=(255,255,255))
        assert not np.array_equal(original, moved), '재표본화가 생략됐습니다'
        input_path = out / 'shifted-input.png'
        cv2.imencode('.png',moved)[1].tofile(str(input_path))
    with (out / 'source.log').open('w', encoding='utf-8') as log:
        completed = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(input_path),
                                    '--output-dir', str(out), '--no-debug'], cwd=ROOT,
                                   env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                                   stdout=log, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    doc = json.loads((out / (input_path.stem + '_라벨.json')).read_text(encoding='utf-8'))
    from modules.preprocess import preprocess
    from modules.notehead_detect import remove_staff_lines
    from modules.clef_keysig import analyze_staves, _timesig_span_end, _vote_key_signature
    result = preprocess(str(input_path))
    contexts = analyze_staves(result)
    no_staff = remove_staff_lines(result.binary, result.staves)
    truth = list(csv.DictReader(INPUT.with_suffix('.tsv').open(encoding='utf-8'), delimiter='\t'))
    # 이 한 픽스처의 기호 상자다. 제품 필터/다른 악보용 판정 문턱이 아니다.
    # 같은 TSV의 첫 실제 머리는 x=407.7; 조표·박자표 기호는 x=300~365에 있다.
    assert min(float(r['x']) for r in truth if float(r['y']) < 850) > 365
    ghosts = [r for r in doc['labels'] if r['staff'] < 4 and 300 <= r['x'] <= 365]
    first_notes = [r for r in doc['labels'] if r['staff'] in (0, 1)
                   and 400 <= r['x'] <= 415 and r['pitch'] == 'F4' and r['text'] == '파']
    headers = [dict(staff=st.index, clef_end=contexts[st.index].clef_end,
                    header_end=contexts[st.index].header_end,
                    timesig_search_from=contexts[st.index].clef_end,
                    timesig_end=_timesig_span_end(no_staff, st, contexts[st.index].clef_end),
                    spacing=st.spacing) for st in result.staves[:4]]
    report = dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  clef_keysig_sha256=hashlib.sha256((ROOT / "modules/clef_keysig.py").read_bytes()).hexdigest(),
                  source=doc['source'], shift_x=args.shift_x,
                  first_candidates=[r for r in doc['labels'] if r['staff'] in (0,1) and 400 <= r['x'] <= 415],
                  key_vote=_vote_key_signature(contexts),
                  headers=headers, remaining_header_labels=ghosts,
                  first_real_notes=first_notes, fixed=not ghosts and sorted(r['staff'] for r in first_notes)==[0, 1])
    (out / 'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'조표·박자표 유령 {len(ghosts)}개 / 첫 실제 F4 음표 {len(first_notes)}/2개')
    print(json.dumps(headers,ensure_ascii=False))
    if args.check and not report['fixed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()