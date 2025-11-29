@echo off
setlocal
set ROOT=%~dp0
cd /d "%ROOT%"

if not exist "%ROOT%venv\" (
    echo [提示] 建议在虛擬環境中運行，以免污染全局環境。
)

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo 找不到 PyInstaller，正在安裝...
    pip install pyinstaller || goto :error
)

set ICON=%ROOT%assets\ninjaicon.ico
if not exist "%ICON%" (
    echo 找不到 %ICON%，請確認檔案存在。
    goto :error
)

pyinstaller ^
  --noconfirm ^
  --windowed ^
  --name FruitNinjaAR ^
  --icon "%ICON%" ^
  --add-data "assets;assets" ^
  --add-data "background;background" ^
  --add-data "cursor;cursor" ^
  --add-data "fonts;fonts" ^
  --add-data "fruits;fruits" ^
  --add-data "sounds;sounds" ^
  --add-data "music;music" ^
  --add-data "hand_tracking.py;." ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  fruit_ninja_enhanced.py || goto :error

echo.
echo 打包完成，雙擊 dist\FruitNinjaAR\FruitNinjaAR.exe 即可遊玩。
goto :eof

:error
echo.
echo 打包失敗，請檢查上方訊息。
exit /b 1

