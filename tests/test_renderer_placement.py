"""인식 데이터는 그대로 두고 계이름의 중심/화음 열을 정리한다."""
import copy
import gzip
import json
from pathlib import Path
import cv2
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
from PIL import ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.renderer import _find_korean_font, render_solfege_on_image


class PlacementConsistency(unittest.TestCase):
    def render(self, named, image=None):
        image = np.full((350, 420, 3), 255, np.uint8) if image is None else image
        before = image.copy(), copy.deepcopy([vars(n) for n, _ in named]), list(named)
        with tempfile.TemporaryDirectory() as folder:
            placed = render_solfege_on_image(image, named, os.path.join(folder, 'result.png'),
                font_size=18, text_offset_y=22, staff_spacings={0: 20})
        self.assertTrue(np.array_equal(image, before[0]))
        self.assertEqual([vars(n) for n, _ in named], before[1])
        self.assertEqual(named, before[2])
        self.assertEqual(len(placed), len(named))
        self.assertCountEqual([(id(p['note']), p['text']) for p in placed],
                              [(id(n), text) for n, text in named])
        return placed

    def _solo_example(self, blocker=None):
        from unittest.mock import patch

        notes = [(SimpleNamespace(staff_index=0, x=x, y=150), '도')
                 for x in (130, 180, 230)]
        image = np.full((350, 420, 3), 255, np.uint8)
        # 양끝만 아래에 잉크가 있어 초기 방향은 위·아래·위다.
        for x in (130, 230):
            image[179:185, x-40:x+40] = 0
        if blocker == 'head':
            notes.append((SimpleNamespace(staff_index=1, x=180, y=115), ''))
        if blocker == 'label':
            notes.append((SimpleNamespace(staff_index=1, x=180, y=82), '도'))
        staff = SimpleNamespace(index=0, top=50, bottom=130,
                                line_ys=[50,70,90,110,130], spacing=20)
        before = image.copy(), copy.deepcopy([vars(n) for n, _ in notes])
        with patch('modules.verify.barline_positions',
                   return_value=[155] if blocker == 'barline' else []):
            placed = render_solfege_on_image(
                image, notes, '', font_size=18, text_offset_y=22,
                staff_spacings={0:20, 1:20}, staves=[staff],
                image_writer=lambda _image: None)
        self.assertTrue(np.array_equal(image, before[0]))
        self.assertEqual([vars(n) for n, _ in notes], before[1])
        self.assertEqual(len(placed), len(notes))
        return placed

    def test_solo_middle_joins_clear_neighbor_side(self):
        placed = self._solo_example()
        self.assertEqual([p['side'] for p in placed], ['above'] * 3)
        self.assertEqual((placed[1]['x'], placed[1]['y'], placed[1]['gap']), (169,106,27))

    def test_solo_preserves_position_at_head_label_and_barline(self):
        for blocker in ('head', 'label', 'barline'):
            with self.subTest(blocker=blocker):
                placed = self._solo_example(blocker)
                self.assertEqual([p['side'] for p in placed[:3]], ['above','below','above'])
                self.assertEqual((placed[1]['x'], placed[1]['y'], placed[1]['gap']), (169,177,27))

    def test_move_does_not_spend_original_search_ink_budget(self):
        n = SimpleNamespace(staff_index=0, x=180, y=150)
        image = np.full((350, 420, 3), 255, np.uint8)
        box = ImageFont.truetype(_find_korean_font(), 22).getbbox('도')
        h = box[3] - box[1]
        y = n.y + round(22 * 22 / 18)
        image[y:y+h, n.x-1:n.x+2] = 0
        placed = self.render([(n, '도')], image)[0]
        self.assertEqual(placed['side'], 'below')
        self.assertGreater(abs(placed['x'] + placed['w']/2 - n.x), .5)

    def test_original_ink_takes_priority_over_staff_direction(self):
        n = SimpleNamespace(staff_index=0, x=180, y=150)
        image = np.full((350,420,3),255,np.uint8)
        y = n.y + round(22*22/18)
        image[y+5:y+8,:,:] = 0
        placed = self.render([(n,'도')],image)[0]
        self.assertEqual(placed['side'],'above')

    def test_gray_outline_is_preserved_even_when_black_ink_count_is_equal(self):
        high = SimpleNamespace(staff_index=0, x=186, y=100)
        low = SimpleNamespace(staff_index=0, x=180, y=125)
        image = np.full((350,420,3),255,np.uint8)
        image[52,180] = 230
        with tempfile.TemporaryDirectory() as folder:
            png = Path(folder)/'gray.png'
            placed = render_solfege_on_image(image, [(low,'도'),(high,'솔')], str(png),
                font_size=18, text_offset_y=22, staff_spacings={0:20})
            result = cv2.imdecode(np.fromfile(png,np.uint8),cv2.IMREAD_COLOR)
        self.assertTrue(np.array_equal(result[52,180], image[52,180]))
        # 한 획이 더 가려지면 화음의 다른 라벨도 함께 원래 열을 유지한다.
        self.assertEqual([p['x']+p['w']/2 for p in placed], [180,186])

    def test_chord_column_aligns_displaced_heads(self):
        high = SimpleNamespace(staff_index=0, x=186, y=100)
        low = SimpleNamespace(staff_index=0, x=180, y=125)
        placed = self.render([(low, '도'), (high, '솔')])
        centers = [p['x'] + p['w']/2 for p in placed]
        self.assertLessEqual(max(centers)-min(centers), 1)
        by_y = sorted(placed, key=lambda p: p['note'].y)
        self.assertLess(by_y[0]['y']+by_y[0]['h'], by_y[1]['y'])
        self.assertEqual([p['side'] for p in by_y], ['above', 'below'])

    def test_saved_schubert_label_does_not_jump_to_another_staff(self):
        from modules.labels_io import document_notes, document_staves
        root = Path(__file__).resolve().parents[1]
        with gzip.open(root/'docs/releases/e141908/strict-rows.json.gz', 'rt', encoding='utf-8') as stream:
            row = next(r for r in json.load(stream) if r['case']=='schubert_bravura')
        doc = row['after']
        source = root/'test_scores/verovio'/doc['source']['file']
        image = cv2.imdecode(np.fromfile(source, np.uint8), cv2.IMREAD_COLOR)
        staves = document_staves(doc)
        with tempfile.TemporaryDirectory() as folder:
            placed = render_solfege_on_image(image, document_notes(doc), str(Path(folder)/'schubert.png'),
                staff_spacings={s.index:s.spacing for s in staves}, staves=staves,
                confidences=[r['confidence'] for r in doc['labels']])
        target = next(p for p in placed if (p['note'].x,p['note'].y,p['text'])==(1481,1225,'라'))
        spacing = next(s.spacing for s in staves if s.index==target['note'].staff_index)
        self.assertLessEqual(target['gap'], 3*spacing)

    def test_db_fingering_and_ledger_ink_is_not_newly_covered(self):
        from modules.labels_io import document_notes, document_staves
        root = Path(__file__).resolve().parents[1]
        with gzip.open(root/'docs/releases/e141908/strict-rows.json.gz', 'rt', encoding='utf-8') as stream:
            doc = next(r['after'] for r in json.load(stream) if r['case']=='chopin_Db_p1')
        image = cv2.imdecode(np.fromfile(root/'tests/fixtures/selftest/chopin_Db_p1.png', np.uint8), cv2.IMREAD_COLOR)
        before = cv2.imdecode(np.fromfile(root/'docs/releases/e141908/chopin_Db_p1.png', np.uint8), cv2.IMREAD_COLOR)
        staves = document_staves(doc)
        with tempfile.TemporaryDirectory() as folder:
            png = Path(folder)/'db.png'
            render_solfege_on_image(image, document_notes(doc), str(png),
                staff_spacings={s.index:s.spacing for s in staves}, staves=staves,
                confidences=[r['confidence'] for r in doc['labels']])
            after = cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_COLOR)
        ink = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) < 128
        for staff in staves:
            for y in staff.line_ys:
                ink[max(0,round(y)-1):round(y)+2,:] = False
        # 원본과 같은 색인 화소가 새 글자/흰 테두리 아래로 사라지는지 본다.
        for x0,y0,x1,y1 in ((500,2670,1190,2930),(980,1290,1980,1660),(300,2040,1140,2390)):
            newly_hidden = (ink[y0:y1,x0:x1] &
                np.any(after[y0:y1,x0:x1] != image[y0:y1,x0:x1],axis=2) &
                ~np.any(before[y0:y1,x0:x1] != image[y0:y1,x0:x1],axis=2))
            self.assertEqual(int(newly_hidden.sum()), 0, (x0,y0,x1,y1))

        annotations = json.loads((root/'docs/review/placement_20261019/ink_revision/symbols.json').read_text(encoding='utf-8'))
        for symbol in annotations['symbols']:
            x0,y0,x1,y1 = symbol['rect']
            original = image[y0:y1,x0:x1].astype(np.int16)
            old_error = np.abs(before[y0:y1,x0:x1].astype(np.int16)-original)
            new_error = np.abs(after[y0:y1,x0:x1].astype(np.int16)-original)
            self.assertFalse(np.any((new_error>old_error) & np.any(original!=255,axis=2)[...,None]), symbol['name'])

    def test_wide_chain_does_not_become_a_common_column(self):
        named = [(SimpleNamespace(staff_index=0, x=x, y=y), '도')
                 for x, y in ((100,100), (115,115), (130,130))]
        placed = self.render(named)
        self.assertGreater(max(p['x']+p['w']/2 for p in placed)-
                           min(p['x']+p['w']/2 for p in placed), 1)

    def test_repeated_note_object_is_not_dropped(self):
        high = SimpleNamespace(staff_index=0, x=186, y=100)
        low = SimpleNamespace(staff_index=0, x=180, y=125)
        self.render([(low, '도'), (high, '솔'), (low, '도#')])


if __name__ == '__main__':
    unittest.main()
