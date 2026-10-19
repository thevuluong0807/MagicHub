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
    (o,) = run("edit.markup", [pdf], marks=marks)
    d = pymupdf.open(str(o))
    assert len(list(d[0].annots())) == 1 and "Kiểm tra" in d[1].get_text()
    try:
        run("edit.markup", [pdf], marks=[])
        assert False
    except ValueError:
        pass
    (o,) = run("organize.reorder", [pdf], order=[2, 0])
    t = pdf_text(o)
    assert len(pymupdf.open(str(o))) == 2 and t.index("page 3") < t.index("page 1") and "page 2" not in t
    (o,) = run("organize.reorder", [pdf], order=[1, 0], rotate={"0": 90})
    d = pymupdf.open(str(o))
    assert d[0].rotation == 0 and d[1].rotation == 90  # trang gốc 0 (giờ ở vị trí 2) bị xoay
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
    # mọi loại mark: bấm/kéo trên canvas -> mark đúng loại; vẽ lại không crash
    cv.marks.clear()
    cv.tool, cv.shape = "shape", "arrow"
    cv.mousePressEvent(ev(QEvent.MouseButtonPress, cx - 40, cy))
    cv.mouseReleaseEvent(ev(QEvent.MouseButtonRelease, cx + 40, cy + 30))
    assert cv.marks[-1]["kind"] == "arrow" and cv.marks[-1]["x1"] > cv.marks[-1]["x0"]
    cv.all_pages, cv.stroke = True, 3.0
    cv.add_border()
    assert cv.marks[-1] == {"type": "border", "all": True, "color": cv._rgb(), "w": 3.0}
    cv.marks.append({"type": "text", "all": True, "x": 0.5, "y": 0.5, "text": "WM", "size": 30, "color": [1, 0, 0], "rot": 45})
    cv.marks.append({"type": "shape", "page": 0, "kind": "ellipse", "x0": .1, "y0": .1, "x1": .3, "y1": .2, "color": [0, 0, 1], "w": 2, "fill": True})
    cv.grab().save(str(td / "canvas.png"))
    # preview và PDF dùng chung engine: marks của canvas áp được vào PDF
    (o,) = run("edit.markup", [pdf], marks=cv.marks)
    assert "WM" in pymupdf.open(str(o))[2].get_text()


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


def test_sandbox(td):
    import subprocess
    from magichub.actions.base import sandbox_prefix
    pre = sandbox_prefix([td])
    if not pre:
        return  # không có bwrap: bỏ qua
    run_ = lambda code: subprocess.run([*pre, sys.executable, "-c", code], capture_output=True).returncode
    assert run_(f"open({str(td / 'ok.txt')!r}, 'w').write('x')") == 0 and (td / "ok.txt").exists()
    assert run_(f"open({str(Path.home() / 'magichub_sandbox_probe')!r}, 'w')") != 0  # ngoài vùng cho phép: chỉ đọc
    assert run_("import socket; socket.create_connection(('1.1.1.1', 80), 2)") != 0  # không mạng


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
    stamp = td / "stamp.png"
    Image.new("RGBA", (100, 50), (0, 128, 0, 255)).save(stamp)
    marks = [
        {"type": "text", "all": True, "x": 0.5, "y": 0.5, "text": "BẢN NHÁP", "size": 40, "color": [0.85, 0.1, 0.1], "rot": 45},
        {"type": "text", "page": 0, "x": 0.1, "y": 0.2, "text": "Dòng một\nDòng hai", "size": 16, "color": [0, 0, 0]},
        {"type": "image", "all": True, "x": 0.7, "y": 0.9, "w": 0.2, "path": str(stamp)},
        {"type": "shape", "page": 0, "kind": "rect", "x0": 0.1, "y0": 0.3, "x1": 0.4, "y1": 0.4, "color": [0, 0, 1], "w": 2, "fill": True},
        {"type": "shape", "page": 0, "kind": "ellipse", "x0": 0.5, "y0": 0.3, "x1": 0.8, "y1": 0.4, "color": [0, 0, 1], "w": 2},
        {"type": "shape", "page": 0, "kind": "arrow", "x0": 0.1, "y0": 0.5, "x1": 0.4, "y1": 0.6, "color": [1, 0, 0], "w": 2},
        {"type": "border", "all": True, "color": [0, 0, 0], "w": 3}]
    (o,) = run("edit.markup", [pdf], marks=marks)
    d = pymupdf.open(str(o))
    assert all("BẢN NHÁP" in pg.get_text() and len(pg.get_images()) == 1 for pg in d) and "Dòng hai" in d[0].get_text()
    assert "Dòng hai" not in d[1].get_text()
    assert len(d[0].get_drawings()) > len(d[1].get_drawings()) > 0
    d[0].get_pixmap(dpi=60).save(str(td / "markup.png"))
    (o,) = run("edit.crop", [pdf], box=(0.1, 0.1, 0.6, 0.5))
    r = pymupdf.open(str(o))[0].rect
    assert abs(r.width - 595 * 0.5) < 3 and abs(r.height - 842 * 0.4) < 3, r
    png = td / "p.png"
    Image.new("RGB", (200, 100), "white").save(png)
    (o,) = run("edit.crop", [png], box=(0, 0, 0.5, 0.5))
    assert Image.open(o).size == (100, 50)
    big = td / "big.png"
    Image.new("RGB", (400, 300), "white").save(big)
    (o,) = run("edit.markup", [big], marks=[
        {"type": "text", "page": 0, "x": 0.1, "y": 0.1, "text": "Hi", "size": 30, "color": [0, 0, 1]},
        {"type": "border", "page": 0, "color": [1, 0, 0], "w": 4}])
    im = Image.open(o).convert("RGB")
    assert im.size == (400, 300) and o.suffix == ".png"
    assert any(im.getpixel((200, y))[0] > 200 and im.getpixel((200, y))[1] < 60 for y in range(30))  # khung đỏ ở mép trên
    assert im.getpixel((200, 150)) == (255, 255, 255)


