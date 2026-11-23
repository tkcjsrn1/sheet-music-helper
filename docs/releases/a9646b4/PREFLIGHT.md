# a9646b4 내부 베타 검증 — 2026-10-15

기준 `a9646b4675218402ace5f4adf325105611c5b712`, 최신 main, dirty=false. 실제 CLI 「#352·#354 병합 — 베타 재빌드 가능」 신호와 병합을 확인했다. #352 꾸밈음 표시·#354 조표 보완·#357 RGB 수정본 재열기·#360 마지막 폴더 기억·#361 실제 클릭 검사를 포함한다. #167·#350·기각된 짝짓기 묶음은 미포함이다. **우리끼리 검증하는 후보이며 친구 배포는 보류한다.**

## 빌드와 비교

CLI의 main1014/cls1014/bundlecls 측정이 끝난 뒤 Python 측정 프로세스0·여유메모리 약2.8GiB를 확인해 공식 build.py를 한 번 실행했다. PyInstaller 성공 및 빌드 후 전체 **실패0·건너뜀0**, 정답 골든711·현재 PDF17 스냅샷 유지. [빌드 후 전체](tests.log)·[직전 전체](prebuild-tests.log)·[빌드 로그 원자료](build.log.gz)·[빌드 정보](build-info.json).

1cbc0d8 대비 [strict8 전체 전후행](strict-before-after.json.gz)은 라벨 추가/삭제·좌표·음고·표기·확신도·조표/음자리표 문맥 변화0. 사용자 허용 예외를 쓸 필요가 없었다([요약](STRICT8_SUMMARY.json)·[로그](strict.log)). 이8개는 깨끗한 원본이며 모든 입력의 무변화를 뜻하지 않는다. #354의 별도 열화 개선 근거는 [CLI 측정](../../KEYSIG_PERSPECTIVE.md)에 있다.

사전 strict 커밋은 d2da167이다. 이후 main에 추가된 #363은 WORKLOG/DECISIONS 기록뿐이며, [사전 제품/골든 파일 SHA](strict-source-identity.json)가 빌드 시점과 전부 같음을 확인해 같은 소스 실행을 재사용했다. 현재 소스/exe 검증은 빌드 커밋 a9646b4와 일치하는지 확인한다.

## 실제 exe 검증

[8입력 JSON/PNG/재렌더링](verification.json)·[로그](verification.log): Aoharu3·D♭1·바흐1·Clara1·Beethoven1·Schubert1 모두 소스와 일치. Aoharu/D♭ selftest 기준 JSON 변경0. 주황 점선·caution 옅기·알토/음자리표 미검출/변경·꾸밈음 표시를 유지한다. 실제 exe의 박자표/기호 영역 라벨0·첫 실제 F4 두 음 유지, #217 Schubert (606,1522) E4 유지. D3 수정 JSON은 원래 확신도를 보존하면서 그림은 certain 대조와 같은 진한 글씨다.

settings 없는 CLI 첫 실행, exe 옆 output, ZIP5파일, Python 없는 PATH, 다른 원본 JSON 거부 통과. 소스 밖 cwd/빈 PYTHONPATH의3입력도 JSON/PNG 동일([근거](clean-cwd.json)). 실제 Python 미설치 사람 PC를 대신한 검사는 아니다.

[Actions38613869206](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38613869206)은 **같은 a9646b4 커밋에서 한 번 성공**: exe 빌드·전체·Python 없는 PATH의 Aoharu/D♭ selftest·기준 JSON 비교([상태](actions.json)·[원로그](actions.log.gz)). d2da167의 사전 Actions38556181835도 성공했지만 실제 빌드 커밋 증거와 구분해 pending-352-354에 보존한다. 동일 커밋 중복 실행0.

Defender ScanType3 exe/ZIP 각각 종료0·대상탐지0. 제품4.18.26080.4·엔진1.1.26090.9·정의1.461.20.0([exe](defender-exe.json)·[ZIP](defender-zip.json), 상태/전체 로그 동봉). 설정/제외 변경0. SmartScreen 검증을 대신하지 않는다.

## 실제 GUI와 산출물

[실제 클릭·재열기](HUMAN_CHECK.md): 새 사본에서 두 장 실제 변환, 완료 후 다음1/2→2/2, 다음 확인0/31→1/31. 둘째 쪽 표시 글씨1건 수정→앱 종료→다른 PID 재실행→원본 해시 확인→수정본 재열기→GUI 재저장 전체327라벨/수정1건/그림 동일. 기존 저장본6파일 SHA 불변, 인식 설정은 마지막 폴더 외 DEFAULT 그대로. 검사 사본과 부트 프로세스 모두 종료했다.

[#312/1ad8323 → 새6쪽 변화표](BETA_CHANGES.md): D♭ 추가2·Clara 추가1, 나머지4쪽 추가0; 삭제/표기/확신도 변화0. 숫자를 정답/오류/복구 수로 해석하지 않는다. [전체 전후행](BETA_CHANGES.json).

실제 exe 결과: [Aoharu1](aoharu_p1.png)·[D♭1](chopin_Db_p1.png)·[바흐1](bach_p1.png)·[Clara1](clef_change_clara1.png). 원본 악보는 추가하지 않았다. [경로·크기·전체 SHA256](artifacts.json), [실제 ZIP 안내문](먼저%20읽어주세요.txt)·[친구 메시지 초안](FRIEND_MESSAGE.md).

**남긴 것:** 실제 다운로드 SmartScreen·스피커 사람 청취·Python 미설치 사람 PC는 미확인. 새 exe N/P·F1 실제 키 검사는 이번에는 하지 않았고 소스 전체 검사만 통과다. 피아노 실제 WASAPI 녹음은 1cbc0d8의 [기록](../1cbc0d8/HUMAN_CHECK.md)을 보존하며 음성 코드 SHA는 동일하다. 새 exe를 새로 녹음했다고 쓰지 않는다. 인식 정확도 전체 보장/사진 일반 지원 보장은 아니다. #167 보류 판단은 #360 WORKLOG에 있다. exe/ZIP·원본 악보 미커밋, 공유C:/stash/기존빌드 보존.

사진 모드 토글·실패 시 사진 재시도 버튼도 이번 새exe 실제 클릭 범위에는 포함하지 않았다. 해당 경로의 소스 회귀 검사와 과거 사람 확인을 새exe 실제 확인으로 바꾸지 않는다.
