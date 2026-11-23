"""D-1 영역 필터는 머리 중심을 고르고 원본·문맥·라벨 순서를 보존한다."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.label_region import filter_region

class RegionTests(unittest.TestCase):
    def setUp(self):
        self.doc=dict(source=dict(width=200,height=120,sha256='original'),music=dict(key_symbol='#'),
                      staves=[dict(id=0,spacing=12)],user_edits=dict(changes=['history']),
                      labels=[dict(x=10,y=20,text='도',pitch='C4',confidence='certain'),
                              dict(x=60,y=70,text='미',pitch='E4',confidence='check',edited=True),
                              dict(x=60,y=85,text='솔',pitch='G4',confidence='caution'),
                              dict(x=190,y=110,text='시',pitch='B4',confidence='certain')])
    def test_whole_page_is_equal_independent_copy(self):
        original=copy.deepcopy(self.doc)
        result=filter_region(self.doc,0,0,200,120)
        self.assertEqual(json.dumps(result),json.dumps(self.doc))
        result['source']['width']=10;result['labels'][0]['text']='수정'
        self.assertEqual(self.doc,original)
    def test_reversed_corners_closed_edges_chord_and_empty(self):
        result=filter_region(self.doc,60,70,10,20)
        self.assertEqual(result['labels'],self.doc['labels'][:2])
        self.assertTrue(result['labels'][1]['edited'])
        self.assertEqual(result['labels'][1]['confidence'],'check')
        for key in ('source','music','staves','user_edits'):self.assertEqual(result[key],self.doc[key])
        self.assertEqual(filter_region(self.doc,61,71,70,80)['labels'],[])
        self.assertEqual(len(self.doc['labels']),4)
    def test_invalid_rectangle_or_document_is_not_silent(self):
        for rect in [(0,0,0,10),(-1,0,100,100),(0,0,201,100),(True,0,100,100),('0',0,100,100),(0,0,float('nan'),100),(0,0,float('inf'),100)]:
            with self.subTest(rect=rect),self.assertRaises(ValueError):filter_region(self.doc,*rect)
        for bad_doc in (None,{},dict(source=None),dict(source={'width':200,'height':120},labels=None)):
            with self.subTest(bad_doc=bad_doc),self.assertRaises(ValueError):filter_region(bad_doc,0,0,100,100)
        bad=copy.deepcopy(self.doc);bad['labels'][0]['x']='10'
        with self.assertRaises(ValueError):filter_region(bad,0,0,200,120)
        bad=copy.deepcopy(self.doc);bad['source']['width']=0
        with self.assertRaises(ValueError):filter_region(bad,0,0,200,120)

if __name__=='__main__':unittest.main()
