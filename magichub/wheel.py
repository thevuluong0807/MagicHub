"""Vòng tròn menu (overlay trong suốt). Một vòng duy nhất: kéo ra ngoài một nhóm thì nội dung vòng đổi sang
tác vụ của nhóm đó (không mở rộng thêm vòng); về tâm để quay lại nhóm. Chọn bằng hướng chuột, không cần bấm."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .geometry import R0, R1, R_MID, ring_arc, ring_hit

ACCENT = {"convert": "#00e5ff", "edit": "#ff2bd6", "organize": "#39ff88"}  # cyber: cyan / magenta / neon green
BASE, INK, FONT = QColor(7, 11, 20), QColor(217, 250, 255), "DejaVu Sans Mono"
CORNER = 8  # px, bo góc ô
GAP = 1.4  # độ, khe giữa các ô
SWAP_STEP, HOVER_STEP = 0.14, 0.28  # tiến độ mỗi tick 16 ms: chuyển nội dung ~110 ms, sáng ô ~55 ms


def annular(c: QPointF, r_in: float, r_out: float, a0: float, a1: float, rc: float = CORNER) -> QPolygonF:
    """Hình quạt vành khuyên bo góc (đa giác mịn); góc theo chiều kim đồng hồ từ 12h.
    Không dùng QPainterPath: PySide6 6.12.0 làm hỏng refcount None ở hàm void của nó (crash)."""
    rad = math.radians
    u = lambda a: (math.sin(rad(a)), -math.cos(rad(a)))  # hướng ra ngoài
    t = lambda a: (math.cos(rad(a)), math.sin(rad(a)))  # hướng cùng chiều kim đồng hồ
    pt = lambda r, a: (c.x() + r * u(a)[0], c.y() + r * u(a)[1])
    ro, ri = r_out - rc, r_in + rc
    do, di = math.degrees(math.asin(rc / ro)), math.degrees(math.asin(rc / ri))  # lệch góc tâm góc bo so với cạnh
    pts: list[tuple[float, float]] = []

    def corner(cx, cy, v1, v2):  # cung tròn bán kính rc quanh (cx,cy), từ hướng v1 sang v2 (đường ngắn)
        g1, g2 = math.atan2(v1[1], v1[0]), math.atan2(v2[1], v2[0])
        d = (g2 - g1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(7):
            g = g1 + d * k / 6
            pts.append((cx + rc * math.cos(g), cy + rc * math.sin(g)))

    def arc(r, x0, x1):
        for k in range(int(abs(x1 - x0)) + 2):
            pts.append(pt(r, x0 + (x1 - x0) * k / (int(abs(x1 - x0)) + 1)))

    neg = lambda v: (-v[0], -v[1])
    cx, cy = pt(ro, a0 + do); corner(cx, cy, neg(t(a0)), u(a0 + do))
    arc(r_out, a0 + do, a1 - do)
    cx, cy = pt(ro, a1 - do); corner(cx, cy, u(a1 - do), t(a1))
    cx, cy = pt(ri, a1 - di); corner(cx, cy, t(a1), neg(u(a1 - di)))
    arc(r_in, a1 - di, a0 + di)
    cx, cy = pt(ri, a0 + di); corner(cx, cy, neg(u(a0 + di)), neg(t(a0)))
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _mix(a: QColor, b: QColor, t: float, alpha: float) -> QColor:
    return QColor(*(int(x + (y - x) * t) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))),
                  int(alpha))


class Wheel(QWidget):
    chosen = Signal(object)  # Action hoặc None (huỷ)

    def __init__(self):
        super().__init__()
        self.size_px = 2 * (R1 + 14)
        self.setFixedSize(self.size_px, self.size_px)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.groups, self.files = [], []
        self.level, self.hover, self.swap, self.glow = None, None, 1.0, {}
        self.click_mode = False
        self.timer = QTimer(self, interval=16, timeout=self._tick)

    def open(self, files, groups, click_mode=False):
        self.files, self.groups, self.click_mode = files, groups, click_mode
        self.level, self.hover, self.swap, self.glow = None, None, 0.0, {}
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if not click_mode:  # chế độ giữ phím: overlay không nhận chuột/focus
            flags |= Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g, m = scr.geometry(), self.size_px // 2
        c = type(pos)(min(max(pos.x(), g.left() + m), g.right() - m), min(max(pos.y(), g.top() + m), g.bottom() - m))
        if c != pos:
            QCursor.setPos(c)  # đưa con trỏ vào tâm vòng khi mở sát mép màn hình
        self.center_global = c
        self.move(c.x() - self.size_px // 2, c.y() - self.size_px // 2)
        self.show()
        if click_mode:
            self.activateWindow()
        self.timer.start()

    def _items(self):
        """[(nhãn, màu)] của nội dung vòng hiện tại: nhóm, hoặc tác vụ của nhóm đang mở."""
        if self.level is None:
            return [(label, ACCENT.get(gid, "#888")) for gid, label, _ in self.groups]
        gid, _, acts = self.groups[self.level]
        return [(a.label, ACCENT.get(gid, "#888")) for a in acts]

    def _set_level(self, level):
        self.level, self.hover, self.swap, self.glow = level, None, 0.0, {}

    def _tick(self):
        d = QCursor.pos() - self.center_global
        n = len(self.groups) if self.level is None else len(self.groups[self.level][2])
        idx, r = ring_hit(d.x(), d.y(), n)
        if self.level is None:
            if idx is not None and r >= R_MID and self.groups[idx][2]:
                self._set_level(idx)  # kéo ra ngoài nhóm: vòng tự đổi sang tác vụ của nhóm
                idx = None
        elif idx is None:
            self._set_level(None)  # về tâm: quay lại vòng nhóm
        self.hover = idx
        self.swap = min(1.0, self.swap + SWAP_STEP)
        for i in range(n):
            g = self.glow.get(i, 0.0)
            self.glow[i] = min(1.0, g + HOVER_STEP) if i == idx else max(0.0, g - HOVER_STEP)
        self.update()

    def _selected_action(self):
        if self.level is None or self.hover is None:
            return None
        return self.groups[self.level][2][self.hover]

    def confirm(self):
        self._close(self._selected_action())

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
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        c = QPointF(self.size_px / 2, self.size_px / 2)
        t = 1 - (1 - self.swap) ** 3  # ease-out: ô mọc từ đường giữa vòng ra hai phía, không vượt R1
        rm, half = (R0 + R1) / 2, (R1 - R0) / 2 * (0.55 + 0.45 * t)
        items = self._items()
        n = len(items)
        # khung vòng ngoài mảnh kiểu HUD
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 229, 255, 55), 1))
        p.drawEllipse(c, R1 + 9, R1 + 9)
        for i, (label, hexcol) in enumerate(items):
            col, h = QColor(hexcol), self.glow.get(i, 0.0)
            a0, a1 = ring_arc(i, n)
            poly = annular(c, rm - half, rm + half, a0 + GAP, a1 - GAP)
            if h > 0:  # hào quang neon khi rê tới
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(70 * h * t)), 7))
                p.drawPolygon(poly)
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int((120 + 135 * h) * t)), 1.6))
            p.setBrush(_mix(BASE, col, 0.08 + 0.42 * h, 215 * t))
            p.drawPolygon(poly)
            self._text(p, c, rm, (a0 + a1) / 2, label.upper(), 11 if self.level is None else 9, True,
                       QColor(255, 255, 255, int(255 * t)) if h > 0.5 else QColor(INK.red(), INK.green(), INK.blue(), int(235 * t)))
        # tâm: số file, hoặc tên nhóm đang mở; về tâm = quay lại
        ring = QColor(ACCENT.get(self.groups[self.level][0], "#00e5ff")) if self.level is not None else QColor("#00e5ff")
        p.setPen(QPen(QColor(ring.red(), ring.green(), ring.blue(), 200), 1.6))
        p.setBrush(QColor(7, 11, 20, 245))
        p.drawEllipse(c, R0 - 8, R0 - 8)
        act = self._selected_action()
        p.setPen(INK)
        font = QFont(FONT)
        font.setPointSize(9)
        p.setFont(font)
        mid = f"{len(self.files)}\nFILE" if self.level is None else f"‹ BACK\n{self.groups[self.level][1].upper()}"
        p.drawText(QRectF(c.x() - R0, c.y() - R0, 2 * R0, 2 * R0), Qt.AlignCenter, mid)
        if act:  # mô tả đầy đủ ở dưới vòng vì tâm quá nhỏ
            font.setPointSize(10)
            p.setFont(font)
            r = QRectF(8, self.size_px - 26, self.size_px - 16, 22)
            p.setPen(QPen(QColor(ring.red(), ring.green(), ring.blue(), 160), 1))
            p.setBrush(QColor(7, 11, 20, 230))
            p.drawRoundedRect(r, 6, 6)
            p.setPen(INK)
            p.drawText(r, Qt.AlignCenter, act.tip)

    @staticmethod
    def _text(p, c, r, ang_deg, text, pt, bold, color):
        a = math.radians(ang_deg)
        x, y = c.x() + r * math.sin(a), c.y() - r * math.cos(a)
        f = QFont(FONT)
        f.setPointSize(pt)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(x - 42, y - 14, 84, 28), Qt.AlignCenter, text)
