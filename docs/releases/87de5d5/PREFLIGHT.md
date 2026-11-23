# 87de5d5 야간 보호 보완 베타 — 2026-10-06

빌드 기준 `87de5d51201bf49c313f78ecf34ea48c37847836` · main · dirty=false. #272 조표·박자표 유령 수정과 기존 #217·#234·#261·#263·꾸밈음/음자리표 안내·쪽 넘기기/수정본 재열기를 유지하며, **#274~#285의 야간 GUI·신고 데이터 보호 보완을 포함한다**. #167 옥타브 GUI와 #269 플랫 판정은 보류 상태를 유지한다.

## 빌드와 전체 검사

공식 `build.py`·원본 spec으로 1회 빌드했다. 시작 검사와 빌드 후 전체 검사 각각 **39개 통과·실패0·건너뜀0**, 골든711·PDF17쪽 스냅샷·#52 통과. 골든·selftest 기준 JSON 수정0, 인식·판정/renderer 코드 변경0(a200ccd 이후). 빌드 전 C: 약4.51GiB/F: 약218GiB 여유, 가용 메모리 약3.2GiB 확인. 산출물·임시 파일은 F:에 두고 공유 C: 체크아웃·stash·기존 빌드를 보존했다.

[시작 검사](prebuild-tests.log), [빌드 로그](build.log), [빌드 후 검사](tests.log), [빌드 정보와 원본 파일 해시](build-info.json). build-info의 PDF 라이브러리 제외 확인도 통과했다. 빌드 후 기록 브랜치에서는 문서·검증 스크립트·결과만 추가하며 제품 코드가 같으므로 전체 검사를 다시 중복 실행하지 않는다.

## 최종 ZIP에서 꺼낸 실제 exe 검증

- **10입력**의 소스/exe 전체 JSON·디코딩 PNG 픽셀·exe JSON 재렌더링 픽셀 모두 일치. Aoharu/D♭ 두 selftest 기준 JSON 전체 일치. [원자료](verification.json), [로그](verification.log), [실행 스크립트](verify_cli.py).
- 두 Verovio 글꼴과 xy0.5px에서 박자표/조표 위 기호 라벨0·첫 실제 F4 2/2 유지. 슈베르트 Leipzig(606,1522) E4 유지. 알토·음자리표 미검출/변경·꾸밈음 check 및 로그 안내 확인.
- check 주황 픽셀과 caution 옅은 픽셀 확인. D3의 원래 check를 수정한 JSON은 실제 exe에서 진한 글씨·점선 제거, 원래 음고/확신도/수정 기록 보존, 소스 편집 그림 및 certain 대조 그림과 픽셀 동일. [수정 자리 부분결과](d3_edited_detail.png). GUI 직접 클릭으로 확인한 기록은 아니다.
- settings 없는 새 한글/공백 폴더·Python 없는 PATH·exe 옆 output 생성·ZIP5파일·다른 원본 JSON 거부 모두 통과. 추가로 **소스 폴더 밖의 압축 해제 폴더**, PYTHONPATH 빈 값에서 Aoharu/D♭/Beethoven 3입력 JSON/PNG 일치. [원자료](clean-cwd.json), [로그](clean-cwd.log), [스크립트](verify_clean_cwd.py). Python 미설치 사람 PC 검증과 같다고 쓰지 않는다.
- 이전 실제 a200ccd exe와 동일10입력의 **전체 JSON 및 PNG 바이트 변화0**. [해시·전체 비교](previous-exe-invariance.json), [6쪽 추가/삭제/표기/확신도 변화표](BETA_CHANGES.md), [원자료](BETA_CHANGES.json). 변화 수는 정답률이 아니다.

[실제 exe Aoharu 1쪽](aoharu_p1.png), [쇼팽 D♭ 1쪽](chopin_Db_p1.png), [바흐 1쪽](bach_p1.png). 원본 악보·exe·ZIP은 저장소에 넣지 않는다.

## Windows Actions와 Defender

[Windows Actions 37386710035](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37386710035)를 **동일 빌드 커밋에서 한 번** 수동 실행했다. exe 빌드·전체39/39·Python 없는 PATH의 Aoharu/D♭ 두 selftest 및 전체 기준 JSON 비교 성공. [상태](actions.json), [전체 로그](actions.log). GitHub-hosted Windows의 PATH 독립성 확인이며 CI와 로컬 exe 바이너리 동일성을 주장하지 않는다.

실제 exe/ZIP 각각 `MpCmdRun.exe -Scan -ScanType 3 -File <경로>` 종료0·대상 탐지0. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.565.0. 보안 설정/제외 변경0. [exe 결과](defender-exe.json), [ZIP 결과](defender-zip.json), [실행 스크립트](check_defender.ps1), 각 로그와 버전 상태 JSON을 보존했다. SmartScreen 확인을 대신하지 않는다.

## 산출물·안내·남긴 것

- exe `F:/sheet-music-helper-codex-night-20261004/dist/87de5d51201b-20261006-081301-618209/악보헬퍼.exe` · 118,675,356바이트
- SHA-256 `20E3776E3067A17D3B236601756189C685836B62F6DA43D00E44F0AF82B9CFE6`
- ZIP `F:/sheet-music-helper-codex-night-20261004/dist/악보헬퍼-87de5d51201b-20261006-081301-618209.zip` · 124,767,768바이트
- SHA-256 `278B0164481B934C86F5AA82359E5D87FA13721CF4E91920BF4D306F228637AB`

[기계 판독용 경로·해시](artifacts.json). [동봉 안내문](먼저%20읽어주세요.txt)은 실제 ZIP member 및 build-info SHA와 일치한다. [친구 메시지](FRIEND_MESSAGE.md)의 SmartScreen은 조건부 설명이고 실제 다운로드 화면 확인을 주장하지 않는다. [쪽 넘기기·재열기 사람 확인 순서](PAGE_REOPEN_HUMAN_CHECK.md)는 확인 절차이며 완료 기록이 아니다.

**남긴 것:** 이 exe의 직접 클릭·스피커 청취·실제 다운로드 SmartScreen·Python 미설치 사람 PC 실행은 미확인이다. 기존 베타의 사람 확인을 이 빌드로 옮겨 쓰지 않는다. #167·#269 판단 보류와 사진/붙은 화음/임시표 전파 등 기존 인식 한계는 그대로다. 이번 빌드의 야간 GUI/신고 보완은 [실패 재현·소스 검사 기록](../../review/night_audit_20261006/SUMMARY.md)에 근거하며 실제 exe GUI 조작 검증으로 확대하지 않는다.

## 재실행

저장소 루트에서 같은 빌드/검증 입력을 준비하고 `verify_cli.py` → `verify_clean_cwd.py` 순서로 실행한다. 첫 스크립트는 settings/output 없는 새 압축 해제 폴더를 요구한다. `check_defender.ps1 -BuildTag 87de5d51201b-20261006-081301-618209`로 두 산출물을 검사한다. xy0.5px 입력은 이전 릴리스와 동일한 `tests/test_header_symbols.py`의 원본/INTER_LINEAR/흰 테두리 변환이다.
