#!/usr/bin/env bash
# Chạy từ gốc repo -> dist/MagicHub/MagicHub
set -e
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --name MagicHub --windowed --collect-submodules magichub --collect-all pdf2docx entry.py
# Tự chạy khi đăng nhập: sửa Exec trong packaging/linux/magichub.desktop rồi copy vào ~/.config/autostart/