def test_v07(td):
    pdf = make_pdf(td / "a.pdf", pages=3)
    # header/footer: trang thường + trang xoay 90
    d = pymupdf.open(str(pdf)); d[1].set_rotation(90); d.saveIncr()
    (o,) = run("edit.headfoot", [pdf], header="HEAD", footer="{n} / {N}", align="Phải", size=10)
    d = pymupdf.open(str(o))
    assert "HEAD" in d[0].get_text() and "3 / 3" in d[2].get_text() and "2 / 3" in d[1].get_text()
    for pg in (d[0], d[1]):  # chữ phải nằm ngang trong hệ toạ độ hiển thị (trang xoay cũng vậy)
        ln = [l for b in pg.get_text("dict")["blocks"] for l in b.get("lines", []) if "/ 3" in "".join(s["text"] for s in l["spans"])][0]
        m = pg.rotation_matrix  # get_text dùng toạ độ gốc: đổi sang hệ hiển thị
        dv = pymupdf.Point(ln["dir"]) * m - pymupdf.Point(0, 0) * m
        bb = pymupdf.Rect(ln["bbox"]) * m
        assert abs(dv.x - 1) < 1e-3, dv
        assert bb.x0 > pg.rect.width * 0.7 and bb.y0 > pg.rect.height * 0.9, bb
    # flatten / strip / unlock
    d = pymupdf.open(str(pdf)); d.set_metadata({"author": "Bi Mat"}); d[0].add_text_annot((50, 50), "ghi chu"); d.save(str(td / "m.pdf"))
    (o,) = run("edit.flatten", [td / "m.pdf"])
    assert not list(pymupdf.open(str(o))[0].annots())
    (o,) = run("edit.strip", [td / "m.pdf"])
    assert not pymupdf.open(str(o)).metadata.get("author")
    (enc,) = run("edit.protect", [pdf], password="pw")
    try:
        run("edit.unlock", [enc], password="sai")
        raise AssertionError
    except ValueError:
        pass
    (o,) = run("edit.unlock", [enc], password="pw")
    assert not pymupdf.open(str(o)).needs_pass
    # compare: khác 1 trang
    b = make_pdf(td / "b.pdf", pages=3, text="Hello Secret 123")
    d = pymupdf.open(str(b)); d[1].insert_text((72, 300), "KHAC BIET", fontsize=30); d.save(str(td / "b2.pdf"))
    assert by_id("organize.compare").accepts([pdf, td / "b2.pdf"]) and not by_id("organize.compare").accepts([pdf])
    (o,) = run("organize.compare", [pdf, td / "b2.pdf"])
    px = [pymupdf.open(str(o))[i].get_pixmap(dpi=40) for i in range(3)]
    red = lambda pm: sum(1 for x in range(0, pm.width, 2) for y in range(0, pm.height, 2) if pm.pixel(x, y)[0] > 180 and pm.pixel(x, y)[1] < 80)
    assert red(px[0]) == 0 and red(px[1]) > 5, (red(px[0]), red(px[1]))
    # ảnh: resize, strip exif, crop giữ EXIF xoay, heic opener
    im = Image.new("RGB", (200, 100), "red")
    ex = Image.Exif(); ex[274] = 6; ex[0x010F] = "Cam"  # Orientation=6 -> xoay còn 100x200
    jpg = td / "ph.jpg"; im.save(jpg, exif=ex)
    (o,) = run("edit.resize", [jpg], mode="Phần trăm (%)", value=50)
    assert Image.open(o).size == (50, 100)
    (o,) = run("edit.resize", [jpg], mode="Chiều rộng (px)", value=40)
    assert Image.open(o).size == (40, 80)
    (o,) = run("edit.strip", [jpg])
    assert Image.open(o).size == (100, 200) and not dict(Image.open(o).getexif())
    (o,) = run("edit.crop", [jpg], box=(0, 0, 1, 0.5))
    assert Image.open(o).size == (100, 100)
    assert "heic" in __import__("magichub.actions.base", fromlist=["x"]).KINDS["img"]


