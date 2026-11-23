# 개발·테스트·빌드 안내

사용법과 현재 오류율은 [README](../README.md), 미완료 작업은 [TASKS](TASKS.md),
완료한 작업과 검증 이력은 [WORKLOG](../WORKLOG.md)를 참조한다.
이 문서는 개발 환경과 실행 절차만 다룬다.

> **개발에 참여한다면** — 이 저장소는 Claude Code와 Codex가 번갈아 작업합니다.
> 코드를 고치기 전에 [`docs/COLLAB.md`](COLLAB.md)(협업 규약·파일 소유권)와
> [`docs/DECISIONS.md`](DECISIONS.md)(채택·기각된 판정 조건)를 읽어 주세요.
> 이어서 작업할 때는 [`WORKLOG.md`](../WORKLOG.md) 맨 아래부터 봅니다.

## 🛠 개발 및 빌드

배포할 때는 [배포 직전 점검표](RELEASE_CHECKLIST.md)를 먼저 확인한다.
현재 빌드는 임시표 수정 검증 뒤로 보류 중이다.

저장소 루트에서 PowerShell로 실행한다.

```powershell
# 처음 한 번만 환경 구성
py -3.14 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
# PDF 악보를 쓰는 개발 테스트용. 배포 exe에서는 제외한다.
venv\Scripts\python.exe -m pip install PyMuPDF

# 이후 빌드는 이 명령 하나로 실행
$env:PYTHONIOENCODING = 'utf-8'
venv\Scripts\python.exe build.py
```

`build.py`는 수작업 `악보헬퍼.spec`을 변경 없이 사용한다. spec 없이 직접
PyInstaller 옵션을 나열하는 경로는 유지하지 않는다.

1. spec의 `fitz`·`pymupdf` 제외와 customtkinter 수집 설정을 확인한다.
2. Git 기준과 입력 파일 해시를 기록하고 spec으로 클린 빌드한다.
3. **빌드 후 `tests/run_all.py`를 자동 실행한다.** 실패·건너뜀·빈 실행·요약 누락이면 중단한다.
4. 완성 exe의 외부 아카이브·내장 PYZ에서 PyMuPDF 관련 항목이 없는지 검사한다.
5. 빌드 중 소스나 HEAD가 바뀌지 않았는지 확인하고, 검증된 exe와 메타데이터를 ZIP으로 묶는다.

산출물은 `dist/<커밋앞12자리>-<빌드시각>/`에 생성한다:

- `악보헬퍼.exe`: 실행 파일. Windows 속성에 제품명·게시자·`0.1.0` 버전이 들어간다.
- `build-info.json`: **전체 커밋 해시**, 브랜치, dirty 상태, 빌드 시각, 의존성 버전,
  spec·exe·배포 문서 SHA-256, 테스트 결과, 번들 검사 결과, 입력 파일 해시.
- 같은 dist의 `악보헬퍼-<커밋앞12자리>-<빌드시각>.zip`: 위 두 파일과
  `먼저 읽어주세요.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.txt`를 함께 포함한다.

제품 버전 리소스는 `assets/version_info.txt`에서 관리한다. 전체 커밋 해시는 exe 버전과
별도로 `build-info.json`과 ZIP 이름에 기록한다. exe만 따로 옮기면 검증 정보와 사용 안내를
잃으므로 ZIP 또는 폴더 전체를 전달한다. `settings.json`은 개인 설정이므로 배포하지 않는다.

빌드·테스트 로그는 `debug/build-pipeline/<태그>/`에 남는다. 실패한 빌드는
성공 메타데이터·ZIP을 만들지 않는다. 기존 성공 산출물을 덮어쓰지 않도록 실행마다 새 경로를 쓴다.
GUI·악보 결과의 육안 확인은 자동 테스트와 별개이며 배포 전 직접 수행한다.

기본값은 **미커밋 변경이 있으면 빌드하지 않는다**. 새 스크립트를 개발 중일 때만
`venv\Scripts\python.exe build.py --allow-dirty`를 사용할 수 있다.
이 경우 폴더·ZIP 이름과 메타데이터에 dirty가 표시되며 배포용으로 쓰지 않는다.

앱 아이콘은 `assets/make_icon.py`로 생성한다. PyMuPDF는 PDF 개발 테스트에만 설치하며,
배포용 exe에서 제외하는 원칙은 유지한다.


