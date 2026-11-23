# a9646b4 실제 exe 확인 — 2026-10-15

같은 SHA `A7671CAF5505F70AEC3E8C2EA92118C6438B554CEE67B340B2679ED226C5339F`의 격리 사본. 첫 GUI PID32268, 종료 후 재시작 GUI PID30912. 새 소스/다른 exe로 대신하지 않았다. 인식 설정 변경0, 마지막 입력 폴더만 저장됐다.

| 항목 | 판정 | 근거 |
|---|---|---|
| 계이름 달기 실제 SendInput | 통과 | Aoharu1·2 두 이미지 선택 후 실제 클릭, 결과PNG/JSON2쌍과 합친 PDF 생성 |
| 처리 중 다음 회색 표시 | 관찰 통과 | [처리중](gui_check/processing.png); 실제 비활성 콜백 검사는 소스 회귀 검사와 구분 |
| 완료 뒤 다음 쪽 실제 클릭 | 통과 | [1/2](gui_check/complete-before-next.png)→[2/2](gui_check/after-next.png), 클릭과 같은 초에 첫 캡처 |
| 다음 확인 필요 실제 클릭 | 통과 | [현재 쪽 1/31](gui_check/after-review.png), 라벨 강조·현재 쪽 개수3check/28caution 표시 |
| 둘째 쪽 글씨 수정·저장 | 통과 | [편집 전](gui_check/editor-before.png)→[저장](gui_check/editor-saved.png). D5 「레」→「레#」는 저장 검사용이며 정답 수정이라는 뜻이 아님. 음고D5·원래caution 보존 |
| 종료→새PID→재열기→재저장 | 통과 | [재열기](gui_check/reopened-complete.png)·[편집 창](gui_check/editor-reopened.png), 실제 GUI 재저장 전체327라벨/수정1건/PNG 원래 저장본과 동일([전체 비교](gui_check/reopen-result.json)) |
| 기존 저장 파일 보존 | 통과 | [6파일 SHA](gui_check/saved-file-hashes.json) 재열기·재저장 뒤 불변 |
| 검사 사본 종료 | 통과 | 두 GUI 모두 실제 닫기 클릭, 마지막 Win32 프로세스 목록의 악보헬퍼0개 |

[실제 입력/현재 사각형/창·PID](gui_check/events.jsonl)·[실제 커서 위치/WindowFromPoint](gui_check/guard-events.jsonl). 창이 다른 앱에 가렸거나 옛 좌표가 현재 창 밖이면 SendInput0으로 차단했다. 가려진 시도와 Windows 다중 파일명 형식 오류는 성공에 넣지 않았다. 옛 강조 위치를 클릭해 열린 추가 창은 취소했고 추가 라벨0, 전체327은 유지됐다.

재열기 캐시는 현재 JSON을 따로 쓰지 않고 원본JSON/원본PNG/현재PNG만 쓴다. 검증기의 초기 잘못된 파일명 가정 및 원본JSON을 수정JSON으로 본 가정은 폐기했다. 성공 판정은 실제 GUI 재저장본 전체JSON·수정기록과 새로 렌더한PNG, 기존 저장 해시를 다시 대조한 결과다.

원본 악보가 통째로 보이는 화면은 로컬에만 두고, 저장소에는 UI 표시줄과 편집 창 부분만 넣었다. 실제 exe/ZIP·입력 원본은 커밋하지 않았다. 다른 사용자 앱/프로세스·공유C:/stash/기존빌드는 건드리지 않았다.

미확인: 새 exe N/P·F1 실제 키, 되돌리기 실제 클릭, 실제 다운로드 SmartScreen, 스피커 사람 청취, Python 미설치 사람 PC. 피아노의 실제 배음 녹음은 [1cbc0d8 기록](../1cbc0d8/HUMAN_CHECK.md), 음성 코드 SHA 동일. 새 beta에서 재녹음하지 않았다.

사진 모드 토글·실패 시 사진 재시도 버튼도 이번 새exe 실제 클릭 범위에는 포함하지 않았다. 해당 경로의 소스 회귀 검사와 과거 사람 확인을 새exe 실제 확인으로 바꾸지 않는다.


## 2026-10-15 남은 실제 입력 확인 (04:38:52~04:47:55 KST)

CLI의 flatc1 측정이 49쪽을 마치고 Python 워커가 사라진 것을 확인한 뒤 시작했다. 같은 SHA의 새 격리 사본(부트 PID34408, GUI PID45664)만 실행했으며 9분3초 안에 닫았다. [출처·시간·종료](remaining_20261015/provenance.json)·[실제 입력/창 소유권](remaining_20261015/events.jsonl).

