"""신고 ZIP의 원본·설정으로 현재 소스를 실행하고 JSON 차이를 남긴다."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from statistics import median
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def unpack_report(archive: Path, output: Path):
    """알려진 네 파일만 읽는다. 압축 속 경로·코드·추가 파일은 실행/추출하지 않는다."""
    try:
        with zipfile.ZipFile(archive) as z:
            entries=z.infolist()
            names=[e.filename for e in entries]
            originals=[n for n in names if re.fullmatch(r'original\.(png|jpg|jpeg|bmp|tif|tiff|pdf)',n)]
            expected={'result.png','labels.json','report.json'}
            if (len(entries)!=4 or len(set(names))!=4 or len(originals)!=1
                    or set(names)!=expected|set(originals)
                    or any(e.file_size>128*1024*1024 or e.flag_bits&1 for e in entries)
                    or sum(e.file_size for e in entries)>256*1024*1024):
                raise ValueError('지원하는 신고 ZIP은 원본·결과 PNG·labels.json·report.json 네 파일입니다. 경로/중복/암호/크기도 확인해 주세요.')
            old=json.loads(z.read('labels.json'))
            info=json.loads(z.read('report.json'))
            if not isinstance(old,dict) or not isinstance(info,dict) or not isinstance(old.get('labels'),list):
                raise ValueError('신고 JSON 구조를 확인해 주세요.')
            data=z.read(originals[0])
            source=old.get('source') or {}
            if not isinstance(source,dict) or source.get('sha256')!=hashlib.sha256(data).hexdigest():
                raise ValueError('신고 원본의 SHA-256이 라벨 JSON과 다릅니다.')
    except (NotImplementedError, zlib.error) as exc:
        raise ValueError(f'신고 ZIP 압축 형식이 지원되지 않거나 내용이 손상됐습니다: {exc}') from exc
    output.mkdir(parents=True,exist_ok=False)
    original=output/originals[0]
    original.write_bytes(data)
    return original,old,info


def conversion_arguments(source: Path, output: Path, old: dict, info: dict):
    from gui import CLEF_LABELS, NOTATION_LABELS
    settings=info.get('settings',{})
    if not isinstance(settings,dict):
        raise ValueError('신고 설정이 객체가 아닙니다.')
    clef=settings.get('clef','자동 인식 (추천)')
    notation=settings.get('notation','계이름 (고정도)')
    clef=CLEF_LABELS.get(clef,clef)
    notation=NOTATION_LABELS.get(notation,notation)
    if clef not in ('auto','treble','bass') or notation not in ('solfege','solfege-fixed','solfege-movable','letter'):
        raise ValueError('알 수 없는 음자리표/표기 설정입니다. 추측해서 실행하지 않습니다.')
    page=old.get('source',{}).get('page',0)
    size=settings.get('font_size',18)
    color=settings.get('text_color','#dc1414')
    key=settings.get('key','')
    if type(page) is not int or page<0 or type(size) is not int or size<=0 or not isinstance(key,str) or not isinstance(color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',color):
        raise ValueError('쪽 번호/글자 크기/색상/조성 설정을 확인해 주세요.')
    args=[sys.executable,str(ROOT/'main.py'),str(source),'--page',str(page),
          '--output-dir',str(output),'--no-debug','--clef',clef,'--notation',notation,
          '--font-size',str(size),'--color',color]
    if key:args+=['--key',key]
    for name in ('photo','minor'):
        value=settings.get(name,False)
        if type(value) is not bool:raise ValueError(f'{name} 설정은 참/거짓이어야 합니다.')
        if value:args+=['--'+name]
    return args


def compare_documents(old: dict, current: dict):
    """좌표 중복은 목록째 비교한다. 가까운 라벨/개수만으로 같다고 판정하지 않는다."""
    rows=[]
    for field in ('source','music','staves','user_edits'):
        before=old.get(field);after=current.get(field)
        if field=='source':
            before={k:v for k,v in (before or {}).items() if k!='file'}
            after={k:v for k,v in (after or {}).items() if k!='file'}
        if before!=after:rows.append(dict(kind=field,key=field,before=before,after=after))
    groups=[]
    for doc in (old,current):
        grouped=defaultdict(list)
        for label in doc['labels']:
            grouped[(label['staff'],label['x'],label['y'])].append(label)
        groups.append(grouped)
    for key in sorted(groups[0].keys()|groups[1].keys()):
        before=groups[0].get(key,[]);after=groups[1].get(key,[])
        if before!=after:
            rows.append(dict(kind='label',key=list(key),before=before,after=after))
    return rows


def summarize_document(doc: dict, input_type: str):
    """저장된 값만 센다. 확신도는 사용자 확인 이후의 실제 표시 기준이다."""
    from modules.label_edits import display_confidences
    labels=doc.get('labels')
    source=doc.get('source',{})
    music=doc.get('music',{})
    staves=doc.get('staves')
    if (not isinstance(labels,list) or any(not isinstance(n,dict) for n in labels)
            or not isinstance(source,dict) or not isinstance(music,dict)
            or (staves is not None and (not isinstance(staves,list)
                or any(not isinstance(s,dict) for s in staves)))):
        raise ValueError('요약할 라벨/원본/조표/보표 구조를 확인해 주세요.')
    for key in ('width','height','dpi'):
        value=source.get(key)
        if value is not None and (type(value) is not int or value<=0):
            raise ValueError(f'원본 {key} 값이 올바르지 않습니다.')
    spacings=[s.get('spacing') for s in staves or []]
    if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<=0) for v in spacings):
        raise ValueError('오선 간격은 양의 유한한 수여야 합니다.')
    spacing=(dict(values=spacings,median=median(spacings),min=min(spacings),max=max(spacings))
             if spacings and all(v is not None for v in spacings) else None)
    if any('edited' in n and type(n['edited']) is not bool for n in labels):
        raise ValueError('사용자 수정 표시는 참/거짓이어야 합니다.')
    edited=sum(n.get('edited') is True for n in labels)
    record=doc.get('user_edits')
    if record is not None and (not isinstance(record,dict)
            or not isinstance(record.get('changes'),list)
            or any(not isinstance(c,dict) for c in record['changes'])):
        raise ValueError('사용자 수정 기록을 확인해 주세요.')
    symbol=music.get('key_symbol');count=music.get('key_count')
    if ((symbol is not None and not isinstance(symbol,str))
            or (count is not None and (type(count) is not int or count<0))):
        raise ValueError('저장된 조표 값이 올바르지 않습니다.')
    return dict(input_type=input_type,width=source.get('width'),height=source.get('height'),
                declared_dpi=source.get('dpi'),sp=spacing,
                key_signature=dict(symbol=symbol,count=count) if symbol is not None and count is not None else None,
                staves=len(staves) if staves is not None else None,labels=len(labels),
                check=display_confidences(doc).count('check'),
                raw_check=sum(n.get('confidence')=='check' for n in labels),
                edited_labels=edited,edit_actions=len(record['changes']) if record is not None else (None if edited else 0))


def replay(archive: Path, output: Path):
    source,old,info=unpack_report(archive,output)
    summary=summarize_document(old,source.suffix[1:].upper())
    settings=info.get('settings',{})
    photo=settings.get('photo',False) if isinstance(settings,dict) else None
    summary['photo_mode']=photo if type(photo) is bool else None
    (output/'reported_summary.json').write_text(json.dumps(dict(reported_commit=info.get('build_commit'),summary=summary),ensure_ascii=False,indent=2),encoding='utf-8')
    args=conversion_arguments(source,output/'current',old,info)
    done=subprocess.run(args,cwd=ROOT,capture_output=True,encoding='utf-8',
                        errors='replace',timeout=240)
    (output/'recognition.log').write_text(done.stdout+'\n'+done.stderr,encoding='utf-8')
    if done.returncode:raise ValueError(f'현재 소스 변환 실패(종료{done.returncode}). recognition.log를 확인해 주세요.')
    current=json.loads((output/'current'/f'{source.stem}_라벨.json').read_text(encoding='utf-8'))
    rows=compare_documents(old,current)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    result=dict(reported_commit=info.get('build_commit'),current_commit=commit,
                old_labels=len(old['labels']),current_labels=len(current['labels']),differences=rows,
                reported_summary=summary,current_summary=summarize_document(current,source.suffix[1:].upper()))
    result['current_summary']['photo_mode']=photo
    (output/'report_diff.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 신고 당시 ↔ 현재 소스','',
           f"신고 {result['reported_commit']} / 현재 {commit}",
           f"라벨 {len(old['labels'])} → {len(current['labels'])}, 차이 행 {len(rows)}",'',
           '정답 판정이 아닙니다. 조표·음자리표·전체 라벨 필드를 비교합니다. 사용자 수정/영역 필터가 있는 신고는 그 의도적 차이도 포함합니다.',
           '신고에 개인 글꼴 경로·범례 설정이 없어 PNG의 동일성을 보장하지 않습니다. 이 도구는 JSON 인식 결과를 비교합니다.','',
           '|종류|보표·x·y / 항목|신고 당시|현재|','|---|---|---|---|']
    for row in rows:
        cells=[json.dumps(row[k],ensure_ascii=False).replace('|','\\|').replace('\n',' ') for k in ('kind','key','before','after')]
        lines.append('| '+' | '.join(cells)+' |')
    (output/'report_diff.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='문제 신고 ZIP을 현재 소스로 다시 인식하고 JSON 차이를 표로 저장합니다.')
    p.add_argument('archive',type=Path)
    p.add_argument('output',type=Path,help='아직 없는 새 출력 폴더')
    args=p.parse_args()
    try:
        result=replay(args.archive,args.output)
        print(f"완료: {args.output/'report_diff.md'} (차이 {len(result['differences'])}행)")
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
        print(f'재현 실패: {exc}',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())

