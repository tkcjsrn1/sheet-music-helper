# d69a025 내부 베타 — 자동 검증 완료, 사용자 확인 대기

빌드2026-10-23 / 남은 검증·기록2026-10-26. 기준 `d69a025a063f9beb7797b4966509d18c7de5f3c4`, 깨끗한 공식 `python build.py`, 태그 `d69a025a063f-20261023-200643-946483`.

- 사용자 승인 순서 #431→#412 병합 후 빌드했다. 건반·재생 위치, 계이름 줄 선택 옵션, #425 포함. Codex의 인식/판정/골든/JSON 스키마 변경0.
- 공식 빌드 자체 전체 **54/54 · 실패0 · 건너뜀0**, 골든711/PDF17 유지. 실제 골든1/OpenCV1. [전체 원문](evidence/full-tests.log.gz) · [스레드 증거](evidence/workers.log.gz).
- 실제 이전015908d의12입력 대비 기본 JSON 원문·PNG 화소 변화0. 새 소스/exe12입력 JSON 원문·PNG 화소 동일, selftest2 기준 동일, exe JSON 재렌더12 화소 동일. [변화표](BETA_CHANGES.md) · [전후 전체행](evidence/strict-rows.json.gz) · [검증 결과](evidence/verification.json).
- 소스3입력 출력은 제품 파일이 같음을 확인한 직전 통합 실행에서 재사용했다. 작업공간 간 LF/CRLF만 다른 파일은 LF 정규화 후 같음을 확인했고, 인식 JSON/결과 바이트 비교는 정규화하지 않았다. [소스 동일성](evidence/source-reuse-identity.json). 첫 재사용 확인 중단 로그도 보존했다.
- ZIP5파일·Python을 뺀 PATH·settings 없는 첫 CLI·exe 옆 output 생성·다른 원본 재렌더 거부 통과. 새 PC/모든 사용자 환경 통과를 뜻하지 않는다.
- Defender exe/ZIP ScanType3 각각 종료0, 해당 경로 탐지0. [엔진·정의/탐지 조회](evidence/defender.json). 실제 다운로드 SmartScreen 판정은 별도다.
- 같은 커밋 [Windows Actions39943689610](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/39943689610) 성공. exe 빌드·Python 없는 PATH의 selftest2/기준 JSON 대조 포함. 중복 dispatch/빌드 없음.
- 실제 새 exe 두 이미지 변환/쪽 이동/한글 N/P/NumLock OFF F1·선택 건반을 확인하고 사본0·IME/NumLock 복원·본인 잠금 해제했다. [실제 입력 범위](HUMAN_CHECK.md). 소스 검사·frozen MIDI 계약과 실제 스피커 검증을 구분했다.
- 무거운 실행은 원자 HEAVY.lock/자기 Windows Job·0.2초 감시를 사용했다. 시작 가용2.5GiB 이상, 중1GiB 또는 커밋여유2GiB 미만 중단. 단계별 실제 최고 메모리는 아래 result.json. 기록값은 임의 입력의 상한이 아니며 WS합은 공유페이지가 중복될 수 있다.

| 작업 | 관측 WS합 최고 MiB | OS Job 커밋 최고 MiB | 시스템 최저 가용 GiB |
|---|---:|---:|---:|
| official-build | 641.64 | 555.99 | 2.52 |
| frozen-verify | 416.84 | 376.10 | 2.29 |
| defender-scan | 175.98 | 123.29 | 2.65 |
| frozen-gui | 509.30 | 426.88 | 3.27 |

[exe·ZIP 경로/크기/SHA256](artifacts.json) · [동일 커밋 원격 원문](evidence/actions.log.gz) · [사용자 확인 목록](USER_CHECKLIST.md).

남긴 것: 건반과 실제 스피커 일치·재생 지연·계이름 줄 ON/OFF 후 재변환·저장 후 다시 열기는 사용자 확인 목록에 있다. 밀집 구간 글자 겹침은 TASKS에 미해결로 남겼다. 친구/공개 배포 보류, 스피커·SmartScreen 사용자 몫. exe/ZIP·원본 악보 미커밋.
