@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PlotForge

rem 콘솔(cmd) 없이 GUI 런처(PlotForge.pyw)를 실행한다. pythonw 우선 → py -w → 폴백 python.
rem 포트 변경: 실행.bat 8000 (인자는 %* 로 런처에 전달)
where pythonw >nul 2>nul && ( start "" pythonw "%~dp0PlotForge.pyw" %* & exit /b 0 )
where py >nul 2>nul && ( start "" py -w "%~dp0PlotForge.pyw" %* & exit /b 0 )
where python >nul 2>nul && ( python "%~dp0PlotForge.pyw" %* & exit /b 0 )

echo [오류] Python을 찾을 수 없습니다.
echo        https://www.python.org 에서 설치 후 다시 실행하세요.
pause
exit /b 1