| 항목 | 이번 판정 | 직접 관측 |
|---|---|---|
| N/P 순회 | 미통과·원인 미확정 | Aoharu1에서 실제 N→N→P 뒤 표시 0/2 그대로. 순회 버튼은 실제 클릭하면 1/2로 바뀌었지만 그 뒤 N도 무반응. 입력칸 n 입력은 확인했고 원래 빈 값으로 되돌렸다. 입력칸에서 순회를 막는 것은 정상 사양이므로, 보이지 않는 Tk 내부 포커스와 주입/제품 문제를 분리하기 전에는 제품 결함으로 단정하지 않음. |
| F1 도움말 | 미통과·원인 미확정 | 일반/입력칸/편집 목록 클릭 뒤 VK112와 스캔59 실제 SendInput에도 도움말 창을 찾지 못함. 기존 소스 event_generate 검사를 실제 exe 통과로 대체하지 않음. |
| 기울기 거부→사진 모드로 다시 | **통과** | 직접 만든 합성 보표6개를4° 회전. 일반 모드 거부 뒤 [재시도 버튼 표시](remaining_20261015/normal-refusal.png), 실제 클릭 후 [완료](remaining_20261015/photo-retry.png). 같은 입력으로 PNG/JSON 생성, photo=true·보표6개·라벨48개. 합성에는 음자리표가 없으므로 음고 정답 검사가 아님. [생성 파라미터](remaining_20261015/synthetic.json). |
| 새 exe 피아노 WASAPI 루프백1회 | **통과** | 실제 듣기/중지 클릭, 기본 출력만48kHz·스테레오 녹음. 마이크0·재생 전 다른 출력음 감지0. D6 기본음1175Hz 외2355/3575/4815Hz의 크기가 기본음 대비11.8/6.6/4.7%. 단일 사인파와 다른 배음 구조. |
| 검사 사본 종료 | **통과** | 편집 창과 앱 닫기 실제 클릭 후 악보헬퍼.exe 실행0개. 기존 빌드·다른 앱·공유C:·stash 보존. |

[N 전](remaining_20261015/ready.png)·[첫 N](remaining_20261015/n-first.png)·[둘째 N](remaining_20261015/n-second.png)·[P](remaining_20261015/p-back.png)·[버튼 뒤 N](remaining_20261015/after-button-n.png)·[F1 뒤](remaining_20261015/f1-state.png)·[입력칸 n 대조](remaining_20261015/key-entry.png)·[편집 목록 뒤](remaining_20261015/editor-after-keys.png). 저장소에는 악보 전체가 없는 UI 표시줄/편집창 부분만 남겼다.

새 exe 실제 녹음은 로컬 F:/sheet-music-helper-codex-night-20261004/output/human-a964-remaining-20261015/piano/ 에 보관했다(원래float32: piano_actual_output.wav, PCM16: listen.wav; GitHub 업로드 안 함)·[분석](remaining_20261015/analysis.json)·[WASAPI 패킷 원자료](remaining_20261015/capture.json)·[녹음 스크립트](remaining_20261015/capture_wasapi.py). WAV는 증폭/필터/재표본화 없이 PCM16 변환만 했다. 분석은 원래float32 녹음을 썼다. 사인파 대조는 **전날 실제 녹음을 재사용**했으며, 이번 동시 대조로 쓰지 않는다. [대조 원자료](../1cbc0d8/gui_check_20261014/analysis.json)에서 추가 피크 약0.0066%. 스피커 사람 청취는 미확인이다.

파일 선택에 기존 문자열이 남거나 다른 창이 가린 시도는 오류/입력 차단으로 보존했으며 성공에 넣지 않았다. 제품·판정·골든 수정0, 재빌드/Actions/전체검사 재실행0. 동일 제품 소스의 앞 절 실패0·건너뜀0·골든711/PDF17 결과와 이번 실제 관측을 구분한다. 남긴 것: N/P·F1 무반응 원인 조사, 실제 다운로드 SmartScreen·스피커 사람 청취·Python미설치PC.

자동 승인 검토가 실제 루프백 WAV의 외부 전송을 환경 오디오 위험으로 거부해, 안전한 대안으로 WAV는 로컬에만 두고 수치·해시·UI 부분만 커밋했다. 녹음 성공과 외부 공유 승인은 구분한다.


## 2026-10-15 N/P·F1 원인 확정 및 소스 수정

기존 a9646b4 사본으로 14:00:27~14:04:55 KST 진단: 영문+NumLock ON이면 N/P/F1 모두 미통과, NumLock OFF이면 N→N→P와 F1 통과. 한글+NumLock OFF에서는 N/P 미통과지만 F1 통과. 한글+NumLock ON은 이번 기존 exe 실행에서 별도 측정하지 않았다. [조건별 표·부분 화면·원자료](../../review/ime_shortcuts_20261015/README.md).

원인은 Windows Tk의 NumLock 마스크8을 Alt로 오인한 것과, 한글 IME가 N/P를 keycode229 PROCESSKEY로 먼저 보내는 것 두 가지다. F1은 영문에서도 바인딩 범위가 좁아서 실패한 것이 아니었다. 기존 exe의 OS 포커스/PID는 기록했으나 Tk 내부 위젯 조회는 불가능했고, 같은 코드 소스의 실제 Canvas/Entry 포커스 추적을 별도로 남겼다.

수정 소스는 실제 입력 큐의 단일 N/P만 인정하고 늦은 조합 완료를 다시 순회하지 않는다. 입력칸·Ctrl/Alt 보호 유지, 다른 키 동시 누름은 무시한다. 최종 소스 실제 입력 네 조건과 전체 검사 근거는 위 검증 폴더에 보존한다. **이 릴리스 exe 자체는 바뀌지 않았으며 새 exe 통과로 판정하지 않는다.** 검사 사본은 종료했다.
