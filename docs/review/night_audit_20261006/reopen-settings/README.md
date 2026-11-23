# 손상 수정본의 렌더 설정 예외 안내

기준 main 3d343a5. 자체 220×180 이미지와 라벨로 실제 저장 수정본을 만든 뒤 재개정보.json의 렌더 설정만 변경했다. font_path={}는 PIL의 AttributeError, text_offset_y=무한대는 round의 OverflowError를 발생시켰다. 기존 GUI 재열기 안내 예외 밖이라 콜백이 끝나지 않았다. 실제 사용자 수정본이 손상됐다는 주장은 아니다.

기존 `_load_edit_version`의 손상 메타데이터 예외 정규화 목록에 두 예외를 추가한다. GUI는 기존 방식으로 이유를 안내하고 이전 결과를 유지한다. 렌더러·글꼴 크기·배치·숫자 문턱은 변경하지 않는다. 새 메타데이터 형식이나 일반 예외 전체 포착을 도입하지 않았다.

실제 재열기 콜백 회귀 검사가 수정 전 AttributeError로 실패했다. 수정 후 두 손상 파일을 열지 않고 안내하며, 이미 저장한 PNG/JSON 바이트·기존 재열기 폴더 목록이 그대로임을 확인했다. 정상 둘째 쪽 수정·저장·재열기·추가 수정·연속 취소 및 기본 PNG/JSON 보존도 통과했다.

before.json의 font_size=무한대/잘못된 색상은 기존 RendererError/ValueError로 이미 GUI에서 안내되는 대조이다. 이번에 새 결함으로 세지 않는다. 자료: before.json, failing-test.log, fixed-test.log, final-tests.log. 소스 핸들러 검사이며 실제 exe 직접 클릭 검증은 아니다.
