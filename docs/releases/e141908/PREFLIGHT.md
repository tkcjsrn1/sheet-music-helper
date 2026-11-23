# e141908 내부 검증용 베타

빌드 완료. 공개 배포·친구 배포는 보류다. 실제 GUI 루프백/스피커 청취/실제 다운로드 SmartScreen은 미확인이다.

- 사용자 승인 #394 병합 e141908fca361a85396a59b91bd820b5e1f77ef4로 공식 build.py 한 번 실행, dirty=false. 13d73f6과 제품·판정·골든·Aoharu selftest 동일, 차이는 승인 D♭ fixture·문서/동봉 안내문뿐(selection.json).
- 공식 빌드 전체 검사 실패0·건너뜀0, 정답 골든711 무변경·PDF17 승인 스냅샷 일치(run-all.log.gz). 최신 main dafad3c까지의 추가는 WORKLOG/ERROR_CENSUS 문서뿐이라 빌드 코드를 바꾸지 않았다.
- 엄격12입력: 생김/사라짐/좌표/음고 변화0. #387 구간 key, #390 side_pair 등급/flags, #388/#391 표기/schema 변화만. 새 전체 라벨 행은 CLI 승인 dblconn 원자료와 일치. strict-rows.json.gz·strict-method.py.gz. 알려진 헛검출/check를 정확도 개선으로 세지 않음.
- 실제 exe/소스 12입력 PNG 픽셀·JSON 전체 일치, 실제 exe JSON 재렌더 픽셀 일치. Python 없는 PATH, settings 없는 첫 CLI 실행, exe 옆 output, ZIP5파일, 오입력 재렌더 거부, 사용자 수정 렌더 통과(verification.json/source-exe.log.gz).
- Defender exe·ZIP 각각 종료0·탐지0. 엔진1.1.26090.9/정의1.461.86.0, 원시 결과 defender-*.json. 보안 탐지 없음이 SmartScreen 통과를 의미하지 않는다.
- 같은 e141908 Windows Actions [39125994497](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/39125994497) success. 빌드/Python 없는 PATH 두 selftest JSON 비교 성공(windows-selftest.json/log.gz). 중복 dispatch하지 않았다.
- 실제 GUI 입력·정리와 미확인은 HUMAN_CHECK.md. 기본 IME 한글/NumLock OFF 복원, 검사 exe 잔류0.
- 경로·크기·SHA-256은 artifacts.json. exe/ZIP·원본 악보 미커밋. #397은 미병합이며 해당 selftest 5행은 변경하지 않았다. 이 빌드에는 #397이 없다.

예전 자동 승인 검토가 사용량 한도로 새 로그 보존 명령을 실행하지 못한 동안 이미 실행 중이던 검증을 재시작하지 않았다. 제한 해제 뒤 종료0을 회수하고 기록을 저장했다. 중복 빌드/전체검사/Actions 없음.
