# 015908d 실제 입력 확인 — 요청 항목 통과

2026-10-20, 실제 ZIP 사본 exe와 SendInput 입력으로 확인했다. 제품 코드·인식 설정은 바꾸지 않았다. [방법·중간 시도·범위](actual_input_20261020/METHOD.md).

| 항목 | 결과 | 근거 |
|---|---|---|
| 두 장 선택·변환·결과 표시 | 통과 | 기존 기록 + 새 실제 입력 |
| 2쪽 처리 중 비활성 → 완료 즉시 다음 쪽 | 통과 | [연속 표시줄](actual_input_20261020/page-progress-contact.png), 활성 관찰 뒤10.90ms 클릭·2/2 |
| 한글 N/P | 통과 | [N1](actual_input_20261020/auto_n1_korean-ui.png) → [N2](actual_input_20261020/auto_n2_korean-ui.png) → [P1](actual_input_20261020/auto_p1_korean-ui.png) |
| NumLock OFF·영문 F1 새 창 | 통과 | [도움말](actual_input_20261020/auto_help_f1_numoff.png), 실제 핸들/IME·NumLock 기록 |
| 수정 저장 → 종료 → 새 실행·재열기 → 되돌리기 | 통과 | [수정](actual_input_20261020/editor_after_change.png), [재열기](actual_input_20261020/reopened_editor_settled.png), [되돌리기](actual_input_20261020/reopened_undo.png) |
| 레bb GUI 입력·선택·저장·출력 | 통과 | 사용자 수정 사례. [저장](actual_input_20261020/gui_rebb_saved.png), 단일음 예상C5/MIDI72 [분석](actual_input_20261020/audio-rebb/analysis.json) |
| 실악보 파## GUI 선택·영역 저장·출력 | 통과 | F4 (679,717), check 유지. [수정 창](actual_input_20261020/real_f4_editor.png), 예상G4/MIDI67 [분석](actual_input_20261020/audio-real-f4/analysis.json) |
| 검사 사본 종료·IME/NumLock 복원·잠금 해제 | 통과 | [마지막 정리](actual_input_20261020/cleanup-real-f4.json), 사본0·자기 잠금 해제 |
| 스피커 청취 | 사용자 몫 | 디지털 출력과 별도 |
| 실제 다운로드 SmartScreen | 사용자 몫 | 화면을 추측해 통과 처리하지 않음 |

사용자 대리 육안 판정: 결과 그림은 이상 없음. **쇼팽10~12마디 글자 겹침이 심함**은 남은 표시 문제이며 #412 비교 그림에 포함한다. 모든 인식이 정확하다고 판정한 것은 아니다.
