# 신고 저장 목적지가 입력 파일과 같을 때 덮어쓰기 거부

기준 main `fba1316`. 저장 함수는 임시 ZIP을 완성한 뒤 목적지에 교체한다. 목적지를 원본 이미지·현재 결과 PNG·라벨 JSON 중 하나로 지정하면 기존 입력을 ZIP으로 교체해 버렸다.

[합성 파일 실제 재현](before-data.json)에서 세 목적지 모두 바이트가 달라지고 ZIP이 됐다. 유효한 작은 PNG와 자체 JSON만 사용했고 실제 악보/사용자 파일은 건드리지 않았다. [수정 전 보호 검사](before.log)도 실패했다.

공통 `save_feedback_bundle`에서 목적지의 정규화된 경로를 입력 세 파일과 비교하고, 같으면 쓰기 전에 ValueError로 거부한다. GUI는 기존 저장 실패 안내를 사용한다. 다른 입력에 영향 주는 판정 조건·인식 코드·골든은 변경하지 않는다.

보호 검사 통과: 세 입력의 바이트 보존, Windows 대소문자 경로도 거부, 정상 네 파일 신고 ZIP/수정 기록 익명화 유지, 기존 신고 ZIP을 같은 이름으로 다시 저장 가능. [신고 재현](replay.log)과 [접수 요약](intake.log)도 통과. 입력 이외의 모든 사용자 파일을 보호하거나 ZIP 내용의 개인정보를 지우는 기능으로 확대하지 않는다.

재실행: `python tests/test_feedback_bundle.py`, `python tests/run_all.py`. 기존 a200ccd exe에 아직 미포함, 새 exe 클릭 검증은 아니다.

[최종 전체 검사](final-tests.log) 실패0·건너뜀0, 골든711·PDF17쪽 스냅샷·기본GUI PNG/JSON 보존 통과. [검사 시작/끝 코드 해시](source-hashes.json) 동일.
