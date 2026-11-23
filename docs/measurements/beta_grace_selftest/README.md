# 꾸밈음 병합 뒤 Actions 기준 갱신

2026-10-05 실제 실행 · 기준 소스7d84fc5. CLI의 「꾸밈음 표시 병합됨」(#241), 음자리표 검색시작#254·문턱/겹침#253, 흐린 인쇄 구제#257이 main에 있는 것을 확인했다.

소스 GUI --selftest를 Actions의 동일 PNG 두 입력으로 실행했다. Aoharu1 JSON 내용은 동일하며 기존 기준 파일은 줄바꿈까지 보존했다(생성 사본의 파일 해시 차이는 줄바꿈 차이). D♭1은255라벨 그대로·추가0·삭제0·표기변화0·확신도9곳 변화이며, 전후 전체 JSON과 조표/음자리표/사유를 포함한 변경 행·입력 SHA는 여기 보존한다. selftest 기준은 인식환경 일치 비교용이며 정답골든711이나 정답률이 아니다. tests/golden을 Codex가 갱신하지 않았다.

갱신 명령: `python gui.py --selftest tests/fixtures/selftest/chopin_Db_p1.png output/beta-grace-preparation/chopin_Db_p1`. 생성된 JSON으로 tests/fixtures/selftest/chopin_Db_p1.json만 교체했다. Aoharu 기준은 변경0. 실제 실행 로그·PNG/원자료는 F: output에 있으며 원본 악보/ZIP은 커밋하지 않는다.
