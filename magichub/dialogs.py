"""Hộp thoại nhập tham số + chọn vùng crop. Chỉ GUI thread dùng."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
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
    def __init__(self, pix: QPixmap):
        super().__init__()
        self.setPixmap(pix)
        self.setFixedSize(pix.size())
        self.a = self.b = None

    def mousePressEvent(self, e):
        self.a = self.b = e.position().toPoint()

    def mouseMoveEvent(self, e):
        self.b = e.position().toPoint()
        self.update()

    def rect_sel(self) -> QRect | None:
        if self.a is None:
            return None
        r = QRect(self.a, self.b).normalized().intersected(self.rect())
        return r if r.width() > 8 and r.height() > 8 else None

    def paintEvent(self, e):
        super().paintEvent(e)
        r = self.rect_sel()
        if r:
            p = QPainter(self)
            p.setPen(QPen(QColor("#ff9f1c"), 2, Qt.DashLine))
            p.setBrush(QColor(255, 159, 28, 40))
            p.drawRect(r)


def _preview(path: Path) -> QImage:
    from ..actions.base import kind_of, open_pdf

    if kind_of(path) == "pdf":
        pix = open_pdf(path)[0].get_pixmap(dpi=100, alpha=False)
        return QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
    return QImage(str(path))


def ask_crop(files) -> dict | None:
    img = _preview(Path(files[0]))
    pix = QPixmap.fromImage(img).scaled(900, 640, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    dlg = QDialog()
    dlg.setWindowTitle("Crop — kéo chuột để chọn vùng giữ lại")
    lab = _CropLabel(pix)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    lay = QVBoxLayout(dlg)
    lay.addWidget(lab)
    lay.addWidget(QLabel("Vùng chọn áp dụng cùng tỉ lệ cho mọi trang/file đã chọn."))
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
