# 악보헬퍼 v1.0.0

악보 이미지에 계이름을 붙이고, 직접 고치거나 피아노 음색으로 확인할 수 있는 Windows 프로그램입니다.

## 주요 기능

- PNG·JPG를 한 장 또는 여러 장 열 수 있습니다. 여러 쪽 결과를 PNG와 300dpi 합본 PDF로 저장합니다. PDF 악보는 먼저 쪽별 PNG·JPG로 저장해 열어 주세요.
- 계이름을 음표 옆이나 계이름 줄에 표시합니다. 확인 표시를 N/P로 훑으며 계이름을 추가·수정·삭제하고 되돌릴 수 있습니다.
- 선택한 음을 건반에서 확인하고, 시작·끝 음을 지정해 구간을 반복하거나 0.5~1.5배로 들을 수 있습니다. 악보와 건반의 강조 시점은 재생에 맞춰 자동 보정합니다.
- 첫 저장에 필요한 폴더는 자동으로 만듭니다. 같은 원본을 선택하면 앱을 닫은 뒤에도 수정본을 열고 편집을 이어갈 수 있습니다.

## 다운로드 및 실행

1. 아래 **Assets**에서 ZIP과 `SHA256SUMS.txt`를 내려받습니다. 단독 `악보헬퍼.exe`도 있습니다.
2. PowerShell에서 `Get-FileHash -Algorithm SHA256 -LiteralPath '<다운로드한 ZIP 경로>'`를 실행해 해당 파일명의 SHA256과 비교합니다. 단독 EXE를 받았다면 같은 방법으로 EXE의 SHA256을 확인합니다.
3. ZIP 전체를 풀고 `악보헬퍼.exe`를 실행합니다. 「악보 파일 선택」에서 악보를 고르고 「계이름 달기」를 누릅니다. [사용 안내](https://github.com/tkcjsrn1/sheet-music-helper/blob/v1.0.0/USER_GUIDE.md)

SmartScreen 경고가 뜨면 이 릴리스에서 받은 파일인지와 SHA256을 먼저 확인하세요. 해시가 다르거나 백신·장치 정책이 막으면 실행을 중단하고 파일명과 경고 내용을 알려 주세요. [Windows 경고 안내](https://github.com/tkcjsrn1/sheet-music-helper/blob/v1.0.0/SMARTSCREEN.md)

## 알려진 한계

- 밀집 화음, 겹친 성부, 임시표, 음자리표와 조가 바뀌는 구간은 계이름이 빠지거나 틀릴 수 있습니다. 알토 음자리표와 꾸밈음은 지원하지 않습니다. [측정 범위와 정확도](https://github.com/tkcjsrn1/sheet-music-helper/blob/v1.0.0/ACCURACY.md)
- 음높이 확인용 재생은 각 음에 같은 길이를 사용합니다. 음 길이와 쉼표를 반영하지 않으며 스피커·헤드셋에 따라 소리와 강조 사이의 시차가 달라질 수 있습니다.

## 소스와 피드백

MIT 소스는 [v1.0.0 태그](https://github.com/tkcjsrn1/sheet-music-helper/tree/v1.0.0)와 아래 **Source code (zip)**에서 받을 수 있습니다. [제3자 고지](https://github.com/tkcjsrn1/sheet-music-helper/blob/v1.0.0/THIRD_PARTY_NOTICES.txt)

오류와 제안은 악보 종류, 쪽 번호, 기대한 결과를 적어 남겨 주세요. 「문제 신고용 저장」 ZIP에는 원본이 들어가므로 공유할 수 있는 악보인지 먼저 확인하세요. [GitHub Issues](https://github.com/tkcjsrn1/sheet-music-helper/issues) · [피드백 양식](https://github.com/tkcjsrn1/sheet-music-helper/blob/v1.0.0/FEEDBACK_FORM.md)
