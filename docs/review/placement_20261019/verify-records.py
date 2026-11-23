"""원본 기호 보호 수정의 보존 원자료를 독립 대조한다. 새 인식은 실행하지 않는다."""
import gzip
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[3]
folder=Path(__file__).resolve().parent
old=json.loads(gzip.decompress((folder/'measurements.json.gz').read_bytes()))['baseline']
new=json.loads(gzip.decompress((folder/'ink_revision/candidate.json.gz').read_bytes()))
proof=json.loads((folder/'verification.json').read_text(encoding='utf-8'))
assert len(old)==len(new)==12
for before,after in zip(old,new):
    assert before['case']==after['case'] and before['labels']==after['labels']
    assert before['json_sha256']==after['json_sha256']
    assert after['input_json_bytes_unchanged'] and after['input_objects_unchanged']
    a={p['index']:p for p in before['placed']};b={p['index']:p for p in after['placed']}
    assert a.keys()==b.keys()
    assert all(p['gap']<=a[i]['gap'] for i,p in b.items())
    for key in ('head_hits','box_hits','bar_crossings','order_inversions'):
        assert not set(map(tuple,after['metrics'][key]))-set(map(tuple,before['metrics'][key]))
assert proof['total_labels']==sum(r['metrics']['labels'] for r in new)==4721
assert proof['changed']==12
for case in proof['cases']:
    for key in ('increased_source_ink_labels','increased_ink_with_decoration_labels','newly_hidden_source_pixels','worsened_nonstaff_source_pixels','newly_hidden_symbols'):
        assert case[key]==0,(case['case'],key)
    if 'symbols' in case:
        assert len(case['symbols'])==9 and all(r['revised_worsened_pixels']==0 for r in case['symbols'])
assert all(p['equal'] and p['before_sha256']==p['after_sha256'] for p in proof['product_pipeline'])
suite=proof['full_suite'];assert (suite['passed'],suite['failed'],suite['skipped'])==(48,0,0)
actual=hashlib.sha256((root/'modules/renderer.py').read_text(encoding='utf-8').encode()).hexdigest()
assert actual==suite['renderer_lf_sha256']
method=json.loads((folder/'method.json').read_text(encoding='utf-8'));assert actual==method['candidate_renderer_lf_sha256']
print('12쪽4721라벨/JSON 불변 · 잉크증가 라벨0 · 신규 기호가림0 · 운지9곳 악화0 · 전체48 통과와 코드해시 동일')
