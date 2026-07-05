# setup.ps1 — Windows 一键建立虚拟环境并安装依赖
# 用法：powershell -ExecutionPolicy Bypass -File setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── 1. 定位项目根目录（脚本所在位置）──────────────────────────────
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# ── 2. 检查 Python 版本 ────────────────────────────────────────────
$PY = $null
foreach ($cmd in @("python", "py", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            # Agent 模块依赖最高支持 3.12，不支持 3.13+
            if ($major -eq 3 -and $minor -ge 10 -and $minor -le 12) {
                $PY = $cmd; break
            }
        }
    } catch { }
}
if (-not $PY) {
    Write-Error "Compatible Python version not found (3.10–3.12 required).`nCurrent Agent dependencies do not support 3.13+, please install 3.12: https://www.python.org/downloads/release/python-3129/"
    exit 1
}
Write-Host "[1/4] Using interpreter: $PY ($(& $PY --version 2>&1))  [Supported: 3.10–3.12]" -ForegroundColor Cyan

# ── 3. 创建虚拟环境 ────────────────────────────────────────────────
$VenvDir = Join-Path $Root ".venv"
if (Test-Path $VenvDir) {
    Write-Host "[2/4] .venv already exists, skipping creation" -ForegroundColor Yellow
} else {
    Write-Host "[2/4] Creating .venv ..." -ForegroundColor Cyan
    & $PY -m venv $VenvDir
}

# ── 4. 升级 pip 并安装依赖 ─────────────────────────────────────────
$PipExe  = Join-Path $VenvDir "Scripts\pip.exe"
$ReqFile = Join-Path $Root "requirements.txt"

Write-Host "[3/4] Upgrading pip ..." -ForegroundColor Cyan
& $PipExe install --upgrade pip --quiet

Write-Host "[4/4] Installing requirements.txt ..." -ForegroundColor Cyan
& $PipExe install -r $ReqFile

# ── 5. 提示激活方式 ────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Setup complete! To activate the environment:" -ForegroundColor Green
Write-Host ""
Write-Host "   .venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host " To start the service:" -ForegroundColor Green
Write-Host ""
Write-Host "   cd backend" -ForegroundColor White
Write-Host "   python run.py" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green