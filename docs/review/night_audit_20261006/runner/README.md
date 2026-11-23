# 건너뜀을 성공으로 처리한 검사 러너 보완

기준 main `b61b62d`. 제품 코드·인식·판정·골든·selftest 기준 변경 없음.

`run_all.py`는 exit0인 자식 검사가 stdout에 `[건너뜀]`을 쓰면 건너뜀을 세면서도 성공 종료했고, stderr의 같은 표시는 통과로 셌다. 빈 검사 목록도 성공이었다. 실제 `test_clef_start.py`는 원본이 없을 때 `unittest.skipUnless`를 사용하므로 표준 `OK (skipped=1)`도 검출해야 한다.

양쪽 출력을 확인하고, `[건너뜀]` 또는 표준 unittest의 양수 skipped 요약·빈 검사 목록을 종료 코드1로 처리한다. 건너뛴 검사의 이유도 출력한다. 알려진 잔여 결함의 `expectedFailure`는 건너뜀이 아니며 기존처럼 허용한다. 한 자식이 실패해도 다음 검사는 계속 실행한다.

- [기준선 전체 검사](start-tests.log): 실패0·건너뜀0.
- [수정 전 실제 자식 검사](before.log): stdout/stderr 건너뜀·빈 목록에서 성공 종료를 재현했다.
- [표준 unittest 추가 재현](native-before.log): 기존 skip 경로도 성공 종료했다.
- [수정 후 자식 검사](native-after.log): 위 경우와 정상·실패·예상 실패·실패 후 계속 실행을 확인했다.
- [기존 빌드 보호 검사](build-gate.log): 통과. build.py는 이미 건너뜀과 빈 요약을 따로 거부했으므로 이전 빌드가 모두 무검증이었다는 뜻은 아니다.
- [수정 후 전체 검사](final-tests.log): 39/39·실패0·건너뜀0. 정답 골든711·PDF17쪽 스냅샷·기본 GUI PNG/JSON 바이트 보존 검사 통과.

재실행: 저장소 루트에서 `python tests/test_runner.py`, `python tests/run_all.py`.

빌드/Actions를 다시 돌리지 않았다. 테스트 러너 보완은 기존 a200ccd exe의 기능·인식 결과를 바꾸지 않는다. exe/ZIP·원본 악보는 포함하지 않는다.
