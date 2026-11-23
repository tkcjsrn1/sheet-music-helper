# 배포 전 검사 — d3ac44d

- 공식 원본 spec 빌드 및 배포 고지 검사: 통과, dirty=false.
- run_all: 24/24, 실패0·건너뜀0. 정답 골든711·PDF17쪽 스냅샷 변화0. 기존 G♭ 예상 실패2는 유지한다.
- Defender: exe/ZIP 모두 MpCmdRun ScanType3 종료0, 탐지 없음. 엔진/정의 버전·원문 로그는 README와 별도 파일에 기록했다. 보안 설정 변경/우회0.
- 새 폴더·settings 없음·Python 없는 PATH의 exe --selftest: Aoharu/D♭ 통과. PNG/JSON 생성 및 소스와 전체 일치.
- exe --relabel: 두 결과 모두 원래 exe PNG와 픽셀 일치. 기본 실행 output은 exe 옆에 생성.
- 확신도: 기존 JSON 등급 그대로, D♭ check 주황 점선946픽셀·caution 옅은 글씨4134픽셀 확인. Aoharu는 check 표본0.
- 패키지: ZIP5개 파일, 사용자 dist 복사본이 ZIP 내용과 바이트 일치, exe 자체 커밋 없음.
- GitHub-hosted Windows: #119·#145 뒤 런37003109488(main19919fe)에서 빌드20/20 및 Python 없는 PATH 두 selftest/JSON 비교 통과. 이 런을 새 d3ac44d 빌드의 CI 런으로 쓰지 않는다. 전체 이력은 ../c8504e2/PREFLIGHT.md.
- 실제 다운로드 SmartScreen·첫 베타 사용자 PC·GUI 화면 재확인: 미확인/사용자 직접 확인 예정. 이번에 샌드박스나 SmartScreen 우회 실행은 하지 않았다.
