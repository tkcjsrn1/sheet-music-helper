# 60a8542 베타 점검 — 2026-10-05

**최종 후속 상태:** 검증 중 #217 병합으로 한때 배포 후보에서 제외했지만, CLI #224가 #217을 되돌리고 「#217 포함」 재빌드 요청을 취소했다. 최신 main38363c9과60a8542의 전체 tracked 파일 차이는 WORKLOG.md뿐이다. 제품·테스트·배포 안내문·의존성이 동일하므로 이미 검증 완료한 이 베타를 사용한다. 실제 빌드 해시는60a8542이며38363c9에서 빌드했다고 바꿔 기록하지 않는다. [동일성 확인](source-equivalence.txt).

기준 `60a8542573317f657eefdb4533c30a89f2be08df`, main·dirty=false. CLI WORKLOG의 「베타 재빌드 가능」 기록을 확인하고 #216 휠 오조작 방지, #219 라벨 추가 안내/입력칸, #221 알토 로그/머리말, #222 손상 JSON 테스트를 포함한다. D-3 수정·삭제·추가·되돌리기, D-1 영역 선택, D-2 음높이 듣기는 유지한다. #167과 #217은 포함하지 않았다. 이번 Codex 작업은 인식·판정 파일·골든을 편집하지 않았다.

## 검증

- 공식 build.py의 원본 spec 빌드/라이선스 검사/전체 검사34/34, 실패0·건너뜀0. 골든711·현재 PDF17쪽 스냅샷 무변경. 빌드 중 소스/커밋 고정 및 fitz/PyMuPDF 제외 확인.
- 같은 최신 판정 코드에서 일반 GUI Aoharu1~3/D♭1쪽 PNG·JSON 수정전후4/4 바이트일치. 알토 입력239라벨도 CLI 수정전후 JSON/본문 픽셀 동일.
- 아래5입력 소스/exe PNG 픽셀·JSON 전체 일치, exe JSON 재렌더링 픽셀 일치. check 주황 점선/주의 연한 글씨 색 픽셀 확인.
- Clara1의 clef_changed144개, Beethoven1의 clef_alto53개는 check. 새 exe의 알토 로그·머리말·재렌더링 경고 확인. [exe 경고 부분](alto_header_exe.png).
- 사용자 수정 check는 exe 그림에서 certain과 같은 진한 글씨이고 점선이 제거된다. JSON 원래 pitch/confidence와 edited 표시 보존, 소스 수정 그림과도 픽셀 일치.
- 새 폴더 settings.json 없는 CLI 첫 실행, Python 없는 PATH, exe 바로 옆 output 생성, ZIP5파일 확인. 실제 Python 미설치 사용자 PC나 GUI 직접 클릭 검증으로 확대하지 않는다.
- [Actions37213060162](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37213060162): 같은 커밋1회 수동 실행, Windows exe 빌드34/34 및 Python 없는 PATH의 두 selftest/기준 JSON 전체 비교 성공. [로그](actions.log).
- 새 기준: Aoharu226 전체 무변경, D♭254개 중 (416,2792)/(2296,2831)의 #215 glyph_shape 확신도/사유만 갱신. 음고·좌표·계이름·조표·보표 동일, [전후행](../../measurements/beta_glyph_shape_selftest_baselines.json). 골든 갱신과 구분한다.
- exe/ZIP Defender ScanType3 각각 종료0·탐지없음. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.547.0. [exe](defender-exe.log) / [ZIP](defender-zip.log) / [상태](defender-status.json).

| 입력 | 악보 줄 | 라벨 | 확실 / 주의 / 확인 필요 | 소스·exe·재렌더링 |
|---|---:|---:|---|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 | 일치 |
| chopin_Db_p1 | 8 | 254 | 206 / 34 / 14 | 일치 |
| bach_p1 | 8 | 184 | 171 / 1 / 12 | 일치 |
| clef_change_clara1 | 12 | 587 | 350 / 65 / 172 | 일치 |
| alto_beethoven1 | 12 | 239 | 169 / 8 / 62 | 일치 |

