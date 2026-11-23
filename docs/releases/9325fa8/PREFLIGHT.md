# 9325fa8 베타 점검 — 2026-10-05

빌드 기준: `9325fa885ece138a5e6c4e995a761162c33557d7`(main, dirty=false). 사용자 결정에 따라 #217 재적용 #233을 Codex가 병합했다. 병합 시 main에 있던 #234 음자리표 글리프 확인 필요 표시도 포함한다. D-3 라벨 수정·삭제·추가·되돌리기 포함, #167 제외. 인식·판정 파일과 정답 골든을 Codex가 직접 고치지 않았다.

## 통합·기준

- #233에서 담당 테스트를 D♭254→255·좌표/음고 검사로 정리하고 selftest 기준 JSON을 갱신했다. [전후 전체행·해시](../../measurements/beta217_adopted_selftest_diff.json) 보존, Aoharu 기준 갱신 없음. 환경 비교 기준이며 정답 골든 변경이 아니다.
- D♭ (2332,2838) B4/시b check 중복1개는 사용자 허용 항목이며 정답 복구로 세지 않는다. 슈베르트 Leipzig1쪽 (606,1522) E4/미는 소스와 실제 새 exe에 모두 남는다([exe 로그](schubert_restored_exe.log)).
- #233 브랜치35/35 뒤 merge commit `3214bd5c20ef9413dbb1afabafab49326b03c661`의 main에서도 전체35/35·실패0·건너뜀0([병합 뒤 검사](post_merge_main_tests.log)). 이후 최신9325fa8은 측정 도구/문서8파일만 추가했고 제품·테스트·의존성 차이는0이다.
- 실제9325fa8 공식 build.py에서도 전체35/35·실패0·건너뜀0([검사](tests.log), [빌드](build.log)). 골든711 무변경. PDF17쪽은 CLI 재적용 기준 스냅샷에 일치한다. CLI 기록상 재적용 전후4쪽 출력이 변하므로 이전 베타와 PDF 전체 불변으로 쓰지 않는다. PyMuPDF/fitz 제외·라이선스 검사 통과([빌드 정보](build-info.json)).

## 실제 exe 검증

동일 입력·기본 설정에서 아래8입력의 JSON 전체와 PNG 디코딩 픽셀이 소스/exe 간 일치했다. exe JSON 재렌더링 픽셀도 일치. 해당 등급이 있는 출력의 check 주황 점선·caution 연한 글씨 색 픽셀을 확인했다. [결과](verification.json), [로그](verification.log), [실행한 스크립트](verify_cli.py). 스크립트는 저장소 루트에서 실행하며 첫 실행 검사용 출력 폴더가 비어 있어야 한다.

| 입력 | 라벨 | 확실 | 주의 | 확인 필요 |
|---|---:|---:|---:|---:|
| aoharu_p1 | 226 | 225 | 1 | 0 |
| aoharu_p2 | 327 | 296 | 28 | 3 |
| aoharu_p3 | 158 | 147 | 10 | 1 |
| chopin_Db_p1 | 255 | 206 | 35 | 14 |
| bach_p1 | 184 | 171 | 1 | 12 |
| clef_change_clara1 | 587 | 350 | 65 | 172 |
| alto_beethoven1 | 239 | 151 | 7 | 81 |
| schubert_restored | 476 | 294 | 158 | 24 |

- Clara clef_changed144개·Beethoven clef_alto53개 전부check. 실제 exe와 JSON 재렌더링의 알토 경고 확인([로그](alto_beethoven1_exe.log)).
- 사용자 수정 check는 certain과 같은 진한 글씨이며 점선이 사라진다. 실제 exe 그림과 소스/강제certain 그림 픽셀 일치, JSON 원래 값·확신도·edited 보존([부분 결과](label_edited_check_detail.png)). GUI 클릭 검사는 아니다.
- 새 폴더 settings.json 없는 CLI 첫 실행, Python 없는 PATH, exe 옆 기본output 생성, ZIP5파일 확인. 다른 입력의 JSON은 종료1·Traceback 없음·PNG 없음으로 거부([로그](wrong_input.log)).
- [Windows Actions37225851404](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37225851404): 같은9325fa8으로1회 수동 실행, Windows exe 빌드35/35 및 Python 없는 PATH의 두 selftest·새 D♭255 기준 JSON 전체 비교 성공([결과](actions.json), [로그](actions.log)). 실제 Python 미설치 사용자 PC 확인으로 확대하지 않는다.

