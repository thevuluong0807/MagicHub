# PROGRESS

> **Đọc file này đầu mỗi phiên làm việc** trước khi sửa gì. Cuối phiên: cập nhật "Trạng thái" + "Việc tiếp theo", thêm mục nhật ký.

## Trạng thái (2026-10-19)
- Bản hiện tại: **v0.1.0 xong**. `tests/test_engine.py` ALL PASS (chạy lại 2026-10-19).
- Có: vòng tròn + hotkey giữ phím; Convert (PDF/Office/ảnh/txt); Organize đủ bộ; Edit (protect, redact, highlight, text, image, crop); CLI `run|menu|do|actions`; 7 file docs.
- Đã kiểm: engine, hình học, clipboard→vòng tròn→job trên Linux/X11.
- Chưa kiểm: file manager thật (Nautilus/Explorer/Finder), Windows, macOS, Wayland.
- Mục lục docs: xem README.md. Lộ trình: docs/PLAN.md.

## Việc tiếp theo
1. Người dùng thử hotkey với file manager thật, báo lại. Nếu "Chưa chọn file": chuyển `send_copy` sang python-xlib XTest (Linux) / SendInput (Windows).
2. v0.2: OCR (Tesseract/OCRmyPDF) cho PDF scan; mức nén tuỳ chọn; thư mục đích tuỳ chọn; hộp thoại tiến độ.
3. Sau đó v0.3 → v0.5 theo docs/PLAN.md.

## Nhật ký
Ghi mọi thay đổi ở đây, mới nhất ở trên.

## 2026-10-19 — UI v2
- Crash khi hiện vòng tròn: PySide6 6.12.0 hỏng refcount None (`Fatal Python error: none_dealloc`), tái hiện bằng gọi hàm void của QPainterPath. Sửa: ghim `PySide6-Essentials<6.12` (venv dùng 6.8.3), vẽ ô bằng đa giác thay QPainterPath.
- UI: một vòng duy nhất, kéo ra ngoài nhóm → vòng tự đổi sang tác vụ (không mở vòng ngoài), về tâm = quay lại; hiệu ứng mượt (fade/sáng dần); ô bo góc; tông cyber (cyan/magenta/xanh neon, font mono).
- `geometry.py` đổi API: `ring_arc`, `ring_hit`; test cập nhật.
- Chưa kiểm: cảm giác kéo với chuột thật.

## 2026-10-19 — hotkey, đóng gói
- Repo GitHub thevuluong0807/MagicHub, tag v0.1.0, workflow build 3 OS (chưa xác nhận kết quả) + AppImage Linux.
- Lỗi: giữ Ctrl+Alt+M làm Nautilus bật type-ahead ("Clear current selection for new search") vì `send_copy` nhả modifier khi phím `m` còn giữ. Sửa: mặc định đổi sang chỉ modifier Ctrl+Alt+Shift (`key: ""`), dialog tray "Đổi phím tắt…" nhận cả tổ hợp modifier-only. Tránh phím chữ làm phím chính.
- `norm()` thêm fallback theo vk cho Ctrl+chữ trên Linux.
- Chưa kiểm: hotkey mới với bàn phím thật.
- Lưu ý khi dev: `pkill -f` tự giết shell của tool; dùng `pkill -x MagicHub`.

## 2026-10-19 — v0.1.0
- Dựng khung dự án: engine (convert/organize/edit), vòng tròn (QPainter), hotkey giữ phím (pynput), tray + job nền, CLI `run|menu|do|actions`.
- Viết tài liệu: README, PLAN, FLOW, ARCHITECTURE, CONSTRAINTS, DATA, PLATFORM, USER_GUIDE.
- Kiểm: `tests/test_engine.py` ALL PASS (hình học, available, organize, convert gồm LibreOffice, bảng PDF→XLSX, edit).
- Kiểm trên Linux/X11: hotkey (XTest giả lập Ctrl+Alt+M) → clipboard → vòng tròn → job; render vòng tròn ra PNG để xem.
- Phát hiện: `QClipboard.text()` treo 5 s khi clipboard trống → chỉ gọi khi `mimeData().hasText()`.
- Phát hiện: `Controller.tap('c')` không phát được phím chữ trên X server này; `tap(KeyCode.from_vk(...))` thì được → `send_copy` dùng mã phím (Linux 0x63, Windows 0x43, macOS 8). Windows/macOS chưa chạy thử.

## Rủi ro mở
- Chưa thử Ctrl+C giả lập với file manager thật; nếu không chạy tool báo "Chưa chọn file". Phương án thay: python-xlib XTest trực tiếp (Linux), SendInput (Windows).
- Windows/macOS/Wayland chưa chạy thử.
