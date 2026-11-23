# ab93bf2 음고 중심 보완 베타 — 2026-10-07

빌드 기준 `ab93bf294cd868ba80439e27bfac5921ec7db46e`, main, dirty=false. #290의 별도 기호 연결에 따른 음고 중심 수정 포함. #272 기호 유령 수정·#274~#285 야간 GUI/신고 보호와 기존 #217·#234·헤더 끝·링 벽·쪽 넘기기·수정본 재열기·음자리표/꾸밈음 안내를 유지한다. #167·#269는 보류 유지.

## 검증

공식 build.py·원본 spec으로 한 번 빌드했다. 시작 제품 검사와 빌드 후 검사 모두 **39/39·실패0·건너뜀0**, 골든711·PDF17쪽 스냅샷·#52 통과. selftest 기준 JSON·골든·판정 문턱 변경0. 사용자가 이번 오류에 한해 notehead_detect.py 수정을 명시적으로 허용했으며 다른 판정/규약 파일은 변경하지 않았다. [사본49쪽·합성사진12입력·실패/통과 근거](../../review/dynamic_join_20261006/MEASURE.md), [시작 검사](prebuild-tests.log), [빌드 후 검사](tests.log), [빌드 정보](build-info.json).

최종 ZIP에서 꺼낸 실제 exe **19입력**의 소스/exe 전체 JSON·디코딩 PNG 픽셀·exe JSON 재렌더링 일치. Aoharu/D♭ 기준 JSON 전체 일치. 두 글꼴 원본과 x0.25/x0.5/x0.75/y0.5/xy0.5 다섯 실제 변환에서 조표·박자표 위 라벨0, 첫 실제 F4/파2/2. 중심 변경7사례의 좌표·음고도 실제 exe에서 확인했다. [원자료](verification.json), [로그](verification.log), [검증 스크립트](verify_cli.py).

**기존 실제 exe에서 실패한 x0.5 입력 전후:** 라벨227→227, 조표·음자리표 문맥 동일. 같은 staff/x에서 y순 대응해 바뀐 행은 하나뿐이다. (407,244) E4/미 caution → (407,239) F4/파 certain. 나머지226행 동일, 짝없는 추가/삭제0. 파일명만 다른 동일 입력 SHA·쪽·크기·dpi를 확인했다. [전체 전후행](actual-phase-before-after.json), [실제 새 exe 박자표·첫 음 부분그림](beethoven_header_detail.png). 위상 입력을 원본에 비교한 전역 음고 불변이나 모든 OMR 오류 해결을 주장하지 않는다.

settings 없는 새 한글/공백 폴더, Python 없는 PATH, exe 옆 output, ZIP5파일, 다른 원본 JSON 거부 통과. source 밖 cwd·빈 PYTHONPATH에서 Aoharu/D♭/Beethoven 세 입력 JSON/PNG 일치. [독립 폴더 검사](clean-cwd.json). check 주황·caution 옅은 픽셀과 기존 꾸밈음/음자리표 경고 유지. 실제 exe로 D3 수정 check를 진하게 그리고 원래 확신도·음고·수정 이력을 보존하며, 소스 편집 그림/certain 대조 그림과 픽셀 동일. [수정 부분결과](d3_edited_detail.png). GUI 클릭 검증 기록은 아니다.

[Windows Actions 37484522149](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37484522149)는 동일 ab93bf2에서 한 번 수동 실행해 성공했다. exe 빌드·전체39/39·Python 없는 PATH의 Aoharu/D♭ selftest 두 건과 전체 기준 JSON 비교 성공. [상태](actions.json), [전체 로그](actions.log). CI와 로컬 바이너리가 동일하다는 의미는 아니다.

실제 exe와 ZIP 각각 MpCmdRun -Scan -ScanType3 -File 검사 종료0·대상탐지0. Defender 제품4.18.26080.4/엔진1.1.26080.3/정의1.459.568.0. 보안 설정·제외 변경0. [exe 검사](defender-exe.json), [ZIP 검사](defender-zip.json), 버전 상태·로그·실행 스크립트를 함께 보존한다. SmartScreen 확인을 대신하지 않는다.

[이전87de5d5→새 베타 6쪽 변화표](BETA_CHANGES.md)는 추가/삭제/표기/확신도 변화 모두0이다. 해당6쪽은 실제 변경7쪽과 다른 집합이다. [Aoharu1쪽](aoharu_p1.png), [D♭1쪽](chopin_Db_p1.png), [바흐1쪽](bach_p1.png)를 남겼다. 원본 악보·exe·ZIP은 커밋하지 않는다.

## 산출물·안내·남긴 것

빌드 전 C:약7.1GiB/F:약218GiB·가용메모리약3.9GiB 확인. 산출물·임시는F:, 공유C:체크아웃·stash·기존빌드 보존. [경로·전체 SHA256](artifacts.json). 안내문은 최종 ZIP member 및 build-info와 동일하다. 친구 메시지와 쪽 넘기기/재열기 확인 순서를 동봉 기록한다.

이 exe 직접 클릭·스피커 청취·실제 다운로드 SmartScreen·Python 미설치 사람 PC 실행은 **미확인**이다. 기존 베타의 사람 확인을 옮겨 쓰지 않는다. 저장한 예전 PNG/수정본은 자동으로 고쳐지지 않으므로 새 exe에서 원본을 다시 변환해야 한다. 기존 인식 한계와 #167·#269 보류는 유지한다.

기록 PR은 문서·자료만 추가한다. 제품 코드가 빌드 후 녹색과 같으므로 전체 검사·빌드·Actions를 중복하지 않는다. 재실행은 verify_cli.py → verify_clean_cwd.py 순서이며 새로운 settings/output 없는 압축 해제 폴더를 사용한다. 추가악보 PNG와 이전 기준선은 F: output 자료에 의존하며 독립 실행 패키지는 아니다.

- exe `F:\sheet-music-helper-codex-night-20261004\dist\ab93bf294cd8-20261007-000552-557107\악보헬퍼.exe` · 118677381바이트 · SHA256 `640CFB45753A87B719832FACD08094940139F489BDEA7EE1419F71C2A9B00659`
- ZIP `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-ab93bf294cd8-20261007-000552-557107.zip` · 124775843바이트 · SHA256 `6D365FE90B2D121AB690893FA7C1C5F51F2BA61D5ABDAB8064FB6682F81804E0`
