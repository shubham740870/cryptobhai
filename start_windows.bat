@echo off
REM ============================================
REM  CryptoBhai Bot - Windows one-click starter
REM  Bas is file pe DOUBLE-CLICK karo!
REM ============================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
title CryptoBhai Bot

REM Pehli baar? Token pooch lo aur .env me save karo
if not exist .env (
  echo.
  echo   Pehli baar setup chal raha hai...
  echo   Telegram me @BotFather kholo, /mybots bhejo,
  echo   apna bot select karo, API Token - copy karo,
  echo   aur wo TOKEN yahan paste karo.
  echo.
  set /p TOKEN=Token yahan paste karo:
  echo TELEGRAM_TOKEN=!TOKEN!>.env
  echo.
  echo   Token save ho gaya!
)

where python >nul 2>nul
if errorlevel 1 (
  echo ❌ Python nahi mila! Pehle python.org se Python install karo.
  echo    Install karte waqt "Add Python to PATH" pe tick zaroor karna.
  pause
  exit /b
)

echo Dependencies check ho rahi hai (pehli baar me 1-2 min)...
pip install -q -r requirements.txt

echo.
echo ============================================
echo   Bot chalu ho gaya!
echo   Is window ko BAND MAT karna - jab tak
echo   khuli hai, bot Telegram pe kaam karta hai.
echo   Band karne ke liye: Ctrl+C
echo ============================================
echo.
python agent.py
pause
