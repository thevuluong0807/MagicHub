"""Tích hợp hệ thống: tự chạy khi đăng nhập + mục menu file manager (chạy `magichub menu FILE...`).
Cần cho Wayland (hotkey toàn cục không dùng được) và tiện cho mọi nền tảng. Không import Qt."""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def launcher() -> list[str]:
    """Lệnh khởi chạy MagicHub hiện tại: AppImage, bản đóng gói (PyInstaller) hoặc python -m magichub."""
    if os.environ.get("APPIMAGE"):
        return [os.environ["APPIMAGE"]]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "magichub"]


def _dq(a: str) -> str:
    """Đối số cho trường Exec= của .desktop / .nemo_action (ngoặc kép khi có khoảng trắng)."""
    return '"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"' if any(c in a for c in ' "\\') else a


def _files(home: Path) -> dict[Path, tuple[str, bool]]:
    """{đường dẫn: (nội dung, executable)} cần ghi cho nền tảng hiện tại."""
    cmd = launcher()
    dq = " ".join(_dq(a) for a in cmd)
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        q = " ".join(f'"{a}"' for a in cmd)
        return {
            appdata / "Microsoft/Windows/SendTo/MagicHub.cmd": (f"@echo off\r\nstart \"\" {q} menu %*\r\n", False),
            appdata / "Microsoft/Windows/Start Menu/Programs/Startup/MagicHub.cmd": (f"@echo off\r\nstart \"\" {q}\r\n", False),
        }
    if sys.platform == "darwin":
        args = "".join(f"<string>{a}</string>" for a in cmd)
        return {home / "Library/LaunchAgents/com.magichub.plist": (
            '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
            f"<key>Label</key><string>com.magichub</string><key>ProgramArguments</key><array>{args}</array>"
            "<key>RunAtLoad</key><true/></dict></plist>\n", False)}
    share = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    conf = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    sh = f"#!/usr/bin/env bash\nIFS=$'\\n'\nexec {shlex.join(cmd)} menu $NAUTILUS_SCRIPT_SELECTED_FILE_PATHS\n"
    return {
        conf / "autostart/magichub.desktop": (
            f"[Desktop Entry]\nType=Application\nName=MagicHub\nExec={dq}\nX-GNOME-Autostart-enabled=true\n", False),
        share / "nautilus/scripts/MagicHub": (sh, True),  # Nautilus: chuột phải → Scripts → MagicHub
        share / "nemo/actions/magichub.nemo_action": (
            f"[Nemo Action]\nName=MagicHub\nComment=Convert / Edit / Organize\nExec={dq} menu %F\n"
            "Selection=NotNone\nExtensions=any;\n", False),
        share / "kio/servicemenus/magichub.desktop": (  # Dolphin
            "[Desktop Entry]\nType=Service\nMimeType=all/allfiles;\nActions=magichub;\n"
            f"[Desktop Action magichub]\nName=MagicHub\nExec={dq} menu %F\n", True),
    }


def install(home: Path | None = None) -> list[Path]:
    out = []
    for p, (text, exe) in _files(home or Path.home()).items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
        if exe:
            p.chmod(0o755)
        out.append(p)
    return out


def remove(home: Path | None = None) -> list[Path]:
    gone = []
    for p in _files(home or Path.home()):
        if p.exists():
            p.unlink()
            gone.append(p)
    return gone
