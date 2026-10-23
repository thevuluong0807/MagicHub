"""Hộp thoại nhập tham số + chọn vùng crop. Chỉ GUI thread dùng."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHeaderView, QTableWidget, QTableWidgetItem, QDialog, QFrame, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)


def _front(dlg):
    for b in dlg.findChildren(QPushButton):  # chỉ nút OK của QDialogButtonBox là nút chính; nút khác không được tô màu nhấn
        if not isinstance(b.parent(), QDialogButtonBox):
            b.setAutoDefault(False)
            b.setDefault(False)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


def header(lay, title: str, hint: str = ""):
    """Đầu hộp thoại: tiêu đề lớn + mô tả mờ (cùng kiểu Outlook/Settings của Windows)."""
    h = QLabel(title)
    h.setObjectName("h1")
    lay.addRow(h) if isinstance(lay, QFormLayout) else lay.addWidget(h)
    if hint:
        m = QLabel(hint)
        m.setObjectName("muted")
        m.setWordWrap(True)
        m.setMinimumWidth(1)
        lay.addRow(m) if isinstance(lay, QFormLayout) else lay.addWidget(m)


def buttons(dlg, ok: str = "OK", wire: bool = True) -> QDialogButtonBox:
    """Nút chính (màu nhấn) + Huỷ, đã nối accept/reject; ok nên là động từ của tác vụ (Cắt, Áp dụng, Lưu…)."""
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok)
    bb.button(QDialogButtonBox.Ok).setDefault(True)
    bb.button(QDialogButtonBox.Cancel).setText("Huỷ")
    if wire:
        bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


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


def ask_form(title: str, fields: list[dict], hint: str = "", ok: str = "OK") -> dict | None:
    """fields: name,label,type(text|password|multiline|choice|int|file),default,choices,min,max,required."""
    dlg = QDialog()
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(400)
    form = QFormLayout(dlg)
    form.setRowWrapPolicy(QFormLayout.WrapAllRows)  # nhãn trên ô nhập, như form hiện đại
    form.setContentsMargins(24, 20, 24, 20)
    form.setVerticalSpacing(8)
    header(form, title, hint)
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
    bb = buttons(dlg, ok, wire=False)  # accept() bên dưới kiểm tra dữ liệu rồi mới đóng
    form.addRow(bb)

    def value(t, w):
        # Lambda lười: dict literal tính mọi giá trị, nên w.currentText/w.value trên QLineEdit sẽ ném AttributeError
        # (OK không đóng hộp thoại; lỗi nằm trong slot nên chỉ in ra console).
        return {"multiline": lambda: w.toPlainText(), "choice": lambda: w.currentText(), "int": lambda: w.value(),
                "file": lambda: w.edit.text()}.get(t, lambda: w.text())()

    def accept():
        for f in fields:
            t, w = ws[f["name"]]
            if f.get("required") and not str(value(t, w)).strip():
                return QMessageBox.warning(dlg, title, f"Thiếu: {f['label']}")
            if f["name"] in confirm and confirm[f["name"]].text() != value(t, w):
                return QMessageBox.warning(dlg, title, "Mật khẩu nhập lại không khớp")
        dlg.accept()

    bb.accepted.connect(accept)
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
        p.setPen(QPen(QColor(0, 0, 0, 90), 3))  # viền trắng có bóng mờ để nổi trên mọi nền
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(0.5, 0.5, 0.5, 0.5))
        p.setPen(QPen(QColor("white"), 1.5))
        p.drawRect(r)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))  # lưới 1/3
        for k in (1, 2):
            p.drawLine(QPointF(r.left() + r.width() * k / 3, r.top()), QPointF(r.left() + r.width() * k / 3, r.bottom()))
            p.drawLine(QPointF(r.left(), r.top() + r.height() * k / 3), QPointF(r.right(), r.top() + r.height() * k / 3))
        p.setPen(QPen(QColor(0, 0, 0, 160), 1))  # tay nắm: ô vuông trắng viền tối như Snipping Tool
        p.setBrush(QColor("white"))
        for x in (r.left(), r.center().x(), r.right()):
            for y in (r.top(), r.center().y(), r.bottom()):
                if (x, y) != (r.center().x(), r.center().y()):
                    p.drawRect(QRectF(x - 4, y - 4, 8, 8))


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
    dlg.setWindowTitle("Crop")
    lab = _CropLabel(pix)
    info = QLabel()
    info.setObjectName("muted")
    ratio = QComboBox()
    ratio.addItems(list(RATIOS))
    ratio.currentTextChanged.connect(lambda t: lab.set_ratio(RATIOS[t]))

    def show():
        r = lab.rect_sel()
        info.setText(f"{round(r.width() / pix.width() * img.width())} × {round(r.height() / pix.height() * img.height())} px"
                     if r else "Kéo cạnh hoặc góc khung để chọn vùng")

    lab.changed = show
    show()
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    lay.setSizeConstraint(QVBoxLayout.SetFixedSize)
    bar = QHBoxLayout()  # thanh công cụ trên cùng: tỉ lệ + kích thước, giống Snipping Tool
    bar.addWidget(QLabel("Tỉ lệ"))
    bar.addWidget(ratio)
    bar.addStretch()
    bar.addWidget(info)
    lay.addLayout(bar)
    stage = QFrame()  # nền tối trung tính quanh ảnh
    stage.setStyleSheet("QFrame { background: #262626; border-radius: 8px; }")
    sl = QVBoxLayout(stage)
    sl.setContentsMargins(10, 10, 10, 10)
    sl.addWidget(lab, 0, Qt.AlignCenter)
    lay.addWidget(stage)
    hint = QLabel("Kéo trong khung để di chuyển · kéo ngoài khung để vẽ lại · áp dụng cùng tỉ lệ cho mọi trang/file đã chọn")
    hint.setObjectName("muted")
    hint.setWordWrap(True)  # không để câu dài kéo giãn hộp thoại rộng hơn ảnh
    hint.setMinimumWidth(1)
    lay.addWidget(hint)
    bb = buttons(dlg, "Cắt", wire=False)
    lay.addWidget(bb)

    def accept():
        if lab.rect_sel():
            dlg.accept()
        else:
            QMessageBox.warning(dlg, "Crop", "Khung quá nhỏ")

    bb.accepted.connect(accept)
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
    dlg.setMinimumWidth(420)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 20)
    lay.setSpacing(12)
    header(lay, "Đổi phím tắt", "Bấm tổ hợp mới (Esc để huỷ). Chỉ giữ 2+ phím Ctrl/Alt/Shift rồi nhả cũng được; "
           "tránh phím chữ vì file manager sẽ gõ chữ đó vào ô tìm kiếm.")
    lab = QLabel("+".join(mods + ([key] if key else [])))
    lab.setAlignment(Qt.AlignCenter)
    lab.setStyleSheet("font-size:22px;font-weight:600;padding:18px;border:1px solid palette(mid);border-radius:8px;background:palette(base)")
    lay.addWidget(lab)
    bb = buttons(dlg, "Lưu")
    ok = bb.button(QDialogButtonBox.Ok)
    ok.setEnabled(False)
    ok.setFocusPolicy(Qt.NoFocus)
    bb.button(QDialogButtonBox.Cancel).setFocusPolicy(Qt.NoFocus)
    lay.addWidget(bb)
    _front(dlg)
    return pending["v"] if dlg.exec() == QDialog.Accepted and "v" in pending else None


DICT_KINDS = ["PERSON", "ORG", "PROJECT", "PLACE", "TECH", "IDENT", "EMAIL", "PHONE", "URL", "ID", "IP", "TERM", "SAFE"]


def ask_dictionaries(select: str | None = None) -> dict | None:
    """Quản lý từ điển mã hoá: danh sách từ điển bên trái, bảng (loại, giá trị) bên phải; nhập/xuất .txt. Lưu vào config khi bấm Lưu."""
    from . import config
    from .anonymize import KIND_LABEL, format_dict_line, parse_dict_line

    cfg = config.load()
    data: dict[str, list[tuple[str, str]]] = {n: [parse_dict_line(l) for l in lines if l.strip()] for n, lines in cfg.get("anonymize_dicts", {}).items()}
    dlg = QDialog()
    dlg.setWindowTitle("Từ điển mã hoá")
    dlg.resize(760, 520)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 20)
    header(lay, "Từ điển mã hoá", "Các cụm trong từ điển luôn được mã hoá khi bạn bật \"Dùng từ điển\" (khớp không phân biệt hoa thường, dấu, khoảng trắng). Loại \"Bỏ qua\" = không bao giờ dò hay mã hoá cụm đó (áp dụng cho mọi từ điển).")
    body = QHBoxLayout()
    lay.addLayout(body, 1)

    left = QVBoxLayout()
    names = QListWidget()
    names.setMaximumWidth(200)
    left.addWidget(names, 1)
    body.addLayout(left)
    right = QVBoxLayout()
    table = QTableWidget(0, 2)
    table.setHorizontalHeaderLabels(["Loại", "Giá trị"])
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    right.addWidget(table, 1)
    body.addLayout(right, 1)

    state = {"cur": None}

    def kind_combo(kind):
        c = QComboBox()
        for k in DICT_KINDS:
            c.addItem(KIND_LABEL.get(k, k), k)
        c.setCurrentIndex(max(0, DICT_KINDS.index(kind) if kind in DICT_KINDS else DICT_KINDS.index("TERM")))
        return c

    def add_row(kind="TERM", value=""):
        r = table.rowCount()
        table.insertRow(r)
        table.setCellWidget(r, 0, kind_combo(kind))
        table.setItem(r, 1, QTableWidgetItem(value))
        return r

    def collect():
        rows = []
        for r in range(table.rowCount()):
            v = (table.item(r, 1).text() if table.item(r, 1) else "").strip()
            if v:
                rows.append((table.cellWidget(r, 0).currentData(), v))
        return rows

    def commit():
        if state["cur"] in data:
            data[state["cur"]] = collect()

    def show(name):
        commit()
        state["cur"] = name
        table.setRowCount(0)
        for kind, value in data.get(name, []):
            add_row(kind, value)

    def refill(select_name=None):
        names.blockSignals(True)
        names.clear()
        names.addItems(sorted(data))
        names.blockSignals(False)
        if select_name in data:
            names.setCurrentRow(sorted(data).index(select_name))
        elif data:
            names.setCurrentRow(0)
        else:
            state["cur"] = None
            table.setRowCount(0)

    names.currentTextChanged.connect(lambda n: show(n) if n else None)

    def new():
        name, ok = QInputDialog.getText(dlg, "Từ điển mới", "Tên từ điển (ví dụ tên dự án):")
        name = name.strip()
        if ok and name and name not in data:
            commit()
            data[name] = []
            refill(name)

    def rename():
        old = state["cur"]
        if not old:
            return
        name, ok = QInputDialog.getText(dlg, "Đổi tên", "Tên mới:", text=old)
        name = name.strip()
        if ok and name and name != old and name not in data:
            commit()
            data[name] = data.pop(old)
            refill(name)

    def delete():
        old = state["cur"]
        if old and QMessageBox.question(dlg, "Xoá từ điển", f"Xoá từ điển \"{old}\"?") == QMessageBox.Yes:
            data.pop(old)
            state["cur"] = None
            refill()

    def del_rows():
        for r in sorted({i.row() for i in table.selectedIndexes()} | {table.currentRow()}, reverse=True):
            if r >= 0:
                table.removeRow(r)

    def import_file():
        if not state["cur"]:
            return
        path = QFileDialog.getOpenFileName(dlg, "Nhập từ file", "", "Văn bản (*.txt *.csv)")[0]
        if path:
            have = {v.lower() for _, v in collect()}
            for line in Path(path).read_text("utf-8-sig", errors="replace").splitlines():
                line = line.strip().replace(",", ": ", 1) if "," in line and ":" not in line else line.strip()
                if line:
                    kind, value = parse_dict_line(line)
                    if value.lower() not in have:
                        add_row(kind, value)
                        have.add(value.lower())

    def export_file():
        if not state["cur"]:
            return
        path = QFileDialog.getSaveFileName(dlg, "Xuất từ điển", f"{state['cur']}.txt", "Văn bản (*.txt)")[0]
        if path:
            Path(path).write_text("\n".join(format_dict_line(k, v) for k, v in collect()) + "\n", "utf-8")

    for text, fn in (("Mới…", new), ("Đổi tên…", rename), ("Xoá", delete)):
        b = QPushButton(text)
        b.clicked.connect(lambda _=False, f=fn: f())
        left.addWidget(b)
    row = QHBoxLayout()
    for text, fn in (("Thêm dòng", lambda: table.setCurrentCell(add_row(), 1)), ("Xoá dòng đã chọn", del_rows), ("Nhập từ file…", import_file), ("Xuất ra file…", export_file)):
        b = QPushButton(text)
        b.clicked.connect(lambda _=False, f=fn: f())
        row.addWidget(b)
    row.addStretch(1)
    right.addLayout(row)
    lay.addWidget(buttons(dlg, "Lưu"))
    refill(select)
    _front(dlg)
    if dlg.exec() != QDialog.Accepted:
        return None
    commit()
    cfg["anonymize_dicts"] = {n: [format_dict_line(k, v) for k, v in rows] for n, rows in data.items()}
    if cfg.get("anonymize_last_dict") not in data:
        cfg.pop("anonymize_last_dict", None)
    config.save(cfg)
    return cfg["anonymize_dicts"]


def ask_anonymize(cands) -> dict | None:
    """Bảng ứng viên (tick để mã hoá) + tuỳ chọn dùng từ điển (chọn từ điển, mở hộp quản lý) + xoá metadata.
    Trả {entries, custom, dictionary, scrub}; dictionary = "" nếu không dùng từ điển."""
    from . import config
    from .anonymize import KIND_LABEL, format_dict_line, parse_dict_line

    cfg = config.load()
    dlg = QDialog()
    dlg.setWindowTitle("Mã hoá văn bản")
    dlg.resize(700, 640)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 20, 24, 20)
    header(lay, "Mã hoá văn bản", "Tick các mục cần thay bằng mã. Khớp không phân biệt hoa thường, dấu, khoảng trắng. Gợi ý tự dò có thể sót hoặc nhầm: hãy xem lại.")
    table = QTableWidget(len(cands), 4)
    table.setHorizontalHeaderLabels(["Mã hoá", "Loại", "Giá trị", "Số lần"])
    table.verticalHeader().setVisible(False)
    table.setSelectionMode(QAbstractItemView.NoSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    for r, c in enumerate(cands):
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked if c.checked else Qt.Unchecked)
        table.setItem(r, 0, chk)
        for col, text in ((1, KIND_LABEL.get(c.kind, c.kind)), (2, c.value), (3, str(c.count))):
            table.setItem(r, col, QTableWidgetItem(text))
    h = table.horizontalHeader()
    h.setSectionResizeMode(2, QHeaderView.Stretch)
    for col in (0, 1, 3):
        h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
    lay.addWidget(table, 1)
    row = QHBoxLayout()
    for text, state in (("Chọn tất cả", Qt.Checked), ("Bỏ tất cả", Qt.Unchecked)):
        b = QPushButton(text)
        b.clicked.connect(lambda _=False, s=state: [table.item(r, 0).setCheckState(s) for r in range(table.rowCount())])
        row.addWidget(b)
    row.addStretch(1)
    lay.addLayout(row)

    drow = QHBoxLayout()
    use_dict = QCheckBox("Dùng từ điển mã hoá:")
    combo = QComboBox()
    manage = QPushButton("Quản lý từ điển…")
    drow.addWidget(use_dict)
    drow.addWidget(combo, 1)
    drow.addWidget(manage)
    lay.addLayout(drow)
    save_ticked = QCheckBox("Lưu các mục đã tick vào từ điển này (lần sau tự mã hoá)")
    lay.addWidget(save_ticked)

    def reload(select=None):
        names = sorted(config.load().get("anonymize_dicts", {}))
        combo.clear()
        combo.addItems(names)
        if select in names:
            combo.setCurrentText(select)
        elif cfg.get("anonymize_last_dict") in names:
            combo.setCurrentText(cfg["anonymize_last_dict"])
        enabled = bool(names)
        use_dict.setEnabled(enabled)
        if not enabled:
            use_dict.setChecked(False)
        sync()

    def sync():
        on = use_dict.isChecked() and combo.count() > 0
        combo.setEnabled(on)
        save_ticked.setEnabled(on)

    use_dict.toggled.connect(lambda _=None: sync())

    def open_manager():
        if ask_dictionaries(combo.currentText() or None) is not None:
            reload(combo.currentText())

    manage.clicked.connect(lambda _=False: open_manager())
    reload()
    use_dict.setChecked(bool(cfg.get("anonymize_use_dict", True)) and combo.count() > 0)
    sync()
    scrub = QCheckBox("Xoá metadata tác giả/công ty của file")
    scrub.setChecked(True)
    lay.addWidget(scrub)
    lay.addWidget(QLabel("Mật khẩu bảng mapping (bắt buộc - bảng chứa giá trị gốc, không khoá thì AI đọc được; mất mật khẩu là không giải mã được):"))
    pw = QLineEdit()
    pw.setEchoMode(QLineEdit.Password)
    lay.addWidget(pw)
    lay.addWidget(buttons(dlg, "Mã hoá"))
    _front(dlg)
    while True:
        if dlg.exec() != QDialog.Accepted:
            return None
        if pw.text():
            break
        QMessageBox.warning(dlg, "Mã hoá", "Phải đặt mật khẩu cho bảng mapping.")  # giữ nguyên các mục đã tick
    entries = [{"value": c.value, "kind": c.kind, "alias_of": c.alias_of} for r, c in enumerate(cands) if table.item(r, 0).checkState() == Qt.Checked]
    name = combo.currentText() if use_dict.isChecked() and combo.count() else ""
    cfg = config.load()
    cfg["anonymize_use_dict"] = use_dict.isChecked()
    if name:
        cfg["anonymize_last_dict"] = name
        if save_ticked.isChecked():
            lines = cfg.setdefault("anonymize_dicts", {}).setdefault(name, [])
            have = {parse_dict_line(l)[1].lower() for l in lines}
            lines += [format_dict_line(e["kind"], e["value"]) for e in entries if e["value"].lower() not in have]
    config.save(cfg)
    return {"entries": entries, "custom": [], "dictionary": name, "scrub": scrub.isChecked(), "password": pw.text()}


def ask_password(title: str) -> str | None:
    """Hỏi một mật khẩu (ẩn ký tự); None = huỷ hoặc để trống."""
    text, ok = QInputDialog.getText(None, title, "Mật khẩu:", QLineEdit.Password)
    return text if ok and text else None


def ask_mapping() -> dict | None:
    """Chọn file bảng mapping (.xlsx) khi không tự tìm thấy cạnh file."""
    path = QFileDialog.getOpenFileName(None, "Chọn bảng mapping", "", "Bảng mapping (*.xlsx)")[0]
    return {"mapping": path} if path else None
