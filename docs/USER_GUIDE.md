# Hướng dẫn sử dụng

## Thao tác
1. Chạy MagicHub (biểu tượng ba màu hiện ở khay hệ thống).
2. Trong file manager, **chọn một hoặc nhiều file**.
3. **Giữ `Ctrl+Alt+Shift`** — vòng tròn hiện tại con trỏ.
4. **Di chuột (không bấm)**: hướng tới nhóm rồi kéo ra ngoài → vòng tự đổi sang tác vụ của nhóm; chọn tác vụ bằng hướng. Về tâm để quay lại nhóm. Dòng mô tả hiện dưới vòng.
5. **Nhả phím** để chạy. Nhả khi chưa chọn tác vụ (ở tâm hoặc vòng nhóm) = huỷ.
6. Một số tác vụ hỏi thêm (mật khẩu, từ khoá, vùng crop…). Xong → thông báo; **bấm thông báo** để mở thư mục kết quả.

File gốc không bao giờ bị sửa; kết quả nằm cạnh file gốc (xem quy ước tên trong DATA.md).

## Tác vụ theo loại file
Chọn nhiều file thì tất cả phải cùng loại (trừ Merge nhận PDF+ảnh; Zip nhận mọi loại).

| Loại | Convert | Edit | Organize |
|---|---|---|---|
| **PDF** | DOCX, XLSX, PPTX, PNG, JPG, TXT | Protect, Redact, Highlight, Text, Image, Crop | Merge (≥2), Split, ↻90°, ↺90°, Compress, Pages, Images, Zip |
| **Ảnh** (png jpg webp bmp tiff gif) | PNG, JPG, WEBP, BMP, PDF (trừ định dạng hiện có) | Text, Image, Crop | Merge→PDF (≥2), ↻90°, ↺90°, Compress, Zip |
| **Word** (docx doc odt rtf) | PDF, TXT, PNG, JPG | — | Zip |
| **Excel** (xlsx xls ods csv) | PDF, CSV, PNG | — | Zip |
| **PowerPoint** (pptx ppt odp) | PDF, PNG, JPG, TXT | — | Zip |
| **Text** (txt md) | PDF | — | Zip |
| Khác | — | — | Zip |

## Ý nghĩa các tác vụ
| Tác vụ | Làm gì | Hỏi gì |
|---|---|---|
| Split | Tách PDF | Khoảng trang; trống = từng trang |
| Pages | Lấy các trang chọn ra PDF mới | Khoảng trang `1-3,5,7-` |
| Images | Lấy ảnh nhúng trong PDF vào thư mục | — |
| Compress | Nén PDF/ảnh; thông báo cho thấy dung lượng trước → sau | — |
| Protect | Đặt mật khẩu mở PDF | Mật khẩu 2 lần |
| Redact | Che đen + xoá thật nội dung khớp từ khoá | Từ khoá |
| Highlight | Tô sáng từ khoá | Từ khoá, màu |
| Text | Chữ/watermark lên mọi trang | Nội dung, vị trí, cỡ, màu |
| Image | Logo/chữ ký/tem lên mọi trang | File ảnh, vị trí, % rộng |
| Crop | Cắt vùng chọn | Kéo chuột trên bản xem trước trang đầu |

## Dòng lệnh
```bash
./run.sh actions            # tất cả tác vụ
./run.sh actions a.pdf      # tác vụ áp dụng cho a.pdf
./run.sh do edit.protect a.pdf -p password=abc
./run.sh do edit.crop a.png -p box=0,0,0.5,0.5
./run.sh menu a.pdf         # vòng tròn một lần, bấm chuột để chọn
```

## Đổi phím tắt
Sửa `config.json` (đường dẫn trong DATA.md) rồi khởi động lại MagicHub.

## Xử lý sự cố
| Hiện tượng | Cách xử lý |
|---|---|
| Không có gì xảy ra khi giữ phím | Kiểm tra phiên Wayland/quyền macOS (PLATFORM.md); xem `magichub.log` |
| "Chưa chọn file nào" | Cửa sổ focus phải là file manager đang có file được chọn; thử chọn lại rồi giữ phím |
| Vòng tròn mở rồi huỷ ngay | Giữ phím đủ lâu và **kéo ra ô tác vụ** trước khi nhả |
| Lỗi LibreOffice | Cài LibreOffice; đóng các cửa sổ LibreOffice đang treo |
| PDF → DOCX/XLSX xấu | Giới hạn đã biết, xem CONSTRAINTS.md |
