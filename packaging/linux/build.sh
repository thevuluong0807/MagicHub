#!/usr/bin/env bash
# Chạy từ gốc repo -> dist/MagicHub/MagicHub
set -e
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --name MagicHub --windowed --collect-submodules magichub --collect-submodules pynput --collect-all pdf2docx --collect-all pillow_heif entry.py
# Tự chạy khi đăng nhập: sửa Exec trong packaging/linux/magichub.desktop rồi copy vào ~/.config/autostart/
