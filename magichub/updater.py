"""Kiểm tra và cài bản mới từ GitHub Releases. Không import Qt. Tắt bằng config `update_check: false` hoặc MAGICHUB_NO_UPDATE=1.
AppImage (Linux): tải bản mới, thay file đang chạy, khởi động lại. Windows (đã đóng gói): chạy MagicHub-Setup.exe.
Chạy từ source (clone git, ví dụ run.bat): git pull + pip install, khởi động lại. macOS / source không có git: mở trang Release."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import __version__
from .actions.base import report, steps  # noqa: F401  (report: tiến trình tải)

REPO = "thevuluong0807/MagicHub"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": f"MagicHub/{__version__}"}


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.lstrip("vV").split(".") if x.isdigit())


def fetch_latest(url: str = API, timeout: int = 8) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def check(current: str = __version__, fetch=fetch_latest) -> dict | None:
    """Có bản mới hơn -> {version, tag, page, assets{tên: url}}; không thì None. Lỗi mạng -> None (không làm phiền người dùng)."""
    try:
        d = fetch()
        if parse(d["tag_name"]) <= parse(current):
            return None
        return {"version": d["tag_name"].lstrip("v"), "tag": d["tag_name"], "page": d["html_url"],
                "assets": {a["name"]: a["browser_download_url"] for a in d.get("assets", [])}}
    except (OSError, ValueError, KeyError):
        return None


def mode() -> str:
    """Cách cập nhật tại chỗ cho bản đang chạy: 'appimage' | 'windows' | 'git' | 'manual'."""
    if sys.platform.startswith("linux") and os.environ.get("APPIMAGE"):
        return "appimage"
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        return "windows"
    if not getattr(sys, "frozen", False) and (ROOT / ".git").exists() and shutil.which("git"):
        return "git"
    return "manual"


def _run(cmd: list[str]) -> str:
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}  # pythonw: không nháy cửa sổ console
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, **kw)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:2])}: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def download(url: str, dest: Path, label: str = "") -> Path:
    """Tải về dest (qua file .part), báo % và huỷ được; trả dest."""
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r, open(part, "wb") as f:
            total, got = int(r.headers.get("Content-Length") or 0), 0
            while chunk := r.read(256 * 1024):
                f.write(chunk)
                got += len(chunk)
                report(got / total if total else None, f"{label} {got / 1048576:.1f}" + (f"/{total / 1048576:.1f} MB" if total else " MB"))
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)
    return dest


def apply(info: dict) -> list[Path]:
    """Tải và cài (xem mode()). Trả [file đã cài/tải]; 'manual' thì không làm gì (nơi gọi mở trang Release)."""
    m = mode()
    if m == "appimage":
        target = Path(os.environ["APPIMAGE"])
        url = info["assets"].get("MagicHub-x86_64.AppImage")
        if not url:
            raise RuntimeError("Release này chưa có file AppImage")
        new = download(url, target.with_name(target.name + ".new"), "Tải bản mới")
        new.chmod(0o755)
        new.replace(target)  # đổi tên nguyên tử; tiến trình đang chạy giữ inode cũ nên không sao
        return [target]
    if m == "windows":
        url = info["assets"].get("MagicHub-Setup.exe")
        if not url:
            raise RuntimeError("Release này chưa có MagicHub-Setup.exe")
        setup = download(url, Path(os.environ.get("TEMP", ".")) / "MagicHub-Setup.exe", "Tải bản cài")
        return [setup]
    if m == "git":
        report(None, "git pull…")
        _run(["git", "pull", "--ff-only", "origin"])  # cây làm việc có sửa đổi xung đột -> git báo lỗi, không ghi đè
        report(None, "Cập nhật thư viện…")
        _run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        return [ROOT]
    return []


def restart(installed: list[Path]) -> None:
    """Chạy bản mới sau khi tiến trình hiện tại thoát (ổ khoá một-bản-chạy phải được nhả trước)."""
    if mode() == "appimage":
        subprocess.Popen(["sh", "-c", 'sleep 2; exec "$0"', str(installed[0])], start_new_session=True)
    elif mode() == "windows":
        subprocess.Popen([str(installed[0]), "/SILENT", "/SUPPRESSMSGBOXES"], close_fds=True)
    elif mode() == "git":
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if sys.platform == "win32" else 0
        boot = "import time, runpy; time.sleep(2); runpy.run_module('magichub', run_name='__main__')"  # chờ tiến trình cũ nhả ổ khoá một-bản-chạy
        subprocess.Popen([sys.executable, "-c", boot], cwd=ROOT, close_fds=True, creationflags=flags, start_new_session=sys.platform != "win32")