## 공개 배포 시 검토할 것

현재는 가까운 사람에게 검증된 ZIP을 직접 전달하며 exe에 Authenticode 서명이 없다.
공개 배포를 결정하면 아래를 다시 검토한다.

- Authenticode 서명 또는 Microsoft Store 배포 경로
- 고정된 앱 버전 정책과 릴리스 노트
- 공식 다운로드 위치, SHA-256 공개와 이전 릴리스 보관
- `LICENSE`·`THIRD_PARTY_NOTICES.txt` 및 포함 라이브러리의 배포 조건 재검토
- Windows 10/11 새 사용자 계정에서 SmartScreen·Smart App Control·첫 실행 확인

SmartScreen이나 Defender를 끄라고 안내하지 않는다. 사용자는 출처와 SHA-256을 확인한
경우에만 실행하며, 조직 정책이 실행을 막으면 우회하지 않고 관리자에게 확인한다.

## 🧪 테스트

```bash
python tests/run_all.py                  # 전부 실행 (하나라도 실패하면 종료 코드 1)
```

개별 실행도 됩니다:

```bash
python tests/test_preprocess.py          # 오선 검출
python tests/test_pipeline_advanced.py   # 레저선 + 빈/채워진 음표 판별
python tests/test_accidentals.py         # 임시표 검출/지속/초기화 (합성 악보)
python tests/test_naturals_real.py       # ♮ 검출 (실제 악보: 바흐 미뉴에트 PDF)
python tests/test_golden_regression.py   # 골든 회귀 (실제 악보 3쪽 전체)
```

앞의 셋은 합성 악보를 만들어 대조하므로 외부 데이터 없이 돌아갑니다.
뒤의 둘은 `test_scores/`·`sample_images/`의 악보가 필요하고, 없으면 건너뜁니다.

### 골든 회귀 테스트

이 프로젝트에서 회귀가 여러 번 났습니다 — 임시표 규칙을 고치면 검출이 따라 움직이고,
라벨 배치를 고치면 없던 겹침이 생기는 식입니다. 그래서 확정된 결과를 파일로 박아 두고
매번 기계가 대조합니다.

- **라벨** (`tests/golden/aoharu_p*.tsv`): 좌표·음이름·임시표·고정도·이동도 표기까지
  한 글자라도 달라지면 실패합니다. 3쪽 합계 711개.
- **배치 품질**: 좌표까지 고정하지는 않고 넘으면 안 되는 선만 지킵니다 —
  유령 0, 화음 상하 역전 0, 라벨끼리 겹침 0, 음표 머리 가림 0, 음표에서 30px 초과 5개 이하.

의도한 변경이라 결과가 바뀌어야 한다면 이렇게 갱신합니다(그 전에 무엇이 왜 바뀌는지 확인하세요):

```bash
python tests/test_golden_regression.py --update
```

## 🔍 동작 원리

OpenCV 기반의 6단계 파이프라인으로 동작합니다. 딥러닝 모델 없이 고전 컴퓨터 비전만 사용합니다.

| 단계 | 모듈 | 하는 일 |
|---|---|---|
| 1 | `preprocess.py` | 적응형 이진화 → 수평 투영으로 오선 검출 → 5줄 단위 보표 그룹핑 (약하게 찍힌 줄 복구, 화면 UI 잡음 폐기) |
| 2 | `clef_keysig.py` | 보표 헤더 분석: 음자리표 판별(높은음자리표만 보표 아래로 꼬리가 내려오는 성질 이용), 조표 개수 판정(모든 보표의 세로 막대 위치 교차 투표) |
| 3 | `notehead_detect.py` | 오선 제거 후 타원 opening으로 기둥/빔을 지워 채워진 음표 검출, 구멍(hole) 검출로 빈 음표 검출 |
| 4 | `pitch_calculator.py` | 음표 y좌표 ÷ 오선 간격 → 음이름/옥타브 계산 (음자리표별 기준음 적용) |
| 5 | `accidental_detect.py` | 음표 왼쪽의 ♯/♭/♮ 글리프 분류 + 바라인 검출로 마디 내 지속 규칙 적용 |
| 6 | `note_namer.py` + `renderer.py` | 조표/임시표를 반영해 한글 계이름으로 변환, 겹침 회피하며 이미지에 합성 |