def test_cropwidget():
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QPixmap
    from PySide6.QtWidgets import QApplication

    from magichub.dialogs import _CropLabel

    app = QApplication.instance() or QApplication([])
    from magichub.dialogs import _preview  # import trong hàm: lỗi đường dẫn import lộ ra ở đây
    pdf = make_pdf(Path(tempfile.mkdtemp()) / "c.pdf", pages=1)
    png = pdf.with_suffix(".png"); Image.new("RGB", (80, 40), "blue").save(png)
    assert _preview(pdf).width() > 100 and _preview(png).width() == 80
    lab = _CropLabel(QPixmap(400, 300))

    def ev(t, x, y):
        b = Qt.LeftButton if t != QEvent.MouseMove or lab.mode else Qt.NoButton
        e = QMouseEvent(t, QPointF(x, y), QPointF(x, y), Qt.LeftButton, b, Qt.NoModifier)
        {QEvent.MouseButtonPress: lab.mousePressEvent, QEvent.MouseMove: lab.mouseMoveEvent,
         QEvent.MouseButtonRelease: lab.mouseReleaseEvent}[t](e)

    def drag(a, b):
        ev(QEvent.MouseButtonPress, *a); ev(QEvent.MouseMove, *b); ev(QEvent.MouseButtonRelease, *b)

    f = lab.sel
    assert (f.left(), f.top(), f.right(), f.bottom()) == (0, 0, 400, 300)  # mặc định khung full
    drag((400, 300), (250, 200))  # kéo góc dưới-phải vào
    drag((0, 0), (50, 50))  # kéo góc trên-trái vào
    r = lab.sel
    assert (r.left(), r.top(), r.right(), r.bottom()) == (50, 50, 250, 200)
    drag((150, 120), (170, 130))  # kéo trong vùng = di chuyển
    assert (lab.sel.left(), lab.sel.top()) == (70, 60) and lab.sel.width() == 200
    drag((270, 130), (300, 130))  # kéo cạnh phải = đổi rộng
    assert lab.sel.right() == 300 and lab.sel.left() == 70 and lab.sel.height() == 150
    lab.set_ratio(1)
    assert abs(lab.sel.width() - lab.sel.height()) < 1e-6
    drag((10, 10), (500, 500))  # kéo ra ngoài ảnh bị kẹp trong ảnh, giữ tỉ lệ 1:1
    r = lab.sel
    assert r.right() <= 400 and r.bottom() <= 300 and abs(r.width() - r.height()) < 1e-6 and r.height() == 290


def test_progress_engine(td):
    from magichub.actions import base, office
    from magichub.actions.base import Cancelled, bind, report, scope, steps
    pdf = make_pdf(td / "p.pdf", pages=5)
    got = []
    bind(lambda f, t: got.append(f), None)
    run("organize.split", [pdf], ranges="")
    fr = [f for f in got if f is not None]
    assert fr == sorted(fr) and fr[-1] == 1.0 and len(fr) >= 6, fr
    got.clear()
    for i in steps(range(2)):  # phạm vi lồng nhau: 2 file x 2 trang -> 0, .25, .5, .75, 1
        for j in steps(range(2)):
            pass
    fr = [round(f, 2) for f in got if f is not None]
    assert fr == sorted(fr) and 0.25 in fr and 0.75 in fr and fr[-1] == 1.0, fr
    n = []
    bind(lambda f, t: n.append(1), lambda: len(n) >= 2)  # huỷ sau 2 lần báo
    try:
        run("organize.split", [pdf], ranges="")
        raise AssertionError("phải bị huỷ")
    except Cancelled:
        pass
    bind(None, None)
    # chọn engine: Linux không có Office -> auto dùng LibreOffice; ép office -> báo lỗi rõ
    from magichub import config
    calls = []
    orig = office.soffice_convert, office.available, office._office_run
    office.soffice_convert = lambda s, f, o: calls.append(("lo", f)) or Path(o) / "x"
    try:
        assert office.office_convert(td / "a.docx", "pdf", td) == td / "x" and calls == [("lo", "pdf")]
        office.available = lambda k: True
        office._office_run = lambda s, f, o: (_ for _ in ()).throw(RuntimeError("COM hỏng"))
        sys_plat = office.sys.platform
        office.sys.platform = "win32"  # giả lập: Office có nhưng lỗi -> auto rơi về LibreOffice
        calls.clear()
        office.office_convert(td / "a.docx", "pdf", td)
        assert calls == [("lo", "pdf")]
        cfg = config.load(); cfg["engine"] = "office"; config.save(cfg)
        try:
            office.office_convert(td / "a.docx", "pdf", td)
            raise AssertionError
        except RuntimeError as e:
            assert "COM" in str(e)
        cfg["engine"] = "libreoffice"; config.save(cfg)
        calls.clear()
        office.office_convert(td / "a.docx", "pdf", td)
        assert calls == [("lo", "pdf")]
        assert not office.use_office("img", "pdf") and not office.use_office("doc", "docx")
    finally:
        office.sys.platform = sys_plat
        office.soffice_convert, office.available, office._office_run = orig
        cfg = config.load(); cfg["engine"] = "auto"; config.save(cfg)


