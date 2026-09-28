# One-shot bootstrap for PowerShell: create the virtualenv, install, seed, start the modules.
#
#   .\run.ps1          three modules on three ports: model API :8000, database API :8001, web :8080
#   .\run.ps1 single   the same three modules in one process on :8000 (what Render runs)
#   .\run.ps1 seed     first training of the regression models + demo account (demo / demo123)
#   .\run.ps1 train    install dev dependencies, retrain the SVM and regression models, redraw figures
#   .\run.ps1 test     install dev dependencies and run the pytest suite
#
# PowerShell twin of run.sh, for people who do not have Git Bash open.

param([ValidateSet('serve', 'single', 'seed', 'train', 'test')][string]$Mode = 'serve', [int]$Port = 0)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Say($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Die($msg) { Write-Host "`nLOI: $msg" -ForegroundColor Red; exit 1 }

# --- 1. Locate a Python interpreter -------------------------------------------
# `py -3` is the reliable launcher on Windows; a bare `python` may be the
# Microsoft Store stub that exits without doing anything.
$pyExe = $null
$pyArgs = @()
foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
    $exe = $c[0]
    # $c[1..($c.Count - 1)] would reverse-index a single-element array, so guard it.
    $rest = @()
    if ($c.Count -gt 1) { $rest = @($c[1..($c.Count - 1)]) }
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        & $exe @rest -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $pyExe = $exe; $pyArgs = $rest; break }
    }
}
if (-not $pyExe) { Die "Khong tim thay Python 3.10+. Cai tai https://www.python.org/downloads/ va tich 'Add python.exe to PATH'." }

# --- 2. Create the virtualenv on first run ------------------------------------
if (-not (Test-Path '.venv')) {
    Say 'Tao moi truong ao .venv (chi lan dau)'
    & $pyExe @pyArgs -m venv .venv
}
$vpy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { Die 'Moi truong ao hong. Xoa thu muc .venv roi chay lai lenh nay.' }

# --- 3. Configuration: .env with a generated JWT secret -------------------------
if (-not (Test-Path '.env')) {
    Say 'Tao .env tu .env.example (sinh JWT_SECRET ngau nhien)'
    $secret = & $vpy -c "import secrets; print(secrets.token_urlsafe(48))"
    (Get-Content '.env.example' -Encoding UTF8) -replace '^JWT_SECRET=.*', "JWT_SECRET=$secret" |
        Set-Content '.env' -Encoding UTF8
}
foreach ($line in Get-Content '.env' -Encoding UTF8) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim() }
}

# --- 4. Install dependencies ---------------------------------------------------
& $vpy -m pip install --quiet --upgrade pip
if ($Mode -eq 'train' -or $Mode -eq 'test') {
    Say 'Cai thu vien huan luyen va kiem thu (requirements-dev.txt)'
    & $vpy -m pip install --quiet -r requirements-dev.txt
} else {
    Say 'Cai thu vien cho 3 module (requirements.txt)'
    & $vpy -m pip install --quiet -r requirements.txt
}

switch ($Mode) {
    'train' {
        Say 'Huan luyen lai SVM phan loai'; & $vpy train.py
        Say 'Huan luyen lai 5 mo hinh hoi quy'; & $vpy train_regression.py
        Say 'Ve lai hinh cho bao cao'; & $vpy figures.py; & $vpy figures_regression.py
        Say "Xong. Chay '.\run.ps1' de khoi dong dich vu."
        exit 0
    }
    'test' { Say 'Chay bo kiem thu pytest'; & $vpy -m pytest; exit $LASTEXITCODE }
    'seed' { & $vpy seed.py; exit $LASTEXITCODE }
}

if (-not (Test-Path 'svm_model.pkl')) { Die "Thieu svm_model.pkl. Chay '.\run.ps1 train' de huan luyen lai." }

Say 'Seed: train lan dau (neu chua co mo hinh) + tai khoan demo'
& $vpy seed.py

# Open the browser on the first port once every given port accepts connections.
function Open-WhenReady([int[]]$ports) {
    Start-Job -ScriptBlock {
        param($ports)
        for ($i = 0; $i -lt 120; $i++) {
            $ready = $true
            foreach ($p in $ports) {
                try { $c = New-Object Net.Sockets.TcpClient('127.0.0.1', $p); $c.Close() } catch { $ready = $false }
            }
            if ($ready) { Start-Process "http://127.0.0.1:$($ports[0])/"; break }
            Start-Sleep -Milliseconds 500
        }
    } -ArgumentList (, $ports) | Out-Null
}

# --- 5. Serve ------------------------------------------------------------------
if ($Mode -eq 'single') {
    if ($Port -eq 0) { $Port = [int]$env:MODEL_API_PORT }
    $env:SERVICE_MODE = 'single'
    Say "Che do gop: ca 3 module trong mot tien trinh tai http://127.0.0.1:$Port  (Ctrl+C de dung)"
    Open-WhenReady $Port
    & $vpy -m uvicorn app:app --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

$env:SERVICE_MODE = 'split'
Say 'Khoi dong 3 module  (Ctrl+C de dung ca ba)'
Write-Host "    API mo hinh : http://127.0.0.1:$($env:MODEL_API_PORT)/docs"
Write-Host "    API CSDL    : http://127.0.0.1:$($env:DB_API_PORT)/docs"
Write-Host "    Giao dien   : http://127.0.0.1:$($env:WEB_PORT)/   (tai khoan demo / demo123)`n"

$procs = @(
    Start-Process -FilePath $vpy -ArgumentList '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', $env:MODEL_API_PORT -NoNewWindow -PassThru
    Start-Process -FilePath $vpy -ArgumentList '-m', 'uvicorn', 'db_api.main:app', '--host', '127.0.0.1', '--port', $env:DB_API_PORT -NoNewWindow -PassThru
)
Open-WhenReady @([int]$env:WEB_PORT, [int]$env:MODEL_API_PORT, [int]$env:DB_API_PORT)
try {
    & $vpy -m uvicorn web.server:app --host 127.0.0.1 --port $env:WEB_PORT
} finally {
    $procs | ForEach-Object { if (-not $_.HasExited) { Stop-Process -Id $_.Id -Force } }
}
