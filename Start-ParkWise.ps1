$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$logs = Join-Path $projectRoot 'outputs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null

# Phone QR codes must point to this computer's Wi-Fi/LAN address, not loopback.
$networkConfig = Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } | Select-Object -First 1
$lanAddress = if ($networkConfig) { $networkConfig.IPv4Address.IPAddress | Select-Object -First 1 } else { '127.0.0.1' }
$env:FRONTEND_BASE_URL = "http://${lanAddress}:5173"
$env:PASSWORD_RESET_URL = "$($env:FRONTEND_BASE_URL)/reset-password"
$env:VITE_API_BASE_URL = '/'

function Test-Endpoint([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch { return $false }
}

if (-not (Test-Endpoint 'http://127.0.0.1:8000/docs')) {
    Start-Process -FilePath (Join-Path $projectRoot '.venv313\Scripts\python.exe') -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory (Join-Path $projectRoot 'parkwise') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'admin-api.out.log') -RedirectStandardError (Join-Path $logs 'admin-api.err.log')
}
if (-not (Test-Endpoint 'http://127.0.0.1:5173/admin')) {
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'node_modules/vite/bin/vite.js','--host','0.0.0.0' -WorkingDirectory (Join-Path $projectRoot 'parkwise\frontend-web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'admin-web.out.log') -RedirectStandardError (Join-Path $logs 'admin-web.err.log')
}

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-Endpoint 'http://127.0.0.1:8000/docs') -and (Test-Endpoint 'http://127.0.0.1:5173/admin')) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw "ParkWise could not start. Check the server logs in $logs" }
Write-Host 'ParkWise is ready: http://127.0.0.1:5173/admin'
Write-Host "Phone access (same Wi-Fi): $($env:FRONTEND_BASE_URL)/user"
Start-Process 'http://127.0.0.1:5173/admin'
