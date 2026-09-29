# 研究室 PC のタスク スケジューラから毎日実行し、当日のレポートを ASEL2 で採点・日本語化して push する。
# GitHub Actions が先に未採点版を作っていればそれを差し替え、まだなら収集から行う。
# 登録: powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$date = (Get-Date).ToString("yyyy-MM-dd")
Start-Transcript -Path (Join-Path $logDir "$date.log") -Append | Out-Null

function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed (exit $LASTEXITCODE)" }
}

try {
    $python = Join-Path $repo ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Invoke-Native "python" @("-m", "venv", ".venv")
    }
    Invoke-Native $python @("-m", "pip", "install", "-q", "-r", "requirements.txt")

    Invoke-Native "git" @("pull", "--rebase", "--autostash")
    Invoke-Native $python @("main.py")

    Invoke-Native "git" @("add", "reports", "collectors/seen.json")
    & git diff --staged --quiet
    if ($LASTEXITCODE -ne 0) {
        Invoke-Native "git" @("commit", "-m", "digest: $date (enriched)")
        # 採点中に GitHub Actions が push していた場合に備えて取り込み直す
        & git pull --rebase
        if ($LASTEXITCODE -ne 0) {
            & git rebase --abort
            throw "git pull --rebase failed; resolve manually and push."
        }
        Invoke-Native "git" @("push")
    } else {
        Write-Output "No changes to commit."
    }
} catch {
    Write-Output "[error] $_"
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
