# 219f4e8 배포 전 로컬 점검 — 2026-09-29

검사 대상은 빌드 커밋 `219f4e8cfd1839c99eba4d12adc538e4f5b81eeb`의 exe와 ZIP이다. 바이너리는 저장소에 커밋하지 않았다.

| 항목 | 결과 |
|---|---|
| Defender | `MpCmdRun.exe -Scan -ScanType 3 -File <파일>`로 exe·ZIP 각각 검사 완료. 둘 다 종료 코드 0, `Scan finished`, `found no threats`. 탐지명 없음. |
| Defender 버전 | 엔진 `1.1.26080.3`, 바이러스 정의 `1.459.453.0`, 서비스 `4.18.26080.4` (`Get-MpComputerStatus`). 사용한 도구: `C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.26080.4-0\MpCmdRun.exe`. |
| exe | 106,271,243바이트, SHA-256 `F002C25D1F356F84B8A5F4FF131C9AD4D9F1A1CB13AF855E6D07BAAFB4AEFDB0` |
| ZIP | 111,748,681바이트, SHA-256 `93A352E8C09009F70D7ACD005D60D7E5CD542B7032DC9889626E9FFCF8D68F73` |
| Windows | Windows 11 Pro, 10.0.26200, 64비트. `Win32_OptionalFeature`의 `Containers-DisposableClientVM` `InstallState=2` = 비활성. |

## SmartScreen 화면 확인용 사본

ZIP을 새 `output/smartscreen-219f4e8-20260929/`에 복사하고 `Zone.Identifier`의 `ZoneId=3`을 붙였다. ZIP 내용 해시는 원본과 같다. `Expand-Archive`로 푼 exe에는 이 스트림이 없었다. Windows 탐색기 ZIP 셸(`Shell.Application`)로 다시 압축을 풀자 exe에도 `ZoneId=3`이 전파됐고, exe SHA-256은 원본과 같았다.

**사람이 더블클릭할 파일:** `C:\Users\user\Desktop\악보헬퍼\output\worktrees\hollow-rescue-085\output\smartscreen-219f4e8-20260929\explorer-extracted\악보헬퍼.exe`. 사본 준비 당시에는 실행하지 않았다. 후속 실행 시도와 실제 화면은 아래에 기록했다.

## Windows Sandbox 준비

[설정 파일](../../../tools/sandbox/219f4e8-beta.wsb)은 호스트의 이 작업트리 `dist` 폴더를 `C:\BetaDist`에 읽기 전용으로 연결하고 로그인 시 **탐색기만** 연다. exe는 자동 실행하지 않는다. 기능이 비활성이므로 `.wsb`는 아직 실행하지 않았다.

**사람이 기능을 켜기로 결정할 때만:** 관리자 PowerShell에서 `Enable-WindowsOptionalFeature -FeatureName "Containers-DisposableClientVM" -All -Online`을 실행하고 필요하면 재부팅한다. 이 점검에서는 기능을 켜거나 재부팅하지 않았다.

상태 코드와 `.wsb` 형식: [Microsoft 선택 기능 문서](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-optionalfeature), [Sandbox 설정 문서](https://learn.microsoft.com/en-us/windows/security/threat-protection/windows-sandbox/windows-sandbox-configure-using-wsb-file), [설치 문서](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-install).

## 실제 보안 경고 화면 확인 — 2026-09-29

`ZoneId=3` exe를 `Start-Process -PassThru -WindowStyle Normal`로 실행 시도했다. 호출은 보안 경고 창에서 반환되지 않아, 별도 PowerShell에서 5초 대기 후 프로세스와 대화형 데스크톱을 확인했다. 악보헬퍼.exe **없음**, `smartscreen.exe` **있음**(PID 28320). 전체 화면을 `System.Drawing.Graphics.CopyFromScreen`으로 [캡처](smartscreen_check.png)했다(1536×864, 비검정 샘플 420개, SHA-256 `9544118D6CDE793C5A823E41AE2D6E7EAC20A21512184E62FAA707DC25D00A34`). 검은 화면이 아니며 캡처 실패도 아니다.

보이는 것은 파란 「Windows의 PC 보호」 화면이 아니라 **「파일 열기 - 보안 경고」** 창이다. 「게시자를 확인하지 못했습니다. 그래도 이 소프트웨어를 실행하시겠습니까?」와 실행·취소 버튼이 보인다. 어느 버튼도 누르지 않았다. `smartscreen.exe` 프로세스가 보인다는 사실만으로 이 대화창을 SmartScreen 화면이라고 부르지 않는다. 악보헬퍼.exe 프로세스가 없어 종료할 대상은 없었다. 보안 경고 창과 차단된 실행 호출은 사용자가 닫을 수 있도록 그대로 두었다. Windows Sandbox는 이번 확인에서 사용하지 않았다.
