[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._/:@-]+$')]
    [string]$ImageRef,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_.-]+$')]
    [string]$ContainerName = 'kbo-salary',
    [ValidateRange(1024, 65535)]
    [int]$Port = 8080,
    [switch]$SkipPull
)

$ErrorActionPreference = 'Stop'
$candidate = "$ContainerName-candidate"
$backup = "$ContainerName-previous"
$managedLabel = 'io.kbo.managed-by'
$managedValue = 'kbo-salary-deploy'
$oldSecret = $env:DJANGO_SECRET_KEY
$candidateOwned = $false
$newOwned = $false
$oldRenamed = $false
$oldWasRunning = $false
$previousPort = $Port

function Invoke-Docker {
    param([string[]]$DockerArgs)
    $output = & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $($DockerArgs[0]) (exit $LASTEXITCODE)" }
    return $output
}

function Get-Container {
    param([string]$Name)
    $names = @(Invoke-Docker -DockerArgs @('container', 'ls', '-a', '--format', '{{.Names}}'))
    if ($names -notcontains $Name) { return $null }
    $json = Invoke-Docker -DockerArgs @('inspect', '--type', 'container', $Name)
    return @($json | ConvertFrom-Json)[0]
}

function Assert-Managed {
    param($Container)
    if ($Container -and $Container.Config.Labels.$managedLabel -ne $managedValue) {
        throw "Container $($Container.Name) belongs to another workflow/user. It will not be changed. Choose another name."
    }
}

function Test-Service {
    param([string]$BaseUrl, [string]$Name)
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 2
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { }
        $state = Get-Container -Name $Name
        if (-not $state -or -not $state.State.Running) {
            throw "Container $Name exited before becoming ready."
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "Timed out waiting for $BaseUrl/health" }
    foreach ($path in @('/', '/static/app.js', '/static/styles.css')) {
        $response = Invoke-WebRequest -Uri "$BaseUrl$path" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ne 200 -or -not $response.Content) { throw "Invalid HTTP response for $path" }
        if ($path -eq '/' -and $response.Content -notmatch 'data-api-url="/"') {
            throw 'Image does not use the same-origin container API.'
        }
    }
    foreach ($type in @('batter', 'pitcher')) {
        $stats = if ($type -eq 'batter') { @{ games = 120; home_runs = 15 } } else { @{ wins = 10; innings_pitched = 150 } }
        $body = @{ player_type = $type; stats = $stats } | ConvertTo-Json -Depth 3
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/v1/predict" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 5
        $salary = [double]$response.suggested_salary_krw
        if ([double]::IsNaN($salary) -or [double]::IsInfinity($salary) -or $salary -le 0 -or $salary -ne [math]::Floor($salary)) {
            throw "Invalid salary prediction for $type"
        }
        Write-Host "HTTP prediction OK: $type=$salary KRW"
    }
    Write-Host "Web/static/API checks passed: $BaseUrl"
}

