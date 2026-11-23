# a200ccd 기호 유령 수정 베타 — 2026-10-06

빌드 기준 `a200ccd2c80b3d11b124bde7e7194687ab9a98df` · main · dirty=false. 사용자 승인 예외로 공통 헤더 판정을 고친 [PR #272](https://github.com/tkcjsrn1/sheet-music-helper/pull/272)가 포함된다. #261 헤더 끝·#263 링 벽 B안·꾸밈음/음자리표 변경·#247 미검출 안내·#249 수정본 재열기·#250 쪽 넘기기는 유지하며 #167 옥타브 GUI는 제외한다.

## 제보된 버그와 재발 검사

조표·3/4 숫자를 음표로 읽던 첫 시스템 경계를 공통 `analyze_staves`에서 고쳤다. 라벨을 화면에서 숨기거나 check를 일괄 삭제한 수정이 아니다. 첫 실제 F4 두 개를 보존하면서 Bravura 기호 라벨16개·Leipzig10개를 제거했다. [구현 근거·기각한 반례·소스 전체 측정](../../review/header_symbols/FIX.md), [Bravura 실제 exe 부분결과](alto_beethoven1_header_detail.png), [Leipzig 실제 exe 부분결과](alto_beethoven_leipzig_header_detail.png).

두 글꼴의 실제 입력, 73px 위치 이동, 부분화소/두 축 이동, 이미 박자표를 덮은 줄의 다음 음표, 네 성부에 같은 9도 화음이 반복되는 반례를 검사한다. 소스49쪽 중 위 두 쪽만 변경(기호26 제거·추가0·유지 라벨의 모든 필드 변화0); 다른47쪽 전체 JSON/PNG 바이트 동일. 조표·음자리표 변화0. 사진 모드 합성12장도 JSON/PNG 바이트 동일. 실제 사진·모든 조판의 보장으로 확대하지 않는다.

## 빌드·exe 검증

- 공식 build.py·원본 spec으로 빌드. 빌드 후 **38/38·실패0·건너뜀0**, 정답 골든711·PDF17쪽 스냅샷·#52 통과. [빌드 정보](build-info.json), [빌드 로그](build.log), [검사 로그](tests.log). 이 베타에서 selftest 기준·골든 변경0.
- 실제 ZIP에서 꺼낸 exe의 **10입력** 전체 JSON/소스 PNG 디코딩 픽셀/저장 JSON 재렌더링 픽셀 일치. 두 글꼴과 xy0.5px에서 기호 라벨0, 첫 F4 두 개 유지. 슈베르트 Leipzig(606,1522) E4 유지. [원자료](verification.json), [로그](verification.log), [실행 스크립트](verify_cli.py).
- settings 없는 새 폴더·Python 없는 PATH·exe 옆 output·ZIP5파일·다른 원본 JSON 거부 확인. 추가로 **소스 폴더 밖의 압축 해제 폴더**에서 PYTHONPATH를 비우고 Aoharu/D♭/Beethoven 실행, JSON/PNG 일치. [원자료](clean-cwd.json), [스크립트](verify_clean_cwd.py). Python이 설치되지 않은 사람PC 검증으로 확대하지 않는다.
- D3 실제 exe 재렌더링: 원래 check 라벨을 사용자가 고치면 진한 글씨·점선 제거, JSON의 원래 음고/확신도/수정 표시 보존, 소스 수정 PNG와 픽셀 동일.
- [Windows Actions 37339159776](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37339159776) 동일 빌드 커밋에서 한 번 수동 실행 성공. exe 빌드38/38, Python 없는 PATH의 Aoharu/D♭ 두 selftest·전체 기준 JSON 일치. [상태](actions.json), [로그](actions.log). CI exe와 로컬 exe의 바이너리 동일성을 주장하지 않는다.

| 입력 | 보표 | 라벨 | 확실 / 주의 / 확인 필요 |
|---|---:|---:|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 |
| aoharu_p2 | 14 | 327 | 296 / 28 / 3 |
| aoharu_p3 | 8 | 158 | 147 / 10 / 1 |
| chopin_Db_p1 | 8 | 260 | 197 / 38 / 25 |
| bach_p1 | 8 | 184 | 171 / 1 / 12 |
| clef_change_clara1 | 12 | 599 | 355 / 67 / 177 |
| alto_beethoven1 | 12 | 223 | 146 / 1 / 76 |
| schubert_restored | 12 | 481 | 295 / 160 / 26 |
| alto_beethoven_leipzig | 12 | 223 | 136 / 1 / 86 |
| header_xy0p5 | 12 | 222 | 147 / 0 / 75 |

## Defender·변화표·안내

실제 exe/ZIP 각각 `MpCmdRun.exe -Scan -ScanType 3 -File <경로>` 종료0·대상 탐지0. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.557.0. 보안 설정/제외 변경0. [exe 결과](defender-exe.json), [ZIP 결과](defender-zip.json), [스크립트](check_defender.ps1); 각 로그와 버전 상태 JSON 동봉. SmartScreen 확인을 대신하지 않는다.

[9325fa8 → 새 베타 6쪽 변화 수](BETA_CHANGES.md), [전후 행·문맥·해시](BETA_CHANGES.json), [이전 실제 exe 출처](OLD_BASELINE.json). [29037e2 → 새 베타 6쪽](from290/BETA_CHANGES.md)은 변화0이다. 제보된 Beethoven Bravura 실제 exe는239→223·추가0·삭제16·표기/확신도 변화0([전후 행](HEADER_CHANGES.json)). 변화 수를 정답률이나 복구 수로 해석하지 않는다.

[동봉 안내문](먼저%20읽어주세요.txt)은 실제 ZIP member SHA와 일치하며 꾸밈음/쪽 넘기기/수정본 재열기 안내를 유지한다. [친구 메시지](FRIEND_MESSAGE.md)의 SmartScreen 설명은 조건부 안내다. [사람 확인 순서](PAGE_REOPEN_HUMAN_CHECK.md)는 완료 기록이 아니다.

## 산출물·남긴 것

- exe `F:\sheet-music-helper-codex-night-20261004\dist\a200ccd2c80b-20261006-011204-511120\악보헬퍼.exe` · 118,673,809바이트
- SHA-256 `C5DE7B906404A75562F1F60D016BE16C230FBB631BEC57CFAC2F61005D3E91F9`
- ZIP `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-a200ccd2c80b-20261006-011204-511120.zip` · 124,758,688바이트
- SHA-256 `E857F1A9784643E3DAC75AB3E9B9CBC8B394F3909938501E775E4A237875A82E`

기존 베타/ZIP·stash·공유 C: 체크아웃 보존. 산출물/임시 파일F:, exe/ZIP·원본 악보 미커밋. **새 exe 직접 클릭·스피커 청취·실제 다운로드 SmartScreen은 미확인**. 9325fa8의 사람 확인을 이 빌드로 옮겨 쓰지 않는다. 알토 자체 인식 등 기존 한계는 그대로다.

### 스크립트 재실행

저장소 루트에서 해당 빌드와 검증용 원본을 준비하고 `verify_cli.py` → `verify_clean_cwd.py` 순으로 실행한다. 첫 스크립트는 settings/output이 없는 새 압축 해제 폴더를 요구한다. 원본 사진/악보는 이 릴리스 폴더에 동봉하지 않는다. xy0.5px 입력은 `tests/test_header_symbols.py`와 같은 원본/INTER_LINEAR/흰 테두리 변환으로 생성해 `output/header-symbols/phase-0.5-0.5.png`에 둔다.
