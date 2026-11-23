"""두 베타의 저장 JSON에서 변화 수만 센다. 옳고 그름은 판정하지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.replay_report import compare_documents

CASES = ('aoharu_p1', 'aoharu_p2', 'aoharu_p3', 'chopin_Db_p1', 'bach_p1', 'clara_p1')


def count_changes(old, new):
    """정확한 보표·좌표로 대응한다. 중복 좌표의 애매한 대응은 수로 뭉개지 않는다."""
    fields = ('sha256', 'page', 'width', 'height', 'dpi')
    if not old['source'].get('sha256') or any(old['source'][f] != new['source'][f] for f in fields):
        raise ValueError('같은 입력·쪽·해상도의 JSON만 비교할 수 있습니다.')
    if old['music']['notation'] != new['music']['notation']:
        raise ValueError('표기 설정이 다른 JSON은 비교할 수 없습니다.')
    counts = dict(added=0, removed=0, text_changed=0, confidence_changed=0)
    rows = compare_documents(old, new)
    for row in rows:
        if row['kind'] != 'label':
            continue
        before, after = list(row['before']), list(row['after'])
        signature = lambda label: tuple(label[f] for f in ('pitch', 'text', 'confidence'))
        # ID/사유만 변한 것, 중복 좌표의 목록 순서가 변한 것은 네 집계에 넣지 않는다.
        for label in before[:]:
            j = next((i for i, candidate in enumerate(after) if signature(label) == signature(candidate)), None)
            if j is not None:
                before.remove(label)
                after.pop(j)
        if before and after:
            if len(before) != 1 or len(after) != 1:
                raise ValueError(f"중복 좌표 {row['key']}의 대응이 모호합니다. 수동 대조가 필요합니다.")
            counts['text_changed'] += before[0]['text'] != after[0]['text']
            counts['confidence_changed'] += before[0]['confidence'] != after[0]['confidence']
        else:
            counts['added'] += len(after)
            counts['removed'] += len(before)
    assert len(new['labels']) - len(old['labels']) == counts['added'] - counts['removed']
    return counts, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old', type=Path, help='6쪽의 <case>.json을 모은 이전 exe 결과 폴더')
    parser.add_argument('new', type=Path, help='같은 입력·설정의 새 exe 결과 폴더')
    parser.add_argument('output', type=Path)
    parser.add_argument('--old-commit', required=True)
    parser.add_argument('--new-commit', required=True)
    args = parser.parse_args()
    results = []
    for case in CASES:
        paths = [folder / (case + '.json') for folder in (args.old, args.new)]
        docs = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
        counts, rows = count_changes(*docs)
        results.append(dict(case=case, old_labels=len(docs[0]['labels']), new_labels=len(docs[1]['labels']),
                            input_sha256=docs[0]['source']['sha256'], json_sha256=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
                            counts=counts, differences=rows))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'BETA_CHANGES.json').write_text(json.dumps(dict(old_commit=args.old_commit, new_commit=args.new_commit, cases=results), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 베타 간 변화 수', '',
             f'기준: `{args.old_commit}` → `{args.new_commit}`. 두 exe의 동일 입력·쪽·해상도·표기 설정 JSON을 비교했다.', '',
             '보표 번호·x·y가 정확히 같은 라벨을 대응한다. 좌표가 이동한 라벨은 삭제+추가로 센다. 표기/확신도 변화는 같은 라벨에서 각각 세므로 중복 집계될 수 있다. ID/사유만 변한 것은 네 집계에 포함하지 않는다. 조표·음자리표 등 문맥과 전체 전후행은 JSON에 보존한다. **이 수치는 정답·오류·복구 수가 아니다.**', '',
             '| 입력 | 이전 라벨 | 새 라벨 | 추가 | 삭제 | 표기 변화 | 확신도 변화 |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        c = r['counts']
        lines.append(f"| {r['case']} | {r['old_labels']} | {r['new_labels']} | {c['added']} | {c['removed']} | {c['text_changed']} | {c['confidence_changed']} |")
    (args.output / 'BETA_CHANGES.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
