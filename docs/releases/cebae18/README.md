# cebae18 야간 베타 — 2026-10-04

빌드 기준 `cebae18ceb7c73949e91b81a766d64b809efb9f8` · dirty=false. 빌드 시작 시 최신 main이며, 이후 올라온 #200·#201은 측정 도구·문서·WORKLOG뿐이다. 런타임 코드 변경은 없다.

포함: #179(오선 봉우리), #181(보표 중간 음자리표 변경 뒤 check), #44(변환 원본/설정 고정), #190(신고 재현 도구), #197(영역 선택), #198(음높이 듣기), #199(안내문). 기존 D-3 라벨 수정·추가 포함. **#167과 #188은 제외**한다. #188은 오삭제1로 병합하지 않았다.

공식 build.py 및 빌드 후 전체 검사31/31, 실패0·건너뜀0. 골든711/PDF17쪽 스냅샷 무변경. Codex의 인식·판정 코드/골든 변경0. Aoharu1·D♭1·바흐1은 이전 dff19b2 JSON 전체·PNG 픽셀과도 같다. 인식이 정확하다는 보장과 구분한다.

| 입력 | 악보 줄 | 라벨 | 확실 / 주의 / 확인 필요 | 소스/exe/재렌더링 |
|---|---:|---:|---|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 | 일치 |
| chopin_Db_p1 | 8 | 254 | 208 / 34 / 12 | 일치 |
| bach_p1 | 8 | 184 | 172 / 2 / 10 | 일치 |
| clef_change_clara1 | 12 | 581 | 356 / 67 / 158 | 일치 |

Clara1 Bravura의 clef_changed 라벨144개는 모두 check. 표시만 바꾸며 음고를 자동으로 고치지는 않는다. PNG·JSON 4세트를 함께 보존했다.

## 산출물

- exe: `F:\sheet-music-helper-codex-night-20261004\dist\cebae18ceb7c-20261004-043144-971094\악보헬퍼.exe`
- exe 크기: 118,646,536바이트. 이전보다47,919바이트 증가(전체 변경 합계, 오디오만의 증가분은 아님). winsound는 원본33,112/압축18,148바이트 포함. 새 패키지 없음, 기존 Python PSF 고지 적용.
- exe SHA-256: `A0C23CBD3CE9B7FDB588AAFC162C184776EDB7F60CFDDBB96FF916DB621B30AD`
- ZIP: `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-cebae18ceb7c-20261004-043144-971094.zip`
- ZIP 크기: 124,703,155바이트.
- ZIP SHA-256: `5D39D8E72C19A387172C510998771FC9F31CD671331AC8B64C8D4D07F58D4053`

exe·ZIP은 Git에 넣지 않았다. ZIP은 exe/build-info/안내문/LICENSE/제3자고지 5파일. PDF 관련 라이브러리는 제외했고 exe PDF 입력은 계속 미지원이다.

## 실행 점검

exe/ZIP Defender ScanType3 종료0·탐지없음. 서비스4.18.26080.4·엔진1.1.26080.3·정의1.459.536.0. 원문 로그와 상태 JSON 첨부.

새 폴더에서 settings 없는 CLI 첫 실행, Python 없는 PATH, exe 옆 output 생성, 4쪽 PNG/JSON 저장·exe 재렌더링 픽셀 일치. D-3 수정 JSON의 원래 confidence/pitch 보존, 수정된 check를 certain과 같은 진한 글씨로 그리는 exe 픽셀 대조도 통과했다.

소스 Tk GUI에서 실제 Canvas 클릭·수정·삭제·추가·3회 되돌리기 및 원본 PNG/JSON 바이트 복귀를 다시 검사했다. label_edit/의 화면6장은 **소스 자동 검사 화면**이다. exe 직접 GUI 자동 조작은 Computer Use 초기화 실패로 미확인(#187). D-1 드래그/전체 복귀·D-2 표준 WAV/Windows API 검증은 각 PR 기록을 참조한다. 스피커 청취는 미확인이다.

[Actions37148263284](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37148263284) 동일 커밋에서1회 수동 실행: exe 빌드31/31 및 Python 없는 PATH의 두 selftest/JSON 전체 비교 통과. 현재 소스에서 selftest 기준을 재계산했으며 두 JSON 내용 변화0이었다. 이는 Python 미설치 실제 PC나 실제 다운로드 SmartScreen 검증은 아니다. CI에서 별도로 빌드한 exe가 이 로컬 ZIP과 바이너리까지 같다고 주장하지 않는다.

빌드 전 C: 약803MiB, F: 약222GiB. 산출물·임시 폴더는 F:를 사용했다. 기존 dff19b2와 stash는 보존했다.

미확인: exe 직접 GUI 전체 기능, 실제 다운로드 SmartScreen, 첫 베타 사용자 PC, 실제 스피커 청취. 알려진 빈 음표 누락·붙은 화음·임시표 전파/조표 오류 등은 안내문대로 남는다. 이번 빌드는 그 한계를 해결했다고 주장하지 않는다.
