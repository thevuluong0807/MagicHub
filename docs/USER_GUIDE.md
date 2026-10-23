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
| Compress | Nén PDF, ảnh, Word/Excel/PowerPoint (docx/xlsx/pptx: nén ảnh bên trong); thông báo cho thấy dung lượng trước → sau | Mức nén (Nhẹ/Vừa/Mạnh/Cực mạnh) + Dung lượng tối đa (MB). Đặt ví dụ 25 thì tự tăng mức nén cho tới khi ≤ 25 MB; nén mạnh nhất vẫn quá thì báo lỗi, không tạo file |
| Mã hoá | Ẩn danh hoá văn bản trước khi gửi AI/bên ngoài: thay tên người, đơn vị, mã dự án, email, SĐT… bằng mã `[PERSON_1]`, `[ORG_2]`… (docx, xlsx, pptx, txt, md). Ra 2 file: `x_anon.docx` + `x_anon_mapping.xlsx` | Bảng gợi ý tự dò (tick/bỏ, xem số lần), ô thêm tay (nhớ lại lần sau), xoá metadata tác giả/công ty |
| Giải mã | Trả lại giá trị gốc cho file đã mã hoá hoặc bản AI trả về (chịu được AI bỏ ngoặc `[]`/đổi hoa thường) | Tự tìm `x_anon_mapping.xlsx` cạnh file; không có thì hỏi chọn file mapping |
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


## Mã hoá văn bản (Anonymize / Restore)
- **Bảng mapping chứa dữ liệu gốc**: giữ riêng, không gửi kèm văn bản đã mã hoá. Sheet "Lưu ý" trong file liệt kê chỗ còn sót.
- Tự dò: email, URL, IP, SĐT, số CCCD/CMND, mã dạng `BVL-2026-01`, tên đơn vị (Công ty/Tập đoàn/Viện… + tên), tên người (họ phổ biến hoặc sau Ông/Bà/TS…), cụm viết hoa lặp lại, viết tắt in hoa lặp ≥ 3 lần. Có thể sót hoặc nhầm: luôn xem lại bảng gợi ý.
- Dạng gọi tắt ("Viettel" từ "Tập đoàn Viettel") được dò thành mục riêng, cùng họ mã: `[ORG_1]` và `[ORG_1s]`, nên AI thấy là cùng một đơn vị còn Restore vẫn trả đúng từng dạng.
- **Khớp không phân biệt hoa thường, dấu, khoảng trắng** (kể cả khoảng trắng đặc biệt, gạch nối lạ). "VIETTEL", "viettel", "Tap doan Viettel" đều bị mã hoá. Mỗi dạng viết khác dạng chuẩn có mã biến thể (`[ORG_1v1]`, `[ORG_1v2]`…) nên Restore trả đúng nguyên văn từng chỗ.
- **Từ điển dự án**: chọn/gõ tên từ điển trong hộp thoại, mỗi dòng một cụm (tuỳ chọn tiền tố `ORG: `, `PERSON: `, `PROJECT: `…). Cụm trong từ điển luôn được mã hoá dù app không dò ra. Tick "Lưu các mục đã tick vào từ điển" để lần sau tự áp dụng. Lưu trong `config.json` (`anonymize_dicts`).
- Mã hoá và giải mã chạy hoàn toàn trên máy bạn bằng bảng tra cứu, không dùng AI và không cần mạng.
- Chưa xử lý: ảnh/biểu đồ/tên sheet trong file (cảnh báo ở sheet "Lưu ý"), PDF (convert PDF→Word trước), .doc/.xls/.ppt cũ.
- Che tên không phải ẩn danh tuyệt đối: ngữ cảnh ("giám đốc công ty ở Quận 1…") vẫn có thể lộ.

### Mã hoá clipboard (không cần file)
Menu khay → **Mã hoá clipboard**:
1. Copy đoạn văn bản, chọn "Mã hoá văn bản trong clipboard…", tick các mục trong bảng gợi ý. Văn bản đã mã hoá được chép lại vào clipboard, dán cho AI.
2. Copy câu trả lời của AI, chọn "Giải mã văn bản trong clipboard": mã được thay lại bằng giá trị gốc, kết quả nằm trong clipboard.
- Mapping **gần nhất** lưu ở `clipboard_mapping.json` trong thư mục cấu hình (chứa dữ liệu gốc; quyền 0600 trên Linux/macOS). Mã hoá đoạn mới thì thay mapping cũ. "Xoá mapping clipboard" để xoá ngay.

## Windows: không nháy cửa sổ console
Mọi tiến trình con (PowerShell cho Office, LibreOffice, Tesseract, taskkill, git/pip khi cập nhật) chạy với cờ ẩn cửa sổ.
