# -*- coding: utf-8 -*-
"""명시적인 LilyPond 선율에서 PDF·MIDI와 음표별 정답을 만든다. OMR은 사용하지 않는다."""
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess

import fitz

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'sources/beam_melody.ly'
PDF = ROOT / 'pdf/beam_melody.pdf'
EXPECTED = ROOT / 'expected.json'
NOTE = re.compile(r"([a-g])([,']*)(2|8|16)(\[|\])?")
SEMITONES = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_notes(text):
    """이 픽스처 문법만 읽는다. 음길이 생략·쉼표·화음 등 새 문법은 조용히 무시하지 않는다."""
    notes = []
    staff = None
    measure = 1
    beat = Fraction(0)
    group = None
    system = 0
    stem = None
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split('%', 1)[0].strip()
        if line in ('trebleMusic = {', 'bassMusic = {'):
            staff = 'treble' if line.startswith('treble') else 'bass'
            measure, beat, group, system = 1, Fraction(0), None, 0
            continue
        if staff is None or not line:
            continue
        if line == '}':
            assert beat == 0 and group is None
            staff = None
            continue
        if line == '|':
            assert beat == 1 and group is None, (line_no, beat, group)
            measure += 1
            beat = Fraction(0)
            continue
        if line == r'\break':
            system += 1
            continue
        if line in (r'\stemUp', r'\stemDown'):
            stem = line[5:].lower()
            continue
        if line == r'\autoBeamOff':
            continue
        m = NOTE.fullmatch(line)
        if not m:
            raise ValueError(f'{line_no}행: 지원하지 않는 소스 구문 {line!r}')
        letter, marks, duration, beam = m.groups()
        octave = 3 + marks.count("'") - marks.count(',')
        duration = int(duration)
        if beam == '[':
            assert group is None
            group = f'{staff}-{line_no}'
        event = dict(id=f'{staff}-{line_no}', source_line=line_no, staff=staff,
                     staff_index=system * 2 + (staff == 'bass'), measure=measure,
                     onset_whole=str(beat), duration_denominator=duration,
                     pitch=f'{letter.upper()}{octave}', midi=12 * (octave + 1) + SEMITONES[letter],
                     beam_group=group, beam_start=beam == '[', stem=stem)
        if beam == ']':
            assert group is not None
            group = None
        notes.append(event)
        beat += Fraction(1, duration)
    assert staff is None and notes
    return notes


def expected_from_pdf():
    notes = source_notes(SOURCE.read_text(encoding='utf-8'))
    links = defaultdict(list)
    with fitz.open(PDF) as doc:
        assert len(doc) == 1, '한 쪽 픽스처여야 한다'
        size = [doc[0].rect.width, doc[0].rect.height]
        for link in doc[0].get_links():
            match = re.search(r':(\d+):\d+:\d+$', link.get('uri', ''))
            if match:
                links[int(match[1])].append(link['from'])
    beams = []
    for n in notes:
        rects = sorted(links[n['source_line']], key=lambda r: r.width)
        # 각 빔 시작 음표에는 음표 머리와 빔의 링크가 하나씩 있다.
        assert len(rects) == (2 if n['beam_start'] else 1), n
        head = rects[0]
        n['bbox_pt'] = [round(v, 5) for v in head]
        n['center_300dpi'] = [round((head.x0 + head.x1) * 300 / 144, 5),
                              round((head.y0 + head.y1) * 300 / 144, 5)]
        if n['beam_start']:
            assert rects[1].width > head.width
            beams.append(dict(id=n['beam_group'], staff_index=n['staff_index'],
                              levels=1 if n['duration_denominator'] == 8 else 2,
                              bbox_pt=[round(v, 5) for v in rects[1]]))
    return dict(schema=1, source='sources/beam_melody.ly', source_sha256=sha256(SOURCE),
                pdf='pdf/beam_melody.pdf', pdf_sha256=sha256(PDF),
                generator='LilyPond 2.26.0', dpi=300, page=1, page_size_pt=size,
                coordinate_origin='PDF 좌상단, point-and-click 음표 머리 상자의 중심',
                truth_origin='음고·길이·마디·빔 묶음은 .ly, 좌표는 LilyPond PDF 링크. OMR 미사용.',
                notes=notes, beams=beams)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lilypond', help='LilyPond 2.26.0 실행 파일. 생략하면 기존 PDF에서 정답만 추출')
    parser.add_argument('--check', action='store_true', help='파일을 쓰지 않고 소스/PDF/저장 정답 일치 검사')
    args = parser.parse_args()
    if args.check and args.lilypond:
        parser.error('--check와 --lilypond는 함께 쓰지 않는다')
    if args.lilypond:
        version = subprocess.check_output([args.lilypond, '--version']).decode('utf-8', errors='replace')
        if 'GNU LilyPond 2.26.0' not in version:
            raise RuntimeError('이 픽스처의 조판 버전은 2.26.0이다')
        subprocess.run([args.lilypond, '-o', str(PDF.with_suffix('')), str(SOURCE)], check=True)
    expected = expected_from_pdf()
    if args.check:
        assert expected == json.loads(EXPECTED.read_text(encoding='utf-8')), '정답이 소스/PDF와 다름'
    else:
        EXPECTED.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"음표 {len(expected['notes'])}개 · 빔 묶음 {len(expected['beams'])}개 · 소스/PDF 대응 확인")


if __name__ == '__main__':
    main()
