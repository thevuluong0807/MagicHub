"""Thẻ tiến trình/kết quả góc dưới-phải màn hình (kiểu thông báo Outlook / hộp sao chép Windows):
tiêu đề, dòng chi tiết, thanh tiến trình (xác định hoặc chạy vô định), thời gian đã chạy + ước tính còn lại, nút Huỷ / Mở.
Không cướp focus. Chỉ GUI thread dùng."""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from . import theme

WIDTH = 380


def _mmss(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


class Toast(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(WIDTH + 28)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)  # chỗ cho bóng đổ
        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(blurRadius=24, xOffset=0, yOffset=4)
        shadow.setColor(Qt.black)
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)
        grid = QVBoxLayout(self.card)
        grid.setContentsMargins(14, 12, 12, 12)
        grid.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.icon = QLabel(alignment=Qt.AlignCenter)
        self.icon.setFixedSize(28, 28)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setStyleSheet("font-size:13px;")
        self.detail = QLabel()
        self.detail.setObjectName("muted")
        col.addWidget(self.title)
        col.addWidget(self.detail)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setStyleSheet("QPushButton{min-width:0;padding:0;border:none;background:transparent;}"
                                     "QPushButton:hover{background:rgba(128,128,128,.25);}")
        self.close_btn.clicked.connect(self.dismiss)
        top.addWidget(self.icon, 0, Qt.AlignTop)
        top.addLayout(col, 1)
        top.addWidget(self.close_btn, 0, Qt.AlignTop)
        grid.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(True)  # hiện % ngay trên thanh khi biết tiến độ (xem _tick)
        grid.addWidget(self.bar)

        bottom = QHBoxLayout()
        self.meta = QLabel()
        self.meta.setObjectName("muted")
        bottom.addWidget(self.meta, 1)
        self.btns = QHBoxLayout()
        bottom.addLayout(self.btns)
        grid.addLayout(bottom)

        self.t0 = 0.0
        self.frac: float | None = None
        self.hover = False
        self.on_cancel = None
        self.tick = QTimer(self, interval=40, timeout=self._tick)
        self.hide_timer = QTimer(self, singleShot=True, timeout=self.hide)
        self.state = "idle"  # idle | running | done | error
        self._sweep = 0

    # ---- trạng thái ----
    def _style(self):
        t = theme.tokens()
        self.card.setStyleSheet(f"QFrame#card{{background:{t['card']};border:1px solid {t['border']};border-radius:10px;}}")

    def _set_icon(self, text, color):
        t = theme.tokens()
        self.icon.setText(text)
        self.icon.setStyleSheet(f"background:{t[color]};color:{t['on_accent']};border-radius:14px;font-weight:700;font-size:14px;")

    def _clear_buttons(self):
        while self.btns.count():
            w = self.btns.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _add_button(self, text, fn, primary=False):
        b = QPushButton(text)
        b.setDefault(primary)
        b.setAutoDefault(False)
        b.setFocusPolicy(Qt.NoFocus)
        b.setStyleSheet("padding:4px 12px;min-width:0;")
        b.clicked.connect(fn)
        self.btns.addWidget(b)
        b.show()  # cha đã hiện: widget thêm sau không tự hiện

    def _elide(self, text):
        return QFontMetrics(self.detail.font()).elidedText(text, Qt.ElideMiddle, WIDTH - 90)

    def running(self, title, detail="", on_cancel=None):
        self._style()
        self.state, self.t0, self.frac, self.on_cancel = "running", time.monotonic(), None, on_cancel
        self.title.setText(title)
        self.detail.setWordWrap(False)
        self.detail.setText(self._elide(detail))
        self._set_icon("⏳", "accent")
        self.bar.show()
        self.bar.setValue(0)
        self._clear_buttons()
        if on_cancel:
            self._add_button("Huỷ", self._cancel)
        self.close_btn.show()  # luôn đóng được thẻ; việc vẫn chạy nền, kết quả báo qua bong bóng khay
        self.hide_timer.stop()
        self.tick.start()
        self._place()

    def progress(self, frac, text=""):
        if self.state != "running":
            return
        self.frac = None if frac is None or frac < 0 else frac
        if text:
            self.detail.setText(self._elide(text))
        if self.frac is not None:
            self.bar.setValue(int(self.frac * 1000))

    def finish(self, ok: bool, title, detail="", actions=()):
        self._style()
        self.tick.stop()
        self.state = "done" if ok else "error"
        self.title.setText(title)
        self.detail.setWordWrap(True)  # kết quả/lỗi: hiện đủ nội dung, không cắt giữa
        self.detail.setMaximumWidth(WIDTH - 90)
        self.detail.setText(detail)
        self._set_icon("✓" if ok else "!", "ok" if ok else "danger")
        self.bar.hide()
        self.meta.setText("")
        self._clear_buttons()
        for i, (text, fn) in enumerate(actions):
            self._add_button(text, lambda _=False, f=fn: (f(), self.dismiss()), primary=i == 0)
        self.close_btn.show()
        self.hide_timer.start(9000 if ok else 20000)
        self._place()

    def dismiss(self):
        self.tick.stop()
        self.hide_timer.stop()
        self.state = "idle"
        self.hide()

    def _cancel(self):
        if self.on_cancel:
            self.title.setText("Đang huỷ…")
            self.on_cancel()

    # ---- hiển thị ----
    def _place(self):
        self.layout().activate()
        self.adjustSize()
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 12, scr.bottom() - self.height() - 12)
        self.show()
        self.raise_()

    def _tick(self):
        el = time.monotonic() - self.t0
        if self.frac is None:  # chưa biết tiến độ: thanh chạy qua lại
            self._sweep = (self._sweep + 18) % 2000
            self.bar.setValue(self._sweep if self._sweep < 1000 else 2000 - self._sweep)
            self.bar.setFormat("")
            self.meta.setText(_mmss(el))
        else:
            self.bar.setFormat(f"{int(self.frac * 100)}%")
            eta = f" · còn ~{_mmss(el * (1 - self.frac) / self.frac)}" if self.frac > 0.05 else ""
            self.meta.setText(f"{int(self.frac * 100)}% · {_mmss(el)}{eta}")

    def enterEvent(self, e):  # rê chuột vào: không tự ẩn
        self.hide_timer.stop()

    def leaveEvent(self, e):
        if self.state in ("done", "error"):
            self.hide_timer.start(4000)
