"""Hotkey toàn cục kiểu 'giữ phím': pressed khi đủ tổ hợp, released khi nhả bất kỳ phím nào của tổ hợp."""
from __future__ import annotations

import sys
import threading
import time

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

MODS = {"ctrl", "alt", "shift", "cmd"}
# Phím "C" theo mã vật lý/keysym: Controller.tap('c') không phát được trên một số X server
KEY_C = keyboard.KeyCode.from_vk({"win32": 0x43, "darwin": 8}.get(sys.platform, 0x63))
KEYOBJ = {"ctrl": keyboard.Key.ctrl, "alt": keyboard.Key.alt, "shift": keyboard.Key.shift, "cmd": keyboard.Key.cmd}


def norm(key) -> str | None:
    if isinstance(key, keyboard.Key):
        n = key.name.split("_")[0]
        return "alt" if n == "alt" else n  # alt_gr -> alt
    ch = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    if sys.platform == "win32" and vk and 0x41 <= vk <= 0x5A:  # Windows trả ký tự điều khiển khi giữ Ctrl
        return chr(vk).lower()
    if ch and ord(ch) >= 32:
        return ch.lower()
    if sys.platform != "darwin" and vk and 0x20 <= vk <= 0x7E:  # Ctrl+M cho char '\r' -> dùng keysym/vk
        return chr(vk).lower()
    return None


class Hotkey(QObject):
    injecting = False  # dùng chung mọi tổ hợp: phím do send_copy giả lập không được kích hoạt tổ hợp khác
    pressed = Signal()
    released = Signal()

    def __init__(self, mods: list[str], key: str):
        super().__init__()
        self.mods, self.key = set(mods), key.lower()  # key "" = chỉ giữ modifier
        self.down: set[str] = set()
        self.active = False
        self.ctl = keyboard.Controller()
        self.listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def _press(self, k):
        if self.injecting:
            return
        n = norm(k)
        if n:
            self.down.add(n)
        if not self.active and (not self.key or self.key in self.down) and self.mods <= self.down:
            self.active = True
            self.pressed.emit()

    def _release(self, k):
        if self.injecting:
            return
        n = norm(k)
        self.down.discard(n)
        if self.active and (n == self.key or n in self.mods):  # key rỗng: n==key không bao giờ đúng với n thật
            self.active = False
            self.released.emit()

    def send_copy(self):
        """Gửi Ctrl+C (Cmd+C trên macOS) mà không để modifier của hotkey lẫn vào. Chạy ở thread riêng."""
        def work():
            copy_mod = "cmd" if sys.platform == "darwin" else "ctrl"
            Hotkey.injecting = True
            try:
                others = [m for m in self.mods if m != copy_mod]
                for m in others:
                    self.ctl.release(KEYOBJ[m])
                if copy_mod not in self.mods:
                    self.ctl.press(KEYOBJ[copy_mod])
                self.ctl.tap(KEY_C)
                if copy_mod not in self.mods:
                    self.ctl.release(KEYOBJ[copy_mod])
                for m in others:  # người dùng vẫn đang giữ -> khôi phục trạng thái
                    self.ctl.press(KEYOBJ[m])
            finally:
                time.sleep(0.05)
                Hotkey.injecting = False

        threading.Thread(target=work, daemon=True).start()
