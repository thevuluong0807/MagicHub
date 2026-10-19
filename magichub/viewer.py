"""Trình xem PDF nhỏ: Markup (vẽ, hình, khung, chữ, ảnh, ghi chú), chọn vùng redact (có xem trước), sắp xếp trang. Chỉ GUI thread dùng.
Mọi toạ độ trả ra là tỉ lệ 0..1 theo trang để engine (headless) dùng thẳng."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QHBoxLayout, QInputDialog, QLabel, QListView, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from .actions.base import open_pdf
from .actions.edit import arrow_head, note_box
from .dialogs import _front, ask_form

INK_COLORS = {"Đỏ": "#e5484d", "Xanh": "#3e63dd", "Đen": "#111111", "Vàng cam": "#f5a524"}


def page_image(doc, i: int, dpi: int = 100) -> QImage:
    pix = doc[i].get_pixmap(dpi=dpi, alpha=False)
    return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()


class PageCanvas(QWidget):
    """Hiện 1 trang, bắt thao tác theo tool: ink, shape, text, note, image, rect (vùng redact)."""

    def __init__(self, doc, tool="ink"):
        super().__init__()
        self.doc, self.i, self.tool = doc, 0, tool
        # tuỳ chọn cho mark mới (do thanh công cụ đặt)
        self.color, self.stroke, self.fsize = QColor(INK_COLORS["Đỏ"]), 2.0, 24
        self.shape, self.fill, self.rot, self.all_pages = "rect", False, False, False
        self.img_path, self.img_pct = "", 25
        self._imgs: dict[str, QImage] = {}
        self.marks: list[dict] = []  # đã hoàn tất, toạ độ 0..1
        self.hits: dict[int, list[tuple]] = {}  # trang -> [(x0,y0,x1,y1)] chỉ để xem trước
        self.cur: dict | None = None
        self.setMinimumSize(640, 760)
        self.setCursor(Qt.CrossCursor)
        self.set_page(0)

    def set_page(self, i: int):
        self.i = max(0, min(i, len(self.doc) - 1))
        self.img = page_image(self.doc, self.i)
        self.update()

    def _box(self) -> QRectF:
        s = min(self.width() / self.img.width(), self.height() / self.img.height())
        w, h = self.img.width() * s, self.img.height() * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _norm(self, pos) -> tuple[float, float]:
        b = self._box()
        return (min(max((pos.x() - b.x()) / b.width(), 0), 1), min(max((pos.y() - b.y()) / b.height(), 0), 1))

    def _px(self, x, y) -> QPointF:
        b = self._box()
        return QPointF(b.x() + x * b.width(), b.y() + y * b.height())

    def _rgb(self) -> list[float]:
        c = self.color
        return [c.redF(), c.greenF(), c.blueF()]

    def _scope(self) -> dict:
        return {"all": True} if self.all_pages else {"page": self.i}

    def add_border(self):
        self.marks.append({"type": "border", **self._scope(), "color": self._rgb(), "w": self.stroke})
        self.update()

    def mousePressEvent(self, e):
        x, y = self._norm(e.position())
        if self.tool == "note":
            text, ok = QInputDialog.getMultiLineText(self, "Ghi chú", "Nội dung:")
            if ok and text.strip():
                self.marks.append({"type": "note", "page": self.i, "x": x, "y": y, "text": text.strip()})
        elif self.tool == "text":
            text, ok = QInputDialog.getMultiLineText(self, "Chữ", "Nội dung:")
            if ok and text.strip():
                self.marks.append({"type": "text", **self._scope(), "x": x, "y": y, "text": text.strip(),
                                   "size": self.fsize, "color": self._rgb(), "rot": 45 if self.rot else 0})
        elif self.tool == "image":
            if not self.img_path or not Path(self.img_path).is_file():
                self.img_path = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)")[0]
            if self.img_path:
                self.marks.append({"type": "image", **self._scope(), "x": x, "y": y, "w": self.img_pct / 100,
                                   "path": self.img_path})
        elif self.tool == "ink":
            self.cur = {"type": "ink", "page": self.i, "pts": [[x, y]], "w": self.stroke, "color": self._rgb()}
        elif self.tool == "shape":
            self.cur = {"type": "shape", **self._scope(), "kind": self.shape, "x0": x, "y0": y, "x1": x, "y1": y,
                        "color": self._rgb(), "w": self.stroke, "fill": self.fill}
        else:
            self.cur = {"type": "rect", "page": self.i, "x0": x, "y0": y, "x1": x, "y1": y}
        self.update()

    def mouseMoveEvent(self, e):
        if not self.cur:
            return
        x, y = self._norm(e.position())
        if self.cur["type"] == "ink":
            self.cur["pts"].append([x, y])
        else:
            self.cur["x1"], self.cur["y1"] = x, y
        self.update()

    def mouseReleaseEvent(self, e):
        self.mouseMoveEvent(e)  # chốt điểm cuối đúng chỗ nhả chuột
        m, self.cur = self.cur, None
        if not m:
            return
        if m["type"] == "ink":
            if len(m["pts"]) > 1:
                self.marks.append(m)
        elif max(abs(m["x1"] - m["x0"]), abs(m["y1"] - m["y0"])) > 0.005:
            if m["type"] == "rect" or m["kind"] in ("rect", "ellipse"):  # hộp: chuẩn hoá góc; đường/mũi tên giữ hướng
                m = {**m, "x0": min(m["x0"], m["x1"]), "x1": max(m["x0"], m["x1"]),
                     "y0": min(m["y0"], m["y1"]), "y1": max(m["y0"], m["y1"])}
            self.marks.append(m)
        self.update()

    def undo(self):
        if self.marks:
            self.marks.pop()
            self.update()

    def _image(self, path) -> QImage:
        if path not in self._imgs:
            self._imgs[path] = QImage(path)
        return self._imgs[path]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        p.fillRect(self.rect(), QColor(40, 42, 50))
        b = self._box()
        p.drawImage(b, self.img)
        W = self.doc[self.i].rect.width
        k = b.width() / W  # pt -> px màn hình
        for x0, y0, x1, y1 in self.hits.get(self.i, []):  # khớp từ khoá: khung cam nét đứt
            p.setPen(QPen(QColor("#ff9f1c"), 1.5, Qt.DashLine))
            p.setBrush(QColor(255, 159, 28, 50))
            p.drawRect(QRectF(self._px(x0, y0), self._px(x1, y1)))
        for m in self.marks + ([self.cur] if self.cur else []):
            if not (m.get("all") or m.get("page") == self.i):
                continue
            self._paint_mark(p, m, b, k, W)

    def _paint_mark(self, p, m, b, k, W):
        H = self.doc[self.i].rect.height
        t = m["type"]
        col = QColor.fromRgbF(*m["color"]) if "color" in m else QColor("black")
        if t == "ink":
            p.setPen(QPen(col, m["w"] * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            pts = [self._px(x, y) for x, y in m["pts"]]
            for a, c2 in zip(pts, pts[1:]):
                p.drawLine(a, c2)
        elif t == "rect":
            p.setPen(QPen(QColor("#ff2bd6"), 1.5))
            p.setBrush(QColor(0, 0, 0, 170))  # vùng sẽ bị che đen
            p.drawRect(QRectF(self._px(m["x0"], m["y0"]), self._px(m["x1"], m["y1"])))
        elif t == "shape":
            a, c2 = self._px(m["x0"], m["y0"]), self._px(m["x1"], m["y1"])
            p.setPen(QPen(col, m["w"] * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 64) if m.get("fill") else Qt.NoBrush)
            if m["kind"] == "rect":
                p.drawRect(QRectF(a, c2).normalized())
            elif m["kind"] == "ellipse":
                p.drawEllipse(QRectF(a, c2).normalized())
            else:
                p.drawLine(a, c2)
                if m["kind"] == "arrow":
                    for hx, hy in arrow_head((m["x0"] * W, m["y0"] * H), (m["x1"] * W, m["y1"] * H), m["w"]):  # tính theo pt như PDF
                        p.drawLine(c2, QPointF(b.x() + hx * k, b.y() + hy * k))
        elif t == "border":
            inset = (m["w"] / 2 + m.get("margin", 10)) * k
            p.setPen(QPen(col, m["w"] * k))
            p.setBrush(Qt.NoBrush)
            p.drawRect(b.adjusted(inset, inset, -inset, -inset))
        elif t == "text":
            f = QFont(self.font())
            f.setPixelSize(max(int(m["size"] * k), 4))
            p.setFont(f)
            p.setPen(col)
            c = self._px(m["x"], m["y"])
            lines = m["text"].split("\n")
            fm = p.fontMetrics()
            p.save()
            p.translate(c)
            if m.get("rot"):  # watermark: tâm tại điểm đặt, quay ngược chiều kim đồng hồ như PDF
                p.setOpacity(0.35)
                p.rotate(-m["rot"])
                for i, line in enumerate(lines):
                    p.drawText(QPointF(-fm.horizontalAdvance(line) / 2,
                                       m["size"] * k / 3 + (i - (len(lines) - 1) / 2) * m["size"] * 1.25 * k), line)
            else:
                for i, line in enumerate(lines):
                    p.drawText(QPointF(0, m["size"] * k * (1 + 1.25 * i)), line)
            p.restore()
        elif t == "image":
            img = self._image(m["path"])
            if not img.isNull():
                w = m["w"] * b.width()
                p.drawImage(QRectF(self._px(m["x"], m["y"]), QSize(int(w), int(w * img.height() / img.width()))), img)
        else:  # note
            r = note_box(m["text"], W, H, m["x"], m["y"])
            box = QRectF(self._px(r.x0 / W, r.y0 / H), self._px(r.x1 / W, r.y1 / H))
            p.setPen(QPen(QColor("#cc9900"), 1))
            p.setBrush(QColor(255, 242, 153))
            p.drawRect(box)
            f = p.font()
            f.setPixelSize(max(int(11 * k), 6))
            p.setFont(f)
            p.setPen(QColor("black"))
            p.drawText(box.adjusted(3, 2, -3, -2), Qt.TextWordWrap, m["text"])


def _pager(canvas, extra: list[QWidget], hint: str, title: str) -> QDialog:
    dlg = QDialog()
    dlg.setWindowTitle(title)
    lay = QVBoxLayout(dlg)
    bar = QHBoxLayout()
    prev, nxt = QPushButton("◀"), QPushButton("▶")
    lab = QLabel()
    show = lambda: lab.setText(f"Trang {canvas.i + 1}/{len(canvas.doc)}")
    go = lambda d: (canvas.set_page(canvas.i + d), show())
    prev.clicked.connect(lambda: go(-1))
    nxt.clicked.connect(lambda: go(1))
    for key, fn in (("PgUp", lambda: go(-1)), ("PgDown", lambda: go(1)), ("Ctrl+Z", canvas.undo)):
        QShortcut(QKeySequence(key), dlg, fn)
    for w in (prev, lab, nxt, *extra):
        bar.addWidget(w)
    bar.addStretch()
    undo = QPushButton("Hoàn tác")
    undo.setToolTip("Ctrl+Z")
    undo.clicked.connect(canvas.undo)
    bar.addWidget(undo)
    lay.addLayout(bar)
    lay.addWidget(canvas, 1)
    lay.addWidget(QLabel(hint))
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    show()
    dlg.resize(860, 960)
    return dlg


def ask_markup(path) -> dict | None:
    """Trình soạn: Bút / Hình / Chữ / Ghi chú / Ảnh + Khung. Trang nào cũng xem được; 'Mọi trang' áp cho chữ, ảnh, hình, khung."""
    from tempfile import TemporaryDirectory

    from .actions.base import kind_of
    from .actions.convert import images_to_pdf

    with TemporaryDirectory(prefix="magichub-") as td:
        src = Path(path)
        doc = open_pdf(src) if kind_of(src) == "pdf" else open_pdf(images_to_pdf([src], Path(td) / "i.pdf"))
        cv = PageCanvas(doc, "ink")
        tools = [("✎ Bút", "ink"), ("▭ Hình", "shape"), ("T Chữ", "text"), ("▤ Ghi chú", "note"), ("▣ Ảnh", "image")]
        buttons = []
        for text, tool in tools:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setChecked(tool == "ink")
            b.clicked.connect(lambda _=False, t=tool: [setattr(cv, "tool", t), [x.setChecked(x is bt[t]) for x in buttons]])
            buttons.append(b)
        bt = {tool: b for (_, tool), b in zip(tools, buttons)}
        frame = QPushButton("▢ Khung")
        frame.setToolTip("Thêm khung viền quanh trang (màu + nét đang chọn)")
        frame.clicked.connect(cv.add_border)

        color = QComboBox()
        color.addItems(list(INK_COLORS))
        color.currentTextChanged.connect(lambda t: setattr(cv, "color", QColor(INK_COLORS[t])))
        width = QSpinBox()
        width.setRange(1, 20)
        width.setValue(2)
        width.setPrefix("Nét ")
        width.valueChanged.connect(lambda v: setattr(cv, "stroke", float(v)))
        fsize = QSpinBox()
        fsize.setRange(6, 300)
        fsize.setValue(24)
        fsize.setPrefix("Cỡ chữ ")
        fsize.valueChanged.connect(lambda v: setattr(cv, "fsize", v))
        pct = QSpinBox()
        pct.setRange(3, 100)
        pct.setValue(25)
        pct.setPrefix("Ảnh rộng ")
        pct.setSuffix("%")
        pct.valueChanged.connect(lambda v: setattr(cv, "img_pct", v))
        shape = QComboBox()
        shape.addItems(["Chữ nhật", "Elip", "Đường thẳng", "Mũi tên"])
        shape.currentIndexChanged.connect(lambda i: setattr(cv, "shape", ("rect", "ellipse", "line", "arrow")[i]))

        def check(text, attr, tip):
            c = QCheckBox(text)
            c.setToolTip(tip)
            c.toggled.connect(lambda v: setattr(cv, attr, v))
            return c

        fill, rot = check("Tô nền", "fill", "Hình chữ nhật/elip: tô nền mờ"), check("Chéo", "rot", "Chữ chéo 45°, mờ (watermark), đặt tâm tại điểm bấm")
        opts = [color, width, shape, fill, fsize, rot, pct, check("Mọi trang", "all_pages", "Chữ, ảnh, hình, khung áp dụng cho mọi trang")]
        ctx = {"shape": [shape, fill], "text": [fsize, rot], "image": [pct]}  # tuỳ chọn riêng của từng công cụ; màu/nét/mọi trang luôn hiện (Khung dùng chung)

        def refresh(tool):
            for w in (shape, fill, fsize, rot, pct):
                w.setVisible(w in ctx.get(tool, []))

        refresh("ink")
        for (_, tool), btn in zip(tools, buttons):
            btn.clicked.connect(lambda _=False, t=tool: refresh(t))
        dlg = _pager(cv, [*buttons, frame], "Chọn công cụ rồi bấm/kéo trên trang. Chữ & ảnh: bấm vị trí. "
                     "Ctrl+Z hoàn tác, PgUp/PgDn đổi trang. Kết quả lưu thành file mới; nhiều file chọn thì áp cho từng file.",
                     "Markup")
        row = QHBoxLayout()
        for w in opts:
            row.addWidget(w)
        row.addStretch()
        dlg.layout().insertLayout(1, row)
        _front(dlg)
        ok = dlg.exec() == QDialog.Accepted
        doc.close()
    if ok and not cv.marks:
        QMessageBox.information(None, "Markup", "Chưa thêm gì")
        return None
    return {"marks": cv.marks} if ok else None


def ask_redact(path) -> dict | None:
    """Nhập từ khoá (tuỳ chọn) -> xem trước khớp (khung cam) + kéo thêm vùng tự chọn (đen) -> xác nhận."""
    kw = ask_form("Redact — từ khoá", [{"name": "keywords", "label": "Từ khoá (trống = chỉ chọn vùng tay)",
                                       "type": "multiline"}])
    if kw is None:
        return None
    from .actions.edit import _words

    doc = open_pdf(path)
    words = _words(kw.get("keywords", ""))
    cv = PageCanvas(doc, "rect")
    n = 0
    for i, page in enumerate(doc):
        W, H = page.rect.width, page.rect.height
        rs = [r for w in words for r in page.search_for(w)]
        cv.hits[i] = [(r.x0 / W, r.y0 / H, r.x1 / W, r.y1 / H) for r in rs]
        n += len(rs)
    info = QLabel(f"Khớp {n} chỗ (khung cam). Kéo chuột để thêm vùng che (áp dụng cho file đầu tiên).")
    dlg = _pager(cv, [], "Xem trước: khung cam = từ khoá sẽ bị xoá; vùng đen = vùng tự chọn. OK để xoá vĩnh viễn.",
                 "Redact — xem trước")
    dlg.layout().insertWidget(1, info)
    _front(dlg)
    ok = dlg.exec() == QDialog.Accepted
    doc.close()
    if not ok:
        return None
    if n == 0 and not cv.marks:
        QMessageBox.information(None, "Redact", "Không có từ khoá khớp và chưa chọn vùng nào")
        return None
    rects = [{k: m[k] for k in ("page", "x0", "y0", "x1", "y1")} for m in cv.marks]
    return {"keywords": kw.get("keywords", ""), "rects": rects}


def ask_reorder(path) -> dict | None:
    """Ảnh thu nhỏ các trang: kéo thả để đổi thứ tự, Delete/nút để xoá trang."""
    doc = open_pdf(path)
    lst = QListWidget()
    lst.setViewMode(QListView.IconMode)
    lst.setIconSize(QSize(110, 150))
    lst.setResizeMode(QListView.Adjust)
    lst.setMovement(QListView.Snap)
    lst.setDragDropMode(QAbstractItemView.InternalMove)
    lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
    lst.setSpacing(8)
    for i in range(len(doc)):
        it = QListWidgetItem(QIcon(QPixmap.fromImage(page_image(doc, i, 40))), str(i + 1))
        it.setData(Qt.UserRole, i)
        lst.addItem(it)
    doc.close()

    def delete():
        for it in lst.selectedItems():
            lst.takeItem(lst.row(it))

    dlg = QDialog()
    dlg.setWindowTitle("Sắp xếp trang")
    lay = QVBoxLayout(dlg)
    row = QHBoxLayout()
    rm = QPushButton("Xoá trang chọn")
    rm.clicked.connect(delete)
    rev = QPushButton("Đảo thứ tự")
    rev.clicked.connect(lambda: [lst.insertItem(0, lst.takeItem(k)) for k in range(1, lst.count())])
    row.addWidget(rm)
    row.addWidget(rev)
    row.addStretch()
    lay.addLayout(row)
    lay.addWidget(lst, 1)
    lay.addWidget(QLabel("Kéo thả để đổi chỗ; chọn rồi bấm Xoá để bỏ trang. Kết quả lưu thành file mới."))
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    dlg.resize(720, 640)
    _front(dlg)
    if dlg.exec() != QDialog.Accepted:
        return None
    order = [lst.item(k).data(Qt.UserRole) for k in range(lst.count())]
    if not order:
        QMessageBox.warning(None, "Sắp xếp trang", "Phải giữ lại ít nhất một trang")
        return None
    return {"order": order}
