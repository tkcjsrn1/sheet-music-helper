# de4b88e — 원격 GUI 검사 실패로 최종 후보 제외

빌드 기준 de4b88ed2806052b4ca9b8c5cdf052a6e2b8c91d. #366 C1·#368 한글/NumLock 단축키 수정 포함. 공식 build.py 한 번, 로컬 빌드 전후 전체검사 실패0·건너뜀0·골든711/현재PDF17 유지. 경로/크기/SHA256은 [artifacts](artifacts.json)에 있다. 기존 빌드를 지우지 않았다.

[실제 exe8입력 검증](verification.json): 소스/exe 전체 JSON·PNG 픽셀·JSON 재렌더링 일치. settings 없는 CLI·Python 없는 PATH·exe 옆 output·ZIP5개·다른 원본 JSON 거부·D3 진한 글씨/원래 확신도 보존 통과. [소스 밖 cwd3입력](clean-cwd.json)도 동일. [exe](defender-exe.json)/[ZIP](defender-zip.json) Defender ScanType3 종료0·대상탐지0. 보안 설정을 바꾸지 않았다.

동일 커밋 [Actions38691631339](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38691631339)는 GUI 순회 검사 실패로 중단됐다. Python 없는 PATH 단계는 **미실행**이다. 이 후보를 통과/최종 배포용으로 표시하지 않는다. [실패 원로그](actions-failed.log.gz).

짧은 [원격 진단38694748398](https://github.com/tkcjsrn1/sheet-music-helper/actions/runs/38694748398)의 [원문](ci-diagnosis.log.gz)에서 test_windows_ime_process_key_keeps_input_and_ignores_late_text의 입력칸 보호 단언이 실패했다. 검사에서 focus_force/update 한 번 뒤 실제 Tk 포커스가 Entry가 아닌 root였다. 합성 이벤트 widget도 Canvas로 남아 있어 GetKeyboardState가 호출됐다. 제품의 실제 입력은 [별도 확인](HUMAN_CHECK.md)대로 동작한다. 기존 포커스 확인 도구를 신규 검사에도 적용하고 stderr 원문을 보존하는 수정은 별도 검증 중이다. 원격 실패를 무시하거나 기준을 완화하지 않는다.
