# 5d2521d 베타 점검 — 2026-10-04

빌드 커밋 `5d2521d16cbeaaac211fcca4cc5216f396938f6b`(PR#210 병합 이후 최신 main), dirty=false. 파일 선택/변환 버튼 고정·되돌린 라벨 선택을 포함한다. D-3 수정/삭제/추가, D-1 영역 선택, D-2 음높이 듣기는 유지하며 #167은 제외한다. 인식·판정 코드와 골든은 이번 작업에서 변경하지 않았다.

1280×700 소스 GUI에서 파일 선택 y94·변환 y182로 스크롤 없이 보인다. 듣기/신고/라벨 수정 등 결과 도구는 아래 스크롤 영역에 남는다. [수정 전](../cebae18/gui_before_1280x700.png) / [수정 후](../cebae18/gui_after_1280x700.png) / [되돌린 라벨 선택](../cebae18/undo_restored_label.png)은 원본 악보를 제외한 빈 미리보기/합성 라벨 캡처이며 **exe 직접 클릭 화면은 아니다**. 수정/삭제 취소 대상 선택, 원본 JSON 복원, 빠른 목록→입력칸 클릭100회 선택 이동 재현 안 됨을 소스 Tk에서 검사했다.

## 검증

- 공식 build.py의 빌드 후 run_all34/34, 실패0·건너뜀0. 정답 골든711·PDF17쪽 스냅샷 무변경.
- 수정 전/후 기본 GUI 변환: Aoharu1~3/D♭1쪽 PNG와 JSON 모두 바이트 일치(4/4), 기본 인식 설정 변화0.
- 새 exe: 아래4입력 소스/exe의 PNG 픽셀·JSON 전체 일치, exe JSON 재렌더링 픽셀 일치. check 주황/주의 연한 색 픽셀 존재 확인.
- D-3 사용자 수정 JSON의 원래 confidence/pitch 보존. 수정된 check의 exe 그림은 certain과 같은 진한 글씨·점선 제거, 소스 그림과도 픽셀 일치.
- 새 폴더에서 settings.json 없는 CLI 첫 실행, Python 없는 PATH, exe 바로 옆 output 생성, ZIP5파일 확인. fitz/PyMuPDF 제외, exe PDF 직접 입력은 계속 미지원.
- exe/ZIP 각각 Defender ScanType3 종료0·탐지없음. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.543.0. [exe 로그](defender-exe.log), [ZIP 로그](defender-zip.log), [상태](defender-status.json).
- [Windows Actions37181700303](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37181700303): 같은 커밋으로1회 수동 실행, Windows에서 exe 빌드34/34 및 Python 없는 PATH의 Aoharu/D♭ 두 selftest/기준 JSON 전체 비교 통과. 로컬에서 두 기준 JSON을 새 빌드 출력과 다시 대조했으며 내용 변화0이라 파일 갱신은 없었다. 별도 CI 빌드이며 로컬 exe 바이너리와 동일하다는 주장은 하지 않는다.

| 입력 | 악보 줄 | 라벨 | 확실 / 주의 / 확인 필요 | 소스·exe·재렌더링 |
|---|---:|---:|---|---|
| Aoharu1쪽 | 12 | 226 | 225 / 1 / 0 | 일치 |
| 쇼팽 D♭1쪽 | 8 | 254 | 208 / 34 / 12 | 일치 |
| 바흐1쪽 | 8 | 184 | 172 / 2 / 10 | 일치 |
| Verovio Clara1 | 12 | 581 | 356 / 67 / 158 | 일치 |

Clara의 clef_changed144개는 전부 check. 인식 정답을 보장하는 검사와 구분한다. [verification.json](verification.json), [exe 실행 로그](exe-verification.log), [전체 테스트](tests.log), [Actions 기록](actions-result.json), [Actions 로그](actions.log), [빌드 정보](build-info.json)를 보존했다. 실행은 기존 cebae18/verify_cli.py의 빌드/ZIP/출력 경로만 바꾸어 재사용했다. 원본/결과 악보 전체 이미지나 exe/ZIP은 이번 기록에 추가하지 않았다.

## 산출물

- exe: `F:/sheet-music-helper-codex-night-20261004/dist/5d2521d16cbe-20261004-150317-135511/악보헬퍼.exe`
- exe 크기118,650,193바이트(약113MiB).
- exe SHA-256: `D3F978D4EEE1D6D45C182CCB64DE329824DCB6DD4579143CB95FE2D370D9A558`
- ZIP: `F:/sheet-music-helper-codex-night-20261004/dist/악보헬퍼-5d2521d16cbe-20261004-150317-135511.zip`
- ZIP 크기124,710,821바이트.
- ZIP SHA-256: `E8353135FE86375EF4813F8D07BF3854A2A2DB83CE085A1D1A7D440F9AFCC011`

[경로·해시](artifacts.json). 빌드 전 C: 약2.0GiB(2,198,134,784바이트), F: 약221GiB 여유. 산출물/임시 폴더는 F: 사용. 기존 베타와 stash, 공유 C: 체크아웃은 보존했다. 안내문·설정 기본값은 그대로 동봉했다.

## 남긴 것

cebae18 exe 실제 클릭 재시도는 다음 Computer Use 초기화 오류로 중단했다. 여러 이미지 선택·사진 모드·라벨 추가는 자동 직접 클릭 미확인이다. 사용자 수동 확인한 나머지 항목은 이전 [PREFLIGHT](../cebae18/PREFLIGHT.md)에 기록했다. 새 exe에서도 GUI 직접 클릭 통과로 바꾸어 보고하지 않는다. PR#187은 OPEN으로 남겼다.

```
failed to write kernel assets: 지정된 경로를 찾을 수 없습니다. (os error 3)
```

실제 다운로드 SmartScreen·실제 베타 PC·스피커 청취는 기존 사용자 확인 대기 상태다. 목록 선택 이동은 소스100회 재현 안 됨이며 exe에서의 재현 여부는 미확인이다.

## 2026-10-04 사람 PC 직접 확인 완료

사용자가5d2521d exe를 직접 눌러 확인했다: 주요 버튼 고정, 여러 이미지2장 성공2/실패0 및 합친PDF, 빈 곳 클릭으로 라벨 추가(보표·음고·계이름 입력/표시/저장), 추가·삭제 되돌리기와 복원 라벨 선택 유지, 사진 모드 변환 오류없음 및 의도한 범례생략.

cebae18에서 사용자 확인한 변환·조표 머리말·범례·글씨 수정·삭제·영역선택·듣기 시작/중지·신고ZIP과 합쳐 exe 직접 기능 확인을 완료로 기록한다. **사용자의 수동 확인이며 Codex Computer Use 성공 기록은 아니다.** 앞선 미확인 항목은 이 후속 결과로 해소돼 #187을 사용자 승인대로 닫았다.

남긴 것: 실제 스피커 청취와 실제 다운로드 SmartScreen은 미확인이다. 이번 안내는 그 두 항목의 통과를 뜻하지 않는다.
