"""Vòng tròn menu (overlay trong suốt). Chọn bằng hướng + khoảng cách chuột, không cần bấm."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .geometry import R0, R1, R2, group_arc, hit, item_arc

ACCENT = {"convert": "#3b82f6", "edit": "#f59e0b", "organize": "#10b981"}
GAP = 1.2  # độ, khe giữa các ô


def annular(c: QPointF, r_in: float, r_out: float, a0: float, a1: float) -> QPainterPath:
    """Hình quạt vành khuyên; góc theo chiều kim đồng hồ từ 12h."""
    ro = QRectF(c.x() - r_out, c.y() - r_out, 2 * r_out, 2 * r_out)
    ri = QRectF(c.x() - r_in, c.y() - r_in, 2 * r_in, 2 * r_in)
    p = QPainterPath()
    p.arcMoveTo(ro, 90 - a0)
    p.arcTo(ro, 90 - a0, -(a1 - a0))
    p.arcTo(ri, 90 - a1, a1 - a0)
    p.closeSubpath()
    return p


class Wheel(QWidget):
    chosen = Signal(object)  # Action hoặc None (huỷ)

    def __init__(self):
        super().__init__()
        self.size_px = 2 * (R2 + 12)
        self.setFixedSize(self.size_px, self.size_px)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.groups, self.files, self.sel = [], [], (None, None)
        self.click_mode = False
        self.timer = QTimer(self, interval=16, timeout=self._tick)

    def open(self, files, groups, click_mode=False):
        self.files, self.groups, self.click_mode, self.sel = files, groups, click_mode, (None, None)
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if not click_mode:  # chế độ giữ phím: overlay không nhận chuột/focus
            flags |= Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g, m = scr.geometry(), R2 + 12
        c = type(pos)(min(max(pos.x(), g.left() + m), g.right() - m), min(max(pos.y(), g.top() + m), g.bottom() - m))
        if c != pos:
            QCursor.setPos(c)  # đưa con trỏ vào tâm vòng khi mở sát mép màn hình
        self.center_global = c
        self.move(c.x() - self.size_px // 2, c.y() - self.size_px // 2)
        self.show()
        if click_mode:
            self.activateWindow()
        self.timer.start()

    def _tick(self):
        d = QCursor.pos() - self.center_global
        sel = hit(d.x(), d.y(), [len(a) for _, _, a in self.groups])
        self.sel = sel
        self.update()

    def _selected_action(self):
        g, i = self.sel
        return self.groups[g][2][i] if g is not None and i is not None else None

    def confirm(self):
        act = self._selected_action()
        self._close(act)

    def cancel(self):
        self._close(None)

    def _close(self, act):
        self.timer.stop()
        self.hide()
        self.chosen.emit(act)

    def mousePressEvent(self, e):
        if self.click_mode:
            self.confirm()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancel()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.size_px / 2, self.size_px / 2)
        n, (hg, hi) = len(self.groups), self.sel
        font = QFont(self.font())
        for g, (gid, label, acts) in enumerate(self.groups):
            col = QColor(ACCENT.get(gid, "#888"))
            a0, a1 = group_arc(g, n)
            base = QColor(30, 32, 40, 225)
            fill = QColor(col.red(), col.green(), col.blue(), 235) if g == hg else base
            p.setPen(QPen(col, 2))
            p.setBrush(fill)
            p.drawPath(annular(c, R0, R1, a0 + GAP, a1 - GAP))
            self._text(p, c, (R0 + R1) / 2, (a0 + a1) / 2, label, 12, True, QColor("white"))
            if g != hg:
                continue
            for i, act in enumerate(acts):
                b0, b1 = item_arc(g, n, i, len(acts))
                on = i == hi
                p.setPen(QPen(col, 1.5))
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 245) if on else QColor(24, 26, 34, 225))
                p.drawPath(annular(c, R1 + 4, R2, b0 + GAP, b1 - GAP))
                self._text(p, c, (R1 + R2) / 2 + 2, (b0 + b1) / 2, act.label, 10, on, QColor("white"))
        # tâm: gợi ý + hướng con trỏ
        p.setPen(QPen(QColor(255, 255, 255, 60), 2))
        p.setBrush(QColor(15, 16, 22, 240))
        p.drawEllipse(c, R0 - 4, R0 - 4)
        act = self._selected_action()
        p.setPen(QColor("white"))
        font.setPointSize(9)
        p.setFont(font)
        p.drawText(QRectF(c.x() - R0, c.y() - R0, 2 * R0, 2 * R0), Qt.AlignCenter, f"{len(self.files)}\nfile")
        if act:  # mô tả đầy đủ ở dưới vòng vì tâm quá nhỏ
            font.setPointSize(10)
            p.setFont(font)
            r = QRectF(0, self.size_px - 26, self.size_px, 22)
            p.fillRect(r, QColor(0, 0, 0, 170))
            p.drawText(r, Qt.AlignCenter, act.tip)

    @staticmethod
    def _text(p, c, r, ang_deg, text, pt, bold, color):
        import math

        a = math.radians(ang_deg)
        x, y = c.x() + r * math.sin(a), c.y() - r * math.cos(a)
        f = p.font()
        f.setPointSize(pt)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(x - 42, y - 14, 84, 28), Qt.AlignCenter, text)
