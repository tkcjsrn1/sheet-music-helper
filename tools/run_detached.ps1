# 무거운 큐를 Claude Code 프로세스 트리 밖에서 띄운다(WMI Win32_Process.Create, 창 숨김). 출력은 전부 로그 파일로.
# 사용: powershell -File tools/run_detached.ps1 <큐.sh> <로그>   → 새 프로세스 PID 출력
# 세션이 쉬는 동안 Claude Code가 배경 셸을 정리해도 이 프로세스는 남는다(MEASUREMENT_PITFALLS B-10). 감시 · 잠금 해제는 run_heavy_step.sh가 한다.
param([Parameter(Mandatory)][string]$Script, [Parameter(Mandatory)][string]$Log)
$bash = Join-Path $env:ProgramFiles 'Git\usr\bin\bash.exe'
$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow = [uint16]0}
$cmd = "`"$bash`" -lc `"bash '$Script' > '$Log' 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; ProcessStartupInformation = $si}
if ($r.ReturnValue -ne 0) { throw "Win32_Process.Create 실패 $($r.ReturnValue)" }
$r.ProcessId
