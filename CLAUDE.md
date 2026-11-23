# CLAUDE.md — Claude Code를 위한 지침

이 저장소는 **Claude Code와 Codex가 번갈아** 작업한다.
작업 전에 `docs/COLLAB.md`(협업 규약)와 `docs/DECISIONS.md`(결정 기록)를 읽어라.
측정을 시작하기 전에는 `docs/MEASUREMENT_PITFALLS.md`(반복된 측정 실수)를 읽어라.
인식 코드를 건드리기 전에는 `docs/WRONG_DELETIONS.md`(알려진 오삭제 현황)를 읽어라.

---

## 1. 시작할 때 반드시

```bash
git pull
python tests/run_all.py          # 실패 0 · 건너뜀 0이어야 시작한다
```

그리고 **`WORKLOG.md` 맨 아래를 읽어라.** Codex가 뭘 했는지, 나에게 남긴 요청이
있는지 거기 있다. 할 일은 `docs/TASKS.md`의 "Claude 담당" 절에 있다.

`[건너뜀]`이 뜨면 검증용 악보가 없다는 뜻이다. 그 상태로 판정 조건을 건드리지 마라.

---

## 2. 내 담당

검출·판정 알고리즘 전부. 이 파일들은 실측으로 유도된 문턱값을 담고 있고,
그 값을 바꿀 수 있는 것은 나뿐이다.

```
modules/verify.py               유령 판정 조건, 덧줄 검출
modules/notehead_detect.py      음표 머리 검출
modules/clef_keysig.py          음자리표·조표·박자표
modules/accidental_detect.py    임시표
modules/preprocess.py           오선 검출
modules/pitch_calculator.py     음고 계산 (동결 — 확인된 음고 오류는 전부 검출 단계(붙은 화음)에서 생겼고,
                                 음고 계산 자체의 오류는 확인된 것이 없다. docs/OMISSION_RATE.md)
modules/labels_io.py            라벨 JSON 입출력 · 매칭 · 확신도 등급(COLLAB.md 소유 표와 같음, 2026-11-17 사용자 승인으로 목록 보완)
tests/golden/aoharu_*.tsv       정답 골든 (711, 육안 확인됨)
tests/golden/snapshot_pdf_*.tsv PDF 17쪽 변화 감지용 스냅샷 (정답 아님, docs/PDF_SNAPSHOT.md)
tests/test_golden_regression.py
tests/_ledger_check.py
docs/DECISIONS.md
```

### Codex 소유 — 요청받을 때만 건드린다

`gui.py`, `main.py`, `modules/renderer.py`, `modules/note_namer.py`,
`tests/test_*.py`(golden 제외), `tests/run_all.py`, `requirements.txt`,
`악보헬퍼.spec`, `README.md`

**규약 문서는 나도 단독으로 못 고친다** — `docs/COLLAB.md`, `AGENTS.md`, `CLAUDE.md`.
모순을 발견하면 `WORKLOG.md`에 제안을 남기고 사람의 승인을 받는다.
`docs/TASKS.md`는 내 절만 고친다.

파이프라인에 새 필터를 끼워야 해서 `main.py`/`gui.py`를 고쳐야 한다면,
**그 호출 한 줄만** 고치고 `WORKLOG.md`에 적어라. 그 파일의 다른 것은 손대지 않는다.

---

## 3. 판정 조건을 바꿀 때 — 순서를 지켜라

이 프로젝트에서 "그럴듯한데 틀린" 방법을 여러 번 채택했다가 되돌렸다.
전부 아래 순서를 건너뛰어서 생긴 일이다.

1. **`docs/DECISIONS.md`의 기각 목록을 먼저 읽는다.** 하려는 것이 거기 있으면
   이미 실패한 방향이다.
2. **원인을 특정한다.** 고치기 전에, 무엇이 왜 틀렸는지 좌표와 실측값으로 짚는다.
3. **문턱값은 실측 분포나 음악 규칙에서 유도한다.** 눈대중 금지.
   가능하면 두 근거가 독립적으로 같은 지점을 가리키게 한다
   (예: `LEDGER_RUN_SP`는 '머리 폭보다 넓다'와 '정상 최소 1.40 / 유령 최대 1.19 사이'
   둘 다 만족하는 값이다).
4. **두 악보의 여러 쪽에서 잰다.** 한 악보만, 또는 1쪽만 재고 통과라고 하지 마라 —
   기각 3번이 정확히 그렇게 해서 진짜 음표 11개를 지웠다.