이 표는 인식 정답률이 아니라 실행환경 일치 검사다. [verification.json](verification.json)과 [실행 로그](exe-verification.log), [전체 검사](tests.log), [빌드 정보](build-info.json)를 보존한다. 검증 스크립트는 기존 cebae18/verify_cli.py의 경로를 바꾸고 알토 입력 검사만 추가했다.

## Defender 최초 오류 보존

첫 검사에서 F:/ 형태의 경로를 전달했을 때 종료2·0x80508023 오류가 발생했다. [최초 로그](defender-exe-initial-error.log)를 보존하며 통과로 세지 않는다. 탐지 기록에 이번 산출물은 없고 파일도 보존된 상태에서 Resolve-Path가 준 동일 파일의 F:\ 경로로 재검사해 종료0·탐지없음을 확인했다. 보안 설정/제외/격리를 변경하지 않았다. 최초 오류의 정확한 원인을 경로 형식만으로 확정하지 않는다. Microsoft의 [오류 코드 문서](https://learn.microsoft.com/en-us/defender-endpoint/troubleshoot-microsoft-defender-antivirus#error-code-0x80508023)에는 ERR_MP_THREAT_NOT_FOUND로 설명돼 있다.

## 산출물

- exe: `F:\sheet-music-helper-codex-night-20261004\dist\60a854257331-20261005-002723-961638\악보헬퍼.exe`
- exe 118,656,540바이트, SHA-256 `7AE8509C30C662F0AC016FBFDF096EB6D4E7CDBE47A2AE7D141EDCF29756DB9D`
- ZIP: `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-60a854257331-20261005-002723-961638.zip`
- ZIP 124,719,903바이트, SHA-256 `CE6593054DCE0F69F9EC9CA59A2366EA43A62B3B49B3572B275FFF6079DAFCF0`

C: 빌드 전2,927,550,464바이트/F:237,408,243,712바이트 여유. 임시·산출물은 F: 사용, [전](disk-before.json)/[후](disk-after.json) 기록. 예전 빌드·stash·공유 C: 체크아웃을 보존했다. exe/ZIP·전체 원본 악보는 이 기록에 커밋하지 않았다. 전체 결과 PNG/JSON은 verification.json의 로컬 산출물 경로에 있다.

## 남긴 것

사용자가 확인한 5d2521d/cebae18 exe 직접 기능 확인은 [5d2521d 후속 기록](../5d2521d/PREFLIGHT.md)에 있고 #187은 CLOSED다. 이번 새 베타는 CLI/소스 GUI 검사이며 새 exe의 실제 클릭 확인으로 바꾸어 쓰지 않는다. 안내/입력칸 [소스 화면](label_editor_help.png), [추가창](label_add_help.png)은 원본 악보를 제외한 자체 생성 화면이다. 스피커 청취와 실제 다운로드 SmartScreen은 미확인 유지. #43도 #222 테스트 이식 병합 뒤 CLOSED 처리했다.

후속: 이 빌드 검증 이후 #225의 clef_unknown 표시가 main3203700에 병합됐다. 60a8542에는 미포함이며 위 코드 동일성 비교는 명시된38363c9까지다. 요청된 휠/도움말/알토 경고는 포함한다. 이후 main을 다시 fetch한 상태와 빌드 시점을 혼동하지 않는다.

기록 PR #227은 main3203700 위에서 전체34/34·실패0·건너뜀0·골든/현재PDF스냅샷유지를별도로확인했다([기록 브랜치 검사](record-main-tests.log)). 이후5b531d0은문서/측정도구뿐이라제품/테스트diff0을확인하고통합했다. 이 후속기록검사는실제exe빌드커밋60a8542를바꾸지않는다.
