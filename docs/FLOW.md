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
Hotkey.released ──► Wheel.confirm
   • có tác vụ được chọn → chosen(action);  ngược lại (tâm / vòng trong) → huỷ
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
- Bán kính < 48 px: vùng chết (huỷ).
- 48–132 px: **vòng nhóm**. Hướng chuột chọn nhóm; nhóm được chọn bung vòng tác vụ.
- 132–272 px: **vòng tác vụ**. Hướng chuột chọn tác vụ trong cung của nhóm đó.
- Nhóm đầu tiên (Convert) nằm giữa hướng 12h; các nhóm còn lại chia đều theo chiều kim đồng hồ.
- Chỉ nhóm/tác vụ áp dụng được cho lựa chọn mới xuất hiện (xem bảng trong USER_GUIDE).

## 3. Luồng dự phòng
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
