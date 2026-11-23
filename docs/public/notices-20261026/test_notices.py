"""원문 대응·해시·미확인 표시만 검사한다. 설치/네트워크/GUI/렌더를 실행하지 않는다."""
import collections,hashlib,json,unittest
from pathlib import Path
D=Path(__file__).parent
A=json.loads((D/'MATCHED_LICENSES.json').read_text(encoding='utf8'))
B=(D/'THIRD_PARTY_NOTICES_DRAFT.txt').read_bytes()
S={s['id']:s for s in A['sources']}
def text(s):return B[s['offset']:s['offset']+s['length']]
def intact(body):return all(hashlib.sha256(body[s['offset']:s['offset']+s['length']]).hexdigest()==s['normalized_sha256'] for s in S.values())
class Notices(unittest.TestCase):
    def test_all_package_primary_and_extra_texts_are_present(self):
        self.assertEqual(len(A['packages']),21);self.assertEqual(len({p['name'] for p in A['packages']}),21)
        for p in A['packages']:
            self.assertEqual(p['status'],'원문 확인');self.assertTrue(p['source_ids'])
            self.assertTrue(all(k in S for k in p['source_ids']))
    def test_each_of_43_fonts_matches_frozen_archive_hash(self):
        previous=json.loads((D.parent/'LICENSE_EVIDENCE.json').read_text(encoding='utf8'))
        frozen={p['entry'].replace('\\','/'):p['sha256'] for p in previous['archive_font_hashes']}
        self.assertEqual({f['entry']:f['sha256'] for f in A['fonts']},frozen)
        self.assertEqual(collections.Counter(f['family'] for f in A['fonts']),dict(Roboto=2,DejaVu=14,STIX=17,BaKoMa=8,LastResort=1,**{'CustomTkinter shapes':1}))
    def test_unconfirmed_font_is_not_silently_licensed(self):
        unknown=[f for f in A['fonts'] if f['status']=='미확인'];self.assertEqual(len(unknown),1)
        self.assertIn('shapes_font',unknown[0]['entry']);self.assertEqual(unknown[0]['source_ids'],[])
        self.assertEqual(sum(f['status']=='원문 확인' for f in A['fonts']),42)
    def test_every_original_text_survives_normalized_in_draft(self):
        self.assertEqual(len(S),62);self.assertTrue(intact(B));B.decode('utf8')
        self.assertEqual(hashlib.sha256(B).hexdigest(),A['draft_sha256'])
    def test_corrupted_license_is_rejected(self):
        changed=bytearray(B);changed[S[next(iter(S))]['offset']]+=1
        self.assertFalse(intact(changed))
    def test_mpl_and_apache_are_full_text_not_only_links(self):
        mpl=next(s for s in S.values() if any(o['path'].startswith('https://www.mozilla.org/') for o in s['origins']))
        self.assertGreater(mpl['length'],15000);self.assertIn(b'Exhibit B',text(mpl))
        apache=next(s for s in S.values() if any(o['path'].endswith('/LICENSE.APACHE') and o['path'].startswith('packaging-') for o in s['origins']))
        self.assertIn(b'END OF TERMS AND CONDITIONS',text(apache))
    def test_existing_packaged_notice_is_retained(self):
        source=next(s for s in S.values() if any(o['path']=='repository:THIRD_PARTY_NOTICES.txt' for o in s['origins']))
        original=(D.parents[2]/'THIRD_PARTY_NOTICES.txt').read_bytes()
        self.assertEqual(text(source),original.decode('utf-8-sig').replace('\r\n','\n').encode())
    def test_font_family_points_to_its_own_license_text(self):
        markers={'Roboto':b'Apache License','DejaVu':b'Bitstream Vera Fonts Copyright',
            'STIX':b'STIX Font License','BaKoMa':b'BaKoMa Fonts Licence','LastResort':b'Last Resort fonts'}
        for f in A['fonts']:
            if f['status']=='미확인':continue
            self.assertTrue(all(k in S for k in f['source_ids']))
            self.assertTrue(any(markers[f['family']] in text(S[k]) for k in f['source_ids']))
            self.assertTrue(f['copyright_source'] in S)

    def test_actual_binary_version_uncertainty_is_explicit(self):
        count=collections.Counter(p['version_in_actual_binary'] for p in A['packages'])
        self.assertEqual(count,{'빌드 기록 버전 일치':4,'미확인(설치본 대응 후보)':17})

if __name__=='__main__':unittest.main()
