# d6cf163 피아노 음색 베타 — 2026-10-07

기준 `d6cf163eea020a6afe2b57cc577b98ee9fd2f98a`, main, dirty=false. #293 피아노 재생과 #294 TASKS 정리 포함. #290 음고 중심·#272 기호 유령·기존 라벨 수정/재열기/쪽 선택 보호는 유지. #167·#269 보류 유지. 인식·판정·골든·selftest 기준 변경0.

## 검증

공식 build.py/원본 spec 빌드 한 번, 빌드 전/후 각각39/39·실패0·건너뜀0, 골든711·PDF17 스냅샷·#52 통과. [빌드 정보](build-info.json), [시작 검사](prebuild-tests.log), [빌드 후 검사](tests.log). C:약5GiB/F:217GiB·가용메모리5.2GiB 확인 후 F:에서 실행. 공유C:·stash·기존 빌드 보존.

최종 ZIP을 settings/output 없는 새 한글 폴더에 풀어 실제 exe **8입력**(Aoharu3·D♭·바흐·Clara·Beethoven·Schubert) 소스/전체JSON·PNG 픽셀·JSON 재렌더링 일치. Aoharu/D♭ selftest 기준 JSON 전체 일치. Python 없는 PATH·exe 옆 output·settings 없는 CLI·ZIP5파일·다른 원본 JSON 거부 성공. source 밖 cwd/빈 PYTHONPATH 3입력도 동일. check 주황·caution 옅기, 꾸밈음/알토/음자리표 변경 경고 유지. Beethoven 기호 영역 라벨0/첫F4·Schubert(606,1522)E4 유지. D3 수정 check를 진하게 그리며 원래 확신도/음고를 보존, 소스/확실 대조 그림과 픽셀 동일. [원자료](verification.json), [독립 폴더](clean-cwd.json), [스크립트](verify_cli.py).

새 음색은 Windows Microsoft GS Wavetable Synth의 GM 그랜드 피아노(program0), ctypes/winmm. 새 패키지·음원 파일·Windows DLL 동봉0. 실제 exe 동봉 모듈을 추출해 피아노 코드/API 호출 성공을 확인했으며 GUI에서 exe를 눌러 재생한 검사는 아니다. 실제 음 재생 중 취소·장치 실패·정리 실패·GUI 종료는 [소스 검사](../../review/piano_20261007/native-api.json)와 자동 테스트로 확인했다. 새 exe118659162바이트, 이전보다18219바이트 작음(winsound.pyd 제거). [동봉 코드/크기 대조](frozen-piano.json).

[Windows Actions37585404051](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37585404051) 동일 d6cf163에서 한 번 실행 성공. exe 빌드·전체검사·Python 없는 PATH 두 selftest·기준 JSON 비교 통과. 기준 갱신0·중복 실행0. [상태](actions.json), [로그](actions.log). 로컬/CI 바이너리가 같다는 의미는 아니다.

Defender exe/ZIP ScanType3 각각 종료0·대상 탐지0. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.576.0, 보안 설정/제외 변경0. [exe](defender-exe.json), [ZIP](defender-zip.json), 상태·전체 로그·스크립트 동봉. SmartScreen 확인을 대신하지 않는다.

[이전 ab93bf2→새 6쪽 변화표](BETA_CHANGES.md) 추가/삭제/표기/확신도 변화 모두0. 숫자를 정답률로 해석하지 않는다. [Aoharu](aoharu_p1.png)·[D♭](chopin_Db_p1.png)·[바흐](bach_p1.png) 결과 PNG와 D3/Beethoven 부분그림 보존. exe/ZIP·전체 원본 미커밋.

## 산출물·남긴 것

[exe·ZIP 경로/전체 SHA256](artifacts.json). 안내문은 최종 ZIP과 해시가 같다. [친구 메시지](FRIEND_MESSAGE.md)와 [쪽 넘기기/재열기 확인 순서](PAGE_REOPEN_HUMAN_CHECK.md)도 유지한다.

실제 exe GUI 직접 클릭/피아노 재생·스피커 청취·다운로드 SmartScreen·Python 미설치 사람 PC 실행은 미확인이다. API 성공을 사람이 듣고 판정한 결과로 쓰지 않는다. 박자 재생·고급 녹음 피아노 음질은 보장하지 않는다. 예전 exe/PNG는 자동 갱신되지 않는다.

인식 잔여 오류와 [104조건 정답 대조](../../QUALITY_RECHECK_20261007.md)는 그대로 남는다. 이 PR은 기록/안내만 고치며 빌드 뒤 녹색과 제품 코드가 같아 전체검사·Actions·빌드를 중복하지 않는다. 검증 스크립트는 F: 원본/이전 출력에 의존하며 독립 입력 패키지는 아니다. 최초 자동 승인 시간 초과는 각 검사 한 번 재시도로 해결했고 완료된 검사를 중복하지 않았다.

사용자 요청 재시험(2026-10-07): [새 exe 동봉 GUI 작업자 실제 피아노 API 정상/화음 중 취소](../../review/piano_20261007/frozen-worker-retest.json) 통과. 테스트 선율과 사용자 수정 음·check 제외·note-off/reset/close 확인. 창 클릭·스피커 청취 검사와 구분하며 마이크는 사용하지 않았다. [재실행 스크립트](../../review/piano_20261007/test_frozen_worker.py).

2026-10-12 추가: [실제 스피커 디지털 출력 루프백·사인파 대조 녹음](../../review/piano_loopback_20261012/MEASURE.md) 성공. Windows 기본 그랜드 피아노 선택과 실제 배음 출력 확인. [들어볼 녹음](../../review/piano_loopback_20261012/piano.wav). 스피커 공기 중 소리/사람 청취·exe 창 클릭 검사는 아니다. 이전 ffmpeg 장치 목록에 근거한 녹음 불가 판단은 WASAPI가 가능한 범위를 빠뜨린 것이어서 정정한다.
