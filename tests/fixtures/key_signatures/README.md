# 15개 조표 생성 악보 픽스처

조표만 바꾼 동일 선율로 조표 인식을 분리해서 확인하기 위한 생성 입력이다. 공개 악보를
가공한 것이 아니라 이 저장소를 위해 직접 생성했으므로 외부 저작권 자료를 포함하지 않는다.

## 구성

- `pdf/`: LilyPond 2.26.0으로 만든 한 쪽짜리 PDF 15개
- `sources/`: 각 PDF의 LilyPond 원본
- `generate_scores.py`: 15개 원본과 manifest를 다시 만들고 선택적으로 PDF도 컴파일
- `manifest.json`: 조별 조표 정답과 파일 대응
- `RESULTS.md`: 2026-08-30 최초 실행 결과

각 악보는 같은 32마디 선율, 4/4박자, 피아노 2단 4시스템으로 구성된다. 조표 정답은
`manifest.json`의 `symbol`, `count`, `letters`에 기록했다.

## 다시 생성하기

LilyPond 2.26.0이 PATH에 있으면 다음 명령으로 `.ly`와 PDF를 모두 다시 만든다.

```powershell
venv\Scripts\python.exe tests\fixtures\key_signatures\generate_scores.py
```

PATH에 없다면 실행 파일을 직접 지정한다.

```powershell
venv\Scripts\python.exe tests\fixtures\key_signatures\generate_scores.py `
  --lilypond C:\path\to\lilypond.exe
```

실행 파일을 찾지 못하면 `.ly`와 `manifest.json`만 갱신한다.

## 알려진 예상 실패

`tests/test_unsupported_scores_xfail.py`에서 다음 두 조건을 예상 실패로 고정한다.

- 올림바장조: ♯6(F/C/G/D/A/E)를 ♯4로 판정
- 올림다장조: ♯7(F/C/G/D/A/E/B)를 전부 읽지 못함

나장조 ♯5의 고정 `6sp` 창 문제는 PR #34에서 간격 기반 스캔으로 고쳤고 정상 회귀
테스트로 바꿨다. ♯6·♯7은 겹친 잉크가 만든 추가 세로막대가 쌍짓기에 끼어드는 별개
문제다. ♭6·♭7은 정상 판정하며 별도 회귀 테스트로 고정했다. 인식 코드를 고치면 두 예상 실패 테스트가
`unexpected success`로 실패하므로 `expectedFailure` 해제를 잊을 수 없다.
