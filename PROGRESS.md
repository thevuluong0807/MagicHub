# PROGRESS

> **Đọc file này đầu mỗi phiên làm việc** trước khi sửa gì. Cuối phiên: cập nhật "Trạng thái" + "Việc tiếp theo", thêm mục nhật ký.

## Trạng thái (2026-10-19)
- Bản hiện tại: **v0.5.0** (v0.4.0 đã có tag + Release CI). `tests/test_engine.py` ALL PASS.
- Có: vòng tròn + hotkey giữ phím; Convert (PDF/Office/ảnh/txt); Organize đủ bộ; Edit (protect, redact, highlight, text, image, crop); CLI `run|menu|do|actions`; 7 file docs.
- Đã kiểm: engine, hình học, clipboard→vòng tròn→job trên Linux/X11.
- Chưa kiểm: file manager thật (Nautilus/Explorer/Finder), Windows, macOS, Wayland.
- Mục lục docs: xem README.md. Lộ trình: docs/PLAN.md.

## Việc tiếp theo
1. Người dùng thử hotkey/click với file manager thật, báo lại. Nếu "Chưa chọn file": chuyển `send_copy` sang python-xlib XTest (Linux) / SendInput (Windows).
2. Xác nhận workflow GitHub Actions build 3 OS (chưa xem kết quả); thử Windows/macOS thật.
3. Cài Tesseract rồi thử Convert → OCR (chưa chạy thử).
4. Thử chuột thật: Draw, Redact xem trước, Reorder (mới chỉ test headless).
5. Chạy thử `install-integration` trong Nautilus thật; thử bản Windows/macOS từ Release (installer, dmg chưa chạy).
6. Thử chuột thật: Phím tắt…, Tuỳ chỉnh menu….
7. Ý tưởng sau v0.5: hotkey Wayland qua portal, sandbox file lạ, xoay từng trang trong Reorder, ký số/notarize.

## Nhật ký
Ghi mọi thay đổi ở đây, mới nhất ở trên.

## 2026-10-19 — v0.5.0
- Config `hotkeys` (danh sách, mỗi mục có `group` tuỳ chọn); config cũ `hotkey` tự migrate. `Hotkey.injecting` dùng chung để phím giả lập không kích hoạt tổ hợp khác. `Hub.on_pressed(hk, group)`; vòng một nhóm vào thẳng tác vụ (`Wheel.locked`).
- `config.menu` {hidden, order} áp dụng trong `actions.available()` (ẩn/sắp xếp; CLI `do` không bị ảnh hưởng).
- `settings.py`: `ask_hotkeys`, `ask_menu`; menu khay "Phím tắt…" và "Tuỳ chỉnh menu…". Test `test_v05` (migrate, ẩn/sắp xếp, hộp thoại offscreen).
- Gộp Text + Image + Draw thành `edit.markup` (label Markup, PDF và ảnh): bút, hình (rect/elip/đường/mũi tên, tô nền), chữ (+watermark chéo), ghi chú, ảnh, khung viền, "Mọi trang". Bỏ `edit.text`/`edit.image`/`edit.annotate` (CLI `do` cũ đổi sang `edit.markup`). Ảnh đi qua PDF tạm 96 dpi để dùng chung engine. Xem trước canvas khớp output (đã so ảnh).
- Thanh công cụ Markup chỉ hiện tuỳ chọn liên quan công cụ; Ctrl+Z, PgUp/PgDn. Thứ tự menu mặc định theo mức dùng (`DEFAULT_ORDER` trong `actions/__init__.py`).
- Bẫy: thuộc tính `width` trên QWidget là hàm; không đặt đè (dùng `stroke`).

## 2026-10-19 — v0.4.0
- `integrate.py` + CLI `install-integration [--remove]`: autostart, Nautilus script, Nemo action, Dolphin service menu; Windows SendTo/Startup `.cmd`; macOS LaunchAgent. Test Linux trong `test_integrate`.
- Wayland: daemon không bật hotkey, báo hướng dẫn; `menu` dùng XWayland, vòng mở giữa màn hình. Chạy thử giả lập `XDG_SESSION_TYPE=wayland` + offscreen: không lỗi; chưa thử Wayland thật.
- Đóng gói: Inno Setup `packaging/windows/MagicHub.iss`, macOS `.app` (LSUIElement) + `.dmg` ad-hoc, workflow build cả ba (chưa xác nhận CI).
- Hotkey toàn cục Wayland (portal GlobalShortcuts) và sandbox: chưa làm.

## 2026-10-19 — v0.3.0
- `viewer.py` mới: `PageCanvas` (vẽ tay / ghi chú / kéo vùng, toạ độ 0..1), `ask_annotate`, `ask_redact` (xem trước khớp từ khoá + vùng tay), `ask_reorder` (kéo thả thumbnail, xoá trang).
- Tác vụ mới: `edit.annotate` (Draw), `organize.reorder`; `edit.redact` nhận `rects`. Test mới `test_v03` (engine + canvas offscreen). Ghi chú in cứng bằng DejaVu nên có tiếng Việt.
- Vòng tròn nay có tới 9 ô Organize cho PDF; nếu chật cân nhắc gộp Pages vào Reorder.

## 2026-10-19 — v0.2.0
- Click tác vụ (vd Convert → PDF) mới chạy; nhả phím khi chưa trỏ tác vụ = huỷ; nhả khi đang trỏ = giữ vòng chờ click; click tâm/nhóm hoặc bấm phím tắt lần nữa = huỷ.
- Compress có 3 mức; thư mục kết quả tuỳ chọn (`output_dir`, menu khay, redirect trong `unique()`); Convert → OCR (cần Tesseract, chưa chạy thử).

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
