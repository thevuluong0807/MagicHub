@echo off
rem Chạy từ gốc repo: packaging\windows\build.bat -> dist\MagicHub\MagicHub.exe
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --name MagicHub --windowed --collect-submodules magichub --collect-all pdf2docx --collect-all pillow_heif entry.py
rem Tự chạy cùng Windows: đặt shortcut của MagicHub.exe vào shell:startup
