# de4b88e 실제 입력 확인 (중간 후보)

2026-10-15 15:49:52~15:53:22 KST, 해시 검증한 ZIP 검사 사본에 ctypes SendInput을 사용했다. 클릭 직전 WindowFromPoint 최상위 HWND/소유 PID를 확인했고 키 직전 전면 창·OS 포커스·NumLock을 기록했다. frozen exe 내부 Tk 위젯은 직접 조회할 수 없어 소스 실제 Tk 포커스 추적과 구분한다. 원로그는 F: output/human-beta366-20261015/events.jsonl에 보존했다.

| 확인 | 결과 |
|---|---|
| 두 이미지 실제 선택·계이름 달기 | 통과 |
| 처리 중 다음 쪽 회색·완료 후 실제 1/2→2/2 | 통과 |
| 영문/한글 × NumLock 켜짐/꺼짐 N/P | 각 화면에서 1/2→2/2→1/2 확인 |
| F1 영문 켜짐·한글 꺼짐·한글 켜짐 | 닫힌 도움말이 열림 확인 |
| F1 영문 NumLock 꺼짐 | 이미 열린 도움말 재사용 상태만 확인. 새 창 생성 검사는 미확인 |
| 한글 입력칸 N/P 보호 | 입력칸에 글자 입력, 순회 1/2 유지 |
| 검사 사본 종료·입력 상태 복원 | 확인. NumLock 원래 켜짐·IME 원래 영문으로 복원 |

[처리 중](converting-ui.png)·[2쪽](second-page-ui.png)·[한글 N](ko-numon-n2-ui.png)·[한글 P](ko-numon-p1-ui.png)·[도움말](ko-numon-help.png). 원본 악보가 보이는 전체 화면은 커밋하지 않았다. 피아노를 새로 녹음하지 않았고 스피커 사람 청취·실제 다운로드 SmartScreen은 미확인이다.
