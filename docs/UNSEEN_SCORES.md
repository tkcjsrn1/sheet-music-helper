# 새 악보 검토 결과 (2026-08-29)

기준 main `990988b528344cfb0ccf912a0e2677712b183824`. 인식·렌더링 코드 변경 없음.

정답·오류율을 판정한 자료가 아니다. 좌표는 축소 미리보기가 아닌 원본 출력 픽셀이다.
`labels.json`은 실행 중 함수 반환값을 관찰한 임시 형식(`observation-labels-v1`)이며 승인 대기인 앱용 라벨 스키마가 아니다. 재불러오기 기능은 구현하지 않았다.

## 조건과 결과

| 결과 폴더 | 확인 조건 | 결과 라벨 / 검출 보표 |
|---|---|---|
| [moonlight-p1](../output/unseen-scores-20260829/moonlight-p1/labels.json) | 2/2(alla breve), 연속 셋잇단음표 | 217 / 8 |
| [moonlight-p2](../output/unseen-scores-20260829/moonlight-p2/labels.json) | 연속 셋잇단음표, 저음부 빈 음표 | 294 / 10 |
| [raindrop-p2](../output/unseen-scores-20260829/raindrop-p2/labels.json) | 27→28마디, D♭장조에서 C♯단조로 조표 변경 | 371 / 10 |
| [raindrop-p3](../output/unseen-scores-20260829/raindrop-p3/labels.json) | 조바꿈 뒤 비교 페이지, 45~66마디 | 392 / 10 |
| [bach-organ-p2](../output/unseen-scores-20260829/bach-organ-p2/labels.json) | 2개 건반+페달: 시스템당 3보표, 4시스템 | 464 / 12 |
| [satie-ogive3](../output/unseen-scores-20260829/satie-ogive3/labels.json) | Très lent, 온음표·2분음표 화음, 마디선 없는 오래된 스캔 | 44 / 1 |

월광과 바흐는 저작권이 만료된 원곡을 새로 조판한 CC 판본이다. 빗방울과 사티는 해당 배포처가 Public Domain으로 표시한 판본이다. 출처·권리 표시는 산출물의 SOURCES.md와 manifest.json에 보존했다.

## 악보 출처

- 월광: [Mutopia 원본과 조판 자료](https://www.mutopiaproject.org/ftp/BeethovenLv/O27/moonlight/), Stewart Holmes, CC BY-SA 2.5. PDF: `moonlight-a4.pdf`.
- 빗방울: [Mutopia 원본과 조판 자료](https://www.mutopiaproject.org/ftp/ChopinFF/O28/Chop-28-15/), Magnus Lewis-Smith, Public Domain. PDF: `Chop-28-15-a4.pdf`.
- 오르간 BWV 639: [Mutopia 원본과 조판 자료](https://www.mutopiaproject.org/ftp/BachJS/BWV639/Ich_ruf_zu_dir2/), Pierre Pouillon, CC BY-SA 3.0. PDF: `Ich_ruf_zu_dir2-a4.pdf`.
- 사티 III: [Wikimedia Commons의 BnF 초판 스캔](https://commons.wikimedia.org/wiki/File:Ogives_%28pour_piano%29_-_btv1b525030386_%2809_of_16%29.jpg), imp. Dupré 1889, Public Domain 표시 확인.

CC 판본은 원곡과 현대 조판의 권리를 구분한다. 결과 이미지의 변경 사항은 계이름 합성이며, 해당 CC BY-SA 조건과 크레딧을 유지한다.
output 링크는 로컬 검토용이다. 새 클론에는 ignore된 산출물이 없으므로 제공된 결과 ZIP을 output에 풀거나 위 원본으로 재실행한다.

## 확인 요청 위치

| ID | 결과 | 좌표 / 범위 | 관찰 (미판정) |
|---|---|---|---|
| M1 | moonlight-p1 | [[1486, 1368], [1516, 1368]] | pp 글자 위에 도# 두 개가 붙어 보인다. 글자와 음표 구분 확인 요청. |
| M2 | moonlight-p1 | [[963, 788]] | 첫 시스템 위쪽 오선·빔 근처에 도# 라벨이 있다. 실제 음표 머리 위치인지 확인 요청. |
| R1 | raindrop-p2 | [[2223, 266], [2294, 276], [2294, 569]] | 첫 시스템 오른쪽의 조표 변경 기호(♮·♯) 자체에 여러 라벨이 붙어 보인다. |
| R2 | raindrop-p2 | [70, 180, 350, 360] | 첫 시스템은 ♭5, 다음 시스템부터 ♯4가 보인다. JSON contexts는 첫 시스템을 포함해 전부 ♯4로 기록됐다. 고정도 결과에서도 조표 적용 확인 요청. |
| B1 | bach-organ-p2 | [[495, 178]] | 첫 보표 조표 기호에 레 라벨이 붙어 보인다. 원본은 ♭4인데 모든 contexts.key_count는 0이다. |
| B2 | bach-organ-p2 | [80, 1890, 450, 2035] | 마지막 시스템 위 보표는 높은음자리표로 보이는데 JSON의 staff 9는 bass다. 3보표 묶음에서 음자리표 귀속 확인 요청. |
| B3 | bach-organ-p2 | [290, 900, 740, 1040] | 중간 보표 아래에서 손가락 번호와 라벨이 겹쳐 보인다. 글자 가독성 확인 요청. |
| S1 | satie-ogive3 | [700, 1010, 2430, 1510] | 첫 시스템 두 보표에 라벨이 없다. 전체 8보표가 보이지만 검출은 1보표(y=2710~2790), 최종 라벨 44개. 완료 메시지만으로 성공 품질을 판단할 수 없다. |

오르간 PDF 첫 쪽은 악보 없는 표지라 `StaffNotFoundError`로 처리되지 않았다. 이 실패는 `bach-organ-cover/labels.json`에 `status=failed`와 빈 labels로 기록했다. 이를 라벨 0개인 성공으로 취급하지 않는다.

## 파일과 재현

- 전체 열람: `output/unseen-scores-20260829/index.html` (파란 상자가 관찰 위치).
- 각 결과 폴더: 원본 PNG, 계이름 PNG, 오선 디버그 PNG, labels.json, run.log.
- 원본 PDF/JPG와 이용 조건: `sources/`. SHA-256과 실행 기준: `manifest.json`, `download-manifest.json`.
- 관찰 목록: `observations.json`. JSON의 observation_index는 이번 실행의 순번이며 영구 ID가 아니다.
- 기존 CLI 재현: `venv\Scripts\python.exe main.py output\unseen-scores-20260829\sources\raindrop.pdf --page 1 --save-source --output-dir output\replay-raindrop`.
- 검토용 JSON 재현: output의 `replay_observation.py`를 개발용 Python으로 실행한다. `sys.setprofile`로 함수 반환값을 읽으며 원본 함수나 판정 상수를 교체하지 않는다.
- 생성 악보·JSON은 output의 ignore 정책을 유지하며 Git에 넣지 않았다. 이 문서와 원본 출처만 저장소 기록으로 남긴다.
- 기존 골든의 정답이나 문턱값은 변경하지 않았다. 새 악보는 골든에 등록하지 않는다.
