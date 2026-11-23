# 기존 OMR 도구 실행 가능성 — Audiveris 5.11.0

2026-09-22 설치·출력 확인이다. 정확도와 도구 간 우열은 판정하지 않았다.
악보헬퍼의 modules/·의존성·빌드 코드는 바꾸지 않았고 exe도 빌드하지 않았다.

## 환경

공식 [5.11.0 릴리스](https://github.com/Audiveris/audiveris/releases/tag/5.11.0)(공개일2026-07-11)의
Windows Console MSI를 사용했다. 파일 크기85,062,430바이트, 공식 공개값과 일치한 SHA-256은
`5f1b4e96a12c53c7da426814b76e599363c4181e291855996e0a6878dda95f71`이다.

첫 다운로드는 연결이 끊겼고 GitHub CLI로 다시 받아 해시를 확인했다.
일반 설치 대신 `msiexec /a ... /qn TARGETDIR=...`로 작업 폴더에 풀었다.
파일 추출과 `Audiveris.exe -batch -help`는 각각 종료0이었다.
시작 메뉴 등록이나 일반 설치 마법사는 검증하지 않았다.
실행 환경은 로컬 `output/omr-comparison/runtime/Audiveris/`에 있다.

[공식 설치 안내](https://audiveris.github.io/audiveris/_pages/tutorials/install/binaries/)에 따라
Java 실행 환경은 포함되어 있다. 문자 인식 언어 파일은 별도이며 이번에는 설치하지 않았다.
로그의 `No installed OCR languages`, `Missing support for 'eng'`를 보존했다.
**모든 기능이 구성된 논문용 비교 환경은 아니다.**

## 두 쪽 실행 결과

Aoharu 원본 PNG를 그대로 복사하고 D♭은 기존 `load_image(pdf_page=0)`로300dpi에서
한 번 꺼냈다. 확대·잘라내기·회전·수동 기호 수정은 하지 않았다.
원본/입력 해시는 `measurements/omr_feasibility/provenance.json`에 있다.

```text
Audiveris.exe -batch -transcribe -export -save -output <결과 폴더> -- <aoharu_p1.png> <chopin_Db_p1.png>
```

실행 파일 도움말로 옵션을 확인했다. `-export`는 MusicXML 내보내기,
`-save`는 처리 중 프로젝트 저장이다.
[공식 CLI 안내](https://audiveris.github.io/audiveris/_pages/guides/advanced/cli/)

| 입력 | 크기 | 실제 결과 |
|---|---|---|
| RE:Aoharu1쪽 | 1640×2360 | SCALE에서 간격2px/낮은 해상도 경고, invalid 처리. .omr만 생성, .mxl 없음 |
| 쇼팽D♭1쪽 | 2481×3508 | PAGE까지 진행해 .omr·.mxl 생성. XML 파싱·음 목록 추출 가능 |

배치 전체 종료 코드는 **1**이다. 한 쪽 출력만으로 전체 성공이라고 하지 않는다.
Aoharu의2px는 Audiveris의 판정값이며 실제 원본 오선 간격 측정값이 아니다.
D♭에도 문자 언어 누락, 기호 처리 NullPointerException, 박자 불일치 경고가 남았다.
내보내기와 경고를 함께 기록하며 결과를 정답으로 취급하지 않는다.

## 비교용 추출

D♭의 압축 MusicXML에서 음고가 있는 note243행을 `notes.tsv`로 추출했다.
쉼표를 제외하고 part·measure·note_index·staff·voice·step·alter·octave·chord·grace를 보존한다.
같은 OMR 프로젝트의 머리243개는 id·staff·상대음높이·모양·x/y/w/h를 `heads.tsv`에 따로 저장했다.

**행 수가 같아도 두 목록의 대응을 확인한 것은 아니다.**
OMR 상대음높이를 MusicXML 음이름·옥타브와 혼동하지 않는다.
좌표는 Audiveris 내부 영상 기준이므로 원본과의 변환 관계부터 확인해야 한다.
MusicXML 배치 좌표를 우리 프로그램의 원본 픽셀 좌표와 바로 비교하지 않는다.

나중에 비교하려면 마디·보표·화음 대응과, 우리 쪽의 조표·임시표 적용 후 최종 음고를
MusicXML step/alter/octave와 같은 정의로 맞춰야 한다.
자동 매칭·정확도 계산·최종 계이름 비교는 하지 않았다.
Aoharu는 유효한 음 목록이 없어 **두 악보 모두 비교 가능한 상태는 아니다.**

[공식 내보내기 안내](https://audiveris.github.io/audiveris/_pages/tutorials/quick/export/)처럼
MusicXML은 OMR 프로젝트의 정보를 모두 보존하지 않는다.
원본 .omr와 입력 이미지·MSI는 로컬에만 보존했다.
MusicXML의 다른 편집기 재수입과 스키마 검증은 미실행이다.

## 재현과 남은 일

`tools/export_audiveris_notes.py`는 표준 라이브러리만 사용한다.

```powershell
venv\Scripts\python.exe tools/export_audiveris_notes.py '<D♭ 결과.mxl>' '<D♭ 결과.omr>' output/omr-comparison/extracted
```

실제243/243행 추출 외 작은 대조 입력으로 쉼표 제외, 반음-1/생략 시0, 옥타브·보표·화음·꾸밈음
보존을 확인했다. 음 목록2행/머리1행을 입력해 두 목록을 강제로 매칭하지 않는 것도 확인했다.

논문용 비교 전 문자 인식 언어 등 설치 조건을 고정하고 Aoharu의 SCALE 실패를 별도로 조사한다.
한 도구에만 입력 보정을 적용한 결과를 원본 그대로의 다른 도구와 비교하지 않는다.
이번 결론은 **이 PC에서 실행되며 D♭의 구조화된 출력은 추출할 수 있다**는 확인까지다.
