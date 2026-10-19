# Dữ liệu

## Vị trí
| OS | Config + log + history | Cache (lock, profile LibreOffice) |
|---|---|---|
| Linux | `~/.config/magichub/` | `~/.cache/magichub/` |
| Windows | `%APPDATA%\magichub\` | `%LOCALAPPDATA%\magichub\` |
| macOS | `~/Library/Application Support/magichub/` | `~/Library/Caches/magichub/` |

## config.json
Tạo tự động lần chạy đầu; thiếu khoá → dùng mặc định; file hỏng → bỏ qua (không ghi đè).
```json
{
  "hotkeys": [{ "modifiers": ["ctrl", "alt", "shift"], "key": "", "group": null },
              { "modifiers": ["ctrl", "alt"], "key": "f9", "group": "convert" }],
  "output_dir": null,
  "menu": { "hidden": ["edit.protect"], "order": ["edit.crop"] },
  "engine": "auto"
}
```
| Khoá | Giá trị | Ghi chú |
|---|---|---|
| `hotkeys[].modifiers` | tập con của `ctrl`, `alt`, `shift`, `cmd` | Phải giữ đủ các phím này |
| `hotkeys[].key` | `""`, một ký tự hoặc tên phím pynput (`space`, `f9`…) | `""` = chỉ giữ modifier (khuyên dùng: phím chữ làm file manager gõ chữ vào ô tìm kiếm). Nhả bất kỳ phím nào của tổ hợp = xác nhận |
| `hotkeys[].group` | `null` \| `convert` \| `edit` \| `organize` | `null` = cả vòng; tên nhóm = vào thẳng tác vụ của nhóm đó |
| `output_dir` | đường dẫn thư mục hoặc `null` | `null` = kết quả cạnh file gốc; đặt thì mọi kết quả vào thư mục đó (không tồn tại → cạnh file gốc) |
| `menu.hidden` | danh sách `id` tác vụ | Ẩn khỏi vòng tròn và `actions` (CLI `do` vẫn chạy được). Nhóm hết tác vụ thì không hiện |
| `engine` | `auto` \| `office` \| `libreoffice` | Engine chuyển Word/Excel/PowerPoint. `auto`: Windows/macOS dùng Microsoft Office nếu đã cài (lỗi thì rơi về LibreOffice), Linux dùng LibreOffice. `office`: ép Microsoft Office (chưa cài → báo lỗi). Đổi được ở menu khay "Engine Office" |
| `menu.order` | danh sách `id` tác vụ | Thứ tự trong nhóm; `id` không có trong danh sách giữ thứ tự mặc định, xếp sau |

Config cũ (v0.1–0.4) có khoá `hotkey` (một tổ hợp) tự chuyển thành `hotkeys` khi đọc. Mọi mục đổi được ngay từ menu khay (Phím tắt… / Tuỳ chỉnh menu… / Thư mục kết quả…), có hiệu lực không cần khởi động lại.

## Action (registry, trong code — `actions/base.py`)
| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | str | `<nhóm>.<tên>` hoặc `convert.<kind>.<đích>`; dùng cho CLI `do` và history |
| `group` | `convert` \| `edit` \| `organize` | Nhóm trên vòng tròn |
| `label` | str ≤ ~9 ký tự | Chữ trên ô |
| `tip` | str | Mô tả đầy đủ, hiện dưới vòng khi rê tới |
| `kinds` | tuple \| None | Loại file chấp nhận: `pdf img doc xls ppt txt`; None = mọi loại |
| `min_files` | int | Số file tối thiểu (Merge = 2) |
| `ask` | hàm \| None | Trả `dict` tham số, hoặc `None` = người dùng huỷ |
| `check` | hàm \| None | Điều kiện thêm theo danh sách file |
| `run` | hàm | `run(files, params) -> list[Path]` |

Loại file theo phần mở rộng:
`pdf` · `img`: png jpg jpeg webp bmp tif tiff gif · `doc`: docx doc odt rtf · `xls`: xlsx xls ods csv · `ppt`: pptx ppt odp · `txt`: txt md.

## Bảng đích Convert (`convert.py: TARGETS`)
| Nguồn | Đích |
|---|---|
| pdf | docx, xlsx, pptx, png, jpg, txt, ocr (chỉ khi có Tesseract) |
| doc | pdf, txt, png, jpg |
| xls | pdf, csv, png |
| ppt | pdf, png, jpg, txt |
| img | png, jpg, webp, pdf, bmp (bỏ đích trùng định dạng nguồn) |
| txt | pdf |

## Tham số các tác vụ có hộp thoại
| id | params |
|---|---|
| `organize.split` | `ranges`: `""` = từng trang; `"1-3,5"` = mỗi nhóm một file; `"7-"` = từ 7 đến hết |
| `organize.compress` | `level`: Nhẹ (giữ nét) · Vừa · Mạnh |
| `organize.pages` | `ranges` như trên, gộp thành 1 PDF |
| `edit.protect` | `password` |
| `edit.redact` | `keywords` (tuỳ chọn; xuống dòng/`,`/`;` phân cách), `rects` (tuỳ chọn, chỉ file đầu): `[{page,x0,y0,x1,y1}]` tỉ lệ 0..1 |
| `edit.markup` | `marks`: danh sách; toạ độ 0..1 theo trang; mark có `all:true` áp mọi trang, không thì theo `page`. `ink{pts,color,w}` · `note{x,y,text}` · `text{x,y,text,size,color,rot}` (rot=45: watermark chéo, mờ, (x,y)=tâm) · `image{x,y,w,path}` (w = tỉ lệ bề rộng trang) · `shape{kind:rect\|ellipse\|line\|arrow,x0,y0,x1,y1,color,w,fill}` · `border{color,w,margin}`; `color` = [r,g,b] 0..1 |
| `organize.reorder` | `order`: chỉ số trang 0-based giữ lại theo thứ tự mới (trang vắng mặt bị xoá) |
| `edit.highlight` | `keywords`, `color`: Vàng · Xanh lá · Hồng |
| `edit.crop` | `box`: `(x0, y0, x1, y1)` tỉ lệ 0..1 theo trang/ảnh |

## history.jsonl
Mỗi dòng một JSON, chỉ ghi thêm. **Không lưu tham số** (có thể chứa mật khẩu).
```json
{"ts": 1792374280, "action": "organize.compress", "inputs": ["/a/t.pdf"], "outputs": ["/a/t_small.pdf"], "status": "ok"}
{"ts": 1792374300, "action": "edit.redact", "inputs": ["/a/t.pdf"], "outputs": [], "status": "error", "error": "Không tìm thấy từ khoá…"}
```

## Quy ước tên file kết quả
| Loại | Mẫu |
|---|---|
| Convert | `<tên>.<đuôi mới>`; PDF nhiều trang → ảnh: thư mục `<tên>_<png\|jpg>/page_001.png…` |
| Edit | `<tên>_protected / _redacted / _highlighted / _marked / _cropped` |
| Organize | `_merged`, `_rotated`, `_small`, `_reordered`, `_pages`, thư mục `_split/`, `_images/`, `<tên>.zip` (nhiều file: `archive.zip`) |
| Trùng tên | thêm `_1`, `_2`… |
