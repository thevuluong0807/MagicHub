#!/usr/bin/env bash
# Chạy từ gốc repo -> dist/MagicHub.app (cấp quyền Accessibility + Input Monitoring lần đầu)
set -e
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --name MagicHub --windowed --collect-submodules magichub --collect-all pdf2docx entry.py
