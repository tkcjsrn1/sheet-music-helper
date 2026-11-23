# CLI 연결 계약 — 10-18 사용자 답변 반영

이 PR은 Codex 소유의 표기·재생 소비층을 CLI 연결용 초안으로 공유한다. 사용자는 #388 연결을 승인했으며, 이 소비층 PR은 명시적으로 병합 금지다. 종류를 알려 주는 CLI 코드는 #388에 있지만 현재 main에는 없다. bb/## JSON 입출력은 아직 없다. fixture의 값을 제품 자동 검출 결과로 세지 않는다.

## 입력·순서
- `note_namer.to_solfege_batch(notes, key_letters, key_symbol, accidentals, notation, warnings, tonic)`의 기존 `accidentals` 배열에, 종류가 확정된 음표만 `"bb"`/`"##"`를 넣는다. 음표 순서·길이와 같아야 한다. 기존 #/b/natural/빈 값은 그대로다.
- 현재 `double_acc_suspects()`는 종류 없는 음표 목록이다. `double_acc` flag나 기존 단일 b/#을 보고 종류를 추론하지 않는다. CLI 제안 `double_acc_kinds`가 들어오면 CLI가 직접/전파·취소를 처리한 최종 값을 제공해야 한다.
- main.py의 `notes_with_solfege` 및 gui.py의 `named` 생성/가운데 머리 합류 뒤, **겹임시표 반영 → apply_key_changes** 순서여야 한다. 이름 붙인 뒤 배열만 바꾸면 글씨·재생·JSON이 갈라지므로 해당 값의 표기도 재생성한다. 최종 음표 목록이 다시 만들어지면 예전 인덱스를 재사용하지 않는다.
- 사진 모드/마디 경계/새 ♮·단일·겹임시표 취소는 CLI 판정 계약을 따른다. Codex가 이 PR에서 전파하지 않는다. 기존 double_acc check는 자동 해제하지 않는다.

## JSON — CLI 소유 labels_io.py의 후속 구현 요청
- 쓰기: 최종 label.accidental 필드에 bb/##가 실제로 들어간 파일만 schema2, 그 외는 schema1 그대로. 사용자 수정 text에만 bb/##가 있는 기존 파일은 기존 계약을 유지한다.
- 읽기: schema1과 schema2 지원. 기존 schema1의 label·music·source 바이트를 바꾸지 않는다. 구버전 프로그램은 schema2 파일을 거부해야 한다.
- 현재 SCHEMA_VERSION=1이며 build_document는 항상1을 쓴다. 이 PR에서 labels_io.py를 직접 고치지 않았고, schema2 파일의 제품 저장/재열기는 아직 통과하지 않았다. 이 연결 전 fixture를 제품 JSON으로 만들어 저장하지 않는다.
- 이후 fixture로 조건부 schema/읽기1·2/구버전 거부/수정·재열기·재렌더·MIDI까지 대조한다. 레거시 문서 전체 바이트0, 겹임시표가 있는 문서 안의 비대상 라벨도 전후 행 바이트0을 확인한다.

## 지금 실제로 검사한 것
`tests/fixtures/double_accidentals/typed_inputs.json`은 가짜 유효 임시표 배열이다. D4bb/natural/b/F4##를 소비한 고정도 레bb/레/레b/파##와 MIDI60/62/61/67을 손으로 정한 기대값과 비교한다. JSON 제품 스키마 파일이나 검출 측정 표본이 아니다. 추가 단위는 영문·이동도·조표 비합산·옥타브 경계·사용자 수정 우선·check 제외·미확정 flag 무승격·지원하지 않는 입력 별칭 거부를 본다.

## 병합·빌드 보류 조건
CLI 종류/취소/JSON 코드가 준비되고 실제 스냅샷 변경 행을 판정한 뒤 사용자 승인을 받는다. CLI의 **새 재빌드 신호**가 오기 전 빌드하지 않는다. 10-16의 과거 #377·#381·#383 신호는 이번 겹임시표/조바꿈 듣기 합본 빌드 신호가 아니다.

