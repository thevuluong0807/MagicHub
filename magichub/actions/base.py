"""Registry + helper dùng chung cho mọi action. Không import Qt."""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

KINDS = {
    "pdf": {"pdf"},
    "img": {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "gif", "heic", "heif"},
    "doc": {"docx", "doc", "odt", "rtf"},
    "xls": {"xlsx", "xls", "ods", "csv"},
    "ppt": {"pptx", "ppt", "odp"},
    "txt": {"txt", "md"},
}
EXT2KIND = {e: k for k, v in KINDS.items() for e in v}
GROUPS = [("convert", "Convert"), ("edit", "Edit"), ("organize", "Organize")]


try:  # HEIC/HEIF (ảnh iPhone) mở được bằng Pillow khi có pillow-heif
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass


def ext(p) -> str:
    e = Path(p).suffix.lower().lstrip(".")
    return "jpg" if e == "jpeg" else e


def kind_of(p) -> str:
    return EXT2KIND.get(Path(p).suffix.lower().lstrip("."), "other")


@dataclass
class Action:
    id: str
    group: str
    label: str  # ngắn, hiện trên vòng tròn
    tip: str  # mô tả đầy đủ, hiện ở tâm
    run: Callable  # run(files: list[Path], params: dict) -> list[Path]
    kinds: tuple | None = None  # None = mọi loại file
    min_files: int = 1
    ask: Callable | None = None  # ask(files) -> dict | None (None = huỷ)
    check: Callable | None = None  # điều kiện thêm

    def accepts(self, files) -> bool:
        if len(files) < self.min_files:
            return False
        if self.kinds is not None and not all(kind_of(f) in self.kinds for f in files):
            return False
        return self.check(files) if self.check else True


REGISTRY: list[Action] = []


def action(id, group, label, tip, kinds=None, **kw):
    def deco(fn):
        REGISTRY.append(Action(id, group, label, tip, fn, kinds, **kw))
        return fn

    return deco


def natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(p).name)]


# ---------- Tiến trình + huỷ (thread-local: mỗi Job một ngữ cảnh) ----------
class Cancelled(BaseException):  # BaseException: không bị `except Exception` của thư viện thứ ba (pdf2docx…) nuốt
    pass


_ctx = threading.local()


def bind(progress=None, cancelled=None):
    """Job gọi đầu luồng chạy. progress(frac|None, text); cancelled() -> bool. Không bind = no-op (CLI/test)."""
    _ctx.cb, _ctx.cancel, _ctx.scope = progress, cancelled, []


def check_cancel():
    c = getattr(_ctx, "cancel", None)
    if c and c():
        raise Cancelled()


def report(frac=None, text=""):
    """frac 0..1 trong phạm vi scope hiện tại; None = chưa biết (thanh chạy vô định)."""
    check_cancel()
    cb = getattr(_ctx, "cb", None)
    if not cb:
        return
    if frac is not None:
        for lo, hi in reversed(_ctx.scope):  # trong ra ngoài
            frac = lo + (hi - lo) * frac
    cb(frac, text)


@contextlib.contextmanager
def scope(lo, hi):
    stack = getattr(_ctx, "scope", None)
    if stack is None:
        yield
        return
    stack.append((lo, hi))
    try:
        yield
    finally:
        stack.pop()


def steps(seq, text=None):
    """for x in steps(items, lambda x: tên): báo tiến trình theo từng phần tử; vòng lặp lồng nhau tự chia khoảng."""
    seq = list(seq)
    n = len(seq)
    for i, x in enumerate(seq):
        report(i / n, text(x) if text else (x.name if isinstance(x, Path) else ""))
        with scope(i / n, (i + 1) / n):
            yield x
    report(1.0)


def run_proc(cmd, timeout=300, **kw) -> subprocess.CompletedProcess:
    """subprocess.run nhưng huỷ được (Cancelled) và giết cả nhóm tiến trình con."""
    kw.setdefault("start_new_session", os.name == "posix")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    t0 = time.monotonic()
    while True:
        try:
            out, err = p.communicate(timeout=0.2)
            return subprocess.CompletedProcess(cmd, p.returncode, out, err)
        except subprocess.TimeoutExpired:
            try:
                check_cancel()
                if time.monotonic() - t0 > timeout:
                    raise subprocess.TimeoutExpired(cmd, timeout)
            except BaseException:
                if os.name == "posix":
                    import signal

                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(p.pid, signal.SIGKILL)
                else:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                p.communicate()
                raise


