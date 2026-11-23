# Windows Actions 자체 점검 — 2026-09-30

[수동 실행 36677330676](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/36677330676)은 **실패**했다. `windows-latest` 체크아웃·Python 3.14.0 준비·고정 의존성 설치는 통과했다. `python build.py`가 첫 한국어 로그를 출력할 때 러너의 기본 `cp1252`에서 `UnicodeEncodeError`가 나서 종료 코드 1로 멈췄다. PyInstaller 빌드와 Python을 PATH에서 제거한 exe 자체 점검은 **실행되지 않았다**. 따라서 GitHub-hosted Windows에서 두 JSON이 일치하는지는 미확인이다.

로컬에서는 같은 고정 자료로 Python을 PATH에서 제거하고 Aoharu 1쪽·쇼팽 D♭ 1쪽을 exe `--selftest`로 실행해 두 JSON이 기준과 일치했다. 이것은 GitHub-hosted Windows 통과로 세지 않는다.

후속 PR #119는 워크플로에 `PYTHONIOENCODING=utf-8`을 추가한다. 사용자가 #119를 병합한 뒤 Actions를 다시 실행해 결과를 기록한다. 현재 판정은 **CI 미통과**이며 재실행 결과는 아직 없다.


## 2026-10-02 #119 병합 후 수동 실행

기준 main `8f15231c3cc19af0b21711acbb7af1e1d2d11d0e`, [런 37000973523](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37000973523), 한국 시간 20:26 시작. 같은 커밋의 중복 실행은 하지 않았다.

| 단계 | 결과 |
|---|---|
| 체크아웃·Python 3.14.0·의존성 설치 | 통과 |
| UTF-8 로그·PyInstaller exe 생성 | 통과 (이전 cp1252 오류 해결) |
| build.py의 전체 검사 | 19/20, 건너뜀0, test_beam_fixture.py 오류1로 패키징 중단 |
| 골든 회귀 검사 | 통과 (711·PDF17쪽 스냅샷 유지) |
| Python 없는 PATH의 Aoharu/D♭ selftest·JSON 비교 | 미실행 — 앞 단계 실패로 건너뜀 |

전체 CI는 **실패**다. 빔 픽스처 오류의 전체 traceback은 기존 러너 출력에 잘려 있었으므로 SHA 원인은 환경 차이 재현으로 확인했다. `core.autocrlf=true` 체크아웃에서 .ly만 CRLF가 되어 저장 정답과 `source_sha256`만 달라졌고, `.gitattributes`의 `*.ly text eol=lf` 적용 후 같은 체크아웃 해시가 정답 `0ba98905c4af8019d87c1f0ed258d8b0a5cfae78f8e0b2af63046b525ee8c7fa`와 일치했다. 정답·소스·PDF는 재생성하지 않았다.

후속에서는 LF를 고정하고 빔 소스/PDF 링크 사전 검사를 빌드 전에 직접 실행해, 같은 오류가 남으면 전체 traceback을 남긴다. 수정 커밋의 재실행 결과는 아래에 별도로 추가한다. 이 실패 런을 Windows selftest 통과로 쓰지 않는다.

보존 기록: #144 측정 문서 병합으로 #145가 충돌한 상태에서 수정 전 main `7297308`으로 런 37002462418이 시작되어 즉시 취소했다. LF 수정 검증이나 성공으로 세지 않는다. 수정 PR 병합을 확인한 다음 새 커밋으로만 실행한다.


## 2026-10-02 LF 보존 수정 후 최종 수동 실행 — 통과

기준 main `19919fe7068f8dbd896ff2a71111d172ca905a91` (#119·#145 포함), [런 37003109488](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37003109488). 한국 시간 20:49~20:55, windows-latest·Python 3.14.0. 해당 커밋은 한 번만 실행했다.

| 단계 | 결과 |
|---|---|
| 빔 픽스처 소스/PDF 링크 사전 검사 | 통과 — Windows에서도 .ly LF 해시 유지 |
| PyInstaller exe·ZIP 생성 / 전체 검사 | 통과 · 20/20, 실패0·건너뜀0 |
| 정답 골든711 / PDF17쪽 스냅샷 | 무변경 |
| Python 없는 PATH, Aoharu 1쪽 --selftest | 종료0 · PNG/JSON 생성 · c8504e2 기준 JSON 전체 일치 |
| Python 없는 PATH, D♭ 1쪽 300dpi --selftest | 종료0 · PNG/JSON 생성 · c8504e2 기준 JSON 전체 일치 |

PATH는 Windows/System32만 남겼고 Get-Command python이 실패함을 확인했다. 이는 개발 venv 경로에 기대지 않는 GitHub-hosted Windows 실행 검증이다. OS에 Python이 설치되어 있지 않다는 주장이나 실제 다운로드 SmartScreen 확인은 아니다. 앞선 실패·취소 런 기록은 보존한다. #119 병합 대기 자동 확인은 목적을 마쳐 삭제했다. 최신 베타 재빌드의 실제 기준 커밋·Defender 검사는 별도 릴리스 폴더에 기록한다.


## 2026-10-04 A-25·D-3 새 베타 기준 수동 실행 — 통과

[런37135358758](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37135358758), main `dff19b286022f736ef9e53bf74bc32abe98114a2`에서1회 실행. exe 빌드·전체27/27(실패0·건너뜀0)·골든711/PDF17쪽 스냅샷 검사·Python 없는 PATH의 Aoharu/D♭ selftest 및 JSON 전체 비교 모두 통과했다. 이 검사는 옛 c8504e2 기준이 아니라 #178에서 승인된 소스 출력으로 갱신한 기준(Aoharu226 무변경/D♭255→254·유지10개 변경)을 쓴다. 전후 행은 docs/measurements/beta_a25_selftest_baselines.json, 최신 로컬 빌드/Defender/PNG/D-3 화면 기록은 [dff19b2](../dff19b2/PREFLIGHT.md). 실제 다운로드 SmartScreen 확인으로 세지 않는다.

## 2026-10-04 야간 베타 기준 Windows selftest — 통과

[런37148263284](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37148263284), main `cebae18ceb7c73949e91b81a766d64b809efb9f8`에서1회 수동 실행. exe 빌드·전체31/31(실패0·건너뜀0), 정답 골든711/PDF17쪽 스냅샷 유지, Python 없는 PATH에서 Aoharu/D♭ 두 selftest 종료0·JSON 전체 일치. 현재 소스로 기준 JSON을 재계산했으며 기존 두 기준과 내용 변화0이었다. 기준을 골든이나 실제 정답과 혼동하지 않는다. 새 로컬 베타·Defender·결과4쪽·소스 GUI 화면은 [cebae18](../cebae18/PREFLIGHT.md). 실제 다운로드 SmartScreen 및 Python 미설치 사용자 PC 검증은 미확인이다.
