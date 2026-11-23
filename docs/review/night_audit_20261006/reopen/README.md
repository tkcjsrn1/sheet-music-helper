# 손상된 수정본 간격 정보의 열기 거부

기준 main `6403d7f`. 정상 수정본은 현재 형식 그대로 사용한다. 인식/판정·골든·렌더링 문턱 변경 없음.

저장된 `재개정보.json`의 `render_options.staff_spacings`가 목록·null·숫자로 손상되면 `.items()`에서 AttributeError가 났다. 사전 형식 검사를 추가한 뒤에도 무한대 값은 렌더러의 글자 크기 계산에서 OverflowError가 났다. 두 예외는 GUI의 기존 열기 실패 처리 밖이었다.

공통 `_load_edit_version`에서 이 필드가 객체인지, 변환한 간격 값이 양의 유한한 수인지 확인한다. 손상된 수정본을 새로 해석하거나 자동 복구하지 않고, 기존 ValueError 안내 경로로 열기를 거부한다. 정상 이미지·계이름·수정 기록·원본 파일에는 손대지 않는다.

- [수정 전 형식 오류 재현](before.log): 실제 저장한 수정본을 손상시키면 AttributeError.
- [수치 오류 추가 재현](numeric-before.log): 무한대 값을 렌더러에 넘겨 OverflowError.
- [관련 검사 통과](after.log): null/빈 목록/목록/숫자/무한대/NaN/0/음수 거부, 실제 GUI 핸들러의 안내·이전 결과 유지. 정상 수정·삭제·추가·연속 되돌리기·둘째 쪽 저장/재열기·원본 PNG/JSON 바이트 보존 유지.

재실행: `python tests/test_gui_reopen_edits.py`, `python tests/run_all.py`. 제품 파일은 gui.py의 재열기 입력 검사만 바꾼다. exe 직접 클릭이나 새 베타 검증은 아니다. 이 보완은 기존 a200ccd exe에 아직 포함되지 않는다.

[최종 전체 검사](final-tests.log)는 실패0·건너뜀0. 골든711·PDF17쪽 스냅샷·기본 GUI PNG/JSON바이트보존 검사 통과. 검사 시작/끝 [코드 해시](source-hashes.json) 동일. 수치 오류 추가 재현 뒤 확정한 코드로 전체 검사를 실행했다.
