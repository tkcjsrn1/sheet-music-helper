# 1ad8323 검토 탐색·p/겹빔 표시 베타 — 2026-10-12

기준 `1ad8323c6155b8ce5f277df1fc9034f38cb86c2c`, main, dirty=false. CLI 신호를 확인한 뒤 #301 다쪽 진행 표시·#302 확인 필요/주의 순회·#303 좁은 구멍·#304 겹빔 check 표시·#307 N/P 및0개 안내·#308 배포 기준 준비를 포함했다. 기존 피아노 음색·D3 수정/재열기·쪽 선택 보호도 유지한다. **친구 배포는 보류하고 우리끼리 검증한다.** #310 판정안과 #167/#269 보류 기능은 미포함이다.

## 검증

C:약4805MiB/F:221744MiB·가용메모리3561MiB 확인 후 F:에서 공식 build.py/원본 spec으로 한 번 빌드했다. 빌드 전후 전체검사 실패0·건너뜀0, 정답 골든711·최신 PDF17 스냅샷 일치. #303에서 CLI가 승인·반영한 확신도 스냅샷9행을 본인이 다시 갱신하지 않았다. 본인이 인식/판정·정답 골든·규약·문턱을 고친 것0. [시작 검사](prebuild-tests.log), [빌드 후 검사](tests.log), [빌드 정보](build-info.json).

최종 ZIP을 새 한글 폴더에 풀어 **실제 exe8입력**(Aoharu3·D♭·바흐·Clara·Beethoven·Schubert)을 소스와 대조했다. 전체 JSON·PNG 픽셀·exe JSON 재렌더링 일치. Aoharu/D♭ static selftest 기준 전체 일치. Python 없는 PATH·settings 없는 CLI 첫 실행·exe 옆 output·ZIP5파일·다른 원본 JSON 거부 통과. 소스 밖 cwd/빈 PYTHONPATH3입력도 동일하다. check 주황색/caution 옅기·꾸밈음/알토/미검출/음자리표 변경 표시 유지. 새 beam_gap은 Aoharu1(1)·D♭(2)·Clara(7), narrow_hole은 Beethoven(6)·Schubert(1)에서 모두 check로 전달됐다. 박자표/조표 영역 라벨0·첫 실제F4 2개 유지·Schubert(606,1522)E4 유지. D3 수정 check는 진하게/점선 없이 그려지며 원래 확신도와 음고를 보존했다. [원자료](verification.json), [독립 폴더](clean-cwd.json), [전체 실행 로그](verification.log), [대조 스크립트](verify_cli.py).

[Windows Actions38247717082](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38247717082) 동일 빌드 커밋에서 한 번 수동 실행 성공. 소스 exe 빌드·전체검사·Python 없는 PATH의 Aoharu/D♭ selftest·전체 기준 JSON 비교 통과. [상태](actions.json), [로그](actions.log). 로컬/CI 바이너리가 같다는 뜻은 아니다. 기준 갱신은 승인된 #303/#304 사유/확신도만, 전체 전후행은 [원자료](../../measurements/beta_20261012_selftest_diff.json)에 남겼다. Aoharu(414,1404) certain→check+beam_gap, D♭(793,832)/(2314,2904) 기존check 유지+beam_gap. 음고·표기·조표·음자리표·좌표·라벨 수 무변경. 실행 환경 비교 기준이며 정답 골든이 아니다.

Defender exe/ZIP ScanType3 각각 종료0·대상 탐지0. 제품 4.18.26080.4·엔진 1.1.26080.3·정의 1.459.678.0. [exe](defender-exe.json), [ZIP](defender-zip.json), 상태·전체 로그·[검사 스크립트](check_defender.ps1) 동봉. 백신 설정/제외 변경0, SmartScreen 검사를 대신하지 않는다.

[d6cf163→새 베타6쪽 변화표](BETA_CHANGES.md): 추가/삭제/표기 변화 모두0, 확신도2(Aoharu1/Clara1 각각1). ID/사유만 달라진 것은 이 네 집계에 넣지 않는다. 전체 문맥/전후행은 [JSON](BETA_CHANGES.json)에 보존했고 숫자를 정답/오류/복구 수로 해석하지 않는다. [Aoharu1](aoharu_p1.png)·[D♭1](chopin_Db_p1.png)·[바흐1](bach_p1.png) 실제 exe 결과와 D3/Beethoven 부분그림을 보존한다. 그림의 머리말·글자 형태를 확인했으며 전체 음표 정답 판정 완료로 확대하지 않는다.

## 다음 쪽 지연·사람 확인

[실제 소스 계측](../../review/page_latency_20261012/MEASURE.md)에서 두 장 처리22.109/21.965초, 완료 후 전환0.173~0.250초. 처리 중 회색disabled 확인. 예전 사람 PC의 약1분 지연은 재현되지 않아 정확한 원인은 미확정이다. 예전 시각적 잠금 문제를 처리 대기로 오인했을 가능성은 (추측)으로만 남겼고 제품을 추가 수정하지 않았다. 계측/무계측 PNG·JSON4파일 바이트 동일.

실제 새 exe 창 클릭·수정본 재열기/쪽 넘기기 사람 판정·스피커 청취·실제 다운로드 SmartScreen·Python 미설치 사람 PC 실행은 **미확인**이다. [내일4단계 확인 목록](HUMAN_CHECK.md). 이전 피아노 디지털 루프백 검증을 사람 청취로 바꿔 쓰지 않는다. 후보 확정이 인식 오류 없음/사진 지원 보장이라는 뜻도 아니다.

## 산출물·남긴 것

[exe·ZIP 전체 경로·SHA256·크기](artifacts.json). exe118667961바이트·ZIP124777486바이트. 동봉 안내는 최종 ZIP에서 꺼낸 파일이며 현재 소스 안내와 바이트 같다. N/P·0개 안내와 '표시 없음이 전부 맞다는 뜻은 아님'을 반영했다. [친구 메시지 초안](FRIEND_MESSAGE.md)은 아직 보내지 않는다. exe/ZIP·원본 악보 미커밋, 공유C:·stash·기존빌드 모두 보존.

검증 중 #311 문서/측정 도구가 main에 들어왔고 완료 뒤 수신했다. 빌드1ad8323과 제품·기존 검사·배포 입력 diff0을 확인해 빌드/Actions/전체검사를 중복하지 않았다. 기록 도구가 안내문을 dist 하위에서 찾던 오류1회는 ZIP을 풀어둔 최종 폴더에서 복사하도록 바로잡았다. 제품/검사 실패가 아니며 산출물은 다시 빌드하지 않았다. 검증 도구는 F: 입력/이전 결과에 의존한다.

**사용자 결정(10-13) — 중간 후보로 변경:** 이 빌드는 #310 미포함 상태로 이미 완료됐습니다. 파일/해시/검증 기록은 보존하고 최종 후보로 사용하지 않습니다. 다음 빌드는 CLI의 #310 병합·재빌드 신호 뒤에 한 번만 수행합니다.
