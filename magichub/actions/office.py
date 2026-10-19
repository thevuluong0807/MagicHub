"""Engine chuyển đổi Office: Microsoft Office (Windows: PowerShell COM, macOS: osascript) hoặc LibreOffice.
config.engine: "auto" (Windows/macOS ưu tiên Microsoft Office nếu có, lỗi thì rơi về LibreOffice) | "office" | "libreoffice"."""
from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

from .base import kind_of, run_proc, soffice_convert, tmpdir

log = logging.getLogger("magichub")
ENGINES = {"auto": "Tự động (ưu tiên Microsoft Office)", "office": "Microsoft Office", "libreoffice": "LibreOffice"}
APP = {"doc": "Word", "xls": "Excel", "ppt": "PowerPoint"}  # loại file -> ứng dụng Office
OFFICE_FMT = {"doc": {"pdf", "txt:Text"}, "xls": {"pdf", "csv"}, "ppt": {"pdf", "pptx"}}  # Office làm được (mac: chỉ pdf)

_PS = r"""
$ErrorActionPreference = 'Stop'
$src = $env:MH_SRC; $out = $env:MH_OUT; $fmt = $env:MH_FMT
$a = New-Object -ComObject "$($env:MH_APP).Application"
try {
  if ($env:MH_APP -eq 'Word') {
    $a.Visible = $false; $a.DisplayAlerts = 0
    $d = $a.Documents.Open($src, $false, $true)
    if ($fmt -eq 'pdf') { $d.ExportAsFixedFormat($out, 17) }
    else { [IO.File]::WriteAllText($out, $d.Content.Text, (New-Object Text.UTF8Encoding($false))) }
    $d.Close(0)
  } elseif ($env:MH_APP -eq 'Excel') {
    $a.Visible = $false; $a.DisplayAlerts = $false
    $w = $a.Workbooks.Open($src, 0, $true)
    if ($fmt -eq 'pdf') { $w.ExportAsFixedFormat(0, $out) } else { $w.SaveAs($out, 62) }
    $w.Close($false)
  } else {
    $p = $a.Presentations.Open($src, -1, 0, 0)
    if ($fmt -eq 'pdf') { $p.SaveAs($out, 32) } else { $p.SaveAs($out, 24) }
    $p.Close()
  }
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
finally { $a.Quit() }
"""

_OSA = {
    "Word": 'tell application "Microsoft Word"\nopen src\nset d to active document\n'
            'save as d file name outp file format format PDF\nclose d saving no\nend tell',
    "Excel": 'tell application "Microsoft Excel"\nopen src\nset w to active workbook\n'
             'save workbook as w filename outp file format PDF file format\nclose w saving no\nend tell',
    "PowerPoint": 'tell application "Microsoft PowerPoint"\nopen src\nset p to active presentation\n'
                  'save p in outp as save as PDF\nclose p saving no\nend tell',
}


def available(kind: str) -> bool:
    app = APP.get(kind)
    if not app:
        return False
    if sys.platform == "win32":
        import winreg

        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{app}.Application"))
            return True
        except OSError:
            return False
    if sys.platform == "darwin":
        return Path(f"/Applications/Microsoft {app}.app").exists()
    return False


def use_office(kind: str, fmt: str) -> bool:
    from ..config import load

    eng = load().get("engine", "auto")
    if eng == "libreoffice" or fmt not in OFFICE_FMT.get(kind, ()) or (sys.platform == "darwin" and fmt != "pdf"):
        return False
    if eng == "office":
        if not available(kind):
            raise RuntimeError(f"Đã chọn engine Microsoft Office nhưng chưa cài Microsoft {APP[kind]} (xem config.engine)")
        return True
    return available(kind)  # auto


def _office_run(src: Path, fmt: str, outdir: Path) -> Path:
    kind, ext = kind_of(src), fmt.split(":")[0]
    out = Path(outdir) / f"{src.stem}.{ext}"
    if sys.platform == "win32":
        env = {**os.environ, "MH_SRC": str(src), "MH_OUT": str(out), "MH_FMT": ext, "MH_APP": APP[kind]}
        with tmpdir() as td:
            (td / "o.ps1").write_text(_PS, "utf-8-sig")
            r = run_proc(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                          "-File", str(td / "o.ps1")], env=env, timeout=300)
    else:  # macOS: Office có sandbox, chỉ ghi được vào Group Container của Office -> ghi tạm rồi chuyển
        group = Path.home() / "Library/Group Containers/UBF8T346G9.Office"
        with tmpdir() as td:
            work = group / f"magichub-{td.name}"
            work.mkdir(parents=True, exist_ok=True)
            try:
                tmp_out = work / out.name
                script = 'on run argv\nset src to POSIX file (item 1 of argv)\nset outp to item 2 of argv\n' + _OSA[APP[kind]] + '\nend run'
                r = run_proc(["osascript", "-e", script, str(src), str(tmp_out)], timeout=300)
                if tmp_out.exists():
                    shutil.move(str(tmp_out), out)
            finally:
                shutil.rmtree(work, ignore_errors=True)
    if r.returncode or not out.exists():
        raise RuntimeError(f"Microsoft {APP[kind]} lỗi: {r.stderr.decode(errors='ignore').strip()[:200]}")
    return out


def office_convert(src, fmt: str, outdir) -> Path:
    """fmt như soffice_convert: 'pdf', 'txt:Text', 'csv', 'pptx'. Chọn engine theo config; auto thì lỗi Office -> LibreOffice."""
    src, kind = Path(src), kind_of(src)
    if not use_office(kind, fmt):
        return soffice_convert(src, fmt, outdir)
    from ..config import load

    try:
        return _office_run(src, fmt, outdir)
    except RuntimeError as e:
        if load().get("engine", "auto") == "office":
            raise
        log.warning("Microsoft Office lỗi (%s), thử LibreOffice", e)
        return soffice_convert(src, fmt, outdir)
