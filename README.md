# MagicHub

Tool chạy ngầm (khay hệ thống): chọn file trong trình quản lý file → **giữ phím tắt** → **di chuột theo hướng** → nhả phím. Một vòng tròn hiện tại con trỏ với 3 nhóm tác vụ: **Convert · Edit · Organize**.

```
        Convert (12h)
       ╱     │     ╲        Giữ Ctrl+Alt+M → vòng tròn mở
  Organize   ●    Edit      Di chuột: vòng trong = nhóm, vòng ngoài = tác vụ
                            Nhả phím = chạy. Nhả ở tâm/vòng trong = huỷ.
```

## Chạy nhanh

```bash
cd MagicHub
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
./run.sh            # daemon (Windows: run.bat)
./run.sh menu a.pdf b.png        # mở vòng tròn một lần cho file chỉ định (bấm chuột để chọn)
./run.sh do organize.compress a.pdf   # chạy thẳng một tác vụ, không GUI
./run.sh actions a.pdf           # liệt kê tác vụ áp dụng được
.venv/bin/python tests/test_engine.py  # kiểm tra engine
```

Cần thêm: **LibreOffice** (convert Office), trên Linux/X11 hoặc Windows/macOS. Chi tiết nền tảng: [docs/PLATFORM.md](docs/PLATFORM.md).

## Tài liệu

| File | Nội dung |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Phạm vi, lộ trình, trạng thái từng bản |
| [docs/FLOW.md](docs/FLOW.md) | Luồng hoạt động từ phím tắt đến file kết quả |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Cấu trúc code, thêm tác vụ mới |
| [docs/CONSTRAINTS.md](docs/CONSTRAINTS.md) | Ràng buộc, giới hạn chất lượng, rủi ro, license |
| [docs/DATA.md](docs/DATA.md) | config.json, registry tác vụ, history, quy ước tên file |
| [docs/PLATFORM.md](docs/PLATFORM.md) | Windows / Linux / macOS: khác biệt và cách cài |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Hướng dẫn dùng, bảng tác vụ theo loại file |
| [PROGRESS.md](PROGRESS.md) | Nhật ký thay đổi |
