# 创建每天09:00运行的计划任务（以当前用户身份运行）
$taskName = "高考招生计划每日爬取"
$scriptPath = "C:\Users\wangm\Projects\gaokao-volunteer-gd\server\daily_crawl.bat"
$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 注销已有任务（如果存在）
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 注册新任务
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "wangm" -RunLevel Highest -Force -Description "每天09:00搜索各高校2026招生计划新闻，更新数据库，7月2日后自动停止"

if ($?) {
    Write-Host "✅ 计划任务创建成功！每天 09:00 自动运行（用户: wangm）"
    $task = Get-ScheduledTask -TaskName $taskName
    Write-Host "   状态: $($task.State)"
    Write-Host "   下次运行: $((Get-ScheduledTaskInfo -TaskName $taskName).NextRunTime)"
} else {
    Write-Host "❌ 创建失败，请尝试以管理员身份运行此脚本"
}
