# Nền tảng

Mức hỗ trợ: ✅ đã chạy thử · 🟡 viết theo tài liệu, **chưa chạy thử** · ❌ không chạy.

| | Linux X11 | Linux Wayland | Windows 10/11 | macOS |
|---|---|---|---|---|
| Hotkey giữ phím | ✅ | ❌ (pynput chỉ thấy phím của cửa sổ XWayland) | 🟡 | 🟡 cần quyền Accessibility |
| Lấy file chọn (Ctrl+C → clipboard) | ✅ đọc clipboard; 🟡 với Nautilus thật | — | 🟡 Explorer ghi CF_HDROP, Qt đọc được | 🟡 Cmd+C trong Finder |
| Vòng tròn overlay trong suốt | ✅ | 🟡 cần compositor | 🟡 | 🟡 |
| Engine (convert/edit/organize) | ✅ | ✅ | 🟡 | 🟡 |
| `menu` / `do` (không hotkey) | ✅ | ✅ (overlay có thể không đặt được vị trí con trỏ) | 🟡 | 🟡 |

## Cài chung
1. Python ≥ 3.10.
2. `python -m venv .venv` → cài `requirements.txt`.
3. (Tuỳ chọn) **Tesseract** cho OCR: Linux `apt install tesseract-ocr tesseract-ocr-vie`; Windows/macOS tải/`brew install tesseract`. Phải nằm trong PATH.
4. Cài **LibreOffice** (chỉ cần cho convert Office): Linux `apt install libreoffice`; Windows/macOS tải từ libreoffice.org. Tool tự tìm `soffice` trong PATH và các thư mục cài mặc định.
5. Chạy `run.sh` (Linux/macOS) hoặc `run.bat` (Windows).

## Linux
- Kiểm tra phiên: `echo $XDG_SESSION_TYPE`. `x11` → dùng hotkey bình thường.
- **Cài tích hợp một lệnh**: `./run.sh install-integration` (AppImage: `./MagicHub-x86_64.AppImage install-integration`) ghi autostart + mục Nautilus (Scripts) / Nemo (chuột phải) / Dolphin (Service menu). Gỡ: thêm `--remove`.
- **Wayland (Ubuntu 22.04+ mặc định)**: chọn "Ubuntu on Xorg" ở màn hình đăng nhập, hoặc dùng đường dự phòng Nautilus script (bấm chuột để chọn):
  ```bash
  mkdir -p ~/.local/share/nautilus/scripts
  cat > ~/.local/share/nautilus/scripts/MagicHub <<'EOF'
  #!/usr/bin/env bash
  IFS=$'\n'; exec /đường/dẫn/MagicHub/run.sh menu $NAUTILUS_SCRIPT_SELECTED_FILE_PATHS
  EOF
  chmod +x ~/.local/share/nautilus/scripts/MagicHub
  ```
  Chuột phải file → Scripts → MagicHub.
- Tray trên GNOME cần extension *AppIndicator* (Ubuntu có sẵn). Không có tray thì tool vẫn chạy, thông báo in ra stdout.
- Tự chạy khi đăng nhập: tạo `~/.config/autostart/magichub.desktop` với `Exec=/đường/dẫn/MagicHub/run.sh`.

## Windows
- `run.bat` dùng `pythonw` (không hiện cửa sổ console). Tự chạy: đặt shortcut của `run.bat` vào `shell:startup`.
- Hotkey **không hoạt động khi cửa sổ đang focus chạy quyền Administrator** (UIPI chặn).
- Phím chữ + Ctrl: tool đọc mã phím ảo (`vk`) để tránh ký tự điều khiển — chưa kiểm chứng; nếu hotkey không nhận, đổi `hotkey.key` sang `space` hoặc phím F.
- Menu dự phòng: shortcut tới `run.bat menu "%1"` đặt trong thư mục `shell:sendto`.

## macOS
- Lần đầu cấp quyền **Accessibility** và **Input Monitoring** cho Terminal/Python (System Settings → Privacy & Security), nếu không phím tắt không nhận.
- Tool gửi **Cmd+C** thay vì Ctrl+C.
- Modifier `ctrl`/`alt` giữ nguyên nghĩa Control/Option; `cmd` = ⌘.
- Đóng gói `.app` chưa làm (v0.4). Hiện chạy qua terminal/venv.

## Wayland chi tiết (v0.4, chưa chạy thử)
- Daemon phát hiện `XDG_SESSION_TYPE=wayland`: **không bật hotkey** (pynput chỉ thấy phím của cửa sổ XWayland), hiện thông báo hướng dẫn; tray vẫn chạy.
- `menu FILE...` chạy Qt bằng XWayland (`QT_QPA_PLATFORM=xcb`): vòng tròn mở **giữa màn hình** (Wayland không cho đọc/đặt vị trí con trỏ), di chuột vào vòng rồi **click** tác vụ.
- Chưa làm: hotkey toàn cục qua portal `org.freedesktop.portal.GlobalShortcuts` (cần GNOME 48+/KDE 6; Ubuntu 22.04 không có) và gửi Ctrl+C qua RemoteDesktop portal.

## Đóng gói (CI: `.github/workflows/release.yml`, đẩy tag `v*`)
| OS | Sản phẩm | Ghi chú |
|---|---|---|
| Windows | `MagicHub-Setup.exe` (Inno Setup, không cần admin; tuỳ chọn tự chạy + Send to) và `MagicHub-windows.zip` | Chưa ký số → SmartScreen cảnh báo |
| Linux | `MagicHub-x86_64.AppImage` và `MagicHub-linux.tar.gz` | |
| macOS | `MagicHub-macos.dmg` (`.app` chạy ở thanh menu, ký ad-hoc) | Chưa notarize: chuột phải → Open lần đầu; cấp Accessibility + Input Monitoring |
