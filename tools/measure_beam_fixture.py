# -*- coding: utf-8 -*-
"""빔 악보 소스 정답과 단계별 검출을 대조한다. 제품 코드·정답 파일은 변경하지 않는다."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / 'tests/fixtures/beams'
spec = importlib.util.spec_from_file_location('beam_fixture_builder', FIXTURE / 'build_fixture.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

from modules.preprocess import preprocess
from modules.clef_keysig import analyze_staves
from modules.notehead_detect import detect_noteheads
from modules.verify import drop_beam_ghosts, drop_offstaff_ghosts
from modules.pitch_calculator import calculate_pitches
from modules.accidental_detect import annotate_accidentals, remove_accidental_ghosts


def match_source(notes, detected):
    """PDF 음표 머리 상자 안의 후보만 대응한다. 거리 문턱이나 총개수 상쇄를 쓰지 않는다."""
    matched = set()
    missing, duplicates, wrong_pitch = [], [], []
    for note in notes:
        x0, y0, x1, y1 = [v * 300 / 72 for v in note['bbox_pt']]
        indexes = [i for i, h in enumerate(detected)
                   if h.staff_index == note['staff_index'] and x0 <= h.x <= x1 and y0 <= h.y <= y1]
        if not indexes:
            missing.append(note['id'])
        if len(indexes) > 1:
            duplicates.append(note['id'])
        for i in indexes:
            assert i not in matched, '한 검출이 소스 음표 둘에 대응하면 안 된다'
            matched.add(i)
            h = detected[i]
            if hasattr(h, 'note_name') and f'{h.note_name}{h.octave}' != note['pitch']:
                wrong_pitch.append(dict(id=note['id'], expected=note['pitch'], actual=f'{h.note_name}{h.octave}'))
    extra = [dict(x=h.x, y=h.y, staff=h.staff_index) for i, h in enumerate(detected) if i not in matched]
    return dict(count=len(detected), matched=len(matched), missing=missing, duplicates=duplicates,
                wrong_pitch=wrong_pitch, extra=extra)


def measure():
    expected = builder.expected_from_pdf()
    assert expected == json.loads(builder.EXPECTED.read_text(encoding='utf-8'))
    result = preprocess(str(builder.PDF), pdf_dpi=300)
    contexts = analyze_staves(result)
    heads = detect_noteheads(result, contexts=contexts)
    kept, dropped = drop_beam_ghosts(result, heads)
    offstaff, offdrops = drop_offstaff_ghosts(result, kept)
    pitched = calculate_pitches(offstaff, result.staves, clef={i: c.clef for i, c in contexts.items()})
    acc = annotate_accidentals(result, contexts, pitched)
    final, final_acc = remove_accidental_ghosts(pitched, acc, result.staves)
    stages = {name: match_source(expected['notes'], items) for name, items in
              [('detected', heads), ('after_beam', kept), ('after_offstaff', offstaff), ('final', final)]}
    report = dict(source_sha256=expected['source_sha256'], pdf_sha256=expected['pdf_sha256'],
                  module_sha256={p.name: builder.sha256(p) for p in (ROOT / 'modules').glob('*.py')},
                  truth_notes=len(expected['notes']), duration_counts=dict(Counter(n['duration_denominator'] for n in expected['notes'])),
                  beam_groups=len(expected['beams']), staves=len(result.staves),
                  detected_filled=sum(h.filled for h in heads), stages=stages,
                  natural_beam_filter_reasons=dict(Counter(d['reason'] for d in dropped)),
                  natural_beam_drops=dropped, offstaff_drops=offdrops,
                  final_accidentals=[dict(x=n.x, y=n.y, accidental=a) for n, a in zip(final, final_acc) if a])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/beam-fixture/measurement.json')
    args = parser.parse_args()
    report = measure()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(v['missing'] or v['duplicates'] or v['wrong_pitch'] for v in report['stages'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
