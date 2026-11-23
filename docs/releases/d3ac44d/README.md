# 지인 베타 후보 — 2026-10-02 빌드 / 2026-10-03 기록

빌드 기준은 PR #119·#136·#140·#142·#137·#143·#52가 병합된 main `d3ac44d85ac5ed1abb8e8b3f9e7fa069e7057612`다. 깨끗한 `codex/beta-keysig-header-20261002`에서 공식 `build.py`를 실행했고 dirty=false이다. 조표 수정·짧은 줄 검출·ASCII 조표 머리 표시가 포함됐다. exe/ZIP은 커밋하지 않았으며, 검증된 사본을 사용자 저장소의 dist에 복사하고 ZIP 내용과 바이트 일치도 확인했다.

| 항목 | 결과 |
|---|---|
| exe | `dist/d3ac44d85ac5-20261002-234331-189442/악보헬퍼.exe` · 118,573,364바이트 |
| exe SHA-256 | `3B97C86E7493DEF1D9D90F5F0A2EAA919D9F0768C1E7C4DD62DBDA5400BAB784` |
| ZIP | `dist/악보헬퍼-d3ac44d85ac5-20261002-234331-189442.zip` · 124,615,966바이트 |
| ZIP SHA-256 | `50A38218C83503B7F6E83B7EAC99E33D8F5D08B98CBFF37B704236D22EF7A060` |
| 공식 빌드·검사 | 종료0 · 24/24 · 실패0·건너뜀0 · 골든711·PDF17쪽 스냅샷 무변경 |
| PDF 라이브러리 | exe에 fitz/pymupdf 포함0, PDF 입력은 소스 전용 |
| Defender exe/ZIP | 각 ScanType3 종료0·found no threats |
| Defender 엔진/정의/서비스 | 1.1.26080.3 / 1.459.514.0 / 4.18.26080.4 |

새 폴더에 ZIP을 풀어 settings.json/output이 없는 상태에서 CLI로 시작했다. Python을 PATH에서 제거하고 exe --selftest와 --relabel을 실행했으며 exe 옆 기본 output도 생성됐다. ZIP/복사 폴더 모두 exe·build-info.json·먼저 읽어주세요.txt·LICENSE·THIRD_PARTY_NOTICES.txt의 5개 파일이다.

| exe 결과 | 보표 | 라벨 | 확실/주의/확인 필요 | 소스↔exe PNG·JSON / exe JSON 재렌더링 |
|---|---:|---:|---|---|
| [Aoharu 1쪽](aoharu_p1.png) | 12 | 226 | 225 / 1 / 0 | 모두 동일 |
| [쇼팽 D♭ 1쪽 300dpi](chopin_Db_p1.png) | 8 | 255 | 208 / 35 / 12 | 모두 동일 |

두 전체 라벨 JSON은 c8504e2 selftest 기준과도 동일하다. D♭ check 12개에는 주황 점선 색 픽셀946개, caution에는 옅은 글자색 픽셀4134개가 있으며 Aoharu caution은63개다. 점선 신호가 모든 오류를 찾아준다는 의미는 아니다. 결과 PNG는 exe CLI가 실제 저장한 파일 그대로이며 GUI 기본 범례는 포함하지 않는다. 머리와 범례 공존 결과는 [별도 검토 PNG](../../review/keysig_header/README.md)에 있다.

[검증 JSON](verification.json), [빌드 정보](build-info.json), [전체 검사 로그](tests.log), [Defender exe](defender-exe.log)·[ZIP](defender-zip.log), [검증 스크립트](verify_cli.py)를 보존했다. 스크립트는 저장소 루트·같은 빌드·새 output/release-d3ac44d 폴더 기준이다. 재실행 때는 work 경로를 새 폴더로 지정해 기존 기록을 보존한다.

남은 한계: G♭ 픽스처 x−0.25/+0.75px의 ♭6→♭5 두 재현은 예상 실패로 남았다. 전체 검사 통과를 이 결함 해결이나 사진 전반 지원으로 해석하지 않는다. 실제 다운로드 SmartScreen 및 첫 베타 사용자의 PC 실행은 별도 확인이 필요하며, GUI 화면을 이번에 다시 캡처했다고 주장하지 않는다. 최종 배포는 사용자 확인 뒤 결정한다.
