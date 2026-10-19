# Hướng dẫn sử dụng

## Thao tác
1. Chạy MagicHub (biểu tượng ba màu hiện ở khay hệ thống).
2. Trong file manager, **chọn một hoặc nhiều file**.
3. **Giữ `Ctrl+Alt+Shift`** — vòng tròn hiện tại con trỏ.
4. **Di chuột (không bấm)**: hướng tới nhóm rồi kéo ra ngoài → vòng tự đổi sang tác vụ của nhóm; chọn tác vụ bằng hướng. Về tâm để quay lại nhóm. Dòng mô tả hiện dưới vòng.
5. **Click** vào tác vụ (ví dụ Convert → PDF) để chạy; có thể nhả phím tắt trước khi click. Nhả phím khi chưa trỏ vào tác vụ, hoặc click ở tâm/nhóm = huỷ.
6. Một số tác vụ hỏi thêm (mật khẩu, từ khoá, vùng crop…). Xong → thông báo; **bấm thông báo** để mở thư mục kết quả.

File gốc không bao giờ bị sửa; kết quả nằm cạnh file gốc (xem quy ước tên trong DATA.md).

## Tác vụ theo loại file
Chọn nhiều file thì tất cả phải cùng loại (trừ Merge nhận PDF+ảnh; Zip nhận mọi loại).

| Loại | Convert | Edit | Organize |
|---|---|---|---|
| **PDF** | DOCX, XLSX, PPTX, PNG, JPG, TXT, OCR | Markup, Highlight, Redact, Crop, Số trang, Protect, Unlock, Flatten, Strip | Merge (≥2), Split, ↻90°, ↺90°, Compress, Reorder, Pages, Images, Compare (đúng 2), Zip |
| **Ảnh** (png jpg webp bmp tiff gif heic) | PNG, JPG, WEBP, BMP, PDF (trừ định dạng hiện có) | Markup, Crop, Resize, Strip | Merge→PDF (≥2), ↻90°, ↺90°, Compress, Zip |
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
| Compress | Nén PDF/ảnh; thông báo cho thấy dung lượng trước → sau | Mức nén (Nhẹ/Vừa/Mạnh) |
| OCR | PDF scan → PDF chọn/copy được chữ (cần Tesseract) | — |
| Protect | Đặt mật khẩu mở PDF | Mật khẩu 2 lần |
| Redact | Che đen + xoá thật nội dung khớp từ khoá và/hoặc vùng tự kéo; có bước xem trước | Từ khoá (tuỳ chọn), rồi xem trước: khung cam = khớp, kéo chuột thêm vùng đen |
| Markup | Trình soạn cho PDF **và ảnh**: Bút, Hình (chữ nhật, elip, đường, mũi tên, tô nền), Chữ (kể cả watermark chéo), Ghi chú, Ảnh (logo/chữ ký), Khung viền | Chọn công cụ, màu, nét; bấm/kéo trên trang. "Mọi trang" áp chữ/ảnh/hình/khung cho cả file. Ctrl+Z hoàn tác, PgUp/PgDn đổi trang |
| Reorder | Đổi thứ tự / xoay / xoá trang PDF (1 file) | Kéo thả ảnh thu nhỏ; chọn + Xoay phải/trái hoặc Xoá |
| Highlight | Tô sáng từ khoá | Từ khoá, màu |
| Crop | Cắt vùng chọn | Kéo vẽ vùng; kéo trong vùng để dời, kéo cạnh/góc để đổi cỡ; chọn tỉ lệ khoá |
| Resize | Đổi cỡ ảnh | % hoặc chiều rộng px |
| Số trang | Header/footer | `{n}` trang, `{N}` tổng |
| Strip | Xoá metadata | Ảnh: EXIF/GPS; PDF: tác giả, XML, JS |
| Flatten | Ép ghi chú/form | Không sửa lại được |
| Unlock | Gỡ mật khẩu PDF | Cần mật khẩu hiện tại |
| Compare | So 2 PDF | Chọn đúng 2 file; kết quả tô đỏ chỗ khác |

## Dòng lệnh
```bash
./run.sh actions            # tất cả tác vụ
./run.sh actions a.pdf      # tác vụ áp dụng cho a.pdf
./run.sh do edit.protect a.pdf -p password=abc
./run.sh do edit.crop a.png -p box=0,0,0.5,0.5
./run.sh menu a.pdf         # vòng tròn một lần, bấm chuột để chọn
```

## Menu khay (chuột phải icon)
- **Phím tắt…**: thêm/xoá phím tắt; mỗi phím mở cả vòng hoặc vào thẳng một nhóm (vd `Ctrl+Alt+F9` → Convert). Chỉ giữ 2+ phím modifier cũng được.
- **Tuỳ chỉnh menu…**: mỗi nhóm một tab; bỏ tích để ẩn tác vụ, kéo thả để đổi thứ tự. Áp dụng ngay.
- **Thư mục kết quả…** / **Lưu cạnh file gốc**: chọn nơi lưu kết quả.

## Xử lý sự cố
| Hiện tượng | Cách xử lý |
|---|---|
| Không có gì xảy ra khi giữ phím | Kiểm tra phiên Wayland/quyền macOS (PLATFORM.md); xem `magichub.log` |
| "Chưa chọn file nào" | Cửa sổ focus phải là file manager đang có file được chọn; thử chọn lại rồi giữ phím |
| Vòng tròn mở rồi huỷ ngay | Kéo ra ô tác vụ rồi **click** (nhả phím khi chưa trỏ vào tác vụ sẽ huỷ) |
| Lỗi LibreOffice | Cài LibreOffice; đóng các cửa sổ LibreOffice đang treo |
| Lỗi Microsoft Office | Đóng hộp thoại đang mở trong Word/Excel/PowerPoint; hoặc đặt `engine` = `libreoffice` ở menu khay |
| File lớn chạy lâu | Thẻ tiến trình góc dưới-phải hiện % và nút Huỷ |
| PDF → DOCX/XLSX xấu | Giới hạn đã biết, xem CONSTRAINTS.md |
