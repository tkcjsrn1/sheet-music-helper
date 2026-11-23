# 입력 실패와 부분 처리 기록


## 2026-09-18 당시 우선순위·재현 범위 정정

2026-10-02 상태: 조표 수정 #136과 사진 M1 #83은 병합됐다. 아래는 당시 기록이며 현재 개발·빌드 보류 지시가 아니다. 최신 구현·제한은 [KEYSIG_VOTE_FIX](KEYSIG_VOTE_FIX.md)와 [PHOTO_PREPROCESS](PHOTO_PREPROCESS.md)를 참조한다.

**C-11 조표 위상 민감도 → C-10 기울기 보정 순서다.** 재표본화로 조표가 먼저 바뀔 수 있어 안전 각도나 .21~.25sp 이하 통과 기준은 폐기한다. 조표·음자리표·최종 표기 비교와 음표별 원본 정답 대조가 필요하다.

아래 바흐197→130·0.42~0.49sp 등은 과거 CLI 전달 기록이다. **main/PR #52 단독 체크아웃에서는 관련 도구가 없어 재현 불가이며 이번에 다시 검증하지 않았다.** 이 PC에서 과거 도구·문서의 별도 브랜치를 찾았으며 [정확한 출처와 한계](C11_PHASE_SCOPE.md)에 기록했다. 아래 과거의 “기울기 보정 최우선”은 현재 우선순위가 아니다. 보표 회복을 조표·음표 보존으로 확대하지 않는다.


과거 600dpi 기록: 2026-08-29, main `990988b528344cfb0ccf912a0e2677712b183824`. 인식 코드 변경 없음.

사용자가 제보한 600dpi 실패를 기존 PDF로 재현했다. 전체 인식 품질 판정이 아니라 기존 `preprocess(path, pdf_page=..., pdf_dpi=...)` 호출의 성공 여부와 보표 수만 확인했다.

## 작은 기울기에서의 조용한 부분 실패 — 최우선 (CLI 2026-09-11, 반영 2026-09-14)

**5°가 실패 한계가 아니다. 0.2°에서 이미 오선 검출이 무너지고, 0.15°에서도
예외 없이 일부를 잃는다.**

- 바흐 미뉴에트 1쪽, 폭 2481px·sp=20.8px: 0.15°에서 밀림 약 6.5px=0.31sp,
  **후보 197→130(67개·약 34% 감소), 예외 없이 정상 완료**.
- 같은 바흐는 0.20°에서 밀림 8.7px=0.42sp로 오선 검출 실패.
  쇼팽 B♭m 1쪽과 RE:Aoharu 화면 캡처도 시험 격자에서 첫 실패가 0.20°였다.
- CLI의 세 표본에서 실패 밀림은 약 **0.45sp(0.42~0.49sp)**다. 각도 자체가 아닌
  **오선 길이에 걸친 세로 밀림**이 핵심이다. `Δy/sp = L × tan(|θ|) / sp`로 기록하며,
  이번 도구는 L 대신 처리 영상 폭을 사용한 근사다.
- **0.45sp는 안전 문턱이 아니다.** 0.31sp에서 이미 후보가 줄었고,
  0.15°가 예외 없이 끝났다는 사실도 완전한 처리를 뜻하지 않는다.

197·130은 `measure_photo_robustness.py`가 출력한 `라벨(삭제 전)` 값이다.
빔·오선 밖 필터 후, 임시표 유령 삭제 전 후보 수이며 최종 렌더링 라벨 수가 아니다.
67개를 모두 실제 음표 오삭제로 개별 확정한 수치로 확장하지 않는다.
각도·폭·sp 표와 해석은 [PORTABILITY의 작은 기울기 재측정](PORTABILITY.md)에 있다.

측정 출처는 Claude CLI의 `def6a5b`이며, 그 브랜치에서 다음처럼 재현한다.
페이지 인자는 0부터다. 원본의 합성 회전이고 실제 휴대전화 사진 분포 검증은 아니다.

```powershell
venv\Scripts\python.exe tools/measure_photo_robustness.py tilt test_scores/bach_minuet_Am.pdf 0
```

앱 착수 전 [TASKS C-10](TASKS.md)의 **기울기 보정 및 보정 후 개별 음표 보존 검증**이
최우선이다. 이번 변경은 수치·우선순위 기록이며 전처리 코드는 아직 수정하지 않았다.

## 과거 실패·부분 처리 목록 (2026-08-29)

