$root = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $root "backend"
$frontendRoot = Join-Path $root "frontend"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

$python = if (Test-Path $venvPython) {
    $venvPython
} else {
    where.exe python | Select-Object -First 1
}
if (-not $python) {
    throw "Could not locate python.exe on PATH."
}

# Node có thể nằm ở nvm-windows/scoop/chữ ký cài khác; chỉ dùng đường dẫn
# cứng làm phương án cuối nếu "node" không có trên PATH.
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node -or -not (Test-Path $node)) {
    $node = "C:\Program Files\nodejs\node.exe"
}
if (-not (Test-Path $node)) {
    throw "Could not locate node.exe on PATH or at C:\Program Files\nodejs\node.exe."
}

$backendLog = Join-Path $root "backend-dev.log"
$backendErr = Join-Path $root "backend-dev.err.log"
$frontendLog = Join-Path $root "frontend-dev.log"
$frontendErr = Join-Path $root "frontend-dev.err.log"

foreach ($path in @($backendLog, $backendErr, $frontendLog, $frontendErr)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")

$backend = Start-Process $python `
    -ArgumentList "-m", "uvicorn", "app.api.server:app", "--host", "localhost", "--port", "8000" `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden `
    -PassThru

$frontend = Start-Process $node `
    -ArgumentList "node_modules/vite/bin/vite.js", "--host", "localhost", "--port", "5173" `
    -WorkingDirectory $frontendRoot `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 3

Write-Output "Backend PID : $($backend.Id)"
Write-Output "Frontend PID: $($frontend.Id)"
Write-Output "Backend URL : http://localhost:8000/api/health"
Write-Output "Frontend URL: http://localhost:5173"
