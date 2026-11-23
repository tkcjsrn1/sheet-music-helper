# 1cbc0d8 베타 검증 — 2026-10-13

빌드 기준 `1cbc0d8ec1b0bed676476813b6366e34f386a264`, main, dirty=false. 사용자21시 승인·CLI #344 실제 신호 뒤 #346 CI 준비를 병합해 공식 build.py로 **한 번** 빌드했다. #310·#329·#333 최신판과 #339~#343을 포함한다. #345는 측정 도구·기록만이며 제품/기존검사 변화0. CLI 새 꾸밈음 초안, 마지막 폴더 기억, #167 보류 기능은 미포함이다. **친구 배포는 보류하고 우리끼리 검증한다.**

## 검증 근거

빌드 전 여유메모리 약2981MiB/C:약6580MiB/F:약221157MiB, CLI 무거운 작업 없음 확인. 시작 전체검사와 공식 빌드 후 전체검사 모두 실패0·건너뜀0, 정답골든711·현재PDF17 일치. 골든·판정 문턱·인식 코드 수정0. [시작 로그](prebuild-tests.log)·[빌드 후 로그](tests.log)·[빌드 정보](build-info.json)·[빌드 로그](build.log).

[새 strict8 비교](APPROVED_20261013.md)에서 #310 주의 추가3, #329 추가11, 독립확인·사용자승인된 Schubert E4/미#/check 한 이동만 허용했다. 나머지 기존행/순서/문맥 변화0. [전체 전후 자료](approved-strict.json.gz)·[요약](STRICT8_SUMMARY.json). #333의 이전 거부 입력 좌표변화는 이8개 깨끗한 원본에서 예외로 쓰지 않았다. 기울기 처리는 전체검사의 자체생성 입력으로 별도 확인하며 이표를 촬영본 일반 보장으로 확대하지 않는다.

최종 ZIP을 새 한글 폴더에 풀어 **실제 CLI exe8입력** Aoharu3·D♭1·바흐1·Clara1·Beethoven1·Schubert1을 처리했다. 소스/exe 전체JSON·PNG 픽셀·exe JSON 재렌더링 일치. [검증 원자료](verification.json)·[로그](verification.log). 실제exe 전체JSON도 승인strict8과 정확히 같다([독립확인](exe-approved.log)). D♭262·Aoharu226 static selftest 기준도 정확히 일치. CI D♭기준은 #329 승인2추가만 반영, 기존260행 변화/삭제0이며 [전후 전체JSON/SHA](selftest-329-before-after.json.gz)를 보존했다. 실행 기준은 정답골든이 아니다.

Python 없는 PATH·settings 없는 CLI 첫실행·exe옆output·ZIP5파일·다른원본 JSON 거부 통과. 소스밖cwd/빈PYTHONPATH3입력도 JSON/PNG 동일([기록](clean-cwd.json)·[로그](clean-cwd.log)). Python 미설치 사람PC 실행을 대신한 것은 아니다. D3 사용자수정 check는 원래음고/확신도를 JSON에 보존하면서 실제exe에서 진하게/점선없이 그렸고 소스 및 certain 대조그림과 픽셀이 같다. check주황색/caution옅기·꾸밈음/알토/미검출/음자리표변경·p/겹빔 표시를 유지했다.

박자표/조표기호 영역 라벨0, 첫실제F4 두음 유지, #217 Schubert (606,1522)E4 유지. 승인 Schubert E4 이동은 같은 음고/표기/등급이다. 기존 「미#」 표기 자체는 여전히 알려진 오류(TASKS M-2)이며 이번빌드가 해결했다고 쓰지 않는다.

[Actions38398537388](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38398537388)은 **같은1cbc0d8 커밋에서 한 번 실행·성공**. 소스exe빌드·전체검사 실패0/건너뜀0·Python없는PATH의 Aoharu/D♭ selftest·기준JSON 전체 비교 성공. [상태](actions.json)·[전체 로그](actions.log). 로컬과 CI exe 바이너리 해시가 같다는 뜻은 아니다.

Defender exe/ZIP ScanType3 각각 종료0·대상탐지0. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.691.0. [exe검사](defender-exe.json)·[ZIP검사](defender-zip.json)·상태/전체로그/검사스크립트 동봉. 백신 설정/제외 변경0. 다운로드 SmartScreen 확인을 대신하지 않는다.

## 결과와 남긴 것

[#312/1ad8323 → 새6쪽 변화표](BETA_CHANGES.md)·[전후행](BETA_CHANGES.json): D♭ 추가2, Clara 추가1, 다른4쪽 추가0. 삭제/표기/확신도 변화0. 숫자를 정답/오류/복구 수로 해석하지 않는다. Schubert는 별도 strict8에 이동1·추가11(#310 2와 #329 9)로 보존했다.

[Aoharu1](aoharu_p1.png)·[D♭1](chopin_Db_p1.png)·[바흐1](bach_p1.png)·[Clara1](clara_p1.png)은 실제exe 결과다. 머리말 ASCII 표기·글자형태를 눈으로 확인했으며 전체음표 정답 판정으로 확대하지 않는다. Beethoven 기호/첫음·D3수정·Schubert 승인 이동과#217의 부분그림도 보존한다.

[산출물 경로·SHA256·크기](artifacts.json): exe118679021바이트, ZIP124797231바이트. [동봉 안내](먼저%20읽어주세요.txt)는 최종ZIP에서 꺼냈고 소스 안내와 바이트 동일하다. 두음표분리·N/P/F1·쪽별확인개수·명시적사진재시도를 반영했다. [친구 메시지 초안](FRIEND_MESSAGE.md)은 아직 보내지 않는다.

실제exe 창클릭·다음쪽·다시열기·피아노 실제청취·실제다운로드SmartScreen·N/P/F1·쪽별확인개수·사진재시도 버튼은 **사람확인 필요**([목록](HUMAN_CHECK.md)). 자동CLI 성공을 실제GUI 확인으로 쓰지 않았다. 검증 범위 밖 악보의 오류0/사진지원 보장도 아니다.

exe/ZIP·원본악보 미커밋. 공유C:·stash·기존빌드 보존. 재현도구는 저장소루트와 기존F: 입력·빌드·과거결과를 요구하며 selection.json/artifacts.json에 실제기준을 남겼다. 판정·골든·규약·새의존성 변경0. CLI의 다음 무거운 작업은 WORKLOG 완료 기록 뒤 진행한다.
