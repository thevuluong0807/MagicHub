# Kế hoạch

## Mục tiêu
Một thao tác duy nhất (giữ phím + hướng chuột) để chạy convert / edit / organize trên file đang chọn, không mở ứng dụng nào.

## Quyết định đã chốt
| # | Quyết định | Lý do |
|---|---|---|
| 1 | Cơ chế: giữ phím → vòng tròn tại con trỏ → di chuột chọn nhóm/tác vụ → **click** tác vụ để chạy | Tránh xung đột với kéo-thả file; click tránh chạy nhầm khi nhả phím |
| 2 | Python + PySide6 (UI) + pynput (hotkey) + PyMuPDF/Pillow (engine) + LibreOffice (Office) | Một ngôn ngữ cho UI và engine, cross-platform, không tự viết codec |
| 3 | Lấy file đang chọn bằng Ctrl+C giả lập + đọc clipboard | Chạy được trên cả 3 OS mà không cần API riêng của từng file manager |
| 4 | Mỗi tác vụ là một mục đăng ký (`Action`), vòng tròn dựng từ registry | Thêm tác vụ không sửa UI |
| 5 | Luôn xuất file mới cạnh file gốc, không ghi đè | An toàn dữ liệu |
| 6 | Máy xử lý tuần tự (1 luồng) | Máy lag; LibreOffice chỉ chạy 1 tiến trình |

## Lộ trình
| Bản | Nội dung | Trạng thái |
|---|---|---|
| **v0.1** | Vòng tròn + hotkey; Convert (PDF/Office/ảnh/txt); Organize đủ bộ; Edit: protect, redact, highlight, text, image, crop | **Xong, engine đã test; hotkey+clipboard kiểm trên Linux/X11** |
| **v0.2** | OCR (Tesseract) cho PDF scan; mức nén tuỳ chọn; thư mục đích tuỳ chọn; vòng đơn đổi nội dung + giao diện cyber; click chọn tác vụ | **Xong** (OCR chưa chạy thử vì máy chưa cài Tesseract); hộp thoại tiến độ: dùng thông báo khay |
| **v0.3** | Vẽ tay + ghi chú (trình xem nhỏ); redact có xem trước + chọn vùng tay; sắp xếp/xoá trang bằng ảnh thu nhỏ | **Xong** (test headless + render ảnh; chưa thử chuột thật) |
| v0.4 | Linux Wayland (extension GNOME / portal); macOS đóng gói .app; Windows installer | Chưa làm |
| v0.5 | Cấu hình menu tuỳ biến (ẩn/hiện/sắp xếp tác vụ), tuỳ chọn nhiều hotkey | Chưa làm |

## Việc đã kiểm / chưa kiểm
- Đã kiểm tự động: toàn bộ engine (`tests/test_engine.py`), hình học vòng tròn, đọc selection từ clipboard, luồng hotkey → clipboard → vòng tròn → job (X11).
- **Chưa kiểm trên máy thật**: Windows, macOS, Wayland. Code đã tính (xem PLATFORM.md) nhưng chưa chạy.
- Chưa kiểm bằng file manager thật (Nautilus/Explorer/Finder) khi Ctrl+C giả lập; cần người dùng thử và báo lại.