try {
    $osType = Invoke-Docker -DockerArgs @('info', '--format', '{{.OSType}}')
    if ($osType.Trim() -ne 'linux') { throw 'Docker Desktop must be running Linux containers.' }
    $existing = Get-Container -Name $ContainerName
    Assert-Managed -Container $existing
    if ($existing) {
        $bindings = @($existing.HostConfig.PortBindings.'8000/tcp')
        if ($bindings.Count -gt 0) { $previousPort = [int]$bindings[0].HostPort }
    }
    # Refuse to discard an interrupted deployment's recovery container.
    if ((Get-Container -Name $backup) -or (Get-Container -Name $candidate)) {
        throw "Recovery/staging container already exists ($backup or $candidate). Inspect it before retrying."
    }
    if (-not $SkipPull) { Invoke-Docker -DockerArgs @('pull', $ImageRef) | Out-Host }
    # Pin both candidate and final instance to the actual image ID just pulled.
    $imageId = Invoke-Docker -DockerArgs @('image', 'inspect', '--format', '{{.Id}}', $ImageRef)
    Invoke-Docker -DockerArgs @('run', '--rm', $imageId, 'python', '-m', 'ml.check_model') | Out-Host

    # Keep the same Django key during replacement; never print it or pass it in argv.
    if ([string]::IsNullOrWhiteSpace($env:DJANGO_SECRET_KEY) -and $existing) {
        $entry = @($existing.Config.Env | Where-Object { $_ -like 'DJANGO_SECRET_KEY=*' })
        if ($entry.Count -gt 0) { $env:DJANGO_SECRET_KEY = $entry[0].Substring('DJANGO_SECRET_KEY='.Length) }
    }
    if ([string]::IsNullOrWhiteSpace($env:DJANGO_SECRET_KEY)) {
        $env:DJANGO_SECRET_KEY = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    }
    $common = @('--label', "$managedLabel=$managedValue", '--env', 'DJANGO_SECRET_KEY', '--env', 'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1', '--env', 'SALARY_API_URL=/')
    Invoke-Docker -DockerArgs (@('run', '-d', '--name', $candidate, '-p', '127.0.0.1::8000') + $common + @($imageId)) | Out-Host
    $candidateOwned = $true
    $binding = Invoke-Docker -DockerArgs @('port', $candidate, '8000/tcp')
    $candidatePort = [int]($binding.Split(':')[-1])
    Test-Service -BaseUrl "http://127.0.0.1:$candidatePort" -Name $candidate

    # Candidate passed; only now release the old service's port.
    if ($existing) {
        $oldWasRunning = [bool]$existing.State.Running
        if ($oldWasRunning) { Invoke-Docker -DockerArgs @('stop', '--timeout', '20', $ContainerName) | Out-Host }
        Invoke-Docker -DockerArgs @('rename', $ContainerName, $backup) | Out-Host
        $oldRenamed = $true
    }
    Invoke-Docker -DockerArgs (@('create', '--name', $ContainerName, '--restart', 'unless-stopped', '-p', "127.0.0.1:${Port}:8000") + $common + @($imageId)) | Out-Host
    $newOwned = $true
    Invoke-Docker -DockerArgs @('start', $ContainerName) | Out-Host
    Test-Service -BaseUrl "http://127.0.0.1:$Port" -Name $ContainerName
    Invoke-Docker -DockerArgs @('rm', '-f', $candidate) | Out-Host
    $candidateOwned = $false
    if ($oldRenamed) {
        Invoke-Docker -DockerArgs @('rm', $backup) | Out-Host
        $oldRenamed = $false
    }
    Write-Host "Deployment succeeded: http://127.0.0.1:$Port ($ContainerName)"
} catch {
    $failure = $_
    # Collect bounded logs from only containers created by this invocation.
    foreach ($name in @($candidate, $ContainerName)) {
        if (($name -eq $candidate -and $candidateOwned) -or ($name -eq $ContainerName -and $newOwned)) {
            $savedPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                & docker logs --tail 60 $name 2>&1 | ForEach-Object { Write-Host $_.ToString() }
            } finally { $ErrorActionPreference = $savedPreference }
        }
    }
    if ($newOwned) { Invoke-Docker -DockerArgs @('rm', '-f', $ContainerName) | Out-Host }
    if ($oldRenamed) {
        Invoke-Docker -DockerArgs @('rename', $backup, $ContainerName) | Out-Host
        if ($oldWasRunning) {
            Invoke-Docker -DockerArgs @('start', $ContainerName) | Out-Host
            Test-Service -BaseUrl "http://127.0.0.1:$previousPort" -Name $ContainerName
            Write-Host 'Previous service restored and verified.'
        }
    } elseif ($existing -and $oldWasRunning) {
        # Handle an old-container rename failure after a successful stop.
        Invoke-Docker -DockerArgs @('start', $ContainerName) | Out-Host
    }
    throw $failure
} finally {
    if ($candidateOwned) { Invoke-Docker -DockerArgs @('rm', '-f', $candidate) | Out-Host }
    $env:DJANGO_SECRET_KEY = $oldSecret
}
