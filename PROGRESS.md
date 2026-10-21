# PROGRESS

> **Đọc file này đầu mỗi phiên làm việc** trước khi sửa gì. Cuối phiên: cập nhật "Trạng thái" + "Việc tiếp theo", thêm mục nhật ký.

## Trạng thái (2026-10-19)
- Bản hiện tại: **v0.9.1**. CI: v0.6.0 xanh cả 3 OS. `tests/test_engine.py` ALL PASS.
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

## 2026-10-21 — v0.9.1
- Hotfix Protect/Unlock: bấm OK không đóng hộp thoại. `ask_form.value()` dựng dict có `w.currentText`/`w.value` tính ngay nên `QLineEdit` ném `AttributeError` trong slot `accept()` (chỉ in ra console). Nay dùng lambda. Test `test_ask_form`.

## 2026-10-19 — v0.9.0
- Tự cập nhật (`updater.py`, không import Qt): hỏi GitHub API `releases/latest` (stdlib urllib, lỗi mạng = im lặng). Có bản mới → thẻ + mục khay "⬆ Cập nhật lên vX". AppImage: tải bản mới (có %, huỷ được), thay file đang chạy, khởi động lại sau 2 s. Windows đã đóng gói: tải và chạy `MagicHub-Setup.exe /SILENT`. macOS/source: mở trang Release. Config `update_check`, `last_update_check` (≤1 lần/ngày); menu khay "Kiểm tra cập nhật". Chưa có kiểm checksum/chữ ký (Release chưa công bố checksum). Test `test_updater` (server cục bộ, huỷ giữa chừng). Windows/macOS chưa thử thật.

## 2026-10-19 — v0.8.1
- Sửa thẻ tiến trình kẹt "đang chạy" và không huỷ/đóng được: `done` so `files is files` nhưng Qt sao chép list khi chuyển luồng -> luôn sai. Nay signal truyền chính `Job`.
- Thẻ luôn có ✕. PDF→Word có % và huỷ được (bắt log `(i/n) Page` của pdf2docx; `Cancelled` giờ kế thừa `BaseException` để không bị `except Exception` của thư viện nuốt). Huỷ khi bước cuối không ngắt được: xoá kết quả vừa tạo. `sys.setswitchinterval(0.002)`.
- Tests: `test_docx_progress_hook`, mở rộng `test_hub_toast` (việc >600 ms xong bình thường; huỷ muộn).

## 2026-10-19 — v0.8.0
- **Engine Office** (`actions/office.py`): Windows/macOS mặc định dùng Microsoft Office nếu có (Windows: PowerShell COM, không thêm dependency; macOS: osascript, ghi qua Group Container của Office), lỗi thì rơi về LibreOffice. `config.engine` = `auto|office|libreoffice` (+ menu khay "Engine Office"). Ép `office` mà chưa cài → báo lỗi rõ. Mac chỉ PDF; Windows làm cả pdf/txt(Word)/csv(Excel)/pptx. **Chưa thử trên Windows/macOS thật** (máy dev Linux); logic chọn engine có test giả lập.
- **Tiến trình + huỷ** (`base.py`: `bind/report/steps/scope/run_proc/Cancelled`, thread-local theo Job): mọi vòng lặp file/trang chính dùng `steps()`, vòng lồng tự chia khoảng; LibreOffice/Office chạy qua `run_proc` nên huỷ được (giết cả nhóm tiến trình). Chuyển PDF→Word chưa có % (pdf2docx không có callback) → thanh chạy vô định.
- **Thẻ tiến trình** (`toast.py`): góc dưới-phải, hiện sau 600 ms nếu việc chưa xong; % + đã chạy + ước tính còn lại, nút Huỷ; khi xong/lỗi đổi thành thẻ kết quả (Mở thư mục / Mở file), tự ẩn sau 9 s (rê chuột = giữ). Thay bong bóng khay cho done/fail; khay chỉ còn dùng khi thẻ đang bận việc khác.
- **Giao diện** (`theme.py`): Fusion + QSS kiểu Fluent (font hệ thống, góc bo 6–10 px, nút chính màu nhấn, sáng/tối theo hệ điều hành). Hộp thoại có tiêu đề + mô tả, nhãn trên ô nhập, nút chính là động từ (Cắt, Lưu, Áp dụng, Xoá vĩnh viễn) và "Huỷ". Crop: thanh công cụ trên, nền tối quanh ảnh, tay nắm vuông trắng kiểu Snipping Tool. `dialogs.header/buttons`; `_front` bỏ autoDefault cho nút ngoài QDialogButtonBox (tránh nút phụ bị tô màu chính).
- Tests: `test_progress_engine`, `test_hub_toast`. Bẫy: widget thêm vào layout của cha đã hiện phải `show()` thủ công.

## 2026-10-19 — v0.7.0
- Sửa gốc lỗi Crop không mở: `dialogs.py` import `..actions` (sai) thay `.actions`; lỗi `ask` giờ báo lên khay. Crop mở với khung full mặc định; hộp thoại vừa khít ảnh.
- Crop làm lại (`dialogs._CropLabel`): xem trước áp EXIF như bước cắt thật (trước đây ảnh điện thoại xem trước lệch hướng so với kết quả), không phóng to ảnh nhỏ, kéo trong vùng = di chuyển, kéo cạnh/góc = đổi cỡ, khoá tỉ lệ (1:1, 4:3, 3:2, 16:9, 3:4, 9:16), tối vùng bị bỏ + lưới 1/3 + kích thước px thật. Ảnh lưu qua `save_img` (JPEG chất lượng 95, alpha→nền trắng). Test `test_cropwidget` (sự kiện chuột giả).
- `actions/extra.py`: Resize (ảnh, % hoặc px), Strip (EXIF ảnh; metadata/XML/JS PDF), Số trang (`edit.headfoot`, `{n}` `{N}`, đúng cả trang xoay), Flatten (`doc.bake`), Unlock (cần mật khẩu), Compare (`organize.compare`, đúng 2 PDF → PDF tô đỏ chỗ khác). Test `test_v07`.
- HEIC/HEIF: thêm `pillow-heif`, `heic/heif` vào loại ảnh (convert, markup, crop… dùng được); build script thêm `--collect-all pillow_heif`.
- Chưa làm: xoá nền ảnh (rembg quá nặng cho gói chính), thử chuột thật Crop mới.

## 2026-10-19 — v0.6.0
- Sandbox LibreOffice bằng bubblewrap (`base.sandbox_prefix`): ro-bind `/`, không mạng, tmpfs `/tmp` `/run`, chỉ ghi outdir + profile; file nguồn ro-bind lại. Test `test_sandbox` (ghi ngoài vùng bị chặn, không mạng) + test_convert chạy qua sandbox.
- Reorder: xoay phải/trái từng trang (`params.rotate`).
- Workflow: bước installer Windows tách riêng, `continue-on-error`, tự cài Inno Setup nếu thiếu, `MSYS2_ARG_CONV_EXCL`; `.iss` dùng `x64`.
- Chưa làm (cần môi trường/giấy tờ không có): hotkey Wayland qua portal GlobalShortcuts (cần GNOME 48+/KDE 6, máy dev X11), ký số Windows + notarize macOS (cần chứng chỉ trả phí), thử OCR (cần cài Tesseract), sandbox Windows/macOS và sandbox cho PyMuPDF.

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
