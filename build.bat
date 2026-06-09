@echo off
chcp 65001 >nul
echo ========================================
echo 解限机路网补给助手 - 打包脚本
echo ========================================
echo.

echo [1/3] 检查依赖...
python -c "import mss, cv2, PIL" 2>nul
if %errorlevel% neq 0 (
    echo 缺少依赖，正在安装...
    pip install -r requirements.txt
)

echo [2/3] 获取版本号...
for /f "tokens=*" %%a in ('git describe --tags --abbrev^=0 2^>nul') do set VER=%%a
if "%VER%"=="" set VER=dev
echo 版本: %VER%

echo [3/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] 开始打包...
python -m PyInstaller --onefile --windowed --uac-admin --collect-all rapidocr --name="MechaBreakAuto-%VER%" --add-data "templates;templates" --clean main.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo 打包成功!
    echo 输出: dist\MechaBreakAuto-%VER%.exe
    echo ========================================
) else (
    echo.
    echo 打包失败，请检查错误信息
)

pause
