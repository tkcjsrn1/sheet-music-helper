# 내부 검증 베타 72ca500 — 2026-10-16

기준 `72ca500692f162e61046d9a9bd79fc5dfecd15c6`. CLI #377 오선 밖 글자 줄·#381 빔 위 채워진 머리 확인 표시, #383 확인된 조바꿈 구간 표기, Codex #385 확인 필요 이유 GUI를 포함한다. #167·정식 겹임시표·조바꿈 재생 보완은 미포함. 친구 배포는 보류한다.

[경로·크기·SHA256](artifacts.json) · [빌드 메타](build-info.json) · [자원 확인](build-preflight.json). 깨끗한 main에서 공식 빌드 한 번, 정확히 같은 커밋 Actions 한 번. 공유 C:/stash/기존 빌드 보존, 산출물/임시는 F:다.

| 검사 | 결과·근거 |
|---|---|
| 전체 검사·골든711·현재 PDF17 | 실패0·건너뜀0. #385 병합 전 전체/기본 PNG·JSON6파일 바이트0는 [GUI 원자료](../../review/reasons_20261016/). 공식 빌드 후 [전체 로그](tests.log.gz) |
| strict12 | 추가0·삭제0·좌표/저장pitch/문맥0. 승인 #377/381 확신도 4행·신호 5행, #383 6쪽 표기 123행만. [요약](strict-summary.json)·[전후 전체행](strict-result.json.gz)·[승인 CLI 원자료](cli-accepted-references.json.gz)·[방법](strict-method.py.gz). 변화 수를 정확도/복구 수로 해석하지 않음 |
| selftest 기준 | Aoharu1·D♭1 기존 기준 JSON 전체 문자열 그대로. 기준 파일 갱신0 |
| 실제 exe12입력 | [검증](verification.json)·[로그](verification.log.gz), 소스/EXE JSON/PNG/EXE 재렌더 일치. 여섯 조바꿈 쪽 전부 포함 |
| 확신도·사용자 수정 | 주황 check/옅은 caution 픽셀, D3 수정한 check는 진하게·원래 confidence 보존·소스 수정 픽셀 일치 |
| 첫 실행·패키지 | Python 없는 PATH·settings 없음·exe 옆 output·ZIP5개·다른 원본에 labels 재사용 거부 통과 |
| 소스 밖 cwd | [3입력](clean-cwd.json)·[로그](clean-cwd.log.gz), PYTHONPATH 비움·JSON/PNG 동일 |
| Defender | EXE/ZIP ScanType3 종료0·대상탐지0. [EXE](defender-exe.json)·[ZIP](defender-zip.json)의 실제 엔진/정의 버전. 보안 설정 변경0 |
| 원격 Windows | [Actions 38895206582](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38895206582) 녹색. 빌드/전체검사/Python 없는 PATH 두 selftest·기준 JSON 일치. [원자료](actions-final.json)·[로그](actions-final.log.gz) |
| 실제 입력 | [HUMAN_CHECK](HUMAN_CHECK.md): 변환/다음 쪽/한글 N·P/영문 NumLock OFF F1 새 창/이유 GUI. 사본0·입력 상태 복원 |

실제 exe 결과 [Aoharu1](aoharu_p1.png) · [D♭1](chopin_Db_p1.png) · [바흐1](bach_p1.png) · [Clara1](clef_change_clara1.png). Beethoven 첫 실제 F4 두 곳, 슈베르트 (606,1522)=E4 유지도 검증했다.

[4fc3343 대비6쪽](vs-4fc3343/BETA_CHANGES.md) · [#312 대비6쪽](vs-312/BETA_CHANGES.md). 변경 행 원문을 보존하며 추가/삭제는 동일 좌표 기준이다. [안내문](먼저%20읽어주세요.txt)은 ZIP 그대로, [친구 초안](FRIEND_MESSAGE.md)은 발송 보류. 이번 후보의 [남은 한계](KNOWN_LIMITATIONS.md), 실제 청취/다운로드 SmartScreen/다른 PC 미확인을 확인한다.
