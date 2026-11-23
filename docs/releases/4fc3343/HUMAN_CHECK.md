# 4fc3343 실제 exe 입력 확인 — 2026-10-15

대상은 [artifacts.json](artifacts.json)의 exe와 SHA가 같은 F: 검사 사본이다. Python ctypes `SendInput` 스캔코드/마우스 클릭을 사용했다. 키 직전 전면 HWND·PID·OS 포커스, 클릭 직전 `WindowFromPoint`의 최상위 창 일치를 확인했다. 외부 frozen Tk의 내부 포커스를 직접 조회한 것은 아니며 [소스 실제 입력 추적](../../review/ime_shortcuts_20261015/)과 구분한다. [이벤트 원자료](gui-events.jsonl), [검사 방법](gui-method.py.gz).

| 항목 | 결과 | 관찰 |
|---|---|---|
| 실제 exe 두 장 선택·변환 | 통과 | 18:26 실제 파일 선택/변환 클릭. [처리 중 UI](converting-ui.png)에서 다음 쪽 회색 |
| 완료 후 쪽 이동 | 통과 | [1/2](resumed-ui.png)에서 실제 클릭 직후 [2/2](page2-ui.png), 쪽별 확인 필요·주의 수와 파일명도 바뀜 |
| 한글 IME·NumLock ON N/P | 통과 | native=1 확인 후 실제 N→N→P. 검토 위치 [1/2](korean_n1-ui.png)→[2/2](korean_n2-ui.png)→[1/2](korean_p-ui.png), 위치 강조·스크롤 |
| 영문 IME·NumLock OFF F1 | 통과 | native=0·NumLock=false, 소유 창은 본창 하나뿐인 상태에서 F1. 새 HWND의 [단축키 도움말](english-off-f1-fresh.png) 생성 확인 |
| 원상 복원·사본 종료 | 통과 | 원래 영문(native=false)·NumLock=true로 복원. [종료 확인](gui-cleanup.json) 검사 사본/부트 프로세스 0 |
| 영문 N/P·나머지 IME/NumLock 조합의 이번 exe 재검사 | 미확인 | 이번 최종 exe에서는 위 두 조건을 직접 확인했다. 소스 네 조건과 중간 de4b88e 결과를 이번 exe 결과로 바꾸어 쓰지 않는다 |
| 이번 exe 저장·종료·다시 열기 | 미확인 | D3 CLI 수정·재렌더는 [별도 통과](verification.json). 이전 a9646b4의 실제 재열기 확인과 구분 |
| 이번 exe 피아노 루프백·사람 청취 | 미확인 | 이전 a9646b4 녹음 기록과 구분. 음색 코드/자산 변경 없이 빌드했지만 새 녹음으로 취급하지 않는다 |
| 실제 다운로드 SmartScreen·Python 없는 별도 PC | 미확인 | Defender 및 Actions의 Python 없는 PATH 검사는 아래 기록대로 별개 |

18:25~18:26 검사 중 자동 승인 검토의 사용량 한도로 후속 캡처가 실행되지 않았다. 검사가 끝났다고 쓰지 않았으며 당시 사본 종료도 미완료였다. 22:20:42~22:22:03에 정상 승인 경로로 남은 입력·복원·종료를 마쳤다. 네 시간 중단 구간을 연속 15분 검사나 변환 지연으로 세지 않는다. 완료 시점 전후를 관찰하지 못했으므로 두 장 총 처리 시간은 측정하지 않았다. 재개 직전 CLI Python 0·여유 메모리 약 2.7GiB 확인, 새 변환/빌드/전체검사 없이 이미 완료된 창을 사용했다.

원본 악보가 통째로 보이는 GUI 화면은 F:에만 두고, 여기에 올린 GUI 캡처는 악보 없는 표시줄/도움말 부분뿐이다. [Aoharu](aoharu_p1.png) 등 전체 결과 PNG는 요청한 exe 출력 자료이며 원본 입력 파일이 아니다.
