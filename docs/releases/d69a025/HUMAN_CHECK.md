# d69a025 실제 입력 확인 — 2026-10-26

공식 exe와 SHA256이 같은 격리 사본에 ctypes SendInput을 보냈다. WindowFromPoint·최상위 창·PID·실행 경로를 확인한 위치에만 입력했다. 코드/인식 설정은 수정하지 않았다. 기록 파일 이름의 HUMAN은 검사 범위 이름이며 사람 청취 완료를 뜻하지 않는다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 실제 두 이미지 선택·변환 | 통과 | 실제 파일 대화상자·PNG2/JSON2, [입력·출력 경로](actual_input_20261026/result.json) |
| 처리 중 다음 쪽 비활성·진행 | 통과 | [처리 중](actual_input_20261026/02_processing_header.png) |
| 완료 뒤 다음 쪽 실제 클릭·2/2 | 통과 | [완료](actual_input_20261026/03_ready_header.png) → [2/2](actual_input_20261026/03b_next_header.png). 완료 즉시의 지연값은 이번에 측정하지 않음 |
| 한글 IME N→N→P | 통과 | 관측 conversion1, [1/73](actual_input_20261026/05_np_0.png) → [2/73](actual_input_20261026/05_np_1.png) → [1/73](actual_input_20261026/05_np_2.png) |
| NumLock OFF F1 새 도움말 창 | 통과 | [도움말](actual_input_20261026/06_f1.png), 전면창/키 직전 NumLock·OS 포커스 원문. 영문 모드 전환 명령은 보냈으나 전환 뒤 IME 읽기값은 별도로 기록하지 않음 |
| 선택 라벨 건반 강조 | 통과 | [시b B3→MIDI58](actual_input_20261026/05_np_0_keyboard.png). 실제 스피커와 비교한 것은 아님 |
| 재생 중 악보·건반 동기화 | 소스 통합 검사 통과 / 실제 음성은 사용자 확인 | 실제 lanes 좌표/확대율·선택·재생 강조·늦은 사건 취소는 #412 통합 검사, frozen audio_plan 계약도 통과. 새 exe 실제 청취/지연은 이번에 검증하지 않음 |
| 레bb·파##·구간 조표 재생 값 | frozen 함수 계약 통과 | [실제 PYZ 함수·MIDI60/67/73](evidence/frozen-double-contract.json), 실제 GUI 음성·청취 검사와 구분 |
| 설정 ON/OFF·수정 저장→종료→재열기 | 소스 단위/전체 통과 / 새 exe 사용자 확인 | 이번 실제 exe 세션에서는 조작하지 않았음. [사용자 목록](USER_CHECKLIST.md) |
| 사본 종료·IME/NumLock 복원·잠금 해제 | 통과 | [정리](evidence/input-cleanup.json), 자기 Job 종료·잠금 해제 |
| 스피커 청취·실제 다운로드 SmartScreen | 사용자 몫 | 이번 자동검사로 통과 판정하지 않음 |

첫 시도는 첫 화면 관찰 대기120초를 넘겨 입력 전 종료했다. 사본·입력 상태를 정리한 원문을 evidence에 보존하고, 관찰 대기를300초로 조정해 같은 바이너리에서 재시도했다. 재시도는 15분 Job 제한 안에 성공했다. 원본 악보가 통째로 보이는 캡처는 커밋하지 않았다.
