# 손상 신고 ZIP 하나가 전체 접수를 중단시키는 결함

기준 main b9b133e. 자체 네 파일 ZIP의 labels.json 압축 방식 번호만 지원되지 않는 99로 바꾸거나 DEFLATE 내용만 손상했다. 파일명·개수·원본 SHA는 유효하여 기존 입구 검사를 통과한다.

기존 `unpack_report`는 각각 NotImplementedError와 zlib.error를 그대로 내보냈다. 단일 재현/일괄 접수의 기존 안내 오류 목록 밖이므로 도구가 예외로 종료되고 뒤의 신고를 처리하지 못했다. 두 경우 모두 출력 폴더 생성 전 오류였다.

ZIP 읽기 경계에서 이 두 압축 예외만 기존 ValueError 안내로 바꾼다. 경로·중복·암호·크기·SHA 검사와 정상 압축 지원은 그대로다. 일반 예외 전체를 잡거나 정상 신고를 실패로 바꾸지 않았다.

회귀 검사는 실제 ZIP 헤더/압축 데이터를 변경하여 실패를 재현한다. 수정 후 손상 신고 두 개는 각각 실패, 뒤의 정상 신고는 성공으로 summary.json에 남는다. 정상 신고의 현재 인식 subprocess만 고정 JSON으로 대체하고 ZIP 검사·접수 루프·대조·요약 저장은 실제 실행한다. 정상 변환 subprocess 호출 1회, 손상 신고의 폴더 생성 0. 기존 잘못된 설정·경로 탈출·좌표 중복 검사도 통과했다.

자료: before.json, failing-test.log, fixed-test.log, intake-test.log, final-tests.log. 실제 친구 신고나 원본 악보를 사용/커밋하지 않았다. exe를 새로 빌드하지 않았고 이번 변경은 개발용 신고 도구다.
