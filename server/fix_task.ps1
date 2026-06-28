$taskName = "gaokao_crawl"
try {
    # Remove old task if exists (existing one with Chinese name)
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction -Execute "C:\Users\wangm\Projects\gaokao-volunteer-gd\server\daily_crawl.bat"
    $trigger = New-ScheduledTaskTrigger -Daily -At 09:00
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Register without explicit user (uses current user context)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

    $task = Get-ScheduledTask -TaskName $taskName
    Write-Host "SUCCESS"
    Write-Host "Status: $($task.State)"
    Write-Host "Next run: $((Get-ScheduledTaskInfo -TaskName $taskName).NextRunTime)"
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
}