### 인식 알고리즘 하이라이트

- **빔으로 묶인 음표**: 단순 윤곽 검출로는 음표 머리가 기둥·빔과 한 덩어리가 되어 놓칩니다. 오선 간격에 비례한 타원 커널로 **모폴로지 opening**을 하면 얇은 기둥/빔만 지워지고 머리만 남습니다.
- **조표 개수 세기**: ♯은 "얇은 세로 막대 2개가 반 칸 간격으로 붙은" 유일한 기호입니다. 조표는 페이지의 모든 보표에서 같은 x 위치에 있으므로, **전체 보표의 막대 위치를 교차 투표**하면 음표 기둥이나 박자표가 만드는 가짜 막대가 걸러집니다.
- **♯ vs ♮ 구분**: 둘 다 세로 막대 2개지만, ♮은 왼쪽 막대가 위로/오른쪽 막대가 아래로 어긋나 있다는 형태 차이로 구분합니다.

## CLI 사용법

개발 환경을 위 절대로 구성한 뒤 소스의 CLI를 실행한다. PDF는 개발용 PyMuPDF가 필요하다.


```bash
python main.py <악보파일> [옵션]

옵션:
  --clef {auto,treble,bass}   음자리표 (기본 auto: 보표별 자동 인식)
  --notation ...              표기 방식
        solfege-fixed         고정도 도레미 (기본, C=도). 옛 이름 solfege와 같음
        solfege-movable       이동도 도레미 (으뜸음=도, 한국 교육과정 기준)
        letter                영문 음이름 (C D E)
  --key D                     이동도 으뜸음 직접 지정 (없으면 조표로 판단)
  --minor                     --key로 준 조성이 단조임을 알림 (--key D --minor)
  --page N                    PDF 페이지 번호 (기본 0 = 첫 페이지)
  --all-pages                 PDF 모든 페이지를 한 번에 (파일명에 _p1, _p2...)
  --font-size N               계이름 글자 크기 (기본 18)
  --color "#dc1414"           계이름 글자 색 (hex)
  --output-dir DIR            결과 저장 폴더
  --no-debug                  오선 검출 디버그 이미지 생략
  --save-source               계이름 얹기 전 원본도 저장 (전수 대조용)
  --save-labels PATH          라벨 JSON 저장 경로 지정 (기본: 결과 이미지 옆)
  --relabel PATH              인식 없이 해당 라벨 JSON으로 다시 렌더링
  --audit                     순방향 점검: 음표로 보이는데 라벨이 없는 자리 표시
  --verify                    역방향 점검: 라벨은 있는데 음표 잉크가 없는 자리 표시
```

`--key`는 `D`, `Bb`, `F#`처럼 C~B 뒤에 `#` 또는 `b`가 최대 하나 붙는 형식만
받는다. 음이름 첫 글자는 대문자로 적는다. 형식이 잘못되면 CLI는 안내를 출력하고
오류로 종료한다. GUI에서는 같은 검사를 입력 즉시 수행해 잘못된 값을
빨간 테두리와 안내 문구로 표시한다.

결과 이미지와 함께 사용자 수정용 라벨 JSON이 항상 저장된다. `--save-labels`를
생략하면 결과 이미지 옆에 저장하고, 경로를 주면 그 위치에 저장한다.
`--all-pages --save-labels labels.json`처럼 여러 페이지와 단일 파일명을 함께 쓰면
덮어쓰지 않고 `labels_p1.json`, `labels_p2.json`처럼 페이지별 파일로 나눈다.

저장한 라벨을 수정한 뒤 다시 그리려면 다음과 같이 실행한다.

```bash
python main.py <원본악보> --relabel labels.json
```

`--relabel`은 JSON에 기록된 원본 해시·이미지 크기·페이지와 지금 연 원본이 다르면
명확한 오류 메시지를 내고 중단한다. 좌표가 맞지 않는 상태로 강제 진행하는 옵션은 없다.

배포용 `악보헬퍼.exe`에도 같은 옵션을 붙일 수 있다. 파일 경로만 주면 GUI에서 열고,
`--save-labels`·`--relabel` 같은 `--` 옵션을 하나라도 주면 위 CLI 경로로 실행한다.
