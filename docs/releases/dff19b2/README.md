# A-25·D-3 지인 베타 — 2026-10-04

빌드 기준 **`dff19b286022f736ef9e53bf74bc32abe98114a2`**, #155(A-25)·#153/#159(D-3)·#178(안내문/Actions 기준) 포함, **#167 옥타브 GUI 제외**. 빌드 당시 최신 main을 깨끗한 `codex/beta-a25-d3`에서 공식 `build.py`로 빌드했다. `dirty=false`, 전체 검사27/27·실패0·건너뜀0, 골든711 일치·PDF17쪽 스냅샷 변화0. exe/ZIP은 커밋하지 않았다.

| 파일 | 값 |
|---|---|
| exe | `C:\Users\user\Desktop\악보헬퍼\dist\dff19b286022-20261004-010104-873552\악보헬퍼.exe` · 118598617B |
| exe SHA-256 | `8FD6AA1683D97A7A059457C9C810C29F1A28DAFBD06408E9A0B40F6CE2EFF5A2` |
| ZIP | `C:\Users\user\Desktop\악보헬퍼\dist\악보헬퍼-dff19b286022-20261004-010104-873552.zip` · 124647870B |
| ZIP SHA-256 | `7B91BACF499D45F33F562150A3448D4F224E206B8742EE2C333533DFE235FDAB` |
| Defender | exe/ZIP 각 ScanType3 종료0, 탐지 없음 |
| 엔진 / 정의 / 서비스 | 1.1.26080.3 / 1.459.522.0 / 4.18.26080.4 |

동봉5파일은 exe·build-info.json·먼저 읽어주세요.txt·LICENSE·THIRD_PARTY_NOTICES.txt이며 사용자 dist 복사본과 ZIP 본문이 바이트 일치한다. PyMuPDF는 번들 제외, PDF 입력은 계속 소스 전용이다. [빌드 정보](build-info.json), [파일/해시](artifacts.json), [전체 검사](tests.log), [소스/exe 검증](verification.json), [실행 입력 해시 재확인](unchanged_inputs.json)을 보존했다.

| exe 결과 | 보표 | 라벨 | 확실 / 주의 / 확인 필요 | 소스↔exe JSON·PNG / exe JSON 재렌더링 |
|---|---:|---:|---|---|
| [aoharu_p1](aoharu_p1.png) | 12 | 226 | 225 / 1 / 0 | 모두 일치 |
| [chopin_Db_p1](chopin_Db_p1.png) | 8 | 254 | 208 / 34 / 12 | 모두 일치 |
| [bach_p1](bach_p1.png) | 8 | 184 | 172 / 2 / 10 | 모두 일치 |

세 PNG는 같은 원본 이미지의 실제 exe CLI 출력이다(기본 GUI 범례는 포함하지 않음). 조표 표시는 각각 #2/b5/없음, 오선/음자리표 정보와 JSON 전체가 소스와 같다. 이는 정답률/오삭제 전수 판정이 아니라 빌드 동등성 검사다. check 주황 색 픽셀은 D♭956·바흐732, caution 옅은 색은 Aoharu63·D♭4025·바흐193으로 표시 경로를 확인했다. Aoharu에는 check 표본이 없다.

새 폴더에 ZIP을 풀어 settings.json/output이 없는 상태에서 시작, Python을 PATH에서 제거한 selftest/재렌더링, exe 옆 기본 output 생성을 확인했다. [재현 스크립트](verify_cli.py)는 같은 커밋/원본/폰트의 소스와 exe를 사용한다. 재실행에는 work/clean 경로를 새 폴더로 지정해 기존 결과를 보존한다. 바흐 입력은 저장소 PDF1쪽을300dpi로 렌더한다.

D-3: [수정 전](label_edit/01_before.png) / [수정 중](label_edit/02_editing.png) / [저장 후](label_edit/03_saved.png), [추가](label_edit/04_add_dialog.png)·[추가 결과](label_edit/05_added.png)·[되돌리기](label_edit/06_undo.png). **캡처는 같은 제품 코드의 소스 GUI(PDF 입력)에서 Tk 위젯 자동 검사/Pillow로 얻었다. 실제 exe GUI의 사람 클릭/Computer Use 검증으로 세지 않는다.** source GUI 무편집 PNG/JSON4파일 동일, 확대/스크롤 뒤 클릭 선택·수정·추가·삭제·3회 되돌리기 원본 복귀를 확인했다. exe에서는 [수정 JSON](label_edit/exe_edited_labels.json)을 실제로 재렌더해 [결과](label_edit/exe_edited_result.png)가 소스 및 수동 certain 대조와 픽셀 일치함을 확인했다. 사용자 수정 check의 점선이 사라지고 원래 confidence/pitch는 JSON에 남는다.

[Windows Actions 37135358758](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37135358758)도 **같은 dff19b2**에서 수동1회 실행·성공: 빌드/27개 검사, Python 없는 PATH의 Aoharu·D♭ selftest 및 갱신 기준 JSON 전체 비교 통과. [전체 로그](actions.log), [단계 결과](actions-result.json). 기준은 #178에서 승인된 main73d4d3b의 실제 소스 출력으로 갱신했으며 골든을 바꾸지 않았다. Aoharu는 줄바꿈 정규화 뒤 전체 동일, D♭255→254 및 유지10개 변경; 전후 행/해시는 ../../measurements/beta_a25_selftest_baselines.json.

실패 이력도 보존: 첫 Defender exe 명령은 / 경로로0x80508023·종료2, 같은 파일의 Windows native 경로로 재검사 종료0·탐지0이었다([첫 오류](defender-exe-first-error.log), [성공](defender-exe.log), [ZIP](defender-zip.log), [버전](defender-status.json)). CLI 검증의3쪽/첫 실행 항목은 통과했지만 마지막 D-3 도구 import 경로가 빠져 ModuleNotFoundError가 났다([첫 로그](exe-verification-first.log)). 도구의 root 경로만 고친 뒤 D-3 잔여 검사만 실행해 통과했다([D-3 로그](d3-exe-verification.log)); 제품 수정이나 앞서 통과한 검사 재실행으로 숨기지 않았다.

알려진 한계는 [동봉 안내](먼저%20읽어주세요.txt)에 남겼다. A-25 뒤에도 일부 전파 오류가 남고, A-19·부분화소 G♭·미지원 입력의 예상 실패는 유지된다. 전체 검사 성공을 인식 완성으로 해석하지 않는다. 실제 다운로드 SmartScreen·첫 베타 사용자 PC·exe GUI 직접 확인은 사용자 판정/후속 확인 대상이다. 이번에는 샌드박스/SmartScreen 우회/보안 설정 변경을 하지 않았다. 최종 배포는 사용자 확인 뒤 결정한다.
