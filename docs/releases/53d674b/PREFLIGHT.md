# 53d674b 헤더 끝 포함 베타 점검 — 2026-10-05

> 배포 후보 정리(2026-10-05, #263 병합 후): **링 벽 미포함 중간 빌드**입니다. 최종 후보는 9325fa8과 [링 벽 포함29037e2](../29037e2/PREFLIGHT.md)입니다. 아래 당시 검증 기록과 기존 exe/ZIP은 보존합니다.

빌드 기준 `53d674bfe653ada3de3d2ac8258376401c0b4ec0` · codex/beta-header-release · dirty=false. 최신 main53d674b에서 #261 병합(`27ba80e`)과 CLI 「헤더 끝 병합됨 — 베타 재빌드 가능」 기록을 확인하고 고정했다. 806130a에 헤더 끝 수정이 더해진 제품이다. #247 음자리표 미검출 안내, #249 수정본 재열기, #250 쪽넘기기, #241 꾸밈음, #253 음자리표 문턱/겹침, #254 검색시작, #257 흐린인쇄구제 포함. #167 옥타브GUI와 #263 링벽 변경은 포함하지 않았다. Codex 인식/판정/정답골든 편집0.

## 검증

- 시작점37/37·공식build.py 원본spec 빌드후37/37, 실패0·건너뜀0. 정답골든711 일치. 현재 CLI가 승인 절차로 갱신한 PDF17쪽 스냅샷 일치. 이전베타와 PDF스냅샷이 전부 같다는 뜻은 아니다: #261은 D♭6쪽 라벨5줄을 수정하고 헤더 문맥을 갱신했다. Codex는 스냅샷을 편집하지 않았다.
- 빌드 중 커밋/소스고정, 라이선스고지 버전, fitz/PyMuPDF 제외 통과. [빌드정보](build-info.json), [빌드로그](build.log), [전체검사](tests.log).
- 동일입력8개 소스/exe 전체JSON·PNG 디코딩 픽셀·exe JSON재렌더 픽셀 모두일치. [검증원자료](verification.json), [로그](verification.log), [스크립트](verify_cli.py). PNG파일의 압축바이트 동일성으로 바꾸어 주장하지 않는다.
- D♭ grace_size 9개check, Clara clef_changed 144개check, Beethoven clef_alto 53/clef_unknown 21개check. 두 경고 로그·JSON재렌더링 확인. [알토/미검출/조표 머리말 부분](alto_unknown_header_exe.png). 실제 부분그림에서 세 줄이 겹치지 않고 글자가 깨지지 않음을 확인했다.
- 슈베르트 Leipzig (606,1522) E4 라벨1개 실제exe 결과 유지(#217).
- 실제exe D-3 사용자수정: 원래 pitch/confidence/edited 보존, 수정한check는 certain과 같은 진한 글씨·점선제거, 소스수정과 픽셀일치. [부분결과](label_edited_check_detail.png).
- 실제ZIP 새폴더, settings없는 CLI첫실행, Python없는PATH, exe옆output, PNG/JSON 저장, ZIP5파일 통과. 다른원본의 JSON은 종료1·Traceback/PNG없음으로 거부.
- [Windows Actions 37301205330](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37301205330) 같은53d674b에서1회 수동실행 성공: exe빌드37/37·Python없는PATH Aoharu/D♭ 두selftest·전체JSON기준 일치. [원자료](actions.json), [로그](actions.log). CI와 로컬exe 바이너리 동일성 또는 실제Python미설치 사람PC 확인으로 확대하지 않는다.
- Actions기준2개 모두 기존파일 바이트보존·전체JSON 내용동일. [사본생성 대조](SELFTEST_BASELINE_CHECK.json). 사본 파일의 줄바꿈 때문에 SHA가 다를 수 있으나 비교내용 무변경이며 기준파일을 갱신하지 않았다. selftest환경기준과 정답골든711은 별개다.

| 입력 | 보표 | 라벨 | 확실 / 주의 / 확인 필요 | 소스·exe·재렌더 |
|---|---:|---:|---|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 | 일치 |
| aoharu_p2 | 14 | 327 | 296 / 28 / 3 | 일치 |
| aoharu_p3 | 8 | 158 | 147 / 10 / 1 | 일치 |
| chopin_Db_p1 | 8 | 255 | 197 / 35 / 23 | 일치 |
| bach_p1 | 8 | 184 | 171 / 1 / 12 | 일치 |
| clef_change_clara1 | 12 | 587 | 350 / 65 / 172 | 일치 |
| alto_beethoven1 | 12 | 239 | 146 / 7 / 86 | 일치 |
| schubert_restored | 12 | 476 | 292 / 158 / 26 | 일치 |

## Defender

MpCmdRun.exe `-Scan -ScanType 3 -File <native경로>`로 실제exe/ZIP 각각 종료0·대상탐지0. 제품 4.18.26080.4 · 엔진 1.1.26080.3 · 정의(exe) 1.459.557.0 / (ZIP) 1.459.557.0.
[exe결과](defender-exe.json)·[로그](defender-exe.log)·[상태](defender-exe-status.json), [ZIP결과](defender-zip.json)·[로그](defender-zip.log)·[상태](defender-zip-status.json), [스크립트](check_defender.ps1). 보안설정·제외 변경0. 탐지0은 실제다운로드SmartScreen 화면 확인을 대신하지 않는다.

## 베타 간 변화 수·동봉안내

[806130a → 53d674b 6쪽 변화표](BETA_CHANGES.md), [전후행·문맥·해시](BETA_CHANGES.json), [806130a 실제exe 기준출처](OLD_BASELINE.json). 최종후보 비교를 위해 [9325fa8 → 53d674b 변화표](VS_9325_BETA_CHANGES.md)도 남겼다. 비교6쪽에는 헤더 수정 대상 D♭6쪽이 포함되지 않는다. 수치는 추가/삭제/표기변화/확신도변화만 세며 정답·오류·복구 수로 해석하지 않는다. 헤더 변화 등 문맥은 JSON에 보존한다.

[동봉안내](먼저%20읽어주세요.txt)는 실제ZIP member SHA와 일치한다. 꾸밈음 줄·쪽넘기기·수정본재열기 사용법 확인. [친구메시지](FRIEND_MESSAGE.md)의 SmartScreen 문구는 경고가 뜰 때의 조건부 안내다. [사람PC 확인5단계](PAGE_REOPEN_HUMAN_CHECK.md)는 실행절차이며 완료기록이 아니다. source_gui_3장은 #249의 자체생성 이미지·소스Tk 검증자료를 재사용했으며 새exe 클릭캡처가 아니다.

## 산출물·후보

- exe: `F:\sheet-music-helper-codex-night-20261004\dist\53d674bfe653-20261005-201451-020137\악보헬퍼.exe`
- exe 118,669,445바이트 / SHA-256 `B134B3F7474531F19ACADA8F7727216721165FD921E6D382C1001B5476DF6C74`
- ZIP: `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-53d674bfe653-20261005-201451-020137.zip`
- ZIP 124,746,244바이트 / SHA-256 `03DEEB7A329CA16B456673E27BFCF45F8474EE0718E73B97449A7F5D1C6C6883`

최종후보는 **9325fa8과53d674b만** 남긴다. 806130a는 **헤더 끝 미포함 중간 빌드**이며 최종배포후보에서 제외한다. 모든 기존산출물은 삭제하지 않고 보존한다.

빌드직전 여유메모리 3,193,724KiB / 총 16,442,780KiB([기록](memory-before.json)). 임시·산출물·dist/work F:, [디스크전](disk-before.json)·[후](disk-after.json). stash/기존빌드/공유C: 보존. exe/ZIP·원본악보 미커밋.

## 남긴 것

새53d674b **exe직접클릭·실제스피커청취·실제다운로드SmartScreen은 미확인**. 사용자9325fa8 직접확인을 새베타로 옮겨쓰지 않는다. [친구신고 접수문서](../../BETA_FEEDBACK_INTAKE.md) 유지. 이번검증은 소스/배포환경 일치이지 모든악보 오삭제0·정답률 보장이 아니다.
