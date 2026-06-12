# 启动 ngrok v3 公网隧道
# 把本地的 http://127.0.0.1:8002 暴露到公网

$ngrok = "C:\Users\wangm\Projects\gaokao-volunteer-gd\ngrok.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动 ngrok 公网隧道" -ForegroundColor Cyan
Write-Host "  公网地址请在终端中查看 Forwarding 行" -ForegroundColor Yellow
Write-Host "  例如: https://xxxx.ngrok-free.app -> http://localhost:8002" -ForegroundColor Green
Write-Host "  关闭此窗口 = 关闭隧道" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 启动 ngrok v3
& $ngrok http http://127.0.0.1:8002
