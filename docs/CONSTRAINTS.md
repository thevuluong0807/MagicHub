# Ràng buộc và giới hạn

## Nguyên tắc bất biến
1. **Không ghi đè file gốc.** Kết quả luôn là file/thư mục mới cạnh file gốc; trùng tên thì thêm `_1`, `_2`.
2. **Không âm thầm "thành công giả".** Redact/Highlight không tìm thấy từ khoá → báo lỗi, không tạo file.
3. **Không gửi dữ liệu ra ngoài.** Mọi xử lý cục bộ, không mạng.
4. **Nhẹ máy.** Một job tại một thời điểm; LibreOffice chạy với `nice 10` (POSIX).

## Chất lượng chuyển đổi (ước lượng)
| Từ → Sang | Chất lượng | Ghi chú |
|---|---|---|
| Word/Excel/PPT → PDF | Tốt | LibreOffice; font lạ có thể bị thay |
| Mọi thứ → PNG/JPG (qua PDF) | Tốt | 150 dpi; nhiều trang → thư mục `page_001…` |
| Ảnh ↔ ảnh, ảnh → PDF | Tốt | JPG/BMP mất kênh trong suốt (nền trắng); không hỗ trợ HEIC |
| PDF → TXT | Tốt với PDF có text | PDF scan ra rỗng → dùng Convert → OCR trước |
| PDF → DOCX | Trung bình | `pdf2docx`; bố cục phức tạp/nhiều cột có thể vỡ |
| PDF → XLSX | Trung bình | Chỉ bảng có đường kẻ/căn hàng rõ; mỗi bảng 1 sheet `P<trang>_T<bảng>`; không có bảng → lỗi |
| PDF → PPTX | Thấp | Mỗi trang = 1 slide chứa **ảnh** (không sửa chữ được) |
| PDF → OCR | Chưa kiểm | Cần cài Tesseract (`apt install tesseract-ocr tesseract-ocr-vie`); chỉ hiện khi tìm thấy `tesseract`; 200 dpi/trang, chậm với PDF dài |
| Excel → CSV | Chỉ sheet đầu | Hành vi mặc định của LibreOffice |
| PPT/ODP → TXT | Trung bình | Qua PPTX, lấy text khung chữ |

## Edit
| Tác vụ | Giới hạn |
|---|---|
| Redact | Xoá thật (gỡ text/ảnh dưới vùng che), theo từ khoá và/hoặc vùng kéo tay (vùng tay chỉ áp dụng file đầu). Không nhận diện chữ trong ảnh: PDF scan cần OCR trước hoặc kéo vùng tay |
| Crop PDF | Đặt CropBox (ẩn phần ngoài, **không xoá** nội dung). Chưa phù hợp để giấu thông tin nhạy cảm — dùng Redact |
| Text/Image | Trang PDF có thuộc tính xoay sẵn có thể đặt lệch hướng. Font Unicode: DejaVu Sans / Arial |
| Protect | AES-256, một mật khẩu cho cả mở và chủ sở hữu. **Mất mật khẩu = mất file**, không khôi phục được |
| Word/Excel/PPT | Không có Edit tại chỗ. Hướng đi: convert sang PDF rồi Edit |
| Draw | Nét vẽ là annotation PDF (sửa được trong trình xem PDF khác); ghi chú là hộp chữ **in cứng vào trang** (hỗ trợ tiếng Việt), không sửa lại được. Chỉ 1 file mỗi lần; cỡ hộp ghi chú ước lượng, chữ dài có thể bị cắt |

## Organize
- Reorder: chỉ 1 PDF; chỉ đổi thứ tự/xoá trang (chưa xoay từng trang).
- Merge sắp xếp **theo tên file (tự nhiên)**, không theo thứ tự chọn, vì file manager không đảm bảo thứ tự clipboard.
- Compress: 3 mức. PDF: Nhẹ 150 dpi/Q80 · Vừa 110/Q65 · Mạnh 72/Q45; ảnh: cạnh dài tối đa 3200/2560/1600 px. PDF chủ yếu là text hầu như không nhỏ đi. Có thể ra file lớn hơn nếu PDF đã tối ưu — thông báo hiện cả hai dung lượng.

## Hotkey và lấy file chọn
- Dựa vào Ctrl+C giả lập: **ghi đè clipboard trong ~0,2 s** (text được khôi phục; nội dung khác như ảnh/file đã copy trước đó thì mất).
- Cửa sổ đang focus phải là file manager có chọn file. Ứng dụng chặn phím giả lập (chạy quyền admin trên Windows, một số game/remote desktop) sẽ không hoạt động.
- Tổ hợp mặc định `Ctrl+Alt+M`; tránh phím mà ứng dụng khác dùng khi giữ (autorepeat phím chính sẽ gửi liên tục).
- Wayland: pynput không bắt được phím toàn cục → xem PLATFORM.md.

## Bảo mật
- File lạ (PDF/Office độc hại) được mở bằng PyMuPDF/LibreOffice trong cùng tiến trình/tiến trình con của người dùng, **chưa sandbox**. Chỉ dùng với file tin cậy. Sandbox chưa làm (chưa có kế hoạch cụ thể).
- Mật khẩu chỉ nằm trong bộ nhớ lúc chạy; `history.jsonl` **không lưu tham số**.

## License
- PyMuPDF: **AGPL-3.0** (hoặc thương mại). Phân phối MagicHub kèm PyMuPDF buộc tuân AGPL hoặc mua license; dùng cá nhân không bị ảnh hưởng.
- PySide6: LGPL. pynput: LGPL. pdf2docx: GPL-3.0 (cân nhắc nếu phân phối). LibreOffice: MPL (gọi như chương trình ngoài).
