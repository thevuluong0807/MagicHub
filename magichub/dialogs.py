"""Hộp thoại nhập tham số + chọn vùng crop. Chỉ GUI thread dùng."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)


def _front(dlg):
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


class _FilePick(QWidget):
    def __init__(self):
        super().__init__()
        self.edit = QLineEdit()
        btn = QPushButton("…")
        btn.clicked.connect(lambda: self.edit.setText(
            QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)")[0]
            or self.edit.text()))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit)
        lay.addWidget(btn)


def ask_form(title: str, fields: list[dict]) -> dict | None:
    """fields: name,label,type(text|password|multiline|choice|int|file),default,choices,min,max,required."""
    dlg = QDialog()
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(380)
    form = QFormLayout(dlg)
    ws, confirm = {}, {}
    for f in fields:
        t = f.get("type", "text")
        if t in ("text", "password"):
            w = QLineEdit(str(f.get("default", "")))
            if t == "password":
                w.setEchoMode(QLineEdit.Password)
                confirm[f["name"]] = QLineEdit()
                confirm[f["name"]].setEchoMode(QLineEdit.Password)
        elif t == "multiline":
            w = QPlainTextEdit()
            w.setFixedHeight(90)
        elif t == "choice":
            w = QComboBox()
            w.addItems(f["choices"])
        elif t == "int":
            w = QSpinBox()
            w.setRange(f.get("min", 1), f.get("max", 999))
            w.setValue(f.get("default", 1))
        else:
            w = _FilePick()
        ws[f["name"]] = (t, w)
        form.addRow(f["label"], w)
        if f["name"] in confirm:
            form.addRow("Nhập lại", confirm[f["name"]])
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    form.addRow(bb)

    def value(t, w):
        return {"multiline": lambda: w.toPlainText(), "choice": w.currentText, "int": w.value,
                "file": lambda: w.edit.text()}.get(t, getattr(w, "text", None))()

    def accept():
        for f in fields:
            t, w = ws[f["name"]]
            if f.get("required") and not str(value(t, w)).strip():
                return QMessageBox.warning(dlg, title, f"Thiếu: {f['label']}")
            if f["name"] in confirm and confirm[f["name"]].text() != value(t, w):
                return QMessageBox.warning(dlg, title, "Mật khẩu nhập lại không khớp")
        dlg.accept()

    bb.accepted.connect(accept)
    bb.rejected.connect(dlg.reject)
    _front(dlg)
    if dlg.exec() != QDialog.Accepted:
        return None
    return {n: value(t, w) for n, (t, w) in ws.items()}


class _CropLabel(QLabel):
    """Kéo để vẽ vùng; kéo trong vùng = di chuyển; kéo cạnh/góc = đổi cỡ. `ratio` (w/h) khoá tỉ lệ."""
    HIT = 9

    def __init__(self, pix: QPixmap):
        super().__init__()
        self.setPixmap(pix)
        self.setFixedSize(pix.size())
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.sel: QRectF | None = QRectF(0, 0, pix.width(), pix.height())  # mặc định: khung full, kéo cạnh/góc để thu nhỏ
        self.ratio: float | None = None
        self.mode = self.anchor = self.grab = None
        self.changed = lambda: None

    def _edges(self, pt):
        """Các cạnh của vùng chọn nằm gần con trỏ: tập con của {'l','r','t','b'}."""
        r, h, e = self.sel, self.HIT, set()
        if r is None or not r.adjusted(-h, -h, h, h).contains(pt):
            return e
        for k, near in (("l", abs(pt.x() - r.left())), ("r", abs(pt.x() - r.right())),
                        ("t", abs(pt.y() - r.top())), ("b", abs(pt.y() - r.bottom()))):
            if near <= h:
                e.add(k)
        return e

    def _clamp(self, pt):
        return QPointF(min(max(pt.x(), 0), self.width()), min(max(pt.y(), 0), self.height()))

    def _span(self, a, pt):
        """Hình chữ nhật từ điểm cố định `a` tới `pt`; có ratio thì ép tỉ lệ và không vượt ảnh."""
        dx, dy = pt.x() - a.x(), pt.y() - a.y()
        sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
        w, h = abs(dx), abs(dy)
        if self.ratio:
            w = min(max(w, h * self.ratio), (self.width() - a.x()) if sx > 0 else a.x())
            h = w / self.ratio
            room = (self.height() - a.y()) if sy > 0 else a.y()
            if h > room:
                h, w = room, room * self.ratio
        return QRectF(a, a + QPointF(sx * w, sy * h)).normalized()

    def mousePressEvent(self, e):
        pt = e.position()
        edges = self._edges(pt)
        if edges:
            if self.ratio:  # có tỉ lệ: cạnh -> góc đối diện làm mốc
                if not edges & {"l", "r"}:
                    edges.add("r")
                if not edges & {"t", "b"}:
                    edges.add("b")
            r = self.sel
            ax = r.right() if "l" in edges else r.left()
            ay = r.bottom() if "t" in edges else r.top()
            self.mode, self.anchor, self.edges, self.orig = "resize", QPointF(ax, ay), edges, QRectF(r)
        elif self.sel and self.sel.contains(pt):
            self.mode, self.grab = "move", pt - self.sel.topLeft()
        else:
            self.mode, self.anchor, self.edges = "new", self._clamp(pt), None
            self.sel = None

    def mouseMoveEvent(self, e):
        pt = self._clamp(e.position())
        if self.mode in ("new", "resize"):
            if self.mode == "resize" and not self.ratio:  # chỉ đổi các cạnh đang kéo
                o = self.orig
                self.sel = QRectF(pt.x() if "l" in self.edges else o.left(), pt.y() if "t" in self.edges else o.top(),
                                  0, 0)
                self.sel.setRight(pt.x() if "r" in self.edges else o.right())
                self.sel.setBottom(pt.y() if "b" in self.edges else o.bottom())
                if "l" in self.edges:
                    self.sel.setRight(o.right())
                if "t" in self.edges:
                    self.sel.setBottom(o.bottom())
                self.sel = self.sel.normalized()
            else:
                self.sel = self._span(self.anchor, pt)
        elif self.mode == "move":
            tl = pt - self.grab
            x = min(max(tl.x(), 0), self.width() - self.sel.width())
            y = min(max(tl.y(), 0), self.height() - self.sel.height())
            self.sel.moveTo(x, y)
        else:  # rê chuột không bấm: đổi con trỏ
            ed = self._edges(e.position())
            self.setCursor(Qt.SizeAllCursor if (not ed and self.sel and self.sel.contains(e.position()))
                           else (Qt.SizeBDiagCursor if ed in ({"l", "b"}, {"r", "t"}) else Qt.SizeFDiagCursor if len(ed) == 2
                                 else Qt.SizeHorCursor if ed & {"l", "r"} else Qt.SizeVerCursor if ed else Qt.CrossCursor))
        self.update()
        self.changed()

    def mouseReleaseEvent(self, e):
        self.mouseMoveEvent(e)
        self.mode = None

    def set_ratio(self, ratio):
        self.ratio = ratio
        if ratio and self.sel:  # áp tỉ lệ cho vùng đang có, giữ góc trên-trái
            r = self.sel
            w = min(r.width(), (self.height() - r.top()) * ratio)
            self.sel = QRectF(r.left(), r.top(), w, w / ratio)
        self.update()
        self.changed()

    def rect_sel(self) -> QRectF | None:
        return self.sel if self.sel and self.sel.width() > 8 and self.sel.height() > 8 else None

    def paintEvent(self, e):
        super().paintEvent(e)
        r = self.rect_sel()
        if not r:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
        dim = QColor(0, 0, 0, 120)  # tối phần bị cắt bỏ
        W, H = self.width(), self.height()
        for q in (QRectF(0, 0, W, r.top()), QRectF(0, r.bottom(), W, H - r.bottom()),
                  QRectF(0, r.top(), r.left(), r.height()), QRectF(r.right(), r.top(), W - r.right(), r.height())):
            p.fillRect(q, dim)
        p.setPen(QPen(QColor("#ff9f1c"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        p.setPen(QPen(QColor(255, 255, 255, 110), 1))  # lưới 1/3
        for k in (1, 2):
            p.drawLine(QPointF(r.left() + r.width() * k / 3, r.top()), QPointF(r.left() + r.width() * k / 3, r.bottom()))
            p.drawLine(QPointF(r.left(), r.top() + r.height() * k / 3), QPointF(r.right(), r.top() + r.height() * k / 3))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ff9f1c"))
        for x in (r.left(), r.center().x(), r.right()):
            for y in (r.top(), r.center().y(), r.bottom()):
                if (x, y) != (r.center().x(), r.center().y()):
                    p.drawRect(QRectF(x - 3, y - 3, 6, 6))


def _preview(path: Path) -> QImage:
    from PIL import Image, ImageOps

    from .actions.base import kind_of, open_pdf

    if kind_of(path) == "pdf":
        pix = open_pdf(path)[0].get_pixmap(dpi=100, alpha=False)
        return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")  # cùng phép xoay EXIF với bước cắt thật
    return QImage(im.tobytes(), im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()


RATIOS = {"Tự do": None, "1:1": 1, "4:3": 4 / 3, "3:2": 3 / 2, "16:9": 16 / 9, "3:4": 3 / 4, "9:16": 9 / 16}


def ask_crop(files) -> dict | None:
    img = _preview(Path(files[0]))
    pix = QPixmap.fromImage(img)
    if pix.width() > 900 or pix.height() > 640:  # chỉ thu nhỏ, không phóng to
        pix = pix.scaled(900, 640, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    dlg = QDialog()
    dlg.setWindowTitle("Crop — kéo cạnh/góc khung để chọn vùng giữ lại")
    lab = _CropLabel(pix)
    info = QLabel()
    ratio = QComboBox()
    ratio.addItems(list(RATIOS))
    ratio.currentTextChanged.connect(lambda t: lab.set_ratio(RATIOS[t]))

    def show():
        r = lab.rect_sel()
        info.setText(f"{round(r.width() / pix.width() * img.width())} × {round(r.height() / pix.height() * img.height())} px"
                     if r else "Kéo chuột trên ảnh để chọn vùng")

    lab.changed = show
    show()
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    lay = QVBoxLayout(dlg)
    lay.addWidget(lab, 0, Qt.AlignCenter)
    row = QHBoxLayout()
    row.addWidget(QLabel("Tỉ lệ"))
    row.addWidget(ratio)
    row.addWidget(info, 1)
    lay.addLayout(row)
    hint = QLabel("Kéo cạnh/góc để thu nhỏ khung, kéo trong khung để di chuyển, kéo ngoài khung để vẽ lại. Áp dụng cùng tỉ lệ cho mọi trang/file đã chọn.")
    hint.setWordWrap(True)  # không để câu dài kéo giãn hộp thoại rộng hơn ảnh
    hint.setMinimumWidth(1)
    lay.addWidget(hint)
    lay.setSizeConstraint(QVBoxLayout.SetFixedSize)
    lay.addWidget(bb)

    def accept():
        if lab.rect_sel():
            dlg.accept()
        else:
            QMessageBox.warning(dlg, "Crop", "Hãy kéo chuột chọn vùng trước")

    bb.accepted.connect(accept)
    bb.rejected.connect(dlg.reject)
    _front(dlg)
    if dlg.exec() != QDialog.Accepted:
        return None
    r, w, h = lab.rect_sel(), pix.width(), pix.height()
    return {"box": (r.left() / w, r.top() / h, r.right() / w, r.bottom() / h)}


def ask_hotkey(mods: list[str], key: str) -> tuple[list[str], str] | None:
    """Bấm tổ hợp mới (ít nhất 1 modifier + 1 phím). Trả (modifiers, key) hoặc None nếu huỷ."""
    import sys
    M = Qt.KeyboardModifier
    pairs = [(M.ControlModifier, "ctrl"), (M.AltModifier, "alt"), (M.ShiftModifier, "shift"), (M.MetaModifier, "cmd")]
    if sys.platform == "darwin":  # Qt hoán Ctrl/Cmd trên macOS
        pairs = [(M.MetaModifier, "ctrl"), (M.AltModifier, "alt"), (M.ShiftModifier, "shift"), (M.ControlModifier, "cmd")]
    MODKEYS = (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr)
    pending: dict = {}
    names = lambda e: [n for flag, n in pairs if e.modifiers() & flag]

    class Dlg(QDialog):
        def keyReleaseEvent(self, e):  # chỉ giữ modifier rồi nhả: chấp nhận tổ hợp >= 2 modifier
            if e.key() in MODKEYS and "mods" in pending and "v" not in pending and not e.isAutoRepeat():
                ms = pending["mods"]
                if len(ms) >= 2:
                    pending["v"] = (ms, "")
                    lab.setText("+".join(ms))
                    ok.setEnabled(True)

        def keyPressEvent(self, e):
            k = e.key()
            if k == Qt.Key_Escape:
                return self.reject()
            if k in MODKEYS:
                pending.pop("v", None)
                pending["mods"] = names(e)
                lab.setText("+".join(pending["mods"]))
                return
            if Qt.Key_F1 <= k <= Qt.Key_F12:
                name = f"f{k - Qt.Key_F1 + 1}"
            elif k == Qt.Key_Space:
                name = "space"
            elif 0x20 < k < 0x7F:
                name = chr(k).lower()
            else:
                return
            ms = names(e)
            if not ms:
                lab.setText("Cần giữ ít nhất một phím Ctrl / Alt / Shift / Cmd")
                return
            pending["v"] = (ms, name)
            lab.setText("+".join(ms + [name]))
            pending.pop("mods", None)
            ok.setEnabled(True)

    dlg = Dlg()
    dlg.setWindowTitle("Đổi phím tắt")
    dlg.setMinimumWidth(340)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Bấm tổ hợp mới (Esc để huỷ). Chỉ giữ 2+ phím Ctrl/Alt/Shift rồi nhả cũng được,\nvà tránh phím chữ: file manager sẽ gõ chữ đó vào ô tìm kiếm:"))
    lab = QLabel("+".join(mods + ([key] if key else [])))
    lab.setAlignment(Qt.AlignCenter)
    lab.setStyleSheet("font-size:20px;font-weight:bold;padding:12px")
    lay.addWidget(lab)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    ok = bb.button(QDialogButtonBox.Ok)
    ok.setEnabled(False)
    ok.setFocusPolicy(Qt.NoFocus)
    bb.button(QDialogButtonBox.Cancel).setFocusPolicy(Qt.NoFocus)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    _front(dlg)
    return pending["v"] if dlg.exec() == QDialog.Accepted and "v" in pending else None
