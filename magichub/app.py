"""Daemon khay hệ thống: hotkey -> lấy file đang chọn -> vòng tròn -> chạy tác vụ nền."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from . import config
from .actions import available
from .hotkey import Hotkey
from .wheel import Wheel

log = logging.getLogger("magichub")


def _icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    for i, col in enumerate(("#3b82f6", "#f59e0b", "#10b981")):
        p.setBrush(QColor(col))
        p.setPen(QColor(0, 0, 0, 0))
        p.drawPie(4, 4, 56, 56, (90 - i * 120) * 16, -110 * 16)
    p.end()
    return QIcon(pm)


def _size(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


class _Sig(QObject):
    done = Signal(object, list, list)  # action, inputs, outputs
    fail = Signal(str)


class Job(QRunnable):
    def __init__(self, act, files, params):
        super().__init__()
        self.act, self.files, self.params, self.sig = act, files, params, _Sig()

    def run(self):
        try:
            self.sig.done.emit(self.act, self.files, self.act.run(self.files, self.params))
        except Exception as e:  # lỗi file người dùng phải hiện, không được nuốt
            log.error(traceback.format_exc())
            self.sig.fail.emit(str(e) or e.__class__.__name__)


def read_selection(cb) -> list[Path]:
    md = cb.mimeData()
    urls = [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []
    if not urls and md.hasFormat("x-special/gnome-copied-files"):
        lines = bytes(md.data("x-special/gnome-copied-files")).decode().splitlines()[1:]
        urls = [QUrl(u).toLocalFile() for u in lines]
    return [Path(u) for u in urls if u]


class Hub(QObject):
    def __init__(self, app: QApplication, hotkey_enabled=True):
        super().__init__()
        self.app, self.cfg = app, config.load()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(1)  # tuần tự: nhẹ máy, và LibreOffice chỉ chạy 1 tiến trình
        self.jobs, self.last_out = set(), None
        self.wheel = Wheel()
        self.wheel.chosen.connect(self.on_chosen)
        self.files, self.held, self.saved_text = [], False, ""
        self.tray = QSystemTrayIcon(_icon())
        self.tray.messageClicked.connect(self.open_last)
        menu = QMenu()
        hk = self.cfg["hotkey"]
        self.hk_label = menu.addAction("")
        self.hk_label.setEnabled(False)
        self._show_hk()
        if hotkey_enabled:
            menu.addAction("Đổi phím tắt…", self.change_hotkey)
        self.out_label = menu.addAction("")
        self.out_label.setEnabled(False)
        menu.addAction("Thư mục kết quả…", self.change_output)
        menu.addAction("Lưu cạnh file gốc", lambda: self.set_output(None))
        self._show_out()
        menu.addAction("Mở thư mục cấu hình", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.config_dir()))))
        menu.addAction("Thoát", app.quit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.show()
        if hotkey_enabled:
            self.start_hotkey()

    def _show_out(self):
        d = self.cfg.get("output_dir")
        self.out_label.setText(f"Kết quả: {d}" if d else "Kết quả: cạnh file gốc")

    def set_output(self, d):
        self.cfg["output_dir"] = d
        config.save(self.cfg)
        self._show_out()

    def change_output(self):
        d = QFileDialog.getExistingDirectory(None, "Thư mục lưu kết quả", self.cfg.get("output_dir") or str(Path.home()))
        if d:
            self.set_output(d)

    def _show_hk(self):
        hk = self.cfg["hotkey"]
        self.hk_label.setText(f"Giữ {'+'.join(hk['modifiers'] + ([hk['key']] if hk['key'] else []))} để mở vòng tròn")

    def start_hotkey(self):
        hk = self.cfg["hotkey"]
        self.hotkey = Hotkey(hk["modifiers"], hk["key"])
        self.hotkey.pressed.connect(self.on_pressed)
        self.hotkey.released.connect(self.on_released)
        self.hotkey.start()

    def change_hotkey(self):
        from .dialogs import ask_hotkey
        hk = self.cfg["hotkey"]
        new = ask_hotkey(hk["modifiers"], hk["key"])
        if new:
            self.hotkey.stop()
            self.cfg["hotkey"] = {"modifiers": new[0], "key": new[1]}
            config.save(self.cfg)
            self.start_hotkey()
            self._show_hk()
            self.notify("MagicHub", "Phím tắt mới: " + "+".join(new[0] + ([new[1]] if new[1] else [])))

    # ---- hotkey flow ----
    def on_pressed(self):
        if self.wheel.isVisible():  # vòng đang chờ click: bấm phím tắt lần nữa = huỷ
            self.wheel.cancel()
            return
        self.held = True
        log.info("hotkey pressed")
        cb = self.app.clipboard()
        self.saved_text = cb.text() if cb.mimeData().hasText() else ""  # text() có thể treo 5s khi clipboard trống
        cb.clear()  # tránh dùng nhầm file cũ nếu Ctrl+C thất bại
        self.hotkey.send_copy()
        QTimer.singleShot(200, self.after_copy)

    def after_copy(self):
        cb = self.app.clipboard()
        files = read_selection(cb)
        if self.saved_text:
            cb.setText(self.saved_text)
        if not self.held:
            return
        self.show_wheel(files)

    def show_wheel(self, files, click_mode=False):
        if not files:
            return self.notify("MagicHub", "Chưa chọn file nào (hãy chọn file trong trình quản lý file rồi giữ phím)")
        groups = available(files)
        if not groups:
            return self.notify("MagicHub", "Không có tác vụ nào áp dụng cho lựa chọn này")
        self.files = files
        self.wheel.open(files, groups, click_mode)

    def on_released(self):
        self.held = False
        if self.wheel.isVisible():
            self.wheel.release()

    # ---- chạy tác vụ ----
    def on_chosen(self, act):
        if act is None:
            return
        params = {}
        if act.ask:
            params = act.ask(self.files)
            if params is None:
                return
        self.notify("MagicHub", f"Đang xử lý: {act.tip}…")
        job = Job(act, self.files, params)
        self.jobs.add(job)
        job.sig.done.connect(self.on_done)
        job.sig.fail.connect(lambda m, j=job: self.on_fail(m, j))
        self.pool.start(job)

    def on_done(self, act, files, outs):
        self.jobs = {j for j in self.jobs if j.act is not act or j.files is not files}
        self.last_out = outs[0] if outs else None
        msg = ", ".join(o.name for o in outs[:3]) + (f" (+{len(outs) - 3})" if len(outs) > 3 else "")
        if len(files) == len(outs) == 1 and files[0].is_file() and outs[0].is_file():
            msg += f"  [{_size(files[0].stat().st_size)} → {_size(outs[0].stat().st_size)}]"
        self.notify("Xong ✔ (bấm để mở thư mục)", msg)
        with (config.config_dir() / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "action": act.id, "inputs": [str(x) for x in files],
                                "outputs": [str(x) for x in outs], "status": "ok"}, ensure_ascii=False) + "\n")
        if getattr(self, "quit_after", False):
            QTimer.singleShot(3000, self.app.quit)

    def on_fail(self, msg, job):
        self.jobs.discard(job)
        self.notify("Lỗi", msg, error=True)
        with (config.config_dir() / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "action": job.act.id, "inputs": [str(x) for x in job.files],
                                "outputs": [], "status": "error", "error": msg}, ensure_ascii=False) + "\n")
        if getattr(self, "quit_after", False):
            QTimer.singleShot(3000, self.app.quit)

    def notify(self, title, text, error=False):
        print(f"[{title}] {text}", flush=True)
        icon = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
        self.tray.showMessage(title, text, icon, 6000)

    def open_last(self):
        if self.last_out:
            d = self.last_out if self.last_out.is_dir() else self.last_out.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))


WAYLAND_MSG = ("Wayland không cho bắt phím tắt toàn cục. Chạy `magichub install-integration` rồi chuột phải file → "
               "Scripts/MagicHub (Nautilus), hoặc đăng nhập phiên Xorg để dùng phím tắt")


def main(files: list[Path] | None = None) -> int:
    """files=None: chạy daemon hotkey. files=[...]: mở vòng tròn một lần tại con trỏ (chế độ bấm chuột)."""
    logging.basicConfig(filename=config.config_dir() / "magichub.log", level=logging.INFO)
    if config.is_wayland():
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")  # XWayland: đặt được cửa sổ overlay không viền, luôn trên cùng
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if files is None:
        lock = QLockFile(str(config.cache_dir() / "daemon.lock"))
        if not lock.tryLock(100):
            print("MagicHub đã chạy rồi")
            return 1
    wayland = files is None and config.is_wayland()
    hub = Hub(app, hotkey_enabled=files is None and not wayland)
    if wayland:
        QTimer.singleShot(500, lambda: hub.notify("MagicHub (Wayland)", WAYLAND_MSG))
    if files is not None:
        hub.quit_after = True
        hub.wheel.chosen.connect(lambda a: a is None and QTimer.singleShot(0, app.quit))
        QTimer.singleShot(100, lambda: hub.show_wheel(files, click_mode=True))
    return app.exec()
