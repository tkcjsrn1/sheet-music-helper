"""전용 계이름 줄 시안: 기본 경로와 인식 데이터는 그대로 둔다."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.renderer import render_solfege_in_lanes, render_solfege_on_image


class LabelLanes(unittest.TestCase):
    def render(self, image, named, staves):
        before = image.copy(), copy.deepcopy([vars(n) for n, _ in named])
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'old.png', Path(tmp)/'lane.png'
            opts = dict(staves=staves, staff_spacings={s.index:s.spacing for s in staves})
            old = render_solfege_on_image(image, named, str(a), **opts)
            new = render_solfege_in_lanes(image, named, str(b), **opts)
            same = a.read_bytes() == b.read_bytes()
        self.assertTrue(np.array_equal(image, before[0]))
        self.assertEqual([vars(n) for n, _ in named], before[1])
        self.assertEqual(len(new), len(named))
        self.assertCountEqual([(id(p['note']), p['text']) for p in new], [(id(n),t) for n,t in named])
        return old, new, same

    def test_common_row_and_high_pitch_on_top_at_own_x(self):
        staff = SimpleNamespace(index=0, top=90, bottom=170, spacing=20, line_ys=[90,110,130,150,170])
        named = [(SimpleNamespace(staff_index=0,x=x,y=y),t) for x,y,t in [(100,110,'솔'),(105,150,'도'),(230,130,'미')]]
        _, ps, same = self.render(np.full((400,360,3),255,np.uint8), named, [staff])
        self.assertFalse(same)
        self.assertTrue(all(p.get('lane') for p in ps))
        for p in ps:self.assertLessEqual(abs(p['x']+p['w']/2-p['note'].x),.5)
        by_text={p['text']:p for p in ps}
        self.assertLess(by_text['솔']['y']+by_text['솔']['h'],by_text['도']['y'])
        self.assertEqual(by_text['도']['y'],by_text['미']['y'])
        self.assertGreater(min(p['y'] for p in ps),staff.bottom)

    def test_no_empty_space_keeps_entire_staff_byte_identical(self):
        staff=SimpleNamespace(index=0,top=40,bottom=120,spacing=20,line_ys=[40,60,80,100,120])
        image=np.full((260,360,3),255,np.uint8);image[121:]=80
        named=[(SimpleNamespace(staff_index=0,x=x,y=90),'도') for x in (90,210)]
        old,new,same=self.render(image,named,[staff])
        self.assertTrue(same)
        self.assertEqual(old,new)

    def test_long_neighbor_labels_separate_without_abandoning_the_staff(self):
        staff=SimpleNamespace(index=0,top=40,bottom=120,spacing=20,line_ys=[40,60,80,100,120])
        named=[(SimpleNamespace(staff_index=0,x=x,y=90),'파##') for x in (100,125)]
        old,new,same=self.render(np.full((350,360,3),255,np.uint8),named,[staff])
        self.assertFalse(same)
        self.assertTrue(all(p.get('lane') for p in new))
        left,right=new
        self.assertTrue(left['x']+left['w']<=right['x'] or right['x']+right['w']<=left['x']
                        or left['y']+left['h']<=right['y'] or right['y']+right['h']<=left['y'])

    def test_adjacent_wide_chords_can_use_neighbor_rows_without_inversion(self):
        staff = SimpleNamespace(index=0, top=40, bottom=120, spacing=20,
                                line_ys=[40, 60, 80, 100, 120])
        named = [(SimpleNamespace(staff_index=0, x=x, y=y), '파##')
                 for x in (96, 126, 156) for y in (80, 100)]
        image = np.full((480, 340, 3), 255, np.uint8)
        _, placements, _ = self.render(image, named, [staff])
        self.assertTrue(all(p.get('lane') for p in placements))
        for x in (96, 126, 156):
            upper, lower = sorted((p for p in placements if p['note'].x == x),
                                  key=lambda p: p['note'].y)
            self.assertLess(upper['y'] + upper['h'], lower['y'])

    def test_shared_gap_cannot_use_the_separation_between_systems(self):
        staves = [SimpleNamespace(index=i, top=y, bottom=y+80, spacing=20,
                                  line_ys=list(range(y,y+81,20)))
                  for i,y in [(1,40),(2,280),(3,440)]]
        named = [(SimpleNamespace(staff_index=i, x=x, y=y), '미')
                 for i,x,y in [(1,90,80),(2,230,315)]]
        image = np.full((620,360,3),255,np.uint8)
        image[121:280] = 80
        image[180:221] = 255
        before, after, same = self.render(image,named,staves)
        self.assertTrue(same)
        self.assertEqual(before,after)

    def test_search_cannot_cross_a_distant_footer(self):
        staff = SimpleNamespace(index=1,top=40,bottom=120,spacing=20,line_ys=[40,60,80,100,120])
        image = np.full((420,360,3),255,np.uint8)
        image[121:271] = 80
        named = [(SimpleNamespace(staff_index=1,x=130,y=95), '도')]
        before, after, same = self.render(image,named,[staff])
        self.assertTrue(same)
        self.assertEqual(before,after)

    def test_blocked_staff_keeps_near_x_but_repairs_reversed_chord(self):
        from unittest.mock import patch

        staffs = [SimpleNamespace(index=i,top=top,bottom=top+80,spacing=20,
                                  line_ys=list(range(top,top+81,20)))
                  for i,top in enumerate((150,330))]
        notes = [SimpleNamespace(staff_index=i,x=x,y=y)
                 for i,x,y in [(0,255,180),(1,110,346),(1,114,367)]]
        original = [dict(note=n, text='도', x=x, y=y, w=20, h=16, gap=n.y-y-16,
                         side='above', want='above')
                    for n,x,y in zip(notes,(240,52,145),(120,325,305))]
        image = np.full((570,360,3),255,np.uint8)
        image[411:] = 80
        status = {}
        with tempfile.TemporaryDirectory() as tmp, patch(
            'modules.renderer.render_solfege_on_image',return_value=[p.copy() for p in original]
        ):
            after = render_solfege_in_lanes(image,[(n,'도') for n in notes],str(Path(tmp)/'result.png'),
                                           staves=staffs,staff_spacings={0:20,1:20},layout_status=status)
        self.assertTrue(after[0].get('lane'))
        self.assertIn('공간',status['message'])
        self.assertEqual([p['x'] for p in after[1:]],[52,145])
        self.assertLessEqual(after[1]['y']+after[1]['h']/2,after[2]['y']+after[2]['h']/2)

    def test_missing_staff_geometry_keeps_default(self):
        named=[(SimpleNamespace(staff_index=0,x=150,y=90),'도')]
        _,_,same=self.render(np.full((260,360,3),255,np.uint8),named,[])
        self.assertTrue(same)

    def test_one_blocked_staff_keeps_its_near_positions_and_check_style(self):
        from modules.renderer import LABEL_STYLES
        import cv2
        staffs=[SimpleNamespace(index=i,top=top,bottom=top+80,spacing=20,
                 line_ys=list(range(top,top+81,20))) for i,top in enumerate((160,380))]
        named=[(SimpleNamespace(staff_index=i,x=x,y=y),text)
               for i,x,y,text in [(0,100,180,'솔'),(0,230,200,'미'),(1,150,420,'파##')]]
        image=np.full((650,360,3),255,np.uint8)
        image[461:]=80
        opts=dict(staves=staffs,staff_spacings={0:20,1:20},confidences=['check','caution','check'])
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.png',Path(tmp)/'b.png'
            before=render_solfege_on_image(image,named,str(a),**opts)
            status={}
            after=render_solfege_in_lanes(image,named,str(b),layout_status=status,**opts)
            old=cv2.imdecode(np.fromfile(a,np.uint8),cv2.IMREAD_COLOR)
            new=cv2.imdecode(np.fromfile(b,np.uint8),cv2.IMREAD_COLOR)
        self.assertTrue(status['applied'])
        self.assertIn('공간',status['message'])
        self.assertTrue(all(p.get('lane') for p in after if p['note'].staff_index==0))
        self.assertEqual([p for p in after if p['note'].staff_index==1],
                         [p for p in before if p['note'].staff_index==1])
        self.assertFalse(np.array_equal(old,new))
        self.assertTrue(np.array_equal(old[360:],new[360:]),'옆 표기의 주황 점선과 화소가 달라졌습니다')


    def test_near_white_background_and_head_boxes(self):
        staff=SimpleNamespace(index=0,top=90,bottom=170,spacing=20,line_ys=[90,110,130,150,170])
        named=[(SimpleNamespace(staff_index=0,x=120,y=185),'도'),
               (SimpleNamespace(staff_index=0,x=210,y=150),'미')]
        image=np.full((360,360,3),254,np.uint8)
        _, new, _=self.render(image,named,[staff])
        self.assertTrue(all(p.get('lane') for p in new))
        self.assertEqual(new[0]['y'],new[1]['y'])
        self.assertGreaterEqual(new[0]['y'],195)

    def test_nearest_line_is_inside_dynamics_when_there_is_room(self):
        staff=SimpleNamespace(index=0,top=90,bottom=170,spacing=20,line_ys=[90,110,130,150,170])
        named=[(SimpleNamespace(staff_index=0,x=120,y=150),'도')]
        image=np.full((400,360,3),255,np.uint8);image[240:255,90:150]=32
        _, ps, _=self.render(image,named,[staff])
        self.assertTrue(ps[0].get('lane'))
        self.assertGreater(ps[0]['y'],staff.bottom)
        self.assertLess(ps[0]['y']+ps[0]['h'],240)

    def test_when_inside_is_blocked_line_is_outside_the_mark(self):
        staff=SimpleNamespace(index=0,top=90,bottom=170,spacing=20,line_ys=[90,110,130,150,170])
        named=[(SimpleNamespace(staff_index=0,x=120,y=150),'도')]
        image=np.full((400,360,3),255,np.uint8);image[171:255,90:150]=32
        _, ps, _=self.render(image,named,[staff])
        self.assertTrue(ps[0].get('lane'))
        self.assertGreater(ps[0]['y'],254)

    def test_missing_one_staff_geometry_restores_all_labels(self):
        staff=SimpleNamespace(index=0,top=90,bottom=170,spacing=20,line_ys=[90,110,130,150,170])
        named=[(SimpleNamespace(staff_index=i,x=120+100*i,y=150+100*i),'도') for i in (0,1)]
        before,after,same=self.render(np.full((450,400,3),255,np.uint8),named,[staff])
        self.assertTrue(same)
        self.assertEqual(before,after)

    def test_explicit_default_is_byte_identical_and_failure_has_notice(self):
        import inspect
        self.assertIn('placement_mode',inspect.signature(render_solfege_on_image).parameters)
        staff=SimpleNamespace(index=0,top=40,bottom=120,spacing=20,line_ys=[40,60,80,100,120])
        image=np.full((260,360,3),255,np.uint8);image[121:]=80
        named=[(SimpleNamespace(staff_index=0,x=120,y=90),'도')]
        opts=dict(staves=[staff],staff_spacings={0:20})
        with tempfile.TemporaryDirectory() as tmp:
            a,b,c=(Path(tmp)/n for n in ('a.png','b.png','c.png'))
            render_solfege_on_image(image,named,str(a),**opts)
            status={}
            render_solfege_on_image(image,named,str(b),placement_mode='near',layout_status=status,**opts)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(status,{})
            render_solfege_on_image(image,named,str(c),placement_mode='lanes',layout_status=status,**opts)
            self.assertEqual(a.read_bytes(),c.read_bytes())
            self.assertFalse(status['applied'])
            self.assertIn('쪽 전체',status['message'])


if __name__ == '__main__': unittest.main()
