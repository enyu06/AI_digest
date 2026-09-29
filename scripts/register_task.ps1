# run_enriched.ps1 を毎日 10:00 に実行するタスクを登録する（現在のユーザーで実行）。
# PC が停止・スリープしていた場合は、次に起動したときに実行される。

$script = Join-Path $PSScriptRoot "run_enriched.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

Register-ScheduledTask -TaskName "AI Daily Digest (enriched)" -Action $action `
    -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output "Registered task 'AI Daily Digest (enriched)' (daily 10:00)."