def unique(p) -> Path:
    """Đường dẫn chưa tồn tại; nếu config.output_dir đặt thì mọi kết quả nằm trong thư mục đó."""
    from ..config import load

    p = Path(p)
    out_dir = load().get("output_dir")
    if out_dir and Path(out_dir).is_dir():
        p = Path(out_dir) / p.name
    q, n = p, 1
    while q.exists():
        q = p.with_name(f"{p.stem}_{n}{p.suffix}")
        n += 1
    return q


def out_path(src, suffix="", new_ext=None) -> Path:
    src = Path(src)
    e = new_ext or src.suffix.lstrip(".")
    name = f"{src.stem}_{suffix}" if suffix else src.stem
    return unique(src.with_name(f"{name}.{e}"))


def parse_ranges(s: str, n: int) -> list[list[int]]:
    """'1-3,5,7-' -> [[0,1,2],[4],[6..n-1]] (chỉ số 0-based). Rỗng -> mỗi trang một nhóm."""
    s = s.strip()
    if not s:
        return [[i] for i in range(n)]
    groups = []
    for part in re.split(r"[,;\s]+", s):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)-(\d*)", part) or re.fullmatch(r"(\d+)()", part)
        if not m:
            raise ValueError(f"Khoảng trang không hợp lệ: {part}")
        a = int(m.group(1) or 1)
        b = int(m.group(2) or n) if "-" in part else a
        if a < 1 or b > n or a > b:
            raise ValueError(f"Trang ngoài phạm vi 1-{n}: {part}")
        groups.append(list(range(a - 1, b)))
    return groups


# ---------- LibreOffice ----------
_SOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def find_soffice() -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    exe = exe or next((p for p in _SOFFICE_PATHS if os.path.exists(p)), None)
    if not exe:
        raise RuntimeError("Cần cài LibreOffice (hoặc Microsoft Office trên Windows/macOS) để chuyển đổi tài liệu Office")
    return exe


_BWRAP: list[str] | None = None


def sandbox_prefix(writable: list, readonly: list = ()) -> list[str]:
    """Linux + bubblewrap: hệ thống chỉ đọc, không mạng, chỉ ghi được vào `writable` (+ /tmp riêng).
    Không có bwrap hoặc không chạy được (userns bị chặn) -> [] (chạy thường)."""
    global _BWRAP
    if not sys.platform.startswith("linux") or os.environ.get("MAGICHUB_NO_SANDBOX"):
        return []
    if _BWRAP is None:
        exe = shutil.which("bwrap")
        ok = exe and subprocess.run([exe, "--ro-bind", "/", "/", "true"], capture_output=True).returncode == 0
        _BWRAP = [exe] if ok else []
    if not _BWRAP:
        return []
    bind = [x for r in readonly for x in ("--ro-bind", str(r), str(r))]  # sau --tmpfs /tmp để file nguồn trong /tmp vẫn thấy
    bind += [x for w in writable for x in ("--bind", str(w), str(w))]
    return [*_BWRAP, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run", "--setenv", "HOME", "/tmp", *bind,
            "--unshare-net", "--unshare-pid", "--die-with-parent"]


def soffice_convert(src, fmt: str, outdir) -> Path:
    """fmt: 'pdf', 'txt:Text', 'csv', 'pptx'. Trả về file kết quả trong outdir."""
    from ..config import cache_dir

    profile = cache_dir() / "lo-profile"
    cmd = [find_soffice(), f"-env:UserInstallation={profile.as_uri()}", "--headless",
           "--convert-to", fmt, "--outdir", str(outdir), str(src)]
    cmd = sandbox_prefix([outdir, profile], [Path(src).resolve()]) + cmd  # file Office lạ chạy trong sandbox khi có bwrap
    kw = {"preexec_fn": lambda: os.nice(10)} if os.name == "posix" else {}
    r = run_proc(cmd, timeout=300, **kw)
    out = Path(outdir) / f"{Path(src).stem}.{fmt.split(':')[0]}"
    if r.returncode or not out.exists():
        raise RuntimeError(f"LibreOffice lỗi: {r.stderr.decode(errors='ignore')[:200]}")
    return out


@contextlib.contextmanager
def tmpdir():
    d = tempfile.mkdtemp(prefix="magichub-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def find_font() -> str:
    cands = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    f = next((c for c in cands if os.path.exists(c)), None)
    if not f:
        raise RuntimeError("Không tìm thấy font Unicode (DejaVu Sans / Arial)")
    return f


def open_pdf(path):
    import pymupdf

    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(f"{Path(path).name}: PDF đã đặt mật khẩu")
    return doc


def save_pdf(doc, out, **kw):
    doc.save(str(out), garbage=3, deflate=True, **kw)
    doc.close()
    return Path(out)
