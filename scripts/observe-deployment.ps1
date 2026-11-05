param([Parameter(Mandatory=$true)][string]$ImageRef,[string]$DeploymentVersion='local',[string]$Directory,[switch]$SkipPull)
$ErrorActionPreference='Stop'
if(-not $Directory){$Directory=Join-Path (Get-Location) ('reports/observe-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Path $Directory -Force|Out-Null
$Directory=(Resolve-Path $Directory).Path
if(Test-Path (Join-Path $Directory 'requests.jsonl')){throw 'Use a new observation directory.'}
$case=Join-Path $Directory 'fixed-case.json'
python -m scripts.monitor_case $case
if($LASTEXITCODE -ne 0){throw 'Monitoring fixture failed.'}
$args="-u -m scripts.monitor --url http://127.0.0.1:8080/api/v1/predict --directory `"$Directory`" --case `"$case`""
$process=Start-Process -FilePath (Get-Command python).Source -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Directory 'monitor.stdout.log') -RedirectStandardError (Join-Path $Directory 'monitor.stderr.log')
$process.Id | Out-File (Join-Path $Directory 'monitor.pid') -Encoding utf8
try {
  for($i=0;$i -lt 30;$i++){if(Test-Path (Join-Path $Directory 'ready')){break};if($process.HasExited){throw 'Monitor exited'};Start-Sleep -Seconds 1}
  if(-not (Test-Path (Join-Path $Directory 'ready'))){throw 'No successful pre-deploy response'}
  New-Item -ItemType File -Path (Join-Path $Directory 'deploy.started')|Out-Null
  & "$PSScriptRoot/deploy-bluegreen.ps1" -ImageRef $ImageRef -DeploymentVersion $DeploymentVersion -SkipPull:$SkipPull
} finally {
  New-Item -ItemType File -Path (Join-Path $Directory 'stop.request') -Force|Out-Null
  if(-not $process.WaitForExit(70000)){$process.Kill();Write-Warning 'Monitor timeout; remaining interval unverified.'}
  python "$PSScriptRoot/monitor_summary.py" $Directory
  python "$PSScriptRoot/capture_report.py" $Directory
  python "$PSScriptRoot/validate_observation.py" $Directory $DeploymentVersion
  if($LASTEXITCODE -ne 0){throw 'Observation incomplete or requests failed. Full logs preserved.'}
  Write-Host "Full UTF-8 reports: $Directory"
}
