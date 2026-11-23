"""신고 재현은 ZIP 경로 탈출·설정 오해·같은 수의 다른 라벨을 놓치지 않는다."""
import copy
import hashlib
import json
import struct
import subprocess
from unittest.mock import patch
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.replay_report import unpack_report, conversion_arguments, compare_documents

class ReplayTests(unittest.TestCase):
    def test_safe_unpack_and_settings_and_changed_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            doc=dict(source=dict(sha256=hashlib.sha256(b'input').hexdigest(),page=2),
                     music=dict(key_symbol='b',key_count=1),staves=[dict(id=0,clef='bass')],
                     labels=[dict(staff=0,x=10,y=20,pitch='B3',text='시b',confidence='check')])
            archive=p/'report.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('original.pdf',b'input')
                z.writestr('result.png',b'output')
                z.writestr('labels.json',json.dumps(doc))
                z.writestr('report.json',json.dumps(dict(settings={
                    'clef':'모두 낮은음자리표','notation':'계이름 (이동도)',
                    'key':'F','minor':True,'photo':True,'font_size':16,
                    'text_color':'#123456'})))
            source,old,report=unpack_report(archive,p/'unpacked')
            self.assertEqual(source.read_bytes(),b'input')
            args=conversion_arguments(source,p/'current',old,report)
            self.assertIn('--photo',args);self.assertIn('--minor',args)
            self.assertEqual(args[args.index('--clef')+1],'bass')
            self.assertEqual(args[args.index('--notation')+1],'solfege-movable')
            self.assertEqual(args[args.index('--page')+1],'2')
            now=copy.deepcopy(doc)
            now['labels'][0]['text']='시'
            now['music']['key_count']=0
            diff=compare_documents(doc,now)
            self.assertEqual({r['kind'] for r in diff},{'music','label'})
            self.assertEqual(len(diff),2)
            self.assertEqual(compare_documents(doc,copy.deepcopy(doc)),[])
    def test_archive_rejection_before_writing_any_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for entries in (['../outside.png'],['original.png','original.png'],
                            ['original.png','result.png','labels.json','report.json','run.exe']):
                archive=p/'bad.zip'
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    with zipfile.ZipFile(archive,'w') as z:
                        for name in entries:z.writestr(name,b'{}')
                output=p/'unpacked'
                with self.assertRaises(ValueError):unpack_report(archive,output)
                self.assertFalse(output.exists())
    def test_bad_compression_does_not_stop_other_reports(self):
        from tools.summarize_reports import summarize_reports
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);incoming=root/'incoming';incoming.mkdir()
            doc=dict(source=dict(sha256=hashlib.sha256(b'input').hexdigest(),page=0),
                     music=dict(key_symbol='',key_count=0),staves=[],labels=[])
            for name in ('a-unsupported','b-damaged','c-valid'):
                archive=incoming/(name+'.zip')
                with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                    for entry,data in [('original.png',b'input'),('result.png',b'result'),
                                       ('labels.json',json.dumps(doc).encode()),('report.json',b'{}')]:
                        z.writestr(entry,data)
                with zipfile.ZipFile(archive) as z:
                    entry=z.getinfo('labels.json');offset=entry.header_offset
                raw=bytearray(archive.read_bytes())
                if name=='a-unsupported':
                    struct.pack_into('<H',raw,offset+8,99)
                    position=raw.find(b'PK\x01\x02')
                    while position!=-1:
                        nlen,xlen,clen=struct.unpack_from('<HHH',raw,position+28)
                        if raw[position+46:position+46+nlen]==b'labels.json':
                            struct.pack_into('<H',raw,position+10,99)
                        position=raw.find(b'PK\x01\x02',position+46+nlen+xlen+clen)
                elif name=='b-damaged':
                    nlen,xlen=struct.unpack_from('<HH',raw,offset+26)
                    start=offset+30+nlen+xlen
                    raw[start:start+entry.compress_size]=b'\xff'*entry.compress_size
                archive.write_bytes(raw)
                if name!='c-valid':
                    with self.assertRaises(ValueError):unpack_report(archive,root/name)
                    self.assertFalse((root/name).exists())
            # 정상 신고의 인식 단계만 대체한다. ZIP 검사·접수 루프·요약 저장은 실제 실행한다.
            def convert(args,**kwargs):
                folder=Path(args[args.index('--output-dir')+1]);folder.mkdir()
                (folder/'original_라벨.json').write_text(json.dumps(doc),encoding='utf-8')
                return subprocess.CompletedProcess(args,0,'','')
            with patch('tools.replay_report.subprocess.run',side_effect=convert) as run, \
                    patch('tools.replay_report.subprocess.check_output',return_value='verified\n'):
                rows=summarize_reports(incoming,root/'out')
            self.assertEqual([r['status'] for r in rows],['failed','failed','success'])
            self.assertEqual(run.call_count,1)
            self.assertFalse((root/'out/001').exists());self.assertFalse((root/'out/002').exists())
            self.assertEqual(json.loads((root/'out/summary.json').read_text(encoding='utf-8')),rows)

    def test_unknown_settings_and_duplicate_coordinates_are_not_silent(self):
        with self.assertRaises(ValueError):
            conversion_arguments(Path('original.png'),Path('out'),
                                 {'source':{'page':0}}, {'settings':{'clef':'guess'}})
        label=dict(staff=0,x=10,y=20,pitch='C4',text='도')
        old=dict(source={},music={},staves=[],labels=[label,label.copy()])
        now=copy.deepcopy(old);now['labels'][1]['pitch']='D4'
        self.assertEqual(compare_documents(old,now)[0]['kind'],'label')

if __name__=='__main__':unittest.main()

