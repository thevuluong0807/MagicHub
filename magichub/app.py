"""Daemon khay hệ thống: hotkey -> lấy file đang chọn -> vòng tròn -> chạy tác vụ nền."""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QActionGroup, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from . import __version__, config, theme, updater
from .actions import available
from .actions.base import Action, Cancelled, bind
from .actions.office import ENGINES
from .hotkey import Hotkey
from .toast import Toast
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


class _UpdSig(QObject):
    found = Signal(dict, bool)  # thông tin bản mới ({} = không có), có phải do người dùng bấm kiểm tra


class _Sig(QObject):
    done = Signal(object, list)  # job, outputs (truyền chính Job: Qt sao chép list khi chuyển luồng nên không so sánh được bằng `is`)
    fail = Signal(str)
    progress = Signal(float, str)  # 0..1 hoặc -1 (chưa biết), dòng chi tiết
    cancelled = Signal()


class Job(QRunnable):
    def __init__(self, act, files, params):
        super().__init__()
        self.act, self.files, self.params, self.sig = act, files, params, _Sig()
        self.stop, self.started, self.finished = threading.Event(), False, False
        self._last = (0.0, "")

    def _report(self, frac, text):  # gọi từ luồng worker; giới hạn ~25 lần/giây để không ngập hàng đợi sự kiện
        now = time.monotonic()
        if text != self._last[1] or now - self._last[0] >= 0.04:
            self._last = (now, text)
            self.sig.progress.emit(-1.0 if frac is None else frac, text)

    def run(self):
        self.started = True
        bind(self._report, self.stop.is_set)
        try:
            self.sig.done.emit(self, self.act.run(self.files, self.params))
        except Cancelled:
            self.sig.cancelled.emit()
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
        self.toast = Toast()
        self.toast_job = None
        self.tray = QSystemTrayIcon(_icon())
        self.tray.messageClicked.connect(self.open_last)
        menu = QMenu()
        self.hotkeys: list[Hotkey] = []
        self.hk_label = menu.addAction("")
        self.hk_label.setEnabled(False)
        self._show_hk()
        if hotkey_enabled:
            menu.addAction("Phím tắt…", self.change_hotkeys)
        menu.addAction("Tuỳ chỉnh menu…", self.change_menu)
        self.out_label = menu.addAction("")
        self.out_label.setEnabled(False)
        menu.addAction("Thư mục kết quả…", self.change_output)
        menu.addAction("Lưu cạnh file gốc", lambda: self.set_output(None))
        self._show_out()
        self.upd = menu.addAction("", self.start_update)  # chỉ hiện khi có bản mới
        self.upd.setVisible(False)
        menu.addAction("Kiểm tra cập nhật", lambda: self.check_update(manual=True))
        eng = menu.addMenu("Engine Office")  # engine chuyển Word/Excel/PowerPoint
        grp = QActionGroup(eng)
        for key, label in ENGINES.items():
            a = eng.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.cfg.get("engine", "auto") == key)
            a.triggered.connect(lambda _=False, k=key: self.set_engine(k))
            grp.addAction(a)
        clip = menu.addMenu("Mã hoá clipboard")  # dán văn bản vào AI mà không tạo file
        clip.addAction("Mã hoá văn bản trong clipboard…", self.anon_clipboard)
        clip.addAction("Giải mã văn bản trong clipboard", self.restore_clipboard)
        clip.addAction("Xoá mapping clipboard", self.clear_clip_mapping)
        menu.addAction("Từ điển mã hoá…", self.manage_dictionaries)
        menu.addAction("Mở thư mục cấu hình", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.config_dir()))))
        menu.addAction("Thoát", app.quit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.show()
        if hotkey_enabled:
            self.start_hotkeys()
        self.update_info = None
        self.upd_sig = _UpdSig()
        self.upd_sig.found.connect(self.on_update_found)
        if self.cfg.get("update_check", True) and not os.environ.get("MAGICHUB_NO_UPDATE") and time.time() - self.cfg.get("last_update_check", 0) > 86400:
            QTimer.singleShot(8000, self.check_update)  # sau khi khởi động xong, tối đa 1 lần/ngày

    # ---- cập nhật ----
    def check_update(self, manual=False):
        def work():
            self.upd_sig.found.emit(updater.check() or {}, manual)

        threading.Thread(target=work, daemon=True).start()

    def on_update_found(self, info, manual):
        self.cfg["last_update_check"] = int(time.time())
        config.save(self.cfg)
        if not info:
            if manual:
                self.toast.finish(True, "Đang dùng bản mới nhất", f"MagicHub {__version__}")
            return
        self.update_info = info
        self.upd.setText(f"⬆ Cập nhật lên v{info['version']}")
        self.upd.setVisible(True)
        label = "Cập nhật" if updater.mode() != "manual" else "Mở trang tải"
        if self.toast.state != "running":
            self.toast.finish(True, f"Có bản mới v{info['version']}", f"Đang dùng {__version__}", [(label, self.start_update)])

    def start_update(self):
        info = self.update_info
        if not info:
            return
        if updater.mode() == "manual":
            return QDesktopServices.openUrl(QUrl(info["page"]))
        act = Action("update", "edit", "Cập nhật", f"Cập nhật lên v{info['version']}", lambda files, p: updater.apply(info))
        self._start(act, [Path(sys.argv[0])], {})

    def set_engine(self, key):
        self.cfg["engine"] = key
        config.save(self.cfg)
        self.notify("MagicHub", f"Engine Office: {ENGINES[key]}")

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
        hks = self.cfg["hotkeys"]
        first = "+".join(hks[0]["modifiers"] + ([hks[0]["key"]] if hks[0]["key"] else []))
        self.hk_label.setText(f"Giữ {first} để mở vòng tròn" + (f" (+{len(hks) - 1} phím khác)" if len(hks) > 1 else ""))

    def start_hotkeys(self):
        for h in self.cfg["hotkeys"]:
            hk = Hotkey(h["modifiers"], h["key"])
            hk.pressed.connect(lambda hk=hk, g=h.get("group"): self.on_pressed(hk, g))
            hk.released.connect(self.on_released)
            hk.start()
            self.hotkeys.append(hk)

    def change_hotkeys(self):
        from .settings import ask_hotkeys
        new = ask_hotkeys(self.cfg["hotkeys"])
        if new is not None:
            for hk in self.hotkeys:
                hk.stop()
            self.hotkeys = []
            self.cfg["hotkeys"] = new
            config.save(self.cfg)
            self.start_hotkeys()
            self._show_hk()
            self.notify("MagicHub", f"Đã lưu {len(new)} phím tắt")

    def change_menu(self):
        from .settings import ask_menu
        new = ask_menu(self.cfg["menu"])
        if new is not None:
            self.cfg["menu"] = new
            config.save(self.cfg)  # available() đọc config mỗi lần mở vòng -> có hiệu lực ngay
            self.notify("MagicHub", "Đã lưu menu")

    # ---- hotkey flow ----
    def on_pressed(self, hk, group=None):
        if self.wheel.isVisible():  # vòng đang chờ click: bấm phím tắt lần nữa = huỷ
            self.wheel.cancel()
            return
        self.held, self.only = True, group
        log.info("hotkey pressed")
        cb = self.app.clipboard()
        self.saved_text = cb.text() if cb.mimeData().hasText() else ""  # text() có thể treo 5s khi clipboard trống
        cb.clear()  # tránh dùng nhầm file cũ nếu Ctrl+C thất bại
        hk.send_copy()
        QTimer.singleShot(200, self.after_copy)

    def after_copy(self):
        cb = self.app.clipboard()
        files = read_selection(cb)
        if self.saved_text:
            cb.setText(self.saved_text)
        if not self.held:
            return
        self.show_wheel(files, only=self.only)

    def show_wheel(self, files, click_mode=False, only=None):
        if not files:
            return self.notify("MagicHub", "Chưa chọn file nào (hãy chọn file trong trình quản lý file rồi giữ phím)")
        groups = [g for g in available(files) if only in (None, g[0])]
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
            try:
                params = act.ask(self.files)
            except Exception as e:  # hộp thoại lỗi không được nuốt im
                log.exception("ask %s", act.id)
                return self.notify("MagicHub", f"Không mở được hộp thoại: {e}", error=True)
            if params is None:
                return
        self._start(act, self.files, params)

    def _start(self, act, files, params):
        job = Job(act, files, params)
        self.jobs.add(job)
        job.sig.done.connect(self.on_done)
        job.sig.fail.connect(lambda m, j=job: self.on_fail(m, j))
        job.sig.progress.connect(lambda f, t, j=job: self.on_progress(j, f, t))
        job.sig.cancelled.connect(lambda j=job: self.on_cancelled(j))
        self.pool.start(job)
        QTimer.singleShot(600, lambda: self._show_progress(job))  # việc nhanh không nháy thẻ tiến trình

    # ---- thẻ tiến trình ----
    def _title(self, job):
        n = len(job.files)
        return f"{job.act.label} · {job.files[0].name}" + (f" (+{n - 1})" if n > 1 else "")

    def _show_progress(self, job):
        if job.finished or self.toast.state == "running":
            return
        self.toast_job = job
        self.toast.running(self._title(job), "Đang chờ…" if not job.started else "Đang xử lý…", lambda: self.cancel_job(job))

    def on_progress(self, job, frac, text):
        if self.toast_job is job:
            self.toast.progress(frac, text)

    def cancel_job(self, job):
        job.stop.set()
        if self.pool.tryTake(job):  # chưa bắt đầu chạy: gỡ khỏi hàng đợi
            self.on_cancelled(job)

    def on_cancelled(self, job):
        job.finished = True
        self.jobs.discard(job)
        if self.toast_job is job:
            self.toast.finish(False, "Đã huỷ", self._title(job))
            self.toast_job = None
        self._log(job.act, job.files, [], "cancelled")
        if getattr(self, "quit_after", False):
            QTimer.singleShot(8000, self.app.quit)

    def _result(self, job, ok, title, detail, actions=()):
        """Thẻ kết quả khi không có việc khác đang chạy trên thẻ; ngược lại dùng bong bóng khay."""
        if self.toast_job is job or self.toast.state != "running":
            self.toast.finish(ok, title, detail, actions)
            self.toast_job = None
        else:
            self.notify(title, detail, error=not ok)

    def _log(self, act, files, outs, status, **extra):
        with (config.config_dir() / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "action": act.id, "inputs": [str(x) for x in files],
                                "outputs": [str(x) for x in outs], "status": status, **extra}, ensure_ascii=False) + "\n")

    def on_done(self, job, outs):
        act, files = job.act, job.files
        job.finished = True
        self.jobs.discard(job)
        if act.id == "update":  # không phải kết quả file: không xoá, không ghi lịch sử
            if job.stop.is_set():
                return self.on_cancelled(job)
            self.toast.finish(True, "Đã cập nhật", "Đang khởi động lại…")
            updater.restart(outs)
            return QTimer.singleShot(500, self.app.quit)
        if job.stop.is_set():  # huỷ nhưng bước cuối không ngắt được: bỏ kết quả vừa tạo
            for o in outs:
                if o not in files and o.exists():
                    shutil.rmtree(o, ignore_errors=True) if o.is_dir() else o.unlink(missing_ok=True)
            return self.on_cancelled(job)
        self.last_out = outs[0] if outs else None
        msg = ", ".join(o.name for o in outs[:3]) + (f" (+{len(outs) - 3})" if len(outs) > 3 else "")
        if len(files) == len(outs) == 1 and files[0].is_file() and outs[0].is_file():
            msg += f"  ·  {_size(files[0].stat().st_size)} → {_size(outs[0].stat().st_size)}"
        buttons = [("Mở thư mục", self.open_last)]
        if len(outs) == 1 and outs[0].is_file():
            buttons.append(("Mở file", lambda o=outs[0]: QDesktopServices.openUrl(QUrl.fromLocalFile(str(o)))))
        self._result(job, True, f"Xong · {act.label}", msg, buttons)
        self._log(act, files, outs, "ok")
        if getattr(self, "quit_after", False):
            QTimer.singleShot(8000, self.app.quit)

    def on_fail(self, msg, job):
        job.finished = True
        self.jobs.discard(job)
        self._result(job, False, f"Lỗi · {job.act.label}", msg)
        self._log(job.act, job.files, [], "error", error=msg)
        if getattr(self, "quit_after", False):
            QTimer.singleShot(8000, self.app.quit)

    # ---- mã hoá văn bản trong clipboard ----
    def _clip_file(self):
        return config.config_dir() / "clipboard_mapping.json"

    def anon_clipboard(self):
        """Clipboard -> hộp thoại chọn mục -> thay bằng mã, chép lại vào clipboard; mapping gần nhất lưu cục bộ để giải mã."""
        from . import anonymize as an
        from .actions.anon import entries_from
        from .dialogs import ask_anonymize

        text = self.app.clipboard().text()
        if not text.strip():
            return self.notify("MagicHub", "Clipboard chưa có văn bản", error=True)
        params = ask_anonymize(an.detect(text.splitlines(), an.load_safe()))
        if params is None:
            return
        try:
            mapper = an.Mapper(entries_from(params, text.splitlines()))
        except ValueError as e:
            return self.notify("MagicHub", str(e), error=True)
        out, n = an.anonymize_text(text, mapper)
        f = self._clip_file()
        f.write_text(json.dumps(mapper.table, ensure_ascii=False), "utf-8")
        if os.name == "posix":
            f.chmod(0o600)  # chứa dữ liệu gốc
        self.app.clipboard().setText(out)
        self.notify("Đã mã hoá clipboard", f"{n} chỗ đã thay; văn bản mã hoá đã nằm trong clipboard. Nhận câu trả lời từ AI thì copy rồi bấm Giải mã.")

    def restore_clipboard(self):
        from . import anonymize as an

        f = self._clip_file()
        if not f.exists():
            return self.notify("MagicHub", "Chưa có mapping clipboard (hãy mã hoá văn bản trước)", error=True)
        out, n = an.restore_text(self.app.clipboard().text(), json.loads(f.read_text("utf-8")))
        if not n:
            return self.notify("MagicHub", "Không thấy mã nào khớp mapping gần nhất trong clipboard", error=True)
        self.app.clipboard().setText(out)
        self.notify("Đã giải mã clipboard", f"{n} chỗ đã trả lại giá trị gốc, văn bản đã nằm trong clipboard.")

    def manage_dictionaries(self):
        from .dialogs import ask_dictionaries

        ask_dictionaries()

    def clear_clip_mapping(self):
        self._clip_file().unlink(missing_ok=True)
        self.notify("MagicHub", "Đã xoá mapping clipboard")

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
    sys.setswitchinterval(0.002)  # luồng xử lý nặng (Python thuần) không được bỏ đói luồng giao diện
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app)
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
