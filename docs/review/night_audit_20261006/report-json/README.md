# 손상된 신고 JSON을 오류 안내로 거부

기준 main `eb90cfb`. `save_feedback_bundle`은 라벨 JSON과 빌드 정보 JSON의 최상위 값을 객체라고 가정하고 `.get`을 호출했다. null/배열/문자열인 파일은 AttributeError가 GUI의 저장 실패 안내 밖으로 빠졌다.

[라벨 파일 실패 재현](before.log), 라벨 경계를 보완한 뒤 [빌드 정보 파일에서도 같은 실패](manifest-before.log)를 확인했다. 실제 GUI 저장 콜백을 자체 임시 파일로 호출했다. 공통 저장 함수에서 객체가 아닌 두 JSON을 ValueError로 거부하며 GUI의 기존 오류 안내를 사용한다. 일반 JSON 스키마 전체를 새로 정의하거나 모든 예외를 숨기지 않는다.

두 파일 각각 null/배열/문자열을 넣은 여섯 경우 모두 실패 안내, 기존 신고 ZIP·원본·결과·손상 입력 파일 바이트 보존 통과. 정상 네 파일 ZIP·수정 기록 익명화·기존 ZIP 재저장과 [재현](replay.log)/[접수](intake.log) 검사도 통과한다.

[최종 전체 검사](final-tests.log) 실패0·건너뜀0. 골든711·PDF17쪽 스냅샷·기본GUI PNG/JSON 보존 통과. [검사 시작/끝 코드 해시](source-hashes.json) 동일. 인식·렌더링·골든·판정 문턱 변경0.

재실행: `python tests/test_feedback_bundle.py`, `python tests/run_all.py`. 기존 a200ccd exe에는 아직 미포함이며 실제 exe 클릭 검증은 아니다.
