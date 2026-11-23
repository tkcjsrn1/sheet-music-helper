# 806130a 베타 점검 — 2026-10-05 실제 실행

> 배포 후보 정리(2026-10-05, #263 병합 후): **헤더 끝·링 벽 미포함 중간 빌드**입니다. 최종 후보는 9325fa8과 [링 벽 포함29037e2](../29037e2/PREFLIGHT.md)입니다. 아래 당시 검증 기록과 기존 exe/ZIP은 보존합니다.

빌드 기준 `806130a043a76c2648b454fbaafad0f65829696a` · 최신main과 동일한 codex/beta-grace-release · dirty=false. CLI WORKLOG의 「꾸밈음 표시 병합됨」과 #241 병합을 확인하고 준비#259를 병합한 직후 최신main을 고정했다. #247 음자리표 미검출 안내, #249 수정본 재열기, #250 쪽넘기기/현재쪽 파일이름, #241 꾸밈음check, #253 음자리표 상관/겹침, #254 검색시작, #257 흐린 인쇄 구제 포함. 기존 #217/#234 오삭제 수정/기호 모양 표시·D-3 수정/추가/삭제·영역선택·듣기 유지. **#167 옥타브GUI는 제외**한다. Codex는 이번 작업에서 인식/판정/골든 코드를 편집하지 않았다.

## 검사

- 시작점37/37 및 공식build.py 원본spec 빌드후37/37, 실패0·건너뜀0. 정답골든711 일치, CLI 승인 후 갱신된 현재PDF17쪽 스냅샷 일치. 이전9325fa8 PDF 스냅샷과 전부 같다는 뜻은 아니다(#241의150줄 확신도 변경은 CLI가 사용자 승인으로 갱신). PyMuPDF/fitz 제외·라이선스 고지 버전·빌드 중 커밋/소스 고정 확인.
- 동일입력·동일설정8개: 소스/exe JSON 전체·PNG 디코딩 픽셀·exe JSON 재렌더링 픽셀 일치. check 주황점선과 caution 연한 글씨 색 픽셀 확인. [원자료](verification.json), [로그](verification.log), [실행스크립트](verify_cli.py).
- D♭ grace_size9개 전부check. Clara clef_changed144개 전부check. Beethoven clef_alto53/clef_unknown21개 전부check, 실제exe 및 JSON재렌더링 로그에서 두 경고 확인. [알토/미검출/조표 머리말 부분](alto_unknown_header_exe.png). 사진에서 꾸밈음 표시를 지원한다고 확대하지 않는다.
- 슈베르트Leipzig (606,1522) E4 라벨1개 유지(#217). 코드검사·실제exe 결과이며 인식오류율 판정과 다르다.
- 사용자 수정 check는 원래 pitch/confidence와 edited 표시를 JSON에 보존하고, 실제exe 그림은 certain과 같은 진한 글씨/점선제거. 소스 수정그림과도 픽셀일치. [부분 결과](label_edited_check_detail.png).
- 실제ZIP을 새 폴더에 풀어 settings없는 CLI첫실행·Python없는PATH·exe옆output 생성·PNG/JSON 저장·ZIP5파일 확인. 다른원본 JSON은 종료1·Traceback/PNG없음으로 거부. 실제Python미설치 사용자PC로 확대하지 않는다.
- [Windows Actions37287457087](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/37287457087): **같은806130a**를1회 수동 실행, exe빌드37/37·Python없는PATH Aoharu/D♭ 두selftest/전체JSON기준 비교 성공. [결과](actions.json), [로그](actions.log). CI 바이너리가 로컬exe와 바이트까지 같다고 주장하지 않는다.
- Actions기준: Aoharu226 내용·기존파일 무변경, D♭255 추가/삭제/표기변화0·확신도9곳 갱신. [전후전체JSON·변경행](../../measurements/beta_grace_selftest/README.md) 보존. selftest환경비교 기준이며 정답골든711과 구분한다.

| 입력 | 보표 | 라벨 | 확실 / 주의 / 확인 필요 | 소스·exe·재렌더링 |
|---|---:|---:|---|---|
| aoharu_p1 | 12 | 226 | 225 / 1 / 0 | 일치 |
| aoharu_p2 | 14 | 327 | 296 / 28 / 3 | 일치 |
| aoharu_p3 | 8 | 158 | 147 / 10 / 1 | 일치 |
| chopin_Db_p1 | 8 | 255 | 197 / 35 / 23 | 일치 |
| bach_p1 | 8 | 184 | 171 / 1 / 12 | 일치 |
| clef_change_clara1 | 12 | 587 | 350 / 65 / 172 | 일치 |
| alto_beethoven1 | 12 | 239 | 146 / 7 / 86 | 일치 |
| schubert_restored | 12 | 476 | 292 / 158 / 26 | 일치 |

## Defender

exe/ZIP 각각 MpCmdRun.exe `-Scan -ScanType 3 -File <Resolve-Path native경로>` 검사 종료0·대상탐지0. 제품4.18.26080.4·엔진1.1.26080.3·정의1.459.557.0, 백신/실시간보호 활성. [exe결과](defender-exe.json)·[로그](defender-exe.log)·[상태](defender-exe-status.json), [ZIP결과](defender-zip.json)·[로그](defender-zip.log)·[상태](defender-zip-status.json), [검사스크립트](check_defender.ps1). 보안설정/제외 변경 없음. Defender 결과가 실제다운로드SmartScreen 화면 확인을 대신하지 않는다.

## 9325fa8 → 새 베타 변화 수·안내

[6쪽 변화표](BETA_CHANGES.md), [전후행·문맥·해시](BETA_CHANGES.json), [기존 실제exe결과 출처](OLD_BASELINE.json). Aoharu3/D♭1/바흐1/Clara1 모두 추가0·삭제0·표기변화0, D♭1만 확신도9곳 변화(나머지0). **이 수치는 정답·오류·복구 수가 아니다.**

[동봉안내](먼저%20읽어주세요.txt)는 ZIP member SHA와 같다. 꾸밈음 미지원·작은음표 확인필요(사진모드제외), 쪽넘기기·새수정본 재열기를 반영했다. [친구메시지](FRIEND_MESSAGE.md)의 파란경고창 안내는 창이 뜰 때의 조건부 문구이며 실제확인으로 쓰지 않는다. 실제exe 결과 PNG4장(Aoharu1/D♭1/바흐1/Clara1)과 D-3부분결과를 보존했다. source_gui_로 시작하는3화면은 #249에서 검증한 **자체생성 이미지의 소스Tk** 둘째쪽저장/재열기/연속취소 캡처이며 새exe 직접클릭이 아니다.

## 산출물

- exe: `F:\sheet-music-helper-codex-night-20261004\dist\806130a043a7-20261005-180234-916866\악보헬퍼.exe`
- exe 118,670,714바이트 / SHA-256 `314FFDF22F1B32B06B57B932F0E90335E8577C50848C6093D3B9CB1C73F6DF88`
- ZIP: `F:\sheet-music-helper-codex-night-20261004\dist\악보헬퍼-806130a043a7-20261005-180234-916866.zip`
- ZIP 124,744,525바이트 / SHA-256 `2ED4D60BB3B3A903922A59D15FA4DBA9462FC92F4A49F6F2481EC561164D0D06`

빌드직전 여유메모리4,295,752KiB(약4.1GiB)/총16,442,780KiB 확인 후 실행([기록](memory-before.json)). TEMP/TMP·PyInstaller dist/work·로그·산출물은F:, [디스크전](disk-before.json)/[후](disk-after.json). 기존9325fa8/다른빌드·stash·공유C:체크아웃 보존. exe/ZIP·입력원본은 커밋하지 않았다.

## 남긴 것

**새806130a exe 직접클릭, 실제스피커청취, 실제다운로드SmartScreen은 미확인**. 사용자9325fa8 사람PC확인을 이 베타 확인으로 바꾸어 쓰지 않는다. 친구 신고ZIP은 [접수문서](../../BETA_FEEDBACK_INTAKE.md)의 실제F:inbox/실행한줄로 처리한다. 알려진 붙은화음·꾸밈음미지원·조바꿈·빈음표누락 등 한계는 안내문대로 유지한다. 이번 검사는 소스/배포환경 일치이지 모든입력 오삭제0/인식정답률 보장이 아니다.
