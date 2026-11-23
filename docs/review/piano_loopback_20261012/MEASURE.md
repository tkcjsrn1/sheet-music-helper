# 피아노 출력 직접 대조 — 2026-10-12

대상은 d6cf163 exe(SHA256 D97C34AD…1DD4C8). 최신 main2981db7과 제품 코드 동일. exe에 동봉된 label_audio 코드를 추출해 실제 Windows Microsoft GS Wavetable Synth의 Acoustic Grand Piano(bank0/program0)를 재생하고, 기본 출력 WASAPI shared loopback으로 디지털 출력을 수집했다. GUI 창을 누른 검사는 아니다. 마이크·볼륨·장치 설정 변경0. 테스트 음은 C4/E4/G4/C장조 화음, 각각0.55초(제품 GUI 기본0.28초보다 관찰 시간을 늘림).

## 실제 출력과 대조군

| 항목 | 새 피아노 출력 | 기존 사인파 대조 |
|---|---:|---:|
| 입력 | 동봉 play_piano | 동봉 write_wav + winsound |
| 수집 형식 | 48kHz·스테레오·float32 | 동일 |
| 수집된 프레임 길이 | 2.74초 | 2.61초 |
| 첫 C4를 단일 사인파로 설명한 에너지 | 49.37% | 98.89% |
| 최대 봉우리 대비5% 이상 주파수 봉우리 | 5개 | 1개 |

첫 음 시작 뒤20~220ms 구간을 분석했다. 피아노에서는260/525/785/1310/2115Hz 등의 봉우리, 대조 사인파에서는260Hz만 유의하게 나왔다(FFT 해상도5Hz). 음색 선택 기록과 배음 차이를 함께 보면 **기존 단순 삐 소리가 아닌 Windows 기본 피아노 음원이 출력됨**을 확인한다. 배음만으로 피아노를 분류하거나 사람 청취/고급 피아노 음질을 판정한 것은 아니다. 프로그램 번호는 #296의 실제 WinMM 관찰 기록과 동봉 코드로 확인했다.

[새 피아노 녹음](piano.wav), [기존 삐 소리 대조](beep_control.wav)는 재생하기 쉬운 PCM16 변환이며 증폭/효과/음색 변경0. 원래float32 녹음은 gzip에 보존했고 원본/압축/PCM 해시를 manifest에 남겼다. 두 음량은 정규화하지 않았으므로 같지 않다. WASAPI가 내준 패킷만 이어 붙였으며 무음 패킷은0으로 채웠다. 출력 스트림이 없던 대기 간격을 벽시계 녹음 길이로 확대하지 않는다. 최대 수집시간은각6초, 재생 전 다른 소리가 감지되면 중단하도록 했다. 두 실행 전 관측 출력은0이며 시험 음만 재생했다.

## 이전 기록 정정과 한계

10/07에는 ffmpeg DirectShow에 스테레오 믹스 장치가 없다는 이유로 출력 녹음이 어렵다고 기록했다. 그 확인은 ffmpeg 장치 목록에만 한정된다. **Windows WASAPI 루프백은 별도 스테레오 믹스 장치 없이 가능했고 이번에 성공했다.** 따라서 이전의 녹음 불가 판단을 전체 시스템의 한계로 읽으면 안 된다. 스피커의 실제 공기 중 소리나 사람 청취는 여전히 별도다. 녹음된 디지털 출력은 확인했지만 exe 창 직접 클릭·다운로드 SmartScreen은 미확인 유지.

공식 근거: [Windows loopback recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), [capture 절차](https://learn.microsoft.com/en-us/windows/win32/coreaudio/capturing-a-stream), Microsoft SDK의 [AudioClient](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/Audioclient.h)·[MMDevice](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/mmdeviceapi.h) 서명/순서. 새 라이브러리·제품 코드 추가0.

재실행은 저장소 루트에서 `python docs/review/piano_loopback_20261012/capture_loopback.py`, 같은 명령에 `--beep-control`, 이어서 `analyze_loopback.py`의 두 모드 순서. 기록한 실제 exe 경로와 개발 Python/기존 scipy·PyInstaller가 필요하다. 시스템의 기본 출력만 짧게 수집하며 마이크는 열지 않는다.
