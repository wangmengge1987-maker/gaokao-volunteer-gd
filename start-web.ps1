# 一键启动广东高考志愿网页版
# 用法：在项目根目录执行  .\start-web.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$server = Join-Path $root "server"
Set-Location $server

if (-not (Test-Path ".venv")) {
    Write-Host "首次运行，安装依赖..."
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt -q
}

if (-not (Test-Path "gaokao.db")) {
    Write-Host "初始化示例数据库..."
    .\.venv\Scripts\python scripts\init_db.py
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  广东高考志愿助手 - 网页版" -ForegroundColor Cyan
Write-Host "  浏览器打开: http://127.0.0.1:8002" -ForegroundColor Green
Write-Host "  按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

.\.venv\Scripts\uvicorn.exe main:app --reload --host 0.0.0.0 --port 8002
