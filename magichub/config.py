"""Đường dẫn dữ liệu người dùng + config.json (xem docs/DATA.md)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def is_wayland() -> bool:
    return sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland"


DEFAULT = {"hotkeys": [{"modifiers": ["ctrl", "alt", "shift"], "key": "", "group": None}], "output_dir": None,
           "menu": {"hidden": [], "order": []}, "engine": "auto"}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "magichub"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "magichub"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> dict:
    p = config_dir() / "config.json"
    cfg = json.loads(json.dumps(DEFAULT))
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if "hotkey" in d:  # v0.1-0.4: một phím tắt -> danh sách
                d.setdefault("hotkeys", [{**d["hotkey"], "group": None}])
                del d["hotkey"]
            cfg.update(d)
        except (ValueError, TypeError):
            pass  # file hỏng -> dùng mặc định, không ghi đè file của user
    else:
        p.write_text(json.dumps(cfg, indent=2), "utf-8")
    return cfg


def save(cfg: dict) -> None:
    (config_dir() / "config.json").write_text(json.dumps(cfg, indent=2), "utf-8")
