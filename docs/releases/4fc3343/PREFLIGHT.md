# 최종 내부 검증 베타 4fc3343 — 2026-10-15

빌드 기준 `4fc33430b8cd17009390fafc18f6cacd00db2293`. #366 C1 내림표, #368 단축키 제품 수정, #373 원격 검사 포커스 경합/오류 원문 보존, CLI #374 §1-40 겹임시표 확인 필요 표시를 포함한다. #167과 CLI #377 미승인 후보는 제외했다. 친구 배포 보류는 유지한다.

[exe·ZIP 경로/크기/전체 SHA256](artifacts.json), [빌드 메타데이터](build-info.json), [공식 빌드 로그](build.log.gz), [빌드 후 전체검사](tests.log.gz), [시작 자원 확인](build-preflight.json). 깨끗한 main에서 공식 빌드는 한 번만 했다. 공유 C:·stash·기존 빌드는 보존했다. 이후 main 5eaffdb까지의 차이는 WORKLOG뿐이라 이 파일을 그 커밋으로 빌드했다고 쓰지 않는다.

| 점검 | 결과·근거 |
|---|---|
| 전체 검사·골든711·현재 PDF17 | 실패0·건너뜀0, 빌드 전 #373 검사와 공식 빌드 후 검사 완료. [전체 로그](tests.log.gz). 골든/인식/판정/규약 수정0 |
| 승인 범위 strict8·기준 JSON | [C1 전후](../pending-366-368/)와 [#374 전후](../pending-373-374/) 보존. 후자는 라벨 수/순서/좌표/음고/표기/문맥0, D♭ double_acc certain→check7곳만. 실제 selftest 기준은 CLI 원문과 일치 |
| 소스/exe8입력 | [JSON·PNG·재렌더 대조](verification.json), [로그](verification.log.gz) 모두 동일. Aoharu p1/Db p1은 selftest 기준과도 동일 |
| 확신도·D3 | 주황 check/옅은 caution 픽셀 확인. 사용자가 고친 check는 진하게 표시, 원래 확신도 보존, 소스/실제exe 수정 결과 픽셀 동일 |
| 첫 실행·패키지 | settings 없는 CLI, Python 없는 PATH, exe 옆 output, ZIP5개, 다른 원본의 labels 재사용 거부 통과 |
| 소스 밖 깨끗한 cwd | [3입력 JSON/PNG](clean-cwd.json), [로그](clean-cwd.log.gz) 동일. PYTHONPATH 비움 |
| Defender | [exe](defender-exe.json)·[ZIP](defender-zip.json) ScanType3 종료0·대상탐지0. 제품4.18.26090.9·엔진1.1.26090.9·정의1.461.28.0. 보안 설정/예외 변경0 |
| 원격 전체·exe | #373 병합 전 [38708427893](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38708427893) 녹색. 최종 정확한 빌드 커밋 [38710415064](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38710415064) 녹색: exe 빌드 및 Python 없는 PATH 두 selftest/JSON 일치. [원자료](actions-final.json)·[원로그](actions-final.log.gz) |
| 실제 입력·정리 | [HUMAN_CHECK](HUMAN_CHECK.md): 다음 쪽, 한글 N/P, 영문·NumLock OFF F1 새 창 생성 통과. IME·NumLock 복원·검사 사본0 |

비교는 두 exe의 저장 JSON을 사용했다. [a9646b4→최종 6쪽](vs-a9646b4/BETA_CHANGES.md), [#312/1ad8323→최종 6쪽](vs-312/BETA_CHANGES.md). 좌표 이동은 추가+삭제로 세며, 수치를 정답/오류/복구로 해석하지 않는다. 전체 전후 행도 각 JSON에 남겼다.

실제 exe 결과: [Aoharu1](aoharu_p1.png), [D♭1](chopin_Db_p1.png), [바흐1](bach_p1.png), [Clara 음자리표 변경 쪽](clef_change_clara1.png). Beethoven 첫 실제 F4 두 곳과 슈베르트 (606,1522)=E4가 exe JSON에 남아 있음을 검증했다. D♭ double_acc 7곳과 C1 check 표시도 보존된다.

동봉 [안내문](먼저%20읽어주세요.txt)은 실제 ZIP에서 그대로 추출했다. [친구 메시지](FRIEND_MESSAGE.md)는 배포 보류 초안이다. de4b88e는 동일커밋 원격 실패 이력을 보존한 중간 후보이며 이 후보로 대체한다. 미확인: 스피커 사람 청취, 이번 exe 새 루프백 녹음, 실제 다운로드 SmartScreen, Python 없는 별도 PC. 겹임시표는 check 표시만 하며 정식 표기/음고 재생을 지원한다고 쓰지 않는다.
