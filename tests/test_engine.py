"""Chạy: .venv/bin/python tests/test_engine.py  (cần LibreOffice cho phần Office; không cần display)."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()  # config riêng cho test, không đụng config thật

import pymupdf
from PIL import Image

from magichub.actions import available, by_id
from magichub.actions.base import parse_ranges
from magichub.geometry import R0, ring_hit


def run(aid, files, **params):
    return by_id(aid).run([Path(f) for f in files], params)


def make_pdf(path, pages=3, text="Hello Secret 123"):
    doc = pymupdf.open()
    for i in range(pages):
        pg = doc.new_page()
        pg.insert_text((72, 100), f"{text} page {i + 1}", fontsize=18)
    doc.save(str(path))
    return path


def pdf_text(path):
    d = pymupdf.open(str(path))
    return "".join(p.get_text() for p in d)


def test_geometry():
    assert ring_hit(0, 0, 3)[0] is None  # vùng chết
    assert ring_hit(0, -(R0 + 5), 3)[0] == 0  # 12h
    assert ring_hit(200, 100, 3)[0] == 1  # phải-dưới
    assert ring_hit(-200, 100, 3)[0] == 2  # trái-dưới
    assert ring_hit(-150, -80, 6)[0] == 5  # lệch trái 12h hơn 30°, 6 ô 60°
    assert ring_hit(0, -100, 0)[0] is None

def test_available(td):
    pdf, png = make_pdf(td / "a.pdf"), td / "a.png"
    Image.new("RGB", (80, 60), "red").save(png)
    ids = lambda files: {a.id for _, _, acts in available(files) for a in acts}
    assert "convert.pdf.docx" in ids([pdf]) and "edit.redact" in ids([pdf])
    assert "organize.merge" not in ids([pdf]) and "organize.merge" in ids([pdf, png])
    assert "convert.img.png" not in ids([png]) and "convert.img.jpg" in ids([png])
    assert "edit.redact" not in ids([png]) and "organize.zip" in ids([png])
    assert ids([td / "x.unknown"]) == {"organize.zip"}


def test_organize(td):
    pdf = make_pdf(td / "doc.pdf")
    (o,) = run("organize.split", [pdf], ranges="1-2,3")
    assert sorted(p.name for p in o.iterdir()) == ["doc_p1-2.pdf", "doc_p3.pdf"]
    (o,) = run("organize.pages", [pdf], ranges="2")
    assert len(pymupdf.open(str(o))) == 1 and "page 2" in pdf_text(o)
    (o,) = run("organize.rotate_cw", [pdf])
    assert pymupdf.open(str(o))[0].rotation == 90
    (o,) = run("organize.compress", [pdf])
    assert o.exists()
    other = make_pdf(td / "b.pdf", pages=2)
    (o,) = run("organize.merge", [pdf, other])
    assert len(pymupdf.open(str(o))) == 5
    (o,) = run("organize.zip", [pdf, other])
    assert o.suffix == ".zip"
    png = td / "i.png"
    Image.new("RGB", (100, 50), "blue").save(png)
    (o,) = run("organize.rotate_cw", [png])
    assert Image.open(o).size == (50, 100)
    (o,) = run("organize.merge", [pdf, png])
    assert len(pymupdf.open(str(o))) == 4


def test_options(td):
    big = Image.effect_noise((1600, 1200), 80).convert("RGB")
    jpg = td / "n.jpg"
    big.save(jpg, quality=95)
    (a,), (b,) = run("organize.compress", [jpg], level="Nhẹ (giữ nét)"), run("organize.compress", [jpg], level="Mạnh")
    assert b.stat().st_size < a.stat().st_size and max(Image.open(b).size) <= 1600
    # output_dir: kết quả vào thư mục đích, không đụng file gốc
    dest = td / "out"
    dest.mkdir()
    from magichub import config
    cfg = config.load()
    cfg["output_dir"] = str(dest)
    config.save(cfg)
    (o,) = run("organize.compress", [jpg])
    assert o.parent == dest and jpg.exists()
    cfg["output_dir"] = None
    config.save(cfg)
    (o,) = run("organize.compress", [jpg])
    assert o.parent == td
    # OCR chỉ hiện khi có tesseract
    import shutil
    pdf = make_pdf(td / "o.pdf")
    assert ("convert.pdf.ocr" in [a.id for _, _, acts in available([pdf]) for a in acts]) == (shutil.which("tesseract") is not None)


def test_v03(td):
    pdf = make_pdf(td / "v.pdf", pages=3)
    marks = [{"type": "ink", "page": 0, "pts": [[0.1, 0.1], [0.5, 0.3], [0.8, 0.2]], "color": [1, 0, 0], "w": 2},
             {"type": "note", "page": 1, "x": 0.2, "y": 0.4, "text": "Kiểm tra lại số liệu\ndòng hai"}]
    (o,) = run("edit.annotate", [pdf], marks=marks)
    d = pymupdf.open(str(o))
    assert len(list(d[0].annots())) == 1 and "Kiểm tra" in d[1].get_text()
    try:
        run("edit.annotate", [pdf], marks=[])
        assert False
    except ValueError:
        pass
    (o,) = run("organize.reorder", [pdf], order=[2, 0])
    t = pdf_text(o)
    assert len(pymupdf.open(str(o))) == 2 and t.index("page 3") < t.index("page 1") and "page 2" not in t
    # redact vùng tay: gỡ text dưới vùng, không cần từ khoá
    W, H = pymupdf.open(str(pdf))[0].rect.width, pymupdf.open(str(pdf))[0].rect.height
    (o,) = run("edit.redact", [pdf], rects=[{"page": 0, "x0": 0, "y0": 0.05, "x1": 1, "y1": 0.2}])
    d = pymupdf.open(str(o))
    assert "Secret" not in d[0].get_text() and "Secret" in d[1].get_text()
    # GUI offscreen: canvas bắt vẽ/vùng đúng toạ độ
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from magichub.viewer import PageCanvas
    app = QApplication.instance() or QApplication([])
    cv = PageCanvas(pymupdf.open(str(pdf)), "ink")
    cv.resize(700, 800)
    box = cv._box()
    ev = lambda t, x, y: QMouseEvent(t, QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    cx, cy = box.x() + box.width() / 2, box.y() + box.height() / 2
    cv.mousePressEvent(ev(QEvent.MouseButtonPress, cx, cy))
    cv.mouseMoveEvent(ev(QEvent.MouseMove, cx + 50, cy + 40))
    cv.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, cx + 50, cy + 40))
    assert len(cv.marks) == 1 and abs(cv.marks[0]["pts"][0][0] - 0.5) < 0.01
    cv.undo()
    assert not cv.marks
    cv.tool = "rect"
    cv.mousePressEvent(ev(QEvent.MouseButtonPress, cx, cy))
    cv.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, cx + 100, cy + 100))
    assert cv.marks[0]["type"] == "rect" and cv.marks[0]["x1"] > cv.marks[0]["x0"]
    cv.grab()  # vẽ không crash


def test_integrate(td):
    from magichub import integrate
    if sys.platform != "linux":
        return
    made = integrate.install(td)
    names = {p.name for p in made}
    assert {"magichub.desktop", "MagicHub", "magichub.nemo_action"} <= names
    assert (td / ".local/share/nautilus/scripts/MagicHub").stat().st_mode & 0o111
    assert " menu " in (td / ".local/share/nemo/actions/magichub.nemo_action").read_text()
    assert len(integrate.remove(td)) == len(made) and not (td / ".config/autostart/magichub.desktop").exists()


def test_v05(td):
    from magichub import config
    # migrate config cũ (một hotkey) sang danh sách
    (config.config_dir() / "config.json").write_text(json.dumps({"hotkey": {"modifiers": ["ctrl"], "key": "m"}}))
    cfg = config.load()
    assert cfg["hotkeys"] == [{"modifiers": ["ctrl"], "key": "m", "group": None}] and "hotkey" not in cfg
    # ẩn + sắp xếp
    pdf = make_pdf(td / "m.pdf")
    ids = lambda: {g: [a.id for a in acts] for g, _, acts in available([pdf])}
    base = ids()
    assert "edit.crop" in base["edit"] and base["edit"][0] != "edit.crop"
    cfg["menu"] = {"hidden": ["edit.protect"], "order": ["edit.crop"]}
    config.save(cfg)
    now = ids()
    assert "edit.protect" not in now["edit"] and now["edit"][0] == "edit.crop"
    assert len(now["edit"]) == len(base["edit"]) - 1
    cfg["menu"] = {"hidden": [a for a in base["organize"]], "order": []}
    config.save(cfg)
    assert "organize" not in ids()  # nhóm rỗng tự biến mất
    cfg["menu"] = {"hidden": [], "order": []}
    config.save(cfg)
    # hộp thoại cài đặt (offscreen): OK giữ nguyên dữ liệu
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from magichub.settings import ask_hotkeys, ask_menu
    from PySide6.QtWidgets import QDialog
    app = QApplication.instance() or QApplication([])
    accept_open = lambda: [w.accept() for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
    QTimer.singleShot(400, accept_open)
    got = ask_menu({"hidden": ["edit.crop"], "order": []})
    assert got and "edit.crop" in got["hidden"] and len(got["order"]) == len(__import__("magichub.actions.base", fromlist=["x"]).REGISTRY)
    QTimer.singleShot(400, accept_open)
    assert ask_hotkeys(cfg["hotkeys"]) == cfg["hotkeys"]


def test_convert(td):
    pdf = make_pdf(td / "c.pdf")
    (o,) = run("convert.pdf.txt", [pdf])
    assert "Secret" in o.read_text("utf-8")
    (o,) = run("convert.pdf.png", [pdf])
    assert o.is_dir() and len(list(o.glob("*.png"))) == 3
    (o,) = run("convert.pdf.pptx", [pdf])
    assert o.stat().st_size > 1000
    (o,) = run("convert.pdf.docx", [pdf])
    assert o.stat().st_size > 1000
    png = td / "x.png"
    Image.new("RGBA", (40, 40), (255, 0, 0, 0)).save(png)
    (o,) = run("convert.img.jpg", [png])
    assert Image.open(o).mode == "RGB"
    (o,) = run("convert.img.pdf", [png])
    assert len(pymupdf.open(str(o))) == 1
    # Office qua LibreOffice
    (d,) = run("convert.pdf.docx", [pdf])
    (o,) = run("convert.doc.pdf", [d])
    assert "Secret" in pdf_text(o)
    (o,) = run("convert.doc.txt", [d])
    assert "Secret" in o.read_text("utf-8")


def test_pdf_table(td):
    doc = pymupdf.open()
    pg = doc.new_page()
    for r in range(4):
        for c in range(3):
            rect = pymupdf.Rect(72 + c * 80, 72 + r * 30, 152 + c * 80, 102 + r * 30)
            pg.draw_rect(rect)
            pg.insert_text((rect.x0 + 5, rect.y0 + 20), f"r{r}c{c}", fontsize=11)
    doc.save(str(td / "t.pdf"))
    (o,) = run("convert.pdf.xlsx", [td / "t.pdf"])
    import openpyxl

    ws = openpyxl.load_workbook(o).worksheets[0]
    assert ws["B2"].value == "r1c1", ws["B2"].value


def test_edit(td):
    pdf = make_pdf(td / "e.pdf")
    (o,) = run("edit.protect", [pdf], password="pw1")
    d = pymupdf.open(str(o))
    assert d.needs_pass and d.authenticate("pw1")
    (o,) = run("edit.redact", [pdf], keywords="Secret")
    assert "Secret" not in pdf_text(o)
    try:
        run("edit.redact", [pdf], keywords="zzzz")
        raise AssertionError("phải lỗi khi không có kết quả")
    except ValueError:
        pass
    (o,) = run("edit.highlight", [pdf], keywords="Hello", color="Vàng")
    assert any(True for _ in pymupdf.open(str(o))[0].annots())
    (o,) = run("edit.text", [pdf], text="BẢN NHÁP", pos="Watermark chéo", size=40, color="Đỏ")
    assert "BẢN NHÁP" in pdf_text(o)
    stamp = td / "stamp.png"
    Image.new("RGBA", (100, 50), (0, 128, 0, 255)).save(stamp)
    (o,) = run("edit.image", [pdf], image=str(stamp), pos="Dưới phải", pct=20)
    assert len(pymupdf.open(str(o))[0].get_images()) == 1
    (o,) = run("edit.crop", [pdf], box=(0.1, 0.1, 0.6, 0.5))
    r = pymupdf.open(str(o))[0].rect
    assert abs(r.width - 595 * 0.5) < 3 and abs(r.height - 842 * 0.4) < 3, r
    png = td / "p.png"
    Image.new("RGB", (200, 100), "white").save(png)
    (o,) = run("edit.crop", [png], box=(0, 0, 0.5, 0.5))
    assert Image.open(o).size == (100, 50)
    (o,) = run("edit.text", [png], text="Hi", pos="Giữa", size=40, color="Xanh")
    (o,) = run("edit.image", [png], image=str(stamp), pos="Trên trái", pct=30)


if __name__ == "__main__":
    test_geometry()
    for t in (test_available, test_organize, test_options, test_v03, test_integrate, test_v05, test_convert, test_pdf_table, test_edit):
        with tempfile.TemporaryDirectory() as d:
            t(Path(d))
        print("ok", t.__name__)
    print("ok test_geometry\nALL PASS")
