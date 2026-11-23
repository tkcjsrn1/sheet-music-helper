# 베타 신고 ZIP 접수·요약

## 9325fa8 친구 피드백 — 받는 곳과 실행 한 줄

친구가 「문제 신고용 저장」으로 만든 ZIP을 아래 폴더에 그대로 넣는다. 폴더는 준비돼 있으며 2026-10-05 준비 시점에 접수된 ZIP은 없다. 원본·ZIP은 Git에 넣지 않는다.

`F:\sheet-music-helper-codex-night-20261004\output\beta-feedback-9325fa8\inbox`

PowerShell에서 다음 한 줄을 실행한다. 매번 새 날짜·시간 폴더를 만들므로 이전 결과를 덮어쓰지 않는다.

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:TEMP='F:\sheet-music-helper-codex-night-20261004\output\tmp'; $env:TMP=$env:TEMP; & 'C:\Users\정혁\Desktop\악보헬퍼\venv\Scripts\python.exe' 'F:\sheet-music-helper-codex-night-20261004\tools\summarize_reports.py' 'F:\sheet-music-helper-codex-night-20261004\output\beta-feedback-9325fa8\inbox' ('F:\sheet-music-helper-codex-night-20261004\output\beta-feedback-9325fa8\runs\' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff'))
```

결과는 `runs\<날짜-시간>\summary.md`와 `summary.json`이다. 현재 소스와 신고 당시의 수치를 나란히 보여 주며 정답 판정은 하지 않는다. 받는 폴더 바로 아래 ZIP만 읽는다. ZIP이 없으면 「신고 ZIP 파일이나 ZIP이 있는 폴더를 지정해 주세요」로 종료하므로 먼저 ZIP을 넣는다. 현재 받은 신고가 있다고 가정한 요약표는 만들지 않았다.

개발 환경에서 실행한다. 친구에게 별도 프로그램을 설치하게 할 필요는 없다. 「문제 신고용 저장」으로 받은 ZIP을 한 폴더에 모은다.

```powershell
$env:PYTHONIOENCODING='utf-8'
venv\Scripts\python.exe tools/summarize_reports.py "받은ZIP폴더" "output/feedback-새날짜"
# 하나만 처리해도 된다
venv\Scripts\python.exe tools/summarize_reports.py "신고.zip" "output/feedback-새이름"
```

출력 폴더는 아직 없어야 한다. 덮어쓰지 않는다. ZIP 폴더의 바로 아래 파일만 이름순으로 처리한다. 하나가 실패해도 다음 ZIP을 계속 처리하며, 실패가 하나라도 있으면 종료 코드1이다(전부 성공이면0).

- `summary.md`: 신고 당시/현재 소스 두 줄씩 요약. 입력 확장자·사진 모드, 가로×세로px, sp 중앙값(최소~최대), 읽은 조표, 검출 보표 수, 라벨 수, check 수, 사용자 수정 수, JSON 차이 행, 오류.
- `summary.json`: 같은 집계 원자료. 저장된 보표 간격 목록, 선언된 dpi, 원래 JSON check 수도 포함한다.
- `001/`, `002/`, …: 기존 `tools/replay_report.py`가 만든 원본·현재 PNG/JSON·로그·전체 차이표. 변환이 실패하면 현재 숫자를 `미확인`으로 남긴다. 원본 검증/요약이 성공한 신고는 `reported_summary.json`에 당시 값을 먼저 남긴다.

## 숫자의 뜻

- **sp는 저장 JSON의 실제 오선 간격(px)**이다. 모든 보표에 값이 있을 때만 중앙값·범위를 낸다. 없으면 미기록이다. JSON의 dpi는 선언값일 뿐 촬영/스캔 해상도의 증명이 아니다. 입력 종류는 확장자와 사진 모드이며, 실제 촬영/스캔/화면 캡처 구분은 피드백 양식에서 확인한다.
- **check는 현재 그림 표시 기준**이다. 사람이 수정한 라벨은 원래 JSON 확신도가 check여도 진한 글씨로 그려지므로 제외한다. `raw_check`에는 원래 확신도 기준 수를 별도로 남긴다.
- **사용자 수정은 `남은 수정 라벨 수 / 수정 동작 수`**다. 동작 수는 삭제·추가·반복 수정도 포함하므로 고친 음표 수와 다르다. 오래된 JSON에 수정 흔적만 있고 동작 기록이 없으면 동작 수를 미기록으로 남긴다.
- 차이0은 현재와 신고 당시 JSON의 일치이며 정답 보장이 아니다. 사람이 고친 값·선택 영역은 현재 자동 인식과 의도적으로 다르다. 차이 행 수를 오삭제/유령/오류율로 읽지 않는다. PNG 바이트 재현은 개인 글꼴·범례 설정이 없어 보장하지 않는다.

ZIP 검증·SHA 확인·설정 적용은 기존 [재현 도구](REPLAY_REPORT.md)를 그대로 사용한다. 파일 네 개의 구조, 경로/중복/암호/크기와 원본 SHA를 검사하고, ZIP 안의 코드나 추가 파일을 실행하지 않는다. 이 도구는 인식 조건을 바꾸지 않는다.

원본에는 저작권/개인 정보가 있을 수 있다. 받은 ZIP과 풀린 원본·결과는 Git에 커밋하지 않는다. 자동 업로드/전송도 하지 않는다. 집계표의 파일 이름·메모도 공유 전에 확인한다. PDF 신고 재현은 PyMuPDF가 있는 소스 개발 환경에서만 지원한다(exe PDF 지원을 추가하지 않음).