| 입력 / 조건 | 관찰 | 재현 상태 |
|---|---|---|
| 바흐 미뉴에트 가단조 PDF 첫 쪽, 600dpi | 오선 후보는 있으나 5줄 보표로 그룹핑하지 못해 `StaffNotFoundError` | 재현됨. 같은 PDF 300dpi에서는 보표 8개 |
| BWV 639 공개 PDF 첫 쪽 | 악보 없는 표지의 오선 후보 2개만 검출, 최소 4개 미달로 `StaffNotFoundError` | 재현됨. 음악이 시작되는 PDF 2쪽은 처리됨 |
| 사티 오지브 III 초판 JPG, 3654×4436 | 예외 없이 종료되지만 화면의 8보표 중 1개만 검출, 라벨 44개 | 부분 처리 관찰. 스캔의 기울기·여백·잉크 품질 등이 섞여 있으며 원인은 특정하지 않음 |
| 쇼팽 D♭ 5쪽 300/600dpi | 전처리는 둘 다 성공하지만 보표 수가 10→9로 달라짐 | 추가 육안 확인 필요. 어느 쪽이 정답인지 판정하지 않음 |

600dpi 자체가 모든 PDF에서 실패하는 것은 아니다. 아래 비교에서 쇼팽 세 종의 첫 쪽은 두 dpi 모두 전처리를 마쳤다.

## 비교 기록

| 입력 | 페이지(1부터) | dpi | 픽셀 크기 | 전처리 결과 | 보표 수 |
|---|---:|---:|---|---|---:|
| bach_minuet_Am.pdf | 1 | 300 | [2481, 3508] | preprocess_success | 8 |
| bach_minuet_Am.pdf | 1 | 600 | [4961, 7016] | failed | — |
| chopin_nocturne_Bbm.pdf | 1 | 300 | [2480, 3509] | preprocess_success | 8 |
| chopin_nocturne_Bbm.pdf | 1 | 600 | [4959, 7017] | preprocess_success | 8 |
| chopin_nocturne_Db_6-8.pdf | 1 | 300 | [2481, 3508] | preprocess_success | 8 |
| chopin_nocturne_Db_6-8.pdf | 1 | 600 | [4961, 7016] | preprocess_success | 8 |
| chopin_nocturne_Em.pdf | 1 | 300 | [2550, 3300] | preprocess_success | 10 |
| chopin_nocturne_Em.pdf | 1 | 600 | [5100, 6600] | preprocess_success | 10 |
| chopin_nocturne_Db_6-8.pdf | 5 | 300 | [2481, 3508] | preprocess_success | 10 |
| chopin_nocturne_Db_6-8.pdf | 5 | 600 | [4961, 7016] | preprocess_success | 9 |

## 증거와 재현

- `output/failure-cases-20260829/reproduction.json`: 입력 SHA-256·페이지·dpi·실제 예외 클래스·메시지·트레이스백.
- 같은 폴더의 `bach_minuet_Am-p1-600dpi.png`: 실패를 재현한 600dpi 래스터 입력. 상업 검증 악보이므로 공개 배포하지 않는다.
- `output/unseen-scores-20260829/bach-organ-cover/`: 표지 실패 로그와 실패 상태 JSON.
- `output/unseen-scores-20260829/satie-ogive3/`: 부분 처리 결과·오선 디버그·라벨 JSON.
- 600dpi 비교는 기존 함수의 공개 인자로만 실행했고 min_line_ratio·기울기·문턱값 등을 바꾸지 않았다.
- 일반 CLI는 PDF를 기본 300dpi로 읽는다. 원본 PDF의 내장 스캔 해상도와 `pdf_dpi=600`으로 다시 래스터화하는 것은 서로 다른 조건이다.
- 재현 코드: `from modules.preprocess import preprocess; preprocess("test_scores/bach_minuet_Am.pdf", pdf_page=0, pdf_dpi=600)`.
- 실행 환경은 개발용 Python 3.14.0 / PyMuPDF 1.28.2. 배포 exe의 PDF 미지원은 별도의 의도된 제한이다.

## 다음 담당자에게

이 목록은 관찰과 재현 결과만 담는다. 현재 역할은 개발 Codex·독립 검증/측정 Claude CLI다. 기울기 보정은 C-10으로 추적하고 기존 골든 기준은 변경하지 않는다.
현재 검증 오류율은 [README](../README.md#검증된-조건)에서만 관리한다.
