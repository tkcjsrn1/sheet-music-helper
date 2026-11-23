"""고정 빌드 커밋의 실제 자체 점검 출력과 CI 기준을 대조한다. 기준은 수정하지 않는다."""
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
OUT = ROOT / 'output/release-13d73f6'
PIN = '13d73f669abce51567526f4ae6ba9804612baeac'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == PIN
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
enc = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
rows = []
for name, image in [('aoharu_p1', 'sample_images/KakaoTalk_20260731_162400402.png'),
                    ('chopin_Db_p1', 'tests/fixtures/selftest/chopin_Db_p1.png')]:
    baseline = ROOT / 'tests/fixtures/selftest' / (name + '.json')
    old_text = baseline.read_text(encoding='utf-8')
    before = json.loads(old_text)
    target = OUT / (name + '_source_selftest')
    assert not target.exists(), '이미 실행한 결과를 덮어쓰지 않는다'
    run = subprocess.run([sys.executable, 'gui.py', '--selftest', str(ROOT / image), str(target)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    (OUT / (name + '_source_selftest.log')).write_bytes(run.stdout)
    assert run.returncode == 0, (name, run.returncode, run.stdout[-1200:])
    actual_file, = target.glob('*_라벨.json')
    after_text = actual_file.read_text(encoding='utf-8')
    after = json.loads(after_text)
    digest = hashlib.sha256((ROOT / image).read_bytes()).hexdigest()
    assert digest == before['source']['sha256'] == after['source']['sha256']
    record = dict(case=name, input_sha256=digest,
                  baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                  actual_sha256=hashlib.sha256(actual_file.read_bytes()).hexdigest(),
                  json_bytes_equal=old_text == after_text,
                  before=before, after=after,
                  document_changes={k:dict(before=before.get(k), after=after.get(k))
                                    for k in before.keys() | after.keys()
                                    if k != 'labels' and before.get(k) != after.get(k)},
                  label_count_before=len(before['labels']), label_count_after=len(after['labels']))
    assert len(before['labels']) == len(after['labels'])
    changes = []
    for old, new in zip(before['labels'], after['labels']):
        assert all(old.get(k) == new.get(k) for k in ('id','staff','x','y','pitch')), (name,old,new)
        changed = {k:dict(before=old.get(k),after=new.get(k)) for k in old.keys() | new.keys()
                   if old.get(k) != new.get(k)}
        if changed:
            changes.append(dict(staff=new['staff'], x=new['x'], y=new['y'], pitch=new['pitch'],
                                changes=changed, before=old, after=new))
    record['changed_labels'] = changes
    record['changed_fields'] = dict(collections.Counter(k for r in changes for k in r['changes']))
    if name == 'chopin_Db_p1':
        refpath = Path('C:/Users/user/Desktop/akbo_kca/debug/sim_lp/dblconn/db1.json')
        raw = refpath.read_bytes()
        ref = json.loads(raw)
        record['cli_reference_sha256'] = hashlib.sha256(raw).hexdigest()
        record['cli_reference_labels_multiset_equal'] = (collections.Counter(map(enc,ref['labels'])) ==
                                                        collections.Counter(map(enc,after['labels'])))
    rows.append(record)
    (OUT / 'selftest-baseline-diff.json').write_text(json.dumps(dict(commit=PIN, cases=rows),
                                                               ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(enc({k:v for k,v in record.items() if k not in ('before','after','changed_labels','document_changes')}),flush=True)
    print('문서 변경:',enc(record['document_changes']),flush=True)
assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
raise SystemExit(0 if all(r['json_bytes_equal'] for r in rows) else 1)
