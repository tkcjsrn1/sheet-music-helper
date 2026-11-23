# 확인 이유 경량 준비 체크포인트

기준 main `207648024028fe94feacdd3ca3cec9dce4b453ad`. 사용자 지시(10-16): CLI 조바꿈 측정 중이므로 전체검사·빌드·exe 실행 금지. 이번에 실행하지 않았다. 새 이유 단위 검사만 실패→통과 확인했다. 실제 창·전체검사·PNG/JSON 바이트/골든711/PDF17 재검증은 미실행이다.

GUI 제품 변경은 아직 미커밋이며 F: 작업 파일 그대로 보존했다. 규약의 전체검사 후 제품 커밋 원칙 때문에 단위 녹색만으로 병합하지 않는다. 문서/로그만 별도 PR로 올린다. 다음 지시 뒤 최신main 충돌 정리→전체 검사·기본 바이트0·실제 작은 창 안내 확인→제품 PR 순서다.

- 변경: gui.py의 수정 창 생성/선택/새로고침, user_messages.py의 설명, tests/test_review_reasons.py.
- 미커밋 패치: `F:/sheet-music-helper-codex-night-20261004/output/review-reasons-pending-20261016.patch`
- SHA256: `4a43d1ad9fba06998a421f0002ad29206d54261b4f6bb8f5dd6fbfa56cd3bd64`
- 패치는 현재 변경에 중복 적용하지 않는다. 세 파일이 이미 수정돼 있다.
- GUI의 다른 메서드 AST는 기준과 같음. CLI·인식·판정·렌더·재생·JSON·규약·골든 수정 없음. 실제 출력 바이트 동일을 실행으로 확인한 것은 아님.

겹임시표는 docs/DOUBLE_ACCIDENTALS_DESIGN.md 제안뿐이다. 친구 문서는 배포 보류 초안이며 실제4fc3343 ZIP/안내문/해시는 바뀌지 않았다.


## 10-16 후속 제품 검증

CLI #377·#381·#383 병합 및 실제 WORKLOG 「베타 재빌드 가능」 신호를 확인하고, CLI Python0에서 최신 main 위 후보를 검사했다. 전체 종료0·실패0·건너뜀0, 골든711/현재PDF17 유지. Aoharu1·D♭1·바흐1 기본 PNG·JSON6파일 바이트0. 원자료는 docs/review/reasons_20261016/run-all.log, default-bytes.json 및 default-bytes.log다. 비교 기준은 #383이 포함된 최신main이며 이전4fc3343과의 인식변화를 이유GUI의 영향으로 혼동하지 않는다.

합성 라벨로 실제 소스 수정창을 열어 겹임시표+전파 및 빔+글자줄 안내를 확인했다. 줄바꿈이 잘리지 않고 버튼도 창 안에 있다(layout.json·double-source.png·beam-source.png). 원본 악보와 인식 실행은 없으며 이는 실제 exe 클릭 검사와 구분한다. 검사창은 닫았다. 제품 PR에는 GUI/문구/단위 및 이 검증 자료만 넣는다. 새exe 검증은 이후 빌드 단계다. 앞의 미실행·미커밋 문구와 보존패치는 경량 준비 당시의 기록이다.
