[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ImageRef,[int]$Port=8080,[string]$DeploymentVersion='local',[switch]$SkipPull)
$ErrorActionPreference='Stop'
$service='kbo-salary';$network='kbo-salary-net';$volume='kbo-salary-routing'
$label='io.kbo.managed-by=kbo-salary-deploy'
$oldSecret=$env:DJANGO_SECRET_KEY
$switched=$false;$bootstrap=$false;$legacyRenamed=$false;$targetCreated=$false;$proxyCreated=$false
function D { param([string[]]$A); $r=& docker @A; if($LASTEXITCODE -ne 0){throw "Docker $($A[0]) failed ($LASTEXITCODE)"}; return $r }
function Container { param([string]$Name); if(@(D -A @('ps','-a','--format','{{.Names}}')) -notcontains $Name){return $null};return @(D -A @('inspect',$Name)|ConvertFrom-Json)[0] }
function Managed { param($C); if($C -and $C.Config.Labels.'io.kbo.managed-by' -ne 'kbo-salary-deploy'){throw "Refusing to alter unrelated container $($C.Name)"} }
function Check { param([string]$Url)
  for($i=0;$i -lt 60;$i++){try{$h=Invoke-RestMethod "$Url/health" -TimeoutSec 2;if($h.status -eq 'ok'){break}}catch{};if($i -eq 59){throw "Health timeout: $Url"};Start-Sleep -Seconds 1}
  foreach($path in @('/','/static/app.js','/static/styles.css')){if((Invoke-WebRequest "$Url$path" -UseBasicParsing -TimeoutSec 5).StatusCode -ne 200){throw "HTTP failure $path"}}
  foreach($kind in @('batter','pitcher')){
    $body=@{player_type=$kind;stats=@{games=120;wins=10}}|ConvertTo-Json -Depth 3
    $r=Invoke-RestMethod "$Url/api/v1/predict" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 5
    if($r.suggested_salary_krw -le 0){throw 'Invalid prediction'}
  }
  Write-Host "Service checks passed: $Url"
}
try {
  if((D -A @('info','--format','{{.OSType}}')).Trim() -ne 'linux'){throw 'Docker Linux mode required'}
  $existing=Container $service;Managed $existing
  $isGateway=$existing -and $existing.Config.Labels.'io.kbo.role' -eq 'gateway'
  $active=if($isGateway){D -A @('exec',$service,'python','-m','api.gateway','--active')}else{''}
  $target=if($active -eq 'kbo-salary-blue'){'kbo-salary-green'}else{'kbo-salary-blue'}
  $stale=Container $target;Managed $stale
  if($stale){D -A @('rm','-f',$target)|Out-Host}
  if(-not $SkipPull){D -A @('pull',$ImageRef)|Out-Host}
  $image=D -A @('image','inspect','--format','{{.Id}}',$ImageRef)
  D -A @('run','--rm',$image,'python','-m','ml.check_model')|Out-Host
  if(@(D -A @('network','ls','--format','{{.Name}}')) -notcontains $network){D -A @('network','create','--label',$label,$network)|Out-Host}
  else {
    $net=@(D -A @('network','inspect',$network)|ConvertFrom-Json)[0]
    if($net.Labels.'io.kbo.managed-by' -ne 'kbo-salary-deploy'){throw 'Unrelated deployment network'}
  }
  if($existing){$entry=@($existing.Config.Env|Where-Object{$_ -like 'DJANGO_SECRET_KEY=*'});if($entry.Count){$env:DJANGO_SECRET_KEY=$entry[0].Substring(18)}}
  if([string]::IsNullOrWhiteSpace($env:DJANGO_SECRET_KEY)){$env:DJANGO_SECRET_KEY=[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')}
  $common=@('--label',$label,'--network',$network,'--env','DJANGO_SECRET_KEY','--env','SALARY_API_URL=/','--env',"DEPLOYMENT_VERSION=$DeploymentVersion")
  D -A (@('run','-d','--name',$target,'--restart','unless-stopped','-p','127.0.0.1::8000','--label','io.kbo.role=backend')+$common+@($image))|Out-Host
  $targetCreated=$true
  $binding=D -A @('port',$target,'8000/tcp');$p=[int]($binding.Split(':')[-1]);Check "http://127.0.0.1:$p"
  if($isGateway){
    D -A @('exec',$service,'python','-m','api.gateway','--switch',$target)|Out-Host;$switched=$true
  } else {
    $bootstrap=$true
    if(Container "$service-next-gateway"){throw 'Recovery gateway exists; inspect before retry'}
    if(Container "$service-previous"){throw 'Recovery legacy service exists; inspect before retry'}
    if(@(D -A @('volume','ls','--format','{{.Name}}')) -notcontains $volume){D -A @('volume','create','--label',$label,$volume)|Out-Host}
    else {$v=@(D -A @('volume','inspect',$volume)|ConvertFrom-Json)[0];if($v.Labels.'io.kbo.managed-by' -ne 'kbo-salary-deploy'){throw 'Unrelated routing volume'}}
    D -A @('run','--rm','-v',"${volume}:/state",$image,'python','-m','api.gateway','--switch',$target)|Out-Host
    D -A (@('create','--name',"$service-next-gateway",'--restart','unless-stopped','-p',"127.0.0.1:${Port}:8000",'-v',"${volume}:/state",'--label','io.kbo.role=gateway')+$common+@($image,'python','-m','api.gateway'))|Out-Host
    $proxyCreated=$true
    if($existing){D -A @('stop','--timeout','20',$service)|Out-Host;D -A @('rename',$service,"$service-previous")|Out-Host;$legacyRenamed=$true}
    D -A @('rename',"$service-next-gateway",$service)|Out-Host
    D -A @('start',$service)|Out-Host
  }
  Check "http://127.0.0.1:$Port"
  if($legacyRenamed){D -A @('rm',"$service-previous")|Out-Host;$legacyRenamed=$false}
  Write-Host "Routing switch complete: $target; version=$DeploymentVersion; http://127.0.0.1:$Port"
  Write-Host 'Previous blue/green backend stays running for in-flight requests until the next deployment.'
} catch {
  $failure=$_
  Write-Host "Deployment failure: $failure"
  if($switched){D -A @('exec',$service,'python','-m','api.gateway','--switch',$active)|Out-Host;Check "http://127.0.0.1:$Port";Write-Host 'Previous routing restored.'}
  elseif($bootstrap -and $proxyCreated){
    foreach($name in @($service,"$service-next-gateway")){$c=Container $name;if($c -and $c.Config.Labels.'io.kbo.role' -eq 'gateway'){D -A @('rm','-f',$name)|Out-Host}}
    if($legacyRenamed){D -A @('rename',"$service-previous",$service)|Out-Host;D -A @('start',$service)|Out-Host;Check "http://127.0.0.1:$Port"}
  }
  if($targetCreated){D -A @('rm','-f',$target)|Out-Host}
  throw $failure
} finally {$env:DJANGO_SECRET_KEY=$oldSecret}
