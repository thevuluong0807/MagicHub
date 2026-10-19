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
{ "hotkey": { "modifiers": ["ctrl", "alt", "shift"], "key": "" } }
```
| Khoá | Giá trị | Ghi chú |
|---|---|---|
| `hotkey.modifiers` | tập con của `ctrl`, `alt`, `shift`, `cmd` | Phải giữ đủ các phím này |
| `hotkey.key` | một ký tự hoặc tên phím pynput (`space`, `f9`…) | Phím "giữ" chính; nhả bất kỳ phím nào của tổ hợp = xác nhận |

Đổi config cần khởi động lại daemon.

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
| pdf | docx, xlsx, pptx, png, jpg, txt |
| doc | pdf, txt, png, jpg |
| xls | pdf, csv, png |
| ppt | pdf, png, jpg, txt |
| img | png, jpg, webp, pdf, bmp (bỏ đích trùng định dạng nguồn) |
| txt | pdf |

## Tham số các tác vụ có hộp thoại
| id | params |
|---|---|
| `organize.split` | `ranges`: `""` = từng trang; `"1-3,5"` = mỗi nhóm một file; `"7-"` = từ 7 đến hết |
| `organize.pages` | `ranges` như trên, gộp thành 1 PDF |
| `edit.protect` | `password` |
| `edit.redact` | `keywords` (xuống dòng/`,`/`;` phân cách) |
| `edit.highlight` | `keywords`, `color`: Vàng · Xanh lá · Hồng |
| `edit.text` | `text`, `pos`: Watermark chéo · Trên · Giữa · Dưới, `size` (pt), `color`: Đen · Đỏ · Xanh · Xám |
| `edit.image` | `image` (đường dẫn), `pos`: Giữa · Trên trái · Trên phải · Dưới trái · Dưới phải, `pct` (% khổ trang) |
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
| Edit | `<tên>_protected / _redacted / _highlighted / _text / _stamped / _cropped` |
| Organize | `_merged`, `_rotated`, `_small`, `_pages`, thư mục `_split/`, `_images/`, `<tên>.zip` (nhiều file: `archive.zip`) |
| Trùng tên | thêm `_1`, `_2`… |
