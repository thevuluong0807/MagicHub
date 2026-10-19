# Kiến trúc

```
magichub/
  __main__.py       CLI: run | menu | do | actions
  app.py            Hub: tray, hotkey flow, đọc clipboard, Job (QRunnable), thông báo, history
  hotkey.py         pynput Listener, trạng thái giữ phím, send_copy (Ctrl+C giả lập)
  wheel.py          Widget vòng tròn (QPainter, đa giác bo góc), timer đọc chuột, đổi nhóm↔tác vụ tại chỗ
  geometry.py       Toán thuần: ring_hit(dx,dy,n) → (ô, bán kính)   ← có test, không Qt
  dialogs.py        ask_form (form tham số) + ask_crop (chọn vùng) + ask_hotkey
  viewer.py         Trình xem PDF nhỏ: PageCanvas (vẽ/ghi chú/vùng), ask_annotate, ask_redact (xem trước), ask_reorder
  config.py         Đường dẫn dữ liệu theo OS + config.json
  actions/
    base.py         Action, REGISTRY, helper (unique, out_path, parse_ranges, soffice, font, PDF)
    convert.py      bảng TARGETS → đăng ký convert.<kind>.<to>
    organize.py     merge, split, rotate, compress, reorder, pages, images, zip
    edit.py         protect, redact, highlight, annotate (Draw), text, image, crop
    __init__.py     available(files), by_id(id)
tests/test_engine.py  assert-based, không cần display
```

## Ranh giới
- `actions/*` **không import Qt** (trừ khi gọi `ask` — import lười trong hàm). Chạy được headless và test được.
- `ask` chạy ở GUI thread; `run` chạy ở worker thread. Tham số truyền qua dict thuần.
- `geometry` là nguồn sự thật duy nhất cho vị trí các ô; `wheel` chỉ vẽ theo nó.

## Thêm một tác vụ mới (ví dụ)
```python
# magichub/actions/organize.py
@action("organize.strip_meta", "organize", "Strip", "Xoá metadata PDF", kinds=("pdf",))
def strip_meta(files, params):
    outs = []
    for f in files:
        doc = open_pdf(f); doc.set_metadata({})
        outs.append(save_pdf(doc, out_path(f, "clean")))
    return outs
```
Xong: vòng tròn tự có ô mới. Cần tham số → thêm `ask=_form(title, fields)` (xem `edit.py`). Tối đa ~8 tác vụ/nhóm để ô còn đủ rộng.

## Điều kiện áp dụng (`Action.accepts`)
`min_files` ≤ số file, **mọi** file thuộc `kinds` (`pdf|img|doc|xls|ppt|txt`, `None` = mọi loại), và `check(files)` nếu có. Loại file suy từ phần mở rộng.

## Luồng dữ liệu một tác vụ
`files: list[Path]` + `params: dict` → `list[Path]` (file hoặc thư mục tạo ra). Tác vụ không bao giờ sửa file gốc.
