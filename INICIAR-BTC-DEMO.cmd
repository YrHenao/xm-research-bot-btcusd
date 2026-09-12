@echo off
cd /d "%~dp0"
echo BTCUSD DEMO: lotaje 1.5x antes de redondeo, target 3:1, sin stop ni timeout.
echo El EA BTCResearchDemo debe estar compilado y adjunto en MT4.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m bot.mt4_bridge --config config.demo.json --folder "%APPDATA%\MetaQuotes\Terminal\Common\Files\BTCResearch"
) else if exist "%USERPROFILE%\Yr\YHFOREX\xm-research-bot\.venv\Scripts\python.exe" (
  "%USERPROFILE%\Yr\YHFOREX\xm-research-bot\.venv\Scripts\python.exe" -m bot.mt4_bridge --config config.demo.json --folder "%APPDATA%\MetaQuotes\Terminal\Common\Files\BTCResearch"
) else (
  py -3 -m bot.mt4_bridge --config config.demo.json --folder "%APPDATA%\MetaQuotes\Terminal\Common\Files\BTCResearch"
)
pause
