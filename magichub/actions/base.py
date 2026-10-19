"""Registry + helper dùng chung cho mọi action. Không import Qt."""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

KINDS = {
    "pdf": {"pdf"},
    "img": {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "gif"},
    "doc": {"docx", "doc", "odt", "rtf"},
    "xls": {"xlsx", "xls", "ods", "csv"},
    "ppt": {"pptx", "ppt", "odp"},
    "txt": {"txt", "md"},
}
EXT2KIND = {e: k for k, v in KINDS.items() for e in v}
GROUPS = [("convert", "Convert"), ("edit", "Edit"), ("organize", "Organize")]


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


def unique(p) -> Path:
    p = Path(p)
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
        raise RuntimeError("Cần cài LibreOffice để chuyển đổi tài liệu Office")
    return exe


def soffice_convert(src, fmt: str, outdir) -> Path:
    """fmt: 'pdf', 'txt:Text', 'csv', 'pptx'. Trả về file kết quả trong outdir."""
    from ..config import cache_dir

    profile = cache_dir() / "lo-profile"
    cmd = [find_soffice(), f"-env:UserInstallation={profile.as_uri()}", "--headless",
           "--convert-to", fmt, "--outdir", str(outdir), str(src)]
    kw = {"preexec_fn": lambda: os.nice(10)} if os.name == "posix" else {}
    r = subprocess.run(cmd, capture_output=True, timeout=300, **kw)
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
