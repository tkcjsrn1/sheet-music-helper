# #397 selftest 기준 5행 갱신

사용자 승인으로 `SELFTEST_DB_CHANGES.json`의 before/after와 정확히 같은 5행만 `tests/fixtures/selftest/chopin_Db_p1.json`에 반영한다. 기준을 실제 출력으로 통째로 덮어쓰지 않았다. 최신 main의 #397·#405·#408 합류 상태에서 소스 selftest 두 쪽을 먼저 순서대로 실행해, D♭은 승인된5행 외 변화0·Aoharu는 변화0을 확인한 뒤 적용했다.

| 보표(0부터) | 좌표 | 음고 | 이전 → 이후 | 확신도 |
|---|---|---|---|---|
| 4 | (1235,2024) | B5 | 시bb → 시b | check 유지 |
| 6 | (2352,2850) | A4 | 라bb → 라b | check 유지 |
| 7 | (1098,2996) | F4 | 파## → 파 | check 유지 |
| 7 | (1340,2996) | F4 | 파## → 파 | check 유지 |
| 7 | (1447,2996) | F4 | 파## → 파 | check 유지 |

A4의 원시 accidental은bb→null이며 최종 「라b」는 조표에서 온다. 「시b」·「라b」 두 유령 라벨을 삭제한 변경이 아니며 check도 그대로다.

라벨262→262·좌표/음고/등급/flags 변화0·schema2 유지·상위문서/순서/그 밖 라벨 불변. Aoharu 기준 파일은 원시바이트/SHA 불변이다. D♭ 파일 기존 EOF(마지막 개행 없음)와 줄바꿈을 유지해, git diff도 승인한5개 accidental/text 쌍(10줄 교체)뿐이다. JSON 비교는 기존 Windows Actions와 같은 CRLF→LF 정규화 후 문자열 전체 일치로 확인하며, Git LF 해시와 Windows 작업파일 해시를 구분했다.

## 실행과 메모리

- 소스 selftest: `python -B gui.py --selftest tests/fixtures/selftest/chopin_Db_p1.png output/selftest-397-20261019/chopin_Db_p1`, Aoharu도 기존 sample_images 원본으로 순서대로 실행. 둘 다 종료0.
- 전체 검사: 47/47 통과 · 실패0 · 건너뜀0 · 종료0. 골든711개와 현재 PDF17쪽 스냅샷 기준 일치(test_golden_regression.py 통과).
- 최근 CLI 메모리 부족 기록 때문에 스냅샷의 ThreadPoolExecutor(4) 실행 수만 임시 런타임에서1로 제한했다. `tests/test_golden_regression.py`·`tests/run_all.py`는 수정하지 않았다. 전 항목·17쪽 map·모든 assert·실패/건너뜀 판정은 그대로 실행한다. 해당 ThreadPool 사용은 제품/검사 소스 중 PDF 스냅샷 한 곳뿐임을 rg로 확인했다.
- F:의 `output/selftest-397-20261019/serial-runtime/sitecustomize.py`는 `SMH_SERIAL_TESTS=1`인 본인 검사 트리에만 `concurrent.futures.ThreadPoolExecutor` 생성자의 max_workers를1로 제한한다. PYTHONPATH·TEMP/TMP·OMP/BLAS 워커1도 그 프로세스 환경에만 지정한다. 다른 CLI/시스템 환경은 바꾸지 않는다. 실제 `_max_workers==1`도 확인했다. 판정·검사 조건을 바꾼 것이 아니다.
- 메모리 검사에서2GiB 미만일 때 시작을 보류했고, 약3.2GiB/다른 Python 실행 없음 확인 후 전체 검사를 시작했다. C: 공유 체크아웃·기존 빌드·stash는 보존했다.

원자료 요약·5행 값·SHA는 SELFTEST_UPDATE_PROOF.json, 전체검사 로그는 SELFTEST_UPDATE_TESTS.log.gz에 보존했다. 제품/판정/골든/규약/다른 fixture 변경은 없다. 새exe/Actions 빌드는 이번 요청 범위에 포함하지 않는다. #407·#412 배치 시안도 이 변경과 섞지 않는다.

## 최종 대조와 범위

- 읽기 전용 독립 검토: Critical/Important 없음. 승인된5행·전체문서 불변·소스2쪽·SHA와 임시워커 제한을 독립 확인했다.
- 검사 뒤 pull한 main 1ba4ac3은 WORKLOG19행만 추가되어 검사 대상 제품/테스트 코드는 동일하다. 원래 CLI 기록은 모두 보존했다.
- SELFTEST_UPDATE_PROOF.json의 source_selftest_before_update는 기준 갱신 전 비교다. D♭의 false는 승인된5행 차이를 뜻하며, 갱신 뒤에는 두 쪽 모두 정규화한 전체 JSON 문자열이 소스 출력과 같다.
- 기본 워커4 병렬 동작은 이번에 재검증하지 않았다. 전체47개 및 PDF17쪽 원래 검사/assert는 워커1로 끝까지 통과했다. 새 exe/Actions·배치 변경은 하지 않는다.
