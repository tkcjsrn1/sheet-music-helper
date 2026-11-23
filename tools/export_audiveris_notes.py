# -*- coding: utf-8 -*-
"""Audiveris MusicXML 음 목록과 OMR 머리 좌표를 따로 추출한다. 정답 판정·서로의 매칭은 하지 않는다."""
import argparse
import csv
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def read_xml(archive, member):
    root = ET.fromstring(archive.read(member))
    for element in root.iter():
        element.tag = element.tag.rsplit('}', 1)[-1]
    return root


def export(mxl, omr, output):
    with zipfile.ZipFile(mxl) as archive:
        container = read_xml(archive, 'META-INF/container.xml')
        member = container.find('rootfiles/rootfile').attrib['full-path']
        root = read_xml(archive, member)
    if root.tag != 'score-partwise':
        raise ValueError('이 추출기는 score-partwise MusicXML만 지원합니다.')
    notes = []
    for part in root.findall('part'):
        for measure in part.findall('measure'):
            for index, note in enumerate(measure.findall('note')):
                pitch = note.find('pitch')
                if pitch is None:
                    continue  # 쉼표·무음고 기호는 음고 비교 목록에 넣지 않는다.
                step, octave = pitch.findtext('step'), pitch.findtext('octave')
                assert step in 'ABCDEFG' and octave is not None, '불완전한 음고'
                notes.append(dict(part=part.attrib['id'], measure=measure.attrib['number'],
                    note_index=index, staff=note.findtext('staff', '1'), voice=note.findtext('voice', ''),
                    step=step, alter=pitch.findtext('alter', '0'), octave=octave,
                    chord=note.find('chord') is not None, grace=note.find('grace') is not None))
    heads = []
    with zipfile.ZipFile(omr) as archive:
        for name in archive.namelist():
            if name.startswith('sheet#') and name.endswith('.xml'):
                for head in read_xml(archive, name).iter('head'):
                    bounds = head.find('bounds')
                    if bounds is not None:
                        heads.append(dict(sheet=name, id=head.attrib['id'], staff=head.attrib.get('staff', ''),
                            relative_pitch=head.attrib.get('pitch', ''), shape=head.attrib.get('shape', ''),
                            **{k: bounds.attrib[k] for k in ('x', 'y', 'w', 'h')}))
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [('notes.tsv', notes), ('heads.tsv', heads)]:
        if not rows:
            raise ValueError(f'{name}: 추출할 행이 없습니다.')
        with (output / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    print(f'MusicXML 음 {len(notes)}행, OMR 머리 {len(heads)}행. 대응·정확도는 미검증.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mxl', type=Path)
    parser.add_argument('omr', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export(args.mxl, args.omr, args.output)
