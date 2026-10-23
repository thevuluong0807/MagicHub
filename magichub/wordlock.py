"""Mật khẩu cho file Office mới (.docx/.xlsx/.pptx): đặt/gỡ mật khẩu MỞ file (mã hoá thật, msoffcrypto) và gỡ khoá chỉ-đọc của Word
(Restrict Editing: word/settings.xml, w:documentProtection)."""
from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
Q = lambda n: f"{{{W}}}{n}"
SETTINGS = "word/settings.xml"
ALGO = {"4": "sha1", "12": "sha256", "13": "sha384", "14": "sha512"}  # w:cryptAlgorithmSid


def _hash(password: str, salt: bytes, algo: str, spin: int) -> bytes:
    h = hashlib.new(algo, salt + password.encode("utf-16-le")).digest()
    for i in range(spin):
        h = hashlib.new(algo, h + i.to_bytes(4, "little")).digest()
    return h


def _rewrite(src: Path, out: Path, edit) -> None:
    """Chép src -> out, thay word/settings.xml bằng edit(root). Các phần khác giữ nguyên byte."""
    try:
        zin = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise ValueError(f"{src.name}: không phải file .docx hợp lệ") from None
    with zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        if SETTINGS not in zin.namelist():
            raise ValueError(f"{src.name}: thiếu {SETTINGS}")
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == SETTINGS:
                root = etree.fromstring(data)
                edit(root)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            zout.writestr(it, data)


def encrypt(src: Path, out: Path, password: str) -> None:
    """Đặt mật khẩu MỞ file (AES, như Word: File > Info > Encrypt with Password)."""
    import msoffcrypto

    with open(src, "rb") as fin, open(out, "wb") as fout:
        try:
            msoffcrypto.OfficeFile(fin).encrypt(password, fout)
        except Exception as e:
            fout.close()
            out.unlink(missing_ok=True)
            raise ValueError(f"{src.name}: không đặt được mật khẩu ({e}). File đã có mật khẩu hoặc không phải .docx/.xlsx/.pptx?") from None


def _decrypt(src: Path, out: Path, password: str) -> None:
    """File đặt mật khẩu MỞ (Word: File > Info > Encrypt with Password): bọc trong container OLE, không phải zip."""
    import msoffcrypto

    with open(src, "rb") as fin, open(out, "wb") as fout:
        try:
            f = msoffcrypto.OfficeFile(fin)
            f.load_key(password=password)
            f.decrypt(fout)
        except msoffcrypto.exceptions.InvalidKeyError:
            fout.close()
            out.unlink(missing_ok=True)
            raise ValueError(f"{src.name}: sai mật khẩu") from None
        except Exception as e:
            fout.close()
            out.unlink(missing_ok=True)
            raise ValueError(f"{src.name}: không giải mã được ({e}). Có thể là .doc cũ không có mật khẩu - mở bằng Word rồi Lưu thành .docx") from None


def unlock(src: Path, out: Path, password: str) -> bool:
    """Gỡ khoá; trả True nếu file có khoá. Sai mật khẩu -> ValueError."""
    if src.read_bytes()[:4] == b"\xd0\xcf\x11\xe0":
        _decrypt(src, out, password)
        return True
    if src.suffix.lower() != ".docx":
        return False
    found = []

    def edit(root):
        for el in root.findall(Q("documentProtection")):
            found.append(1)
            h, s = el.get(Q("hash")), el.get(Q("salt"))
            if h and s:  # có mật khẩu
                algo = ALGO.get(el.get(Q("cryptAlgorithmSid"), ""))
                if not algo:
                    raise ValueError(f"{src.name}: kiểu mã hoá mật khẩu không hỗ trợ")
                if _hash(password, base64.b64decode(s), algo, int(el.get(Q("cryptSpinCount"), "0"))) != base64.b64decode(h):
                    raise ValueError(f"{src.name}: sai mật khẩu")
            root.remove(el)

    _rewrite(src, out, edit)
    return bool(found)
