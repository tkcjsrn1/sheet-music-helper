# 지인 베타 후보 — 2026-09-29

빌드 기준은 main `fdc108bb19eeeaafd0f12124193e61c8c6ae6996`이며 `dirty=false`다. 이전 `7d368fe` ZIP은 exe의 cp949 예외로, `96f8c4e` ZIP은 붙은 화음 안내문이 오래돼 배포 후보에서 제외했다.

빌드 뒤 병합된 PR #94는 측정 문서·도구만 바꿨다. 제품 코드와 동봉 안내문은 이 빌드 기준과 같다.

| 항목 | 값 |
|---|---|
| exe | `dist/fdc108bb19ee-20260929-145151-581570/악보헬퍼.exe` · 106,273,040바이트 · SHA-256 `99D36453B57D6D4B4DADAB53093E555340DD0549CAEE5FECCC0278C262A5BFB0` |
| ZIP | `dist/악보헬퍼-fdc108bb19ee-20260929-145151-581570.zip` · 111,748,347바이트 · SHA-256 `92D264E061F86616A3F46DE65E43135B337FA7A3309A803FF0577E6F4E698600` |
| 빌드 | `venv/Scripts/python.exe build.py`, 종료 0 · 빌드 후 전체 테스트 14/14, 건너뜀 0, 실패 0 · 골든 711개 무변경 · PDF 라이브러리 제외 |

ZIP에는 exe, `build-info.json`, `먼저 읽어주세요.txt`, LICENSE, THIRD_PARTY_NOTICES 다섯 파일이 있다. 동봉 안내문은 사진 모드, 붙은 화음 누락(임시표 유무와 관계없이 약 절반), 꾸밈음 미지원, 확신도 표시와 [오류 제보 양식](../../FEEDBACK_FORM.md)을 설명한다. 이 exe는 스캔 PDF를 직접 열지 못하므로 필요한 쪽을 PNG/JPG로 저장해 넣는다. 붙은 화음 수치의 전체 표본은 [B 측정](../../CHORD_SPLIT_MEASURE.md)의 269/522(52%)이다.

동일 입력·자동 음자리표·고정도·맑은 고딕 18pt·`#dc1414`로 소스와 exe를 실행했다. RE:Aoharu 1쪽 [결과](aoharu_p1.png)는 라벨 226개(확실 225·주의 1·의심 0), 쇼팽 D♭ 1쪽 [결과](chopin_Db_p1.png)는 240개(확실 208·주의 21·의심 11)다. 두 쪽 모두 RGB 픽셀과 라벨 JSON 전체가 같고, exe JSON 재렌더링도 픽셀 일치했다. 입력·결과 해시는 [검증 기록](verification.json)에 있다. 쇼팽 입력은 원본 PDF 1쪽을 제품과 같은 300dpi로 렌더링한 PNG다.

ZIP을 새 폴더에 풀어 `settings.json`·`output`이 없는 상태로 실행했고, exe 옆 output에 PNG와 JSON이 생겼다. [GUI 사진 모드 OFF](../../review/photo_mode_off.png)·[ON](../../review/photo_mode_on.png)·[보정 거부 안내](../../review/photo_mode_rejected.png) 화면은 소스 GUI에서 캡처했다.

Python이 없는 별도 PC 실행, 실제 다운로드 뒤 SmartScreen 경고, 두 결과 악보의 사람 눈 판정은 아직 하지 않았다. 사용자가 직접 확인한 뒤 배포 여부를 정한다.
