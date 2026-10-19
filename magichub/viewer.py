"""Trình xem PDF nhỏ: vẽ tay, ghi chú, chọn vùng redact (có xem trước), sắp xếp trang. Chỉ GUI thread dùng.
Mọi toạ độ trả ra là tỉ lệ 0..1 theo trang để engine (headless) dùng thẳng."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
                               QLabel, QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from .actions.base import open_pdf
from .actions.edit import note_box
from .dialogs import _front, ask_form

INK_COLORS = {"Đỏ": "#e5484d", "Xanh": "#3e63dd", "Đen": "#111111", "Vàng cam": "#f5a524"}


def page_image(doc, i: int, dpi: int = 100) -> QImage:
    pix = doc[i].get_pixmap(dpi=dpi, alpha=False)
    return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()


class PageCanvas(QWidget):
    """Hiện 1 trang, bắt thao tác theo tool: ink (vẽ), note (bấm để đặt ghi chú), rect (kéo vùng)."""

    def __init__(self, doc, tool="ink"):
        super().__init__()
        self.doc, self.i, self.tool, self.color = doc, 0, tool, QColor(INK_COLORS["Đỏ"])
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

    def mousePressEvent(self, e):
        x, y = self._norm(e.position())
        if self.tool == "note":
            text, ok = QInputDialog.getMultiLineText(self, "Ghi chú", "Nội dung:")
            if ok and text.strip():
                self.marks.append({"type": "note", "page": self.i, "x": x, "y": y, "text": text.strip()})
                self.update()
        elif self.tool == "ink":
            c = self.color
            self.cur = {"type": "ink", "page": self.i, "pts": [[x, y]], "w": 2.5,
                        "color": [c.redF(), c.greenF(), c.blueF()]}
        else:
            self.cur = {"type": "rect", "page": self.i, "x0": x, "y0": y, "x1": x, "y1": y}

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
        if m["type"] == "ink" and len(m["pts"]) > 1:
            self.marks.append(m)
        elif m["type"] == "rect":
            m = {**m, "x0": min(m["x0"], m["x1"]), "x1": max(m["x0"], m["x1"]),
                 "y0": min(m["y0"], m["y1"]), "y1": max(m["y0"], m["y1"])}
            if m["x1"] - m["x0"] > 0.005 and m["y1"] - m["y0"] > 0.005:
                self.marks.append(m)
        self.update()

    def undo(self):
        if self.marks:
            self.marks.pop()
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(40, 42, 50))
        b = self._box()
        p.drawImage(b, self.img)
        page = self.doc[self.i]
        W, H = page.rect.width, page.rect.height
        for x0, y0, x1, y1 in self.hits.get(self.i, []):  # khớp từ khoá: khung cam nét đứt
            p.setPen(QPen(QColor("#ff9f1c"), 1.5, Qt.DashLine))
            p.setBrush(QColor(255, 159, 28, 50))
            p.drawRect(QRectF(self._px(x0, y0), self._px(x1, y1)))
        for m in self.marks + ([self.cur] if self.cur else []):
            if m["page"] != self.i:
                continue
            if m["type"] == "ink":
                c = m["color"]
                p.setPen(QPen(QColor.fromRgbF(*c), m["w"] * b.width() / W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.setBrush(Qt.NoBrush)
                pts = [self._px(x, y) for x, y in m["pts"]]
                for a, c2 in zip(pts, pts[1:]):
                    p.drawLine(a, c2)
            elif m["type"] == "rect":
                p.setPen(QPen(QColor("#ff2bd6"), 1.5))
                p.setBrush(QColor(0, 0, 0, 170))  # vùng sẽ bị che đen
                p.drawRect(QRectF(self._px(m["x0"], m["y0"]), self._px(m["x1"], m["y1"])))
            else:
                r = note_box(m["text"], W, H, m["x"], m["y"])
                box = QRectF(self._px(r.x0 / W, r.y0 / H), self._px(r.x1 / W, r.y1 / H))
                p.setPen(QPen(QColor("#cc9900"), 1))
                p.setBrush(QColor(255, 242, 153))
                p.drawRect(box)
                f = p.font()
                f.setPixelSize(max(int(11 * b.width() / W), 6))
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
    prev.clicked.connect(lambda: (canvas.set_page(canvas.i - 1), show()))
    nxt.clicked.connect(lambda: (canvas.set_page(canvas.i + 1), show()))
    for w in (prev, lab, nxt, *extra):
        bar.addWidget(w)
    bar.addStretch()
    undo = QPushButton("Hoàn tác")
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
    dlg.resize(820, 940)
    return dlg


def ask_annotate(path) -> dict | None:
    doc = open_pdf(path)
    cv = PageCanvas(doc, "ink")
    pen, note = QPushButton("✎ Bút"), QPushButton("▤ Ghi chú")
    color = QComboBox()
    color.addItems(list(INK_COLORS))
    pen.clicked.connect(lambda: setattr(cv, "tool", "ink"))
    note.clicked.connect(lambda: setattr(cv, "tool", "note"))
    color.currentTextChanged.connect(lambda t: setattr(cv, "color", QColor(INK_COLORS[t])))
    dlg = _pager(cv, [pen, note, color], "Bút: kéo chuột để vẽ. Ghi chú: bấm vào vị trí rồi gõ chữ. Kết quả lưu thành file mới.",
                 "Vẽ / ghi chú")
    _front(dlg)
    ok = dlg.exec() == QDialog.Accepted
    doc.close()
    if ok and not cv.marks:
        QMessageBox.information(None, "Vẽ / ghi chú", "Chưa vẽ hay ghi chú gì")
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
