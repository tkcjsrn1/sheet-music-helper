# Windows selftest 기준 자료

수동 GitHub Actions 실행에서 `--selftest` 결과를 승인된 소스 기준과 비교한다. 2026-10-04에 A-25 병합 후 main `73d4d3b`의 실제 소스 CLI 출력으로 기준을 갱신했다. 새 베타 빌드 후 소스/exe의 JSON 전체 일치를 별도로 검사한다. 두 JSON은 처리 결과 전체를 그대로 보관하며 `tests/golden/*.tsv`를 대체하거나 갱신하지 않는다.

| 입력 | 원본 | SHA-256 | 기준 라벨 |
|---|---|---|---:|
| Aoharu 1쪽 | `sample_images/KakaoTalk_20260731_162400402.png` | `34dab8064e56796256ea8a11fa89452cb09263c543ffbb353ad7f0acb4e867f8` | 226 |
| 쇼팽 D♭ 1쪽 300dpi | `chopin_Db_p1.png` (저장소의 저작권 만료 PDF 1쪽에서 추출) | `85b0792c2caee0225664daf060da800621291dd65fca47eb9aeebf599177fdf2` | 262 |

워크플로는 `build.py`가 요구하는 고지 버전에 맞춰 의존성을 고정하고, exe 실행 단계에서는 PATH에서 Python을 제거한다. Git 체크아웃의 CRLF/LF 차이만 정규화한 뒤 JSON 본문 전체를 비교한다. JSON이 다르면 자동 병합 근거로 삼지 않는다. 이는 새 Windows 실행 환경 한 대의 검사이지 모든 PC에서의 정상 동작 보장은 아니다.

이전 기준은 `c8504e29ef4c6e5ef053e814d104b9d8d1647f8a` exe의 2026-09-30 출력이다. Aoharu는 줄바꿈 정규화 후 JSON 전체 무변경, D♭은 라벨255→254(승인된 임시표 글리프 유령1 제거)·유지 라벨10개 변경, 두 입력의 조표/음자리표/오선 정보는 동일하다. 전체 전후 행 및 해시는 `docs/measurements/beta_a25_selftest_baselines.json`에 기록했다. 이는 골든 갱신이 아니라 승인된 제품 변경에 맞춘 배포 환경 비교 기준 갱신이다.

2026-10-05 새 베타 준비: CLI #215 glyph_shape 표시를 포함한 main 소스의 --selftest로 두 기준을 다시 대조했다. Aoharu226개 전체 무변경, D♭254개 중 (416,2792)·(2296,2831) 두 라벨의 confidence certain→check 및 glyph_shape 사유만 갱신했다. 음고·계이름·좌표·조표·보표는 무변경이다. 전후 행은 docs/measurements/beta_glyph_shape_selftest_baselines.json에 보존한다. 이는 제품 변경에 맞춘 실행 환경 비교 기준이며 정답 골든이 아니다.

2026-10-05 #217 재적용 PR#233 기준: 사용자 결정으로 D♭ (2332,2838)의 중복1개를 감수한다. 실제 소스 --selftest는 D♭254→255(B4/시b 추가1, 유지2곳 raw·확신도/사유 변화)이며 Aoharu226개는 JSON 전체 동일하다. 조표·보표·입력 정보는 동일, 전후행과 해시는 docs/measurements/beta217_adopted_selftest_diff.json에 보존했다. 실행환경 비교 기준만 갱신했으며 정답 골든711은 바꾸지 않았다. 중복 라벨을 정답 복구로 세지 않는다.

2026-10-12 #303/#304 승인 표시 반영: main bbea899의 소스 자체 점검으로 갱신했다. 라벨 수·좌표·음고·표기·조표·음자리표 무변경을 먼저 검사하고 confidence/flags 변화만 허용했다. 전체 전후행·해시는 docs/measurements/beta_20261012_selftest_diff.json에 보존한다. 정답 골든711은 수정하지 않았다.

2026-10-15 #374 병합 후: D♭ 라벨262개·음고/좌표/표기/문맥 동일, 7곳의 double_acc 사유와 check 변경만 실제 소스 출력으로 반영했다. CLI가 main에 병합한 PDF스냅샷과 전행 일치한다. Aoharu 전체JSON 변화0, 전후원문/SHA는 docs/releases/pending-373-374/SELFTEST_DB_CHANGES.json.gz에 보존했다. 정답 골든은 수정하지 않았다.

2026-10-18 사용자 승인(#394): 지정13d73f6의 실제 gui.py --selftest 출력과 저장된 전체 전후 행을 다시 대조한 뒤 D♭ 기준만 갱신했다. 262→262·추가/삭제/좌표/음고 변화0, #388/#391의 bb/## 7곳과 조건부schema2, #390의 side_pair(등급1곳·flags2곳)만 변경이다. Aoharu 기준 파일 원시 바이트는 그대로다. 자료 docs/releases/13d73f6/baseline-update.json 및 selftest-baseline-diff.json.gz. 정답 골든은 변경하지 않았다.
