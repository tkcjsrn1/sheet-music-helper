"""신고 ZIP들을 기존 재현기로 처리하고 접수 요약표를 만든다."""
import argparse
import html
import json
from pathlib import Path
import subprocess
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.replay_report import replay


def cell(value):
    return html.escape(str(value if value is not None else '미기록')).replace('|','\\|').replace('\n',' ').replace('\r',' ')


def summary_cells(summary):
    if summary is None:return ['미확인']*8
    sp=summary.get('sp');key=summary.get('key_signature')
    mode={True:'사진 모드 ON',False:'사진 모드 OFF',None:'사진 모드 미기록'}[summary.get('photo_mode')]
    dimensions=(f"{summary['width']}×{summary['height']}" if summary.get('width') and summary.get('height') else None)
    return [summary['input_type']+' / '+mode,dimensions,
            f"{sp['median']:.3f} ({sp['min']:.3f}~{sp['max']:.3f})" if sp else None,
            f"{key['symbol'] or '없음'} {key['count']}" if key else None,
            summary.get('staves'),summary['labels'],summary['check'],
            f"{summary['edited_labels']} / {summary.get('edit_actions') if summary.get('edit_actions') is not None else '미기록'}"]


def summarize_reports(incoming: Path, output: Path):
    if incoming.is_file() and incoming.suffix.lower()=='.zip':archives=[incoming]
    elif incoming.is_dir():
        archives=sorted((p for p in incoming.iterdir() if p.is_file() and p.suffix.lower()=='.zip'),key=lambda p:p.name)
    else:archives=[]
    if not archives:raise ValueError('신고 ZIP 파일이나 ZIP이 있는 폴더를 지정해 주세요.')
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for number,archive in enumerate(archives,1):
        folder=output/f'{number:03}'
        row=dict(archive=archive.name,output=folder.name,status='success',reported=None,current=None,
                 reported_commit=None,current_commit=None,difference_rows=None,error=None)
        try:
            result=replay(archive,folder)
            row.update(reported=result['reported_summary'],current=result['current_summary'],
                       reported_commit=result['reported_commit'],current_commit=result['current_commit'],
                       difference_rows=len(result['differences']))
        except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
            row.update(status='failed',error=str(exc))
            saved=folder/'reported_summary.json'
            if saved.is_file():
                data=json.loads(saved.read_text(encoding='utf-8'))
                row.update(reported=data['summary'],reported_commit=data['reported_commit'])
        rows.append(row)
        print(f"{archive.name}: {row['status']}")
    (output/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 베타 신고 접수 요약','',
           '정답 판정/오류율이 아닙니다. sp는 저장된 보표 간격(px)의 중앙값(최소~최대)입니다. 미기록·실패를 0으로 세지 않습니다.',
           'check는 사용자 확인 이후 화면 표시 기준, 사용자 수정은 남아 있는 수정 라벨 수 / 삭제 포함 수정 동작 수입니다.',
           '신고 당시 사용자 수정·영역 선택은 현재 자동 인식과 의도적인 차이를 만듭니다. 자세한 대조는 각 폴더의 report_diff.md를 봅니다.','',
           '|신고|상태|시점|빌드|입력 종류|가로×세로 px|sp|읽은 조표|보표|라벨|check|사용자 수정|차이 행|오류|',
           '|---|---|---|---|---|---|---|---|---:|---:|---:|---|---:|---|']
    for row in rows:
        for phase,caption in (('reported','신고 당시'),('current','현재')):
            values=[row['archive'],row['status'],caption,row[phase+'_commit'],*summary_cells(row[phase]),row['difference_rows'],row['error'] or '']
            lines.append('| '+' | '.join(cell(v) for v in values)+' |')
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('incoming',type=Path,help='신고 ZIP 하나 또는 ZIP 폴더(하위 폴더 제외)')
    p.add_argument('output',type=Path,help='아직 없는 새 결과 폴더')
    args=p.parse_args()
    try:
        rows=summarize_reports(args.incoming,args.output)
        print(f"요약: {args.output/'summary.md'}")
        return int(any(r['status']=='failed' for r in rows))
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
        print(f'접수 실패: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
