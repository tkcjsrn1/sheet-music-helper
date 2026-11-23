# dff19b2 베타 배포 전 점검 — 2026-10-04

- 기준 dff19b286022f736ef9e53bf74bc32abe98114a2, #155/#153/#159 포함·#167 제외·dirty=false.
- 공식 build.py 종료0·27/27·실패0·건너뜀0·정답 골든711/PDF17쪽 스냅샷 무변경.
- exe/ZIP Defender ScanType3 종료0·탐지 없음. / 경로의 첫 오류는 native 경로 재검사로 해결; 실패 로그도 보존.
- Aoharu1/D♭1/바흐1: 소스/exe JSON 전체 및 PNG 픽셀 동일, exe JSON 재렌더링 동일.
- settings 없는 새 폴더·Python 없는 PATH·exe 옆 output·ZIP5파일·사용자 dist 복사 바이트 일치 확인.
- D-3 소스 GUI 클릭/수정/삭제/추가/연속 되돌리기 및6화면 기록. exe 수정 JSON은 진한 글씨·점선 제거·원래 확신도 보존·소스/수동 certain 대조 픽셀 일치.
- Actions37135358758 같은 커밋에서1회 실행·성공, 빌드27/27 및 Python 없는 PATH 두 selftest/갱신 JSON 전체 일치.
- 미확인: 실제 다운로드 SmartScreen, 첫 베타 사용자 PC, exe GUI 직접 클릭. GUI 캡처는 소스 자동 검사 화면이다.

해시·경로·PNG/화면·원문 로그·잔여 한계는 [README](README.md)와 [artifacts.json](artifacts.json)에 있다. exe 자체는 저장소에 넣지 않았다.
