# 실제 베타 악보 재검사 — 2026-10-06

## 지금 열려 있는 창

읽기 전용 프로세스 조회에서 PID 21372(부모)와 18668(GUI 자식)는 2026-10-05 23:41 KST에 시작한 `29037e2fe602-20261005-211648-214621/악보헬퍼.exe`였다. 두 프로세스 모두 같은 실행 경로다. 최신 베타 창이라는 추정은 틀렸다. 창은 닫지 않았으며 저장하지 않은 수정 내용을 확인하거나 폐기하지 않았다. `running-processes.json`은 실제 조회 결과다.

| 구분 | 빌드 | exe SHA-256 |
|---|---|---|
| 현재 열린 이전 창 | 29037e2fe60229682ccb6fa3f1e3e927a9a306cd | 92A7E48EAADF1A71DCBC1BB4D8360F65169875446D99DE32C1236BA226CDBD7B |
| 이번 실제 재검사 | 87de5d51201bf49c313f78ecf34ea48c37847836 | 20E3776E3067A17D3B236601756189C685836B62F6DA43D00E44F0AF82B9CFE6 |

수정본 경로는 `F:/sheet-music-helper-codex-night-20261004/dist/87de5d51201b-20261006-081301-618209/악보헬퍼.exe`. 수정 내용을 저장한 뒤 이전 창을 닫고 이 파일을 열어 **원본 악보를 다시 변환**해야 한다. 이미 저장한 이전 결과 PNG가 자동으로 고쳐지지는 않는다.

## 재검사 범위와 결과

현재 소스 main `d0194dac9624997d68bb68781f4e9820f3b8bbca`는 빌드 기준 이후 릴리스 문서만 바뀐 상태다. 실제 최종 ZIP을 새 한글 폴더에 풀고 exe 해시를 검증했다. Python 없는 PATH·빈 PYTHONPATH·settings.json 없는 상태에서 exe의 --selftest를 실행했다. 소스도 같은 입력을 현재 run_page로 새로 처리했다. 제품 함수를 사본으로 바꾸거나 모형 결과로 대체하지 않았다.

| 대상 | 이번 결과 |
|---|---|
| 기존 실제 악보 20쪽 | 소스/exe 전체 JSON·PNG 바이트·화소, 수정 후 기준과 일치 |
| 추가 악보 9쪽 | 같은 대조 일치 |
| Verovio 20쪽 | 같은 대조 일치 |
| Beethoven Bravura·Leipzig 원본 | 각각 라벨223; 첫4보표 조표·3/4 기호 영역 라벨0; 첫 실제 F4/파 각각2개 유지 |
| x0.25px | 소스/exe 일치, 기호 라벨0, 첫 F4/파 2개 유지 |
| x0.5px | **최종 음고 보존 실패**: 첫 보표 F4/파 → E4/미. 기호 라벨은0 |
| x0.75px / y0.5px / xy0.5px | 이번 묶음에서는 미실행: x0.5 실패에서 중단 |
| tests/run_all.py | 39/39·실패0·건너뜀0, 골든711·PDF17쪽 스냅샷·#52 통과 |

54조건을 계획했으나 **50조건 통과, 51번째 실패, 나머지3 미실행**이다. report.json의 cases는 통과한50조건이며 실패 조건은 failure.json에 별도로 보존했다. 일반 회귀 일치가 기존 모든 라벨의 음악적 정답을 보증하지 않는다. 기존 알토 미지원·누락·유령도 기준에 포함된다.

PDF17쪽은 소스 전처리의 300dpi 결과를 무손실 PNG로 옮겨 exe에 넣었다. PDF 입력과 수정 후 기준의 원본 SHA·쪽 번호를 검증했고, 기준 JSON 대조에서 PDF→PNG로 달라지는 source.file/page/sha256 3항목만 원래 식별로 되돌렸다. 이미지 크기·dpi·라벨·조표·음자리표는 제외하지 않았다. 소스/exe 상호 대조는 이 정규화 없이 전체 JSON 그대로 비교했다. exe PDF 지원을 주장하지 않는다.