## Defender

exe·ZIP 각각 MpCmdRun.exe `-Scan -ScanType 3 -File <Resolve-Path로 확인한 대상>` 검사. 둘 다 종료0·위협 없음·이번 파일 탐지 기록 없음. 엔진1.1.26080.3, 정의1.459.551.0, 제품4.18.26080.4, 백신·실시간 보호 활성. 보안 설정/제외 변경 없음. [exe 결과](defender_exe.json)·[로그](defender_exe.log)·[상태](defender_status.json), [ZIP 결과](defender_zip.json)·[로그](defender_zip.log)·[상태](defender_zip_status.json).

## 변화표·안내·결과

[cebae18→새 베타6쪽 변화 수](BETA_CHANGES.md), [전후행·문맥·해시](BETA_CHANGES.json), [이전 실제 exe 기준 출처](OLD_BASELINE.json)를 보존했다. 좌표 이동=삭제+추가이며 이 수치는 정답/오류/복구 수가 아니다.
pending-217 친구 메시지·비교 기준을 이 폴더로 옮겼다. [동봉 안내문](먼저%20읽어주세요.txt)은 ZIP과 바이트 해시가 같고 실제 포함된 #217 오삭제1건 수정·#234 기호 모양 확인 필요 안내를 반영했다. [친구 메시지](FRIEND_MESSAGE.md)의 SmartScreen 문장은 창이 뜰 때의 조건부 안내이다.
새 exe 결과 PNG: [Aoharu1](aoharu_p1.png), [D♭1](chopin_Db_p1.png), [바흐1](bach_p1.png). 입력 원본·exe·ZIP은 커밋하지 않았다. 다른 결과 PNG/JSON 로컬 경로는 verification.json에 있다.

## 산출물

- exe: `F:\sheet-music-helper-codex-night-20261004\dist\9325fa885ece-20261005-034822-857327\악보헬퍼.exe`
- exe 118,658,585바이트 / SHA-256 `0BF07478A6C1C56C942894461E00082FB45957F16B2B4DF9A8E60A46780FC830`
- zip: `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-9325fa885ece-20261005-034822-857327.zip`
- zip 124,726,137바이트 / SHA-256 `68CA60E031017E16B5D98F49CB345849C1C11A667F7646D5C613AC52BFA86890`

## 남긴 것

빌드 검증 당시 Codex의 새 exe 직접 클릭은 사용자 지시에 따라 미시도였다. 2026-10-05 사용자 전달로 [사람PC exe 직접 확인 완료](HUMAN_GUI_CHECK.md)를 기록했다(베토벤 Bravura1쪽 변환·알토 경고·비올라check·휠·추가안내·듣기시작/중지). 스피커 청취·실제 다운로드 SmartScreen은 미확인 유지. 과거5d2521d/cebae18 직접 확인을 새 exe 확인으로 바꾸어 쓰지 않는다. #167 제외 유지. #45는 사용자 승인 및 CLI HIRES_DOWNSCALE.md 재측정 근거 코멘트 후 CLOSED, A-15·A-16 CLI 과제로 유지. 예전 빌드·stash·공유C:체크아웃 보존.

기록 PR 통합 때 origin/main0a94d92는 WORKLOG/DECISIONS 문서만 추가(제품·테스트diff0)였다. 양쪽 WORKLOG를 보존해 통합했으며 실제 빌드 기준은9325fa8로 유지한다.
