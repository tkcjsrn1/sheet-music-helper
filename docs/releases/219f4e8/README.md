# 지인 베타 후보 — 2026-09-29

빌드 기준: main `219f4e8cfd1839c99eba4d12adc538e4f5b81eeb`, `dirty=false`. PR #97의 300dpi 이하 스캔 권고와 600dpi 입력 한계가 ZIP의 `먼저 읽어주세요.txt`에 포함됐다. 이전 `fdc108b` ZIP에는 이 문구가 없어 배포 후보에서 제외한다. 근거는 [600dpi 측정](../../NORMALIZE_SP_MEASURE.md) §2다. 300dpi 이하 권고는 무오류 보장이 아니다.

| 항목 | 값 |
|---|---|
| exe | `dist/219f4e8cfd18-20260929-162710-453524/악보헬퍼.exe` · 106,271,243바이트 · SHA-256 `F002C25D1F356F84B8A5F4FF131C9AD4D9F1A1CB13AF855E6D07BAAFB4AEFDB0` |
| ZIP | `dist/악보헬퍼-219f4e8cfd18-20260929-162710-453524.zip` · 111,748,681바이트 · SHA-256 `93A352E8C09009F70D7ACD005D60D7E5CD542B7032DC9889626E9FFCF8D68F73` |
| 빌드 | `venv/Scripts/python.exe build.py`, 종료 0 · 전체 테스트 14/14, 건너뜀 0, 실패 0 · 골든 711개 무변경 |

ZIP은 exe, `build-info.json`, `먼저 읽어주세요.txt`, LICENSE, THIRD_PARTY_NOTICES 다섯 파일이다. 동봉 안내문과 저장소 안내문은 바이트 단위로 같다.

동일 입력에서 소스와 exe를 실행했다. RE:Aoharu 1쪽 [결과](aoharu_p1.png)는 라벨 226개(확실 225·주의 1·의심 0), 쇼팽 D♭ 1쪽 [결과](chopin_Db_p1.png)는 240개(확실 208·주의 21·의심 11)다. 두 쪽 모두 RGB 픽셀과 라벨 JSON 전체가 같고, exe JSON을 재렌더링한 이미지도 픽셀 일치했다. 입력·결과 해시는 [검증 기록](verification.json)에 있다. 쇼팽 입력은 원본 PDF 1쪽을 300dpi로 한 번 렌더링한 PNG를 양쪽에 사용했다.

ZIP을 새 폴더에 풀어 `settings.json`·`output`이 없는 상태로 실행했고 exe 옆 output에 PNG·JSON이 생겼다. GUI 사진 모드 [OFF](../../review/photo_mode_off.png)·[ON](../../review/photo_mode_on.png)·[보정 거부](../../review/photo_mode_rejected.png) 화면은 소스 GUI에서 이전에 캡처했다. 안내문 갱신 뒤 최신 main의 소스 GUI에서 세 화면을 다시 캡처했다. 보정 거부 화면은 `PhotoRejectedError` 모의 주입으로 GUI의 안내 경로를 확인한 것이며 실제 사진 판정의 재검증은 아니다.

Python이 없는 별도 PC 실행, 실제 다운로드 뒤 SmartScreen 경고, 두 결과 악보의 사람 눈 판정은 미확인이다. 사용자가 직접 확인한 뒤 배포 여부를 정한다.
