param([string]$BuildTag)
$ErrorActionPreference='Stop'
$taskRoot=(Get-Location).Path
$taskScanDir=Join-Path $taskRoot 'output/a200ccd-defender'
New-Item -ItemType Directory -Path $taskScanDir -Force | Out-Null
$taskScanner=Get-ChildItem 'C:\ProgramData\Microsoft\Windows Defender\Platform' -Directory | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'MpCmdRun.exe' } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $taskScanner) { throw 'Defender 검사 실행 파일을 찾지 못함' }
foreach ($taskType in @('exe','zip')) {
    $taskRelative=if ($taskType -eq 'exe') { "dist/$BuildTag/악보헬퍼.exe" } else { "dist/악보헬퍼-$BuildTag.zip" }
    $taskTarget=(Resolve-Path -LiteralPath (Join-Path $taskRoot $taskRelative)).Path
    $taskStarted=(Get-Date).ToString('o')
    Get-MpComputerStatus | Select-Object AMProductVersion,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntivirusEnabled,RealTimeProtectionEnabled | ConvertTo-Json | Set-Content (Join-Path $taskScanDir "$taskType-status.json") -Encoding utf8
    & $taskScanner -Scan -ScanType 3 -File $taskTarget > (Join-Path $taskScanDir "$taskType.log") 2>&1
    $taskExit=$LASTEXITCODE
    $taskDetections=@(Get-MpThreatDetection | Where-Object { ($_.Resources -join '\n').IndexOf($taskTarget,[StringComparison]::OrdinalIgnoreCase) -ge 0 })
    $taskResult=[ordered]@{target=$taskTarget;scanner=$taskScanner;exit_code=$taskExit;started_at=$taskStarted;finished_at=(Get-Date).ToString('o');target_detections=$taskDetections}
    $taskResult | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $taskScanDir "$taskType.json") -Encoding utf8
    if ($taskDetections.Count) { Get-MpThreat | Where-Object { $_.ThreatID -in $taskDetections.ThreatID } | Format-List ThreatName,ThreatID; throw '이번 산출물 탐지: 후속 작업 중단' }
    if ($taskExit -ne 0) { throw "Defender $taskType 검사 종료 코드 $taskExit" }
    Write-Output "$taskType 검사 종료0, 대상 탐지0"
}
