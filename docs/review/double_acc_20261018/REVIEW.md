# 소비층 읽기 전용 검토

2026-10-18 독립 검토자 review_double_acc_consumer가 기준 함수 사본·pending-product.patch·현재 두 함수·fixture/신규 검사·설계·CLI_CONNECTION을 읽었다. Critical/Important0. 확정 bb/##의 자연음 기준 ±2/조표 대체, 고정도·영문 철자, 이동도 기존 정책, MIDI 옥타브 경계, 수정텍스트 우선/check 유지가 계약에 맞다고 검토했다.

검토자는 테스트·GUI·빌드를 실행하지 않았다. 전체 검사·기본 PNG/JSON 바이트0은 본 작업자가 CLI 측정 종료 뒤 수행해야 한다. CLI 종류/전파취소/schema2 저장·재열기 연결 미완료는 명시된 후속 의존으로 구분했다.

## 승인된 CLI 종류 API 연결 사본 재검토
2026-10-18 독립 검토자 review_double_acc_wiring가 apply_double_accidentals, 신규 종류 매핑 검사, main/gui 호출 사본을 읽었다. 새 Critical/Important0. 대상 제한·입력 배열과 비대상 튜플 보존·자체 전파 없음, 사진 모드 종류 미적용, 가운데 머리 합류→겹임시표→apply_key_changes 순서와 typed 전부 double_acc/check를 확인했다. #387 구간 key 우선과 자연음 기준 ±2도 충돌하지 않는다.
검토자는 파일 수정·테스트·인식·빌드를 실행하지 않았다. 현 main에 없는 #387 반환 튜플/#388 API 및 조건부schema2 의존이 해결되기 전 호출 사본만 단독 적용하면 실패하므로, 아직 제품에 적용하지 않은 상태다. 실제 악보 회귀·출력 바이트 검증을 대신하지 않는다.