5. **지울 후보를 전부 격자로 잘라 눈으로 본다.** 정밀도 숫자만 보면 못 찾는다.
6. **오삭제 목록을 출력한다. 0개여야 한다.**
7. **골든을 돌린다.** 정답 골든(아오하루 711개)은 한 글자도 바뀌면 안 된다.
   PDF 17쪽 **변화 감지용 스냅샷**은 알려진 오류가 든 현재 값이라 바뀌어도 실패가 아니다 —
   바뀐 줄 목록(`debug/snapshot_diff.tsv`)을 육안 판정해 고쳐짐이면 `--update-snapshot`, 오삭제면 되돌린다(`docs/PDF_SNAPSHOT.md`).
8. 유도 근거를 **코드 주석**에 남기고, 채택/기각을 `docs/DECISIONS.md`에 기록한다.

### 절대 조건

**오삭제 0.** 유령은 사용자가 "없는 음이 하나 더 있네" 하고 넘어가지만,
지워진 음은 알아챌 방법이 없다. 의심스러우면 덜 지우는 쪽을 택한다.

---

## 4. 검증 도구

```bash
python tests/run_all.py                              # 전체 (6개)
python tests/test_golden_regression.py               # 골든 대조
python tests/test_golden_regression.py --update      # 정답 골든 갱신 (승인받은 변경일 때만)
python tests/test_golden_regression.py --update-snapshot  # PDF 스냅샷 갱신 (바뀐 줄 판정 뒤)
python tests/_ledger_check.py <악보>                 # 보표 귀속 검증
python main.py <악보> --audit --verify               # 순방향·역방향 점검
```

`verify.diagnose_labels(result, notes)`는 라벨마다 조건별 값을 **판정하지 않고**
기록해 돌려준다. 유형별로 세야 할 때 쓴다 — 조건을 하나로 합치면 무엇부터
고쳐야 할지 알 수 없다.

---

## 5. 작업 마무리

- **커밋은 알아서 한다.** "커밋할까요?"라고 묻지 않는다.
  `run_all.py`가 실패 0 · 건너뜀 0이고 논리 단위 하나가 끝날 때마다 커밋하고 푸시한다.
  테스트가 빨갛거나 측정 결론이 안 난 중간 상태는 커밋하지 않는다.
- **브랜치:** `claude/<주제>` — `main`에 직접 커밋하지 않는다. PR로 올리고,
  검증이 전부 통과하면 머지까지 자동으로 한다.
  **단 아래 둘은 머지 전에 보고하고 승인을 받는다** — 골든 라벨이 바뀌는 변경,
  판정 문턱값 변경.
  **오삭제는 승인 대상이 아니다.** 하나라도 나오면 중단하고 보고한다 — 승인을
  구하는 것이 아니라 그 방향이 틀렸다는 사실을 알리는 것이다.
  승인을 받아도 파일 소유권을 넘어갈 수는 없다.
- **커밋 메시지:** `[claude]` 접두사 + 무엇을 왜 바꿨는지 + 측정 결과

```
[claude] 덧줄 검출을 수평 런 길이로 교체

좌우 띠 비율은 머리 중심 추정에 의존해 쇼팽 5쪽에서 정상 음표 11개를 지웠다.
덧줄은 수평선이므로 그 y에서 런 길이를 잰다.
문턱 1.30sp: 머리 폭 실측(봉우리 1.2sp)보다 넓고, 정상 최소 1.40sp와
유령 최대 1.19sp 사이.

측정: 쇼팽 6쪽 + 바흐 1쪽, 90개 제거, 전부 육안 확인, 오삭제 0
```

- **`WORKLOG.md`에 기록을 추가하고 그 갱신까지 함께 커밋한다.** 푸시한 뒤에 쓰면
  그 기록이 어디에도 남지 않는다. 커밋을 여러 번 했다면 마지막 커밋에 한 번만 넣는다.
  **"남긴 것"은 반드시 쓴다** — 다음 세션이나 Codex가 그것만 읽고 이어받는다.

---

## 6. 이 프로젝트를 쓸 때 유의

- 소스·주석·문서 전부 **한국어**
- venv: `venv\Scripts\python.exe`, 콘솔 출력에 한글이 있으니 `PYTHONIOENCODING=utf-8`
- OpenCV `imwrite`는 한글 경로에서 **조용히 실패한다.**
  `open(path,"wb").write(cv2.imencode(".png", img)[1].tobytes())`를 쓸 것
- 결과 이미지는 경로만 알려주지 말고 **파일이나 아티팩트로 전달한다**
