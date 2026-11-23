# 변환 중 중간 결과를 저장하지 않기

기준 main `17e8f57`. `_convert_page`의 라벨/세션 공개와 worker의 결과 PNG 선택 사이에는 이전 PNG와 새 JSON이 함께 참조될 수 있다. 같은 결과 경로에 PNG를 쓰는 중에는 아직 완성되지 않은 파일도 존재한다. 저장 콜백은 변환 상태를 확인하지 않고 복사/신고했다.

실제 사용자 파일 대신 자체 작은 PNG/JSON으로 이 중간 상태를 구성해 실제 콜백을 호출했다. [수정 전 자료](before-data.json): 신고 ZIP은 이전 PNG와 새 JSON, PNG 내보내기는 열 수 없는 작성 중 파일을 성공 저장으로 알렸다. 실제 발생 빈도나 모든 변환 실패의 영향을 이 합성 상태로 추정하지 않는다.

[기존 소스 Tk 검사 확장도 실패](before.log)했다. 두 저장 콜백의 시작 조건에 `_converting`을 더한 두 줄 수정이다. [수정 후 중간 상태](after-data.json)는 대화상자/파일이 생기지 않으며 기존 입력을 유지한다. 완료된 현재 PNG·JSON 신고와 PNG 내보내기는 정상 동작한다. [소스 Tk 검사](after.log)에서도 진행 중 저장 무접근, 완료 뒤 원본/설정/PNG/JSON 보존 통과. 실제 exe 클릭 검증은 아니다.

[최종 전체검사](final-tests.log) 실패0·건너뜀0, 골든711·PDF17쪽 스냅샷·기본GUI PNG/JSON 보존. [검사 시작/끝 코드 해시](source-hashes.json) 동일. 인식/판정/renderer/골든 변경0. 신고 입력 보호 검사의 모의 앱에는 실제 `_converting=False` 필드를 명시했다.

재실행: `python tests/test_gui_snapshot.py`, `python tests/test_feedback_bundle.py`, `python tests/run_all.py`. 기존 a200ccd exe에 미포함. 이번 범위는 진행 중 저장 보호이며 실패한 변환 전체를 트랜잭션으로 만든 것은 아니다.
