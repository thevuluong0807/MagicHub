#!/usr/bin/env bash
# Chạy từ gốc repo -> dist/MagicHub.app + MagicHub-macos.dmg
# App chạy ở thanh menu (không icon Dock). Lần đầu cấp Accessibility + Input Monitoring (System Settings -> Privacy & Security).
set -e
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --name MagicHub --windowed --osx-bundle-identifier com.magichub \
  --collect-submodules magichub --collect-all pdf2docx entry.py
plutil -insert LSUIElement -bool true dist/MagicHub.app/Contents/Info.plist
codesign --force --deep -s - dist/MagicHub.app   # ký ad-hoc; chưa notarize nên người dùng phải chuột phải -> Open lần đầu
hdiutil create -volname MagicHub -srcfolder dist/MagicHub.app -ov -format UDZO MagicHub-macos.dmg
