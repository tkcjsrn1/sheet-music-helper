# 온음표·2분음표 픽스처 리소스

2026-10-04 사용자 승인으로 PR #51에서 리소스만 분리했다. 인식 코드·과거 측정 원자료·인식 경로 회귀 검사는 가져오지 않는다.

같은 테스트 선율을 LilyPond 2.26.0 / Emmentaler의 보표 크기 16·20·24로 조판했다. 각 판은 피아노 3시스템·6보표·12마디·1쪽, 조표 없음, 온음표12개·2분음표24개다. 높은/낮은 음자리표, 줄·칸·덧줄과 위/아래 기둥을 포함한다.

- `sources/hollow_{16,20,24}.ly`: 음고·길이·마디·기둥 방향의 원본.
- `pdf/hollow_{16,20,24}.pdf`, `.mid`: 조판과 MIDI 리소스.
- `expected_{16,20,24}.json`: 음고·길이·마디는 소스, 머리 좌표는 PDF point-and-click 링크에서 얻은 정답. 소스/PDF SHA-256 포함. PDF 좌상단 point 좌표와 300dpi 머리 중심 좌표를 함께 기록했다.
- `build_fixture.py`: 기존 빔 픽스처의 소스 파서/PDF 링크 추출을 재사용한다. OMR을 호출하지 않는다.

**세 판은 같은 선율의 세 크기다. 서로 다른 폰트3종이나 독립 선율108개가 아니다.** filled/빈 머리 분류, 유령 필터 발동, 오삭제 여부는 이 리소스 검사로 확인하지 않는다. 과거 PR #51 측정을 현재 main의 결과처럼 사용하지 않는다. GHOST_SIDE_THRESHOLD 0.30의 근거로 삼지 않는다.

## 원자료 확인

```powershell
$env:PYTHONIOENCODING='utf-8'
venv\Scripts\python.exe tests/fixtures/hollow_notes/build_fixture.py --check
venv\Scripts\python.exe tests/test_hollow_fixture_resources.py
```

두 명령은 저장 정답·소스/PDF 해시·음고/길이/좌표 링크를 비교한다. 제품 인식 결과는 측정하지 않는다. PDF 읽기에는 개발 환경의 PyMuPDF를 쓰며 exe PDF 지원을 추가하지 않는다.

## 리소스 재생성

LilyPond 2.26.0이 있는 개발 환경에서만 실행한다. 검증 실패를 없애려고 정답을 갱신하지 않는다.

```powershell
venv\Scripts\python.exe tests/fixtures/hollow_notes/build_fixture.py --lilypond <실행파일>
```

소스·PDF와 정답의 음고·좌표는 PR #51에서 보존했고, 소스 해시만 아래 줄바꿈 정정에 따라 갱신했다. 재조판하면 PDF 바이트와 SHA가 달라질 수 있으므로 생성 환경과 원자료 변경을 별도 기록해야 한다.

원래 정답 JSON의 소스 해시는 Windows CRLF 작업 사본 기준이었다. 현재 `.gitattributes`의 LF 소스와 대조해 세 해시만 갱신했다. CRLF로 되돌린 바이트의 해시가 원래 값과 일치하며, 음고·좌표·PDF 해시 등 다른 모든 필드는 그대로다.
