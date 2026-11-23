# 72ca500 실제 exe 입력 확인 — 2026-10-16

대상은 [artifacts.json](artifacts.json)과 SHA가 같은 F: 격리 사본이다. Python ctypes SendInput의 실제 마우스/스캔코드를 사용했다. 클릭 직전 WindowFromPoint의 최상위 HWND/PID, 키 직전 전면 창/OS 포커스와 키보드 상태를 기록했다. frozen Tk 내부 포커스를 외부에서 직접 조회한 것으로 쓰지 않는다. [원로그](gui-events.jsonl) · [관찰](gui-observations.json) · [방법](gui-method.py.gz).

| 항목 | 결과·근거 |
|---|---|
| 실제 파일 선택·계이름 달기 | 통과 — Aoharu 두 이미지 선택 뒤 실제 변환 클릭. [처리 중 다음 쪽 회색](converting-ui.png) |
| 완료 뒤 다음 쪽 | 통과 — [완료 1/2](complete-ui.png)에서 실제 다음 쪽 클릭으로 [2/2](page2-ui.png), 표시 파일명/쪽별 확인 수 변경 |
| 실제 다음 확인 필요 버튼 | 통과 — [1/2→2/2](next_review_button-ui.png) |
| 한글 IME N/P | 통과 — native=1 확인 후 N→N→P, 검토 [1/2](korean_n1-ui.png)→[2/2](korean_n2-ui.png)→[1/2](korean_p-ui.png) |
| 영문·NumLock OFF F1 새 창 | 통과 — 도움말 없는 상태에서 실제 F1 후 새 HWND [도움말](english_off_f1_fresh-ui.png) 생성 |
| 확인 필요 이유 안내 | 통과 — 실제 선택/수정창의 [이유 문구](reason_editor-ui.png), 입력칸/버튼 표시 확인 |
| 원상 복원·검사 사본 종료 | 통과 — [cleanup](gui-cleanup.json), 검사 사본/부트 0·원래 IME/NumLock 복원 |
| 이번 exe 나머지 IME/NumLock 조합 | 미확인 — 소스 전체 조합 검사나 지난 exe 결과를 대체 증거로 쓰지 않음 |
| 이번 exe 저장→종료→재열기 / 피아노 새 루프백·사람 청취 | 미확인 — D3 CLI 수정/재렌더와 별개. 과거 a9646b4/4fc3343 관찰을 재사용하지 않음 |
| 실제 다운로드 SmartScreen / Python 없는 별도 PC | 미확인 — Defender/Windows Actions Python 없는 PATH 결과와 구분 |

원본 악보가 통째로 보이는 GUI 캡처는 F: 임시 자료에만 보존한다. 여기에는 악보 없는 표시줄/팝업 부분만 올렸다. 결과 PNG 네 장은 사용자가 요청한 실제 exe 출력이다. [조바꿈 뒤 듣기 불일치](KNOWN_LIMITATIONS.md)를 확인했으며 정확한 듣기 지원으로 판정하지 않는다.
