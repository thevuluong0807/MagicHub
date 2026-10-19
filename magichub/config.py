"""Đường dẫn dữ liệu người dùng + config.json (xem docs/DATA.md)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT = {"hotkey": {"modifiers": ["ctrl", "alt", "shift"], "key": ""}, "output_dir": None}


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
            cfg.update(json.loads(p.read_text("utf-8")))
        except ValueError:
            pass  # file hỏng -> dùng mặc định, không ghi đè file của user
    else:
        p.write_text(json.dumps(cfg, indent=2), "utf-8")
    return cfg


def save(cfg: dict) -> None:
    (config_dir() / "config.json").write_text(json.dumps(cfg, indent=2), "utf-8")
