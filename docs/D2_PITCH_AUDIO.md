# D-2 음높이만 듣기

## 의존성과 크기 조사 (제품 구현 전, 2026-10-04)

새 패키지 없이 Python 표준 라이브러리 wave·math로 짧은 사인파 WAV를 만들고 Windows winsound.PlaySound로 재생한다. Python/표준 라이브러리는 기존 PSF 고지가 적용된다. 개발 환경의 winsound.pyd는 33,112바이트이며, 압축 후 exe 증가분은 아직 실측하지 않았다. 새 베타 빌드에서 포함 여부·전체 크기를 기록한다. 오디오 드라이버/스피커가 없으면 재생 오류를 안내한다.

[Python 공식 winsound 문서](https://docs.python.org/3/library/winsound.html)에 따라 파일 경로를 비동기 재생하고 종료·중지 시 PlaySound(None,0)으로 멈춘다. 메모리 WAV의 비동기 재생은 지원하지 않아 임시 파일을 쓴다.

## 1단계 범위

선택 영역이 있으면 현재 표시 라벨만, 없으면 전체를 재생한다. 피아노 2단 한 묶음 안에서 왼쪽→오른쪽, 정확히 같은 x의 음은 동시에, 모든 묶음은 같은 길이로 소리 낸다. 박자·음표 길이·타이·꾸밈음·MIDI 내보내기는 지원하지 않는다. 가까운 x를 임의로 합치지 않는다.

인식 음고에 실효 임시표/조표를 반영한다. 사용자가 고친 계이름은 고친 값으로 재생하고 옥타브는 기존 음고를 유지한다(추가 라벨은 사용자가 지정한 옥타브). 해석할 수 없는 사용자 문구는 원래 음으로 되돌리지 않고 사유와 함께 제외한다. 확인 필요 라벨 제외 옵션은 기본 켜짐이며, 사람이 수정한 라벨은 원래 check라도 재생한다.

변환·렌더링·JSON 생성에는 관여하지 않는다. 재생 버튼을 누르지 않으면 기존 결과가 그대로다. Windows 재생 API 성공은 실제 스피커 청취 검증과 구분한다.

## 실행 결과

2026-10-04: test_label_audio의 실효 조표·제자리표·사용자 수정·확인 필요 제외·시스템/x 순서·동시 화음 WAV 검사 통과. 소스 Tk GUI에서 실제 재생 작업자의 시작/종료와 실패 안내를 확인했다. Aoharu 226라벨→161묶음, 기본 PNG·JSON 바이트 무변경. Windows PlaySound 파일 재생 호출 성공(스피커 청취는 미확인). 화면·짧은 WAV는 docs/review/label_audio/에 있다.

전체 tests/run_all.py 31/31, 실패0·건너뜀0. 골든711 및 PDF 스냅샷17쪽 무변경. 인식 파일 변경0. exe 검증은 다음 야간 빌드에서 수행한다.


## 2026-10-07 피아노 음색 연결

기존 순수 사인파 대신 Windows의 Microsoft GS Wavetable Synth에서 General MIDI 그랜드 피아노(프로그램 0)를 선택한다. 표준 라이브러리 ctypes와 Windows winmm API를 쓰며 새 패키지·샘플 파일이 없다. 기존 WAV 생성 도구는 호환용으로 유지하되 GUI 재생은 WAV를 만들지 않는다. Windows 음원/DLL을 ZIP에 복사하지 않는다.

기존 음고·임시표·사용자 수정 해석, 같은 x의 화음, 확인 필요 제외, 묶음당 0.28초, 중지를 유지한다. 박자 재생은 아니다. 중지·창 닫기·재생 실패에는 note-off/reset/close로 소리를 정리한다. 해당 음원이 없거나 열기/재생에 실패하면 이유를 로그에 표시하며 사인파나 다른 장치로 조용히 바꾸지 않는다.

이 PC의 장치 이름·프로그램 선택 및 실제 API 정상 완료/음이 켜진 동안 취소 호출은 성공했다. 자동 검사는 화음·취소·재생/정리 실패·잘못된 음높이·장치 부재·GUI 연결/종료·입력 불변을 확인한다. 실제 스피커 청취와 exe 재생은 아직 미확인이다. 녹음된 고급 피아노 샘플 수준의 음질을 보장하지 않는다. 기존 ab93bf2 exe에는 이 변경이 없다. 새 d6cf163 빌드에는 포함됐고 이전보다18,219바이트 작다(winsound 제거). 동봉 피아노 코드/API·CLI 자동 검증은 통과했지만 실제 exe GUI 피아노 재생은 미확인이다. [배포 검사](releases/d6cf163/PREFLIGHT.md).

근거: [Microsoft GS Wavetable Synth](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/midi), [midiOutOpen](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutopen), [MIDI 메시지](https://learn.microsoft.com/en-us/windows/win32/multimedia/using-midioutshortmsg-to-send-individual-midi-messages), [midiOutReset](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutreset), [General MIDI 1](https://midi.org/general-midi-level-1). 첫 절의 사인파 조사는 변경 전 역사 기록이다.