## CLI 후속 PR을 읽은 결과 (10-18)
- #387은 조바꿈 뒤 구간 조표를 labels[].key로 넘겨 재생에 우선 적용한다. 이 PR의 명시 bb/##는 그 조표에도 더하지 않고 자연음 기준 ±2로 대체해야 한다. 초안 작성 당시에는 #387이 main에 없어 미병합 코드를 가져오지 않았고, 후속 소비층 단독 검증에서는 #387이 병합된 main718abd3을 반영했다.
- #388(e486c79)은 double_acc_kinds(result, contexts, notes) → {음표 번호: ("bb"|"##", "직접"|"전파")}를 제안한다. CLI가 같은 음표 목록을 기준으로 최종 accidentals 배열을 구성하면 현재 fixture 계약과 맞는다. 후보 반환 함수를 Codex가 직접 연결하거나 종류를 추측하지 않는다.
- #388의 CLI 보고는 표기 고침67·새로 틀림9(전부 check), 반대 종류0이다. 이는 CLI 측정 보고이며 이 소비층의 정확도 검증이나 연결 승인으로 대신하지 않는다. 사용자는 이후 #388 연결 준비를 승인했다. 이 측정보고 범위와 실제 연결 후 변화행을 따로 대조하며, 범위 밖 변화는 중단·보고한다. 이 소비층 초안은 병합하지 않는다.
- 조건부 schema2 쓰기·읽기1/2는 여전히 labels_io 소유자인 CLI의 후속 구현이 필요하다. 현 PR을 실제 저장/재열기까지 구현된 겹임시표 지원으로 설명하지 않는다.
## 초안 PR에서 CLI가 가져갈 것
- 제품 변경: modules/note_namer.py의 bb/## 분기와 apply_double_accidentals, modules/label_audio.py의 명시 ±2 분기.
- 함수: apply_double_accidentals(notes, accidentals, named, kinds, key_letters=(), key_symbol="", notation="solfege", tonic="") → (새 accidentals, 새 named). kinds는 #388 반환값을 그대로 받는다. 비어 있으면 기존 배열 객체 그대로 반환한다.
- tests/test_double_accidentals.py와 tests/fixtures/double_accidentals/typed_inputs.json은 소비 계약 검사다. 인식 정확도 측정이나 제품 schema 파일이 아니다.
- [wiring.patch](wiring.patch)는 #387 기준 main/gui 호출 블록 사본이다. 현재 main에 직접 적용하지 않았다. #387/#388 API 반영 뒤 해당 블록만 이식하고 최신 호출 줄을 보존한다. 순서는 가운데 머리 합류 → bb/## 표기 반영 → apply_key_changes이며 typed 대상은 double_acc/check로 표시한다. 사진 모드는 빈 종류 목록이다.
- 조건부schema2, 읽기1·2, 승인된 PDF 스냅샷 변경행은 CLI 소유 범위다. 골든 정답711은 바꾸지 않는다. Codex는 이 PR에서 labels_io/판정/골든 파일을 수정하지 않았다.
- 최신 기준897ded7에 받은 #390의 판정·스냅샷은 기존 upstream 변경이며 이 PR의 소비층 변경이 아니다.

사용자의 최신 지시로 전체 검사 미완료 상태에서도 CLI 연결을 시작할 수 있게 초안을 먼저 올린다. 초안 게시 당시 미완료였던 소비층 단독 run_all·골든711·PDF17·기본 PNG/JSON6바이트 대조는 후속 검증에서 통과했다([검증 근거](standalone/VALIDATION.md), [현재 상태](verification.json)). 실제 종류 연결·schema2·연결 후 실악보 검증은 아직 미완료다. 이전 중단 로그를 성공으로 세지 않는다. 이 PR은 병합 금지이며 새 베타는 CLI가 #387을 병합하고 새 재빌드 신호를 기록한 뒤에만 진행한다.
## 소비층 단독 검증 후 CLI 인계
최신 main718abd3을 반영해 #387 구간 key 우선과 명시±2를 모두 보존했고 전체/정답711/PDF17·기본3입력6파일 바이트0을 확인했다. [검증 근거](standalone/VALIDATION.md). #391은 여전히 draft·병합 금지다. CLI는 이 브랜치의 최신 HEAD를 기준으로 준비된 소비층과 wiring.patch만 연결하고, labels_io 조건부schema2/읽기1·2 및 허용 변화행을 담당한다. 단독 검증이 실제 종류 판정의 정확도를 입증한 것은 아니다. 다음 베타 조건은 실제 CLI의 정확한 「#388·#391 연결 병합 — 베타 재빌드 가능」 기록과 연결 병합이다.