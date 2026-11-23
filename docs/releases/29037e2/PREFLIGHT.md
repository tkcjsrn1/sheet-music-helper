# 29037e2 링 벽 B안 포함 베타 점검 — 2026-10-05

> 후속 사용자 제보(2026-10-05): 베토벤 Bravura 첫 시스템의 조표·3/4 박자표 유령16개가 남아 있음을 현재 소스에서 재현했습니다. **이 인식 결함은 미수정**입니다. 아래 배포환경 일치 검사는 기호를 옳게 인식했다는 검사가 아닙니다. [재현·수정 요청](../../review/header_symbols/README.md).

빌드 기준 `29037e2fe60229682ccb6fa3f1e3e927a9a306cd` · codex/beta-ringwall-release · dirty=false. 사용자 승인 #263 병합29037e2 직후 최신main을 고정했다. #261 헤더 끝, #241 꾸밈음, 음자리표 문턱/검색시작, 흐린인쇄구제, #247 미검출안내, #249 수정본재열기, #250 쪽넘기기 포함. #167 옥타브GUI 제외. 링벽 예외는 사진모드에 적용하지 않는다. Codex 인식/판정/정답골든 편집0.

## 검증

- #263 브랜치37/37, 병합뒤main37/37, 공식build.py 원본spec 빌드후37/37. 모두 실패0·건너뜀0·정답골든711 통과. 현재 CLI가 갱신한 PDF17쪽 스냅샷 통과(이전베타와 스냅샷 무변경이라는 뜻은 아니다). [main검사](start-tests.log), [빌드검사](tests.log), [빌드정보](build-info.json), [빌드로그](build.log).
- D♭ 고정값255→260과 구제19→24, 중복(2332,2838) 제거는 [#263 전후행/근거](../../measurements/ring263_integration/README.md)에 보존했다. 순증가5·추가7/삭제2를 구분한다. CLI가 확인한 (1976,2824) 표기오류와 (2236,2824) 레b→레 표기악화1을 숨기지 않는다. 다른 인식조건으로 보정하지 않았다.
- Actions selftest D♭ 기준도255→260으로 갱신했으며 [전체변경행](SELFTEST_BASELINE_CHANGES.json)을 보존했다. Aoharu 기준파일 바이트 무변경. 환경 비교 기준과 정답골든711은 별개다.
- 빌드커밋/소스 고정, 라이선스고지 버전, fitz/PyMuPDF 제외 확인. 동일입력8개 소스/exe 전체JSON·PNG 디코딩 픽셀·exe JSON재렌더링 픽셀 일치. [검증원자료](verification.json), [로그](verification.log), [스크립트](verify_cli.py). 압축PNG 파일바이트 일치로 확대하지 않는다.
- 꾸밈음/음자리표변경/알토/미검출 신호 check와 경고로그 확인. [알토/미검출/조표 머리말 부분](alto_unknown_header_exe.png)을 실제 결과에서 확대 확인했고 세 줄의 겹침·글자 깨짐은 없었다. 슈베르트 Leipzig(606,1522) E4 라벨1개 실제exe 결과에 유지.
- 실제ZIP 새폴더·settings없는 CLI첫실행·Python없는PATH·exe옆output·ZIP5파일·JSON저장/재렌더 통과. 다른원본JSON은 종료1·Traceback/PNG없이 거부. D3 수정check는 원래음고/확신도/수정표시를 보존하고 진한글씨·점선제거, 소스 수정PNG 픽셀 일치([부분결과](label_edited_check_detail.png)).
- [Windows Actions 37308437029](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37308437029) 동일빌드커밋에서1회 수동실행 성공. exe빌드37/37·Python없는PATH 두selftest/전체JSON 기준일치([원자료](actions.json), [로그](actions.log)). 실제Python미설치 사람PC 또는 CI/로컬바이너리 동일성 주장으로 확대하지 않는다.

| 입력 | 보표 | 라벨 | 확실 / 주의 / 확인 필요 | 소스·exe·재렌더 |
|---|---:|---:|---|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 | 일치 |
| aoharu_p2 | 14 | 327 | 296 / 28 / 3 | 일치 |
| aoharu_p3 | 8 | 158 | 147 / 10 / 1 | 일치 |
| chopin_Db_p1 | 8 | 260 | 197 / 38 / 25 | 일치 |
| bach_p1 | 8 | 184 | 171 / 1 / 12 | 일치 |
| clef_change_clara1 | 12 | 599 | 355 / 67 / 177 | 일치 |
| alto_beethoven1 | 12 | 239 | 146 / 7 / 86 | 일치 |
| schubert_restored | 12 | 481 | 295 / 160 / 26 | 일치 |

## Defender

MpCmdRun.exe `-Scan -ScanType 3 -File <native경로>` 실제exe/ZIP 각각 종료0·대상탐지0. 제품 4.18.26080.4 · 엔진 1.1.26080.3 · 정의(exe) 1.459.557.0 / (ZIP) 1.459.557.0.
[exe결과](defender-exe.json)·[로그](defender-exe.log)·[상태](defender-exe-status.json), [ZIP결과](defender-zip.json)·[로그](defender-zip.log)·[상태](defender-zip-status.json), [스크립트](check_defender.ps1). 보안설정/제외변경0. 탐지0이 SmartScreen 화면확인을 대신하지 않는다.

## 변화 수·안내

[9325fa8 → 새베타6쪽 변화표](BETA_CHANGES.md), [전후행·문맥·해시](BETA_CHANGES.json), [이전실제exe 출처](OLD_BASELINE.json). 추가/삭제/표기/확신도 수만 세며 정답·오류·복구수로 해석하지 않는다. 좌표가 움직인 라벨은 삭제+추가다.

[동봉안내](먼저%20읽어주세요.txt)는 실제ZIP member SHA와 일치한다. 꾸밈음(사진모드제외)/쪽넘기기/수정본재열기 안내를 확인했다. [친구메시지](FRIEND_MESSAGE.md)의 SmartScreen 문구는 경고가 뜰 때의 조건부 안내다. [사람PC 5단계](PAGE_REOPEN_HUMAN_CHECK.md)는 확인절차이며 완료기록이 아니다. source_gui_3장은 #249 자체생성 이미지·소스Tk 검증자료를 재사용했고 새exe 클릭화면이 아니다.

## 산출물·남긴 것

- exe `F:\sheet-music-helper-codex-night-20261004\dist\29037e2fe602-20261005-211648-214621\악보헬퍼.exe` · 118,673,104바이트
- exe SHA-256 `92A7E48EAADF1A71DCBC1BB4D8360F65169875446D99DE32C1236BA226CDBD7B`
- ZIP `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-29037e2fe602-20261005-211648-214621.zip` · 124,754,371바이트
- ZIP SHA-256 `7B076AA9270A814F95F8D41B9F7EB9F6C018A6ECACC4B1F6B68095105CE52752`

최종후보는9325fa8과29037e2. 806130a는「헤더 끝·링 벽 미포함 중간 빌드」, 53d674b는「링 벽 미포함 중간 빌드」로 제외하되 기존산출물/기록은 보존한다.

빌드직전 여유메모리 3,574,668KiB/총 16,442,780KiB([기록](memory-before.json)). [디스크전](disk-before.json)·[후](disk-after.json). 임시/산출물F:, stash/기존빌드/공유C:보존. exe/ZIP·원본악보 미커밋.

**새exe 직접클릭·실제스피커청취·실제다운로드SmartScreen은 미확인**. 사용자의9325fa8 확인을 새빌드로 옮겨쓰지 않는다. [신고접수](../../BETA_FEEDBACK_INTAKE.md) 유지. 이번검증은 소스/배포환경 일치이며 모든악보 오삭제0·정답률 보장이 아니다.