원본 두 조판의 actual exe PNG 부분은 `beethoven_op18no1_*_header_detail.png`로 확인할 수 있다. 두 그림은 원본 재검사 결과의 일부이며, 전체 악보·exe·ZIP은 커밋하지 않았다.

## 별도 결함: 수평 재표본화 뒤 음고가 바뀜

Beethoven Bravura 첫 보표는 원본 `(406,243)` F4/파 → x0.25 `(407,243)` F4/파 → x0.5 `(407,244)` E4/미가 된다. 둘째 보표 첫 F4/파는 유지된다. x0.5에서 라벨이 지워진 것은 아니며, 조표는 그대로 ♭1(B), 보표0의 줄/spacing/기준선도 같다. 해당 라벨은 caution이며 vertical_blocked·snap_residual 신호가 있다. **소스와 exe 모두 같은 오류**다.

grid_bottom=248, spacing=18 조건에서 y243→244는 `(248-y)/9`가 약0.556→0.444로 바뀌어 step1→0이 되는 것과 일치한다. 수평 변환인데 머리 y가1px 움직였다는 관측이며, 어떤 검출 분기가 중심을 이동시켰는지의 전체 원인 추적은 아직 하지 않았다. 음고 문턱이나 좌표를 임의로 고치지 않았다.

기존 test_header_symbols.py의 원본 두 조판 검사는 최종 F4/파까지 본다. 부분화소 검사는 머리 검출 단계의 존재·기호 영역만 본다. 따라서 기존 전체 검사가 녹색이어도 최종 음고 오류를 놓칠 수 있다. **3/4 기호 유령 재발과 별개**로 소유자에게 넘긴다. 검사 기대값을 E4로 낮추거나 실패를 숨겨 통과시킬 수 없다.

phase-controls.json은 5입력 모두 실제 cv2.warpAffine INTER_LINEAR/흰 테두리와 화소 일치, 원본과 화소 차이가 있음을 확인한 결과다. 세 미실행 조건의 변환 검증은 인식 검사를 실행한 것과 다르다.

### 최소 재현

저장소 루트의 venv Python에서 아래로 실제0.5px 변환을 만들고 현재 CLI 또는 실제 exe로 처리한다. 임시 위치는 F: 출력 폴더이며 원본은 변경하지 않는다.

```python
from pathlib import Path
import cv2, numpy as np
from modules.preprocess import preprocess
p = Path('test_scores/verovio/beethoven_op18no1_bravura_p1.png')
bgr = preprocess(str(p)).original_bgr
shift = cv2.warpAffine(bgr, np.float32([[1,0,0.5],[0,1,0]]),
                      (bgr.shape[1],bgr.shape[0]),
                      flags=cv2.INTER_LINEAR, borderValue=(255,255,255))
assert not np.array_equal(bgr,shift)
out = Path('output/phase-pitch-repro'); out.mkdir(parents=True,exist_ok=True)
cv2.imencode('.png',shift)[1].tofile(str(out/'phase.png'))
```

```powershell
python main.py output/phase-pitch-repro/phase.png --no-debug --output-dir output/phase-pitch-repro/source
& 'F:/sheet-music-helper-codex-night-20261004/dist/87de5d51201b-20261006-081301-618209/악보헬퍼.exe' --selftest output/phase-pitch-repro/phase.png output/phase-pitch-repro/exe
```

결과 JSON에서 staff=0, x400~415의 라벨이 F4/파여야 하지만 E4/미로 나온다. 문자열뿐 아니라 pitch와 step을 함께 확인한다.

실제로 실행한 전체 대상 스크립트를 recheck_exe.py / inspect_inputs.py에 보존했다. 기존 출력 장소가 있으면 재실행을 거부하는 가드가 있다. 다른 출력 장소로 변경하고 입력 목록을 만든 뒤 사용한다. 원자료·과거 로컬 기준 경로는 측정 당시 F: 체크아웃을 가리킨다.

## 남긴 것

인식 코드·정답·selftest 기준·GUI 변경0. 새 빌드/Actions/Defender 중복 실행 없음. 이번 별도 음고 결함은 Claude 소유 검출/음고 경로의 조사 요청이며 수정을 채택한 것이 아니다. 최신 베타 GUI 직접클릭·스피커·실제 다운로드 SmartScreen 미확인 유지.
