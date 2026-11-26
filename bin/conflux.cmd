@echo off
setlocal DisableDelayedExpansion
rem Python applies defaults after parsing, while the launcher forwards the full command line.
python "%~dp0..\conflux.py" --windows-wrapper %*
exit /b %errorlevel%