def test_docx_progress_hook():
    import logging
    from magichub.actions.base import Cancelled, bind
    from magichub.actions.convert import _PageLog

    got = []
    bind(lambda f, t: got.append(round(f, 2)), None)
    h = _PageLog()
    for i in (1, 2, 1, 2):  # 2 trang: pha phân tích rồi pha dựng
        h.emit(logging.LogRecord("x", logging.INFO, "", 0, f"({i}/2) Page {i}", None, None))
    assert got == [0.25, 0.5, 0.75, 1.0], got
    bind(None, lambda: True)
    try:
        h.emit(logging.LogRecord("x", logging.INFO, "", 0, "(1/2) Page 1", None, None))
        raise AssertionError
    except Cancelled:
        pass
    bind(None, None)


def test_hub_toast(td):
    import time as _t
    from PySide6.QtWidgets import QApplication
    from magichub import theme
    from magichub.actions.base import REGISTRY, Action, steps
    from magichub.app import Hub

    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    hub = Hub(app, hotkey_enabled=False)

    def pump(cond, sec=5):
        end = _t.time() + sec
        while not cond() and _t.time() < end:
            app.processEvents()
        assert cond()

    def slow(files, p):
        for _ in steps(range(200)):
            _t.sleep(0.02)
        return [files[0]]

    act = Action("t.slow", "edit", "Slow", "chậm", slow)
    f = make_pdf(td / "s.pdf", 1)
    hub.files = [f]
    hub.on_chosen(act)
    pump(lambda: hub.toast.state == "running")  # sau 600 ms thẻ tiến trình hiện
    pump(lambda: hub.toast.frac is not None and hub.toast.frac > 0.1)
    assert "Slow" in hub.toast.title.text() and hub.toast.isVisible()
    hub.cancel_job(next(iter(hub.jobs)))
    pump(lambda: hub.toast.state == "error" and "huỷ" in hub.toast.title.text())
    assert not hub.jobs
    def mid(files, p):  # chạy lâu hơn 600 ms rồi xong bình thường: thẻ phải chuyển từ chạy sang xong (lỗi cũ: kẹt "đang chạy")
        for _ in steps(range(40)):
            _t.sleep(0.02)
        return []

    hub.on_chosen(Action("t.mid", "edit", "Mid", "vừa", mid))
    pump(lambda: hub.toast.state == "running")
    pump(lambda: hub.toast.state == "done" and "Mid" in hub.toast.title.text())
    assert not hub.jobs and hub.toast.close_btn.isVisible()

    def late(files, p):  # bước cuối không ngắt được: huỷ trước khi xong -> kết quả bị bỏ
        for _ in range(75):
            _t.sleep(0.02)
        o = td / "late_out.txt"
        o.write_text("x")
        return [o]

    hub.on_chosen(Action("t.late", "edit", "Late", "muộn", late))
    pump(lambda: hub.toast.state == "running")
    hub.cancel_job(next(iter(hub.jobs)))
    pump(lambda: hub.toast.state == "error" and not hub.jobs)
    assert not (td / "late_out.txt").exists()
    done = Action("t.fast", "edit", "Fast", "nhanh", lambda files, p: files)
    hub.on_chosen(done)
    pump(lambda: hub.toast.state == "done" and "Fast" in hub.toast.title.text())
    hub.toast.dismiss()
    hub.tray.hide()


if __name__ == "__main__":
    test_geometry()
    for t in (test_available, test_organize, test_options, test_v03, test_integrate, test_v05, test_sandbox, test_convert, test_pdf_table, test_edit, test_v07, test_progress_engine, test_hub_toast):
        with tempfile.TemporaryDirectory() as d:
            t(Path(d))
        print("ok", t.__name__)
    test_docx_progress_hook()
    test_cropwidget()
    print("ok test_cropwidget")
    print("ok test_geometry\nALL PASS")
