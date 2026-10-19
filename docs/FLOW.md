# Luồng hoạt động

## 1. Luồng chính (giữ phím)

```
Người dùng chọn file trong file manager
   │  giữ Ctrl+Alt+Shift (mặc định)
   ▼
Hotkey.pressed ──► Hub.on_pressed
   • lưu text clipboard (nếu có), xoá clipboard
   • thread phụ: nhả modifier hotkey, gửi Ctrl+C (Cmd+C trên macOS), khôi phục modifier
   • chờ 200 ms
   ▼
Hub.after_copy
   • đọc danh sách file từ clipboard (text/uri-list hoặc x-special/gnome-copied-files)
   • khôi phục text clipboard cũ
   • người dùng đã nhả phím? → bỏ
   • không có file → thông báo "Chưa chọn file"
   ▼
actions.available(files) → các nhóm/tác vụ áp dụng được
   ▼
Wheel.open  (overlay không nhận chuột/focus, hiện tại con trỏ)
   • timer 16 ms: vector chuột → geometry.hit() → (nhóm, tác vụ) → vẽ lại
   ▼
Wheel.mousePressEvent (click)
   • đang trỏ vào tác vụ → chosen(action);  ngược lại → huỷ
Hotkey.released ──► Wheel.release (chưa trỏ tác vụ → huỷ)
   ▼
Hub.on_chosen
   • action.ask (nếu có) → hộp thoại tham số;  Cancel → dừng
   • đẩy Job vào QThreadPool (1 luồng)
   ▼
Job.run → action.run(files, params) → danh sách file/thư mục kết quả
   ▼
Thông báo khay "Xong" (bấm để mở thư mục) + ghi history.jsonl
```

## 2. Quy tắc chọn trên vòng tròn
Một vòng duy nhất, nội dung đổi tại chỗ (không mở thêm vòng ngoài):
- Bán kính < 58 px: vùng chết ở tâm.
- **Vòng nhóm** (mặc định): hướng chuột rê sáng nhóm. Kéo ra nửa ngoài của ô (≥ 109 px) → vòng tự đổi sang **tác vụ của nhóm đó** (hiệu ứng ~110 ms).
- **Vòng tác vụ**: các tác vụ chia đều 360°, tác vụ đầu giữa hướng 12h. Hướng chuột chọn tác vụ.
- Về tâm (< 58 px) → quay lại vòng nhóm. **Click** tác vụ = chạy. Nhả phím tắt khi chưa trỏ vào tác vụ = huỷ; nhả khi đang trỏ vào tác vụ = vòng giữ lại chờ click. Click tâm/nhóm = huỷ; bấm phím tắt lần nữa = huỷ.
- Chỉ nhóm/tác vụ áp dụng được cho lựa chọn mới xuất hiện (xem bảng trong USER_GUIDE).
- Giao diện: ô bo góc, tông cyber (cyan Convert · magenta Edit · xanh neon Organize).

## 3. Luồng dự phòng
- Phím tắt gắn nhóm (`hotkeys[].group`): vòng chỉ có nhóm đó, mở thẳng ở tác vụ (không có bước chọn nhóm). Nếu lựa chọn chỉ còn một nhóm áp dụng được, vòng cũng vào thẳng tác vụ.
- `magichub menu FILE...`: mở vòng tròn một lần tại con trỏ; **bấm chuột** để chọn, Esc để huỷ. Dùng cho script, menu chuột phải, hoặc nơi hotkey không chạy (Wayland).
- `magichub do ACTION FILE... -p k=v`: chạy không GUI.

## 4. Xử lý lỗi
| Tình huống | Hành vi |
|---|---|
| Không có file trong clipboard | Thông báo, không mở vòng tròn |
| PDF có mật khẩu | Lỗi rõ tên file, không tạo file |
| Redact/Highlight không khớp từ khoá | Lỗi, không tạo file (tránh tưởng đã redact) |
| Thiếu LibreOffice | Lỗi hướng dẫn cài |
| Lỗi bất kỳ trong tác vụ | Thông báo + ghi `magichub.log` + `history.jsonl` (status=error); file gốc không đổi |
