@echo off
chcp 65001 >nul
set BASE=C:\Users\wangm\Projects\gaokao-volunteer-gd\server
set PYTHON=C:\Users\wangm\AppData\Local\Programs\Python\Python312\python.exe
set LOGDIR=%BASE%\logs
if not exist %LOGDIR% mkdir %LOGDIR%
cd /d %BASE%

REM Get date via PowerShell
for /f %%I in ('powershell -Command "Get-Date -Format yyyyMMdd"') do set today=%%I
set month=%today:~4,2%
set day=%today:~6,2%

REM Stop after Jul 2
if %month% GTR 6 goto :STOP
if %month% EQU 7 if %day% GTR 2 goto :STOP

REM Run crawl
echo [%date% %time%] start >> %LOGDIR%\daily_run.log
%PYTHON% -m scripts.crawl_plan_news --roundup-only >> %LOGDIR%\daily_run.log 2>&1
set RESULT=%ERRORLEVEL%
echo [%date% %time%] done exit=%RESULT% >> %LOGDIR%\daily_run.log
exit /b %RESULT%

:STOP
echo [%date% %time%] stopped >> %LOGDIR%\daily_crawl_stop.log
exit /b 0
