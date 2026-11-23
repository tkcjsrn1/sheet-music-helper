# e141908 실제 exe 확인 — 2026-10-19 KST

실제 ZIP 사본의 exe SHA는 artifacts.json과 같다. ctypes SendInput과 WindowFromPoint로 검사 사본 창 소유자를 확인했다. 입력/판정 설정은 변경하지 않았다. 원본 악보 전체가 드러나는 GUI 캡처는 보존용 로컬에만 두고 여기에는 UI 영역만 넣었다.

| 항목 | 결과 | 근거/한계 |
|---|---|---|
| 두 이미지 선택·변환 | 통과 | Aoharu1 + D♭1 성공2·실패0. 실제 GUI에서 변환 버튼 클릭 |
| 처리 중 쪽 이동 | 통과 | 2쪽 처리 중 회색 비활성, 완료 후 2/2와 파일명 즉시 갱신. page-processing/page-ready PNG |
| 쪽별 확인 수 | 통과 | Aoharu 확인1·주의1, D♭ 확인35·주의38 |
| N/P 한글 입력 | 통과 | 실제 IME conversion=1, 1/73→2/73→1/73. n-korean/p-korean PNG·events |
| F1 영문·NumLock OFF | 통과 | 실제 conversion=0, NumLock=false, 도움말 새 창 생성. help.png |
| 사용자 수정 저장·종료·재열기 | 통과(화면 확인) | 2쪽 B3 시b를 시험용 시bb로 변경, 사용자 수정/원래 check 유지 확인. 새 폴더 자동 저장 후 앱 완전 종료·재실행·원본 해시 확인으로 열었고 화면에 수정본 표시. 메모리 JSON을 외부에서 읽었다는 뜻은 아님 |
| 레bb·파## 음높이 | 수치 계약 통과, 실제 GUI 개별음 미확인 | frozen-double-contract.json: 실제 exe PYZ 함수+명시 fixture D4bb=60/F4##=67. 실악보 재생을 녹음한 증거와 구분 |
| 실제 GUI 피아노 루프백 | 미확인 | WindowFromPoint가 다른 창 hit_root=66884/pid4824를 반환하여 클릭 거부. 첫 시도와 전면화 재시도 모두 같은 이유. 녹음 성공/무음으로 판정하지 않았음 |
| 스피커 청취·다운로드 SmartScreen | 미확인 | 이번 확인에 포함하지 않음 |
| 검사 사본 종료·입력 복원 | 통과 | 두 세션 모두 closed_own_copies/ime_restored/numlock_restored=true |

첫 세션에서 편집 창 WM_CLOSE 직후의 스크롤은 아직 창이 가린 것으로 차단됐다. 도구 오류로 분리했으며 finally 정리 후 재개했다. 두 번째 세션 중 최소화된 창의 캡처는 검은 화면이라 증거로 쓰지 않았다. 앱 자체 변환·저장 실패로 바꾸어 쓰지 않는다. 실제 음색·개별 겹임시표 GUI 재생 확인은 남는다.
