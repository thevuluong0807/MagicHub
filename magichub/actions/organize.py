"""Nhóm Organize: merge, split, rotate, compress, extract, zip."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from .base import (action, kind_of, natural_key, open_pdf, out_path, parse_ranges, save_pdf, steps,
                   tmpdir, unique)
from .convert import images_to_pdf

PDF, IMG = ("pdf",), ("img",)


@action("organize.merge", "organize", "Merge", "Gộp các file PDF/ảnh thành 1 PDF (theo tên file)",
        kinds=("pdf", "img"), min_files=2)
def merge(files, p):
    files = sorted(files, key=natural_key)
    out = out_path(files[0], "merged", "pdf")
    doc = pymupdf.open()
    with tmpdir() as td:
        for f in steps(files):
            if kind_of(f) == "pdf":
                src = open_pdf(f)
            else:
                src = pymupdf.open(str(images_to_pdf([f], td / "img.pdf")))
            doc.insert_pdf(src)
            src.close()
    return [save_pdf(doc, out)]


def _ask_ranges(label, hint):
    def ask(files):
        from ..dialogs import ask_form

        return ask_form(label, [{"name": "ranges", "label": hint, "type": "text", "default": ""}])

    return ask


@action("organize.split", "organize", "Split", "Tách PDF: để trống = mỗi trang 1 file; '1-3,5' = mỗi nhóm 1 file",
        kinds=PDF, ask=_ask_ranges("Tách PDF", "Khoảng trang (vd 1-3,5; trống = từng trang)"))
def split(files, p):
    outs = []
    for f in files:
        src = open_pdf(f)
        d = unique(f.with_name(f"{f.stem}_split"))
        d.mkdir()
        for g in steps(parse_ranges(p.get("ranges", ""), len(src)), lambda g: f"{f.name}: trang {g[0] + 1}"):
            part = pymupdf.open()
            part.insert_pdf(src, from_page=g[0], to_page=g[-1])
            tag = f"p{g[0] + 1}" if len(g) == 1 else f"p{g[0] + 1}-{g[-1] + 1}"
            save_pdf(part, d / f"{f.stem}_{tag}.pdf")
        src.close()
        outs.append(d)
    return outs


def _rotate(deg):
    def run(files, p):
        outs = []
        for f in steps(files):
            if kind_of(f) == "pdf":
                doc = open_pdf(f)
                for page in doc:
                    page.set_rotation((page.rotation + deg) % 360)
                outs.append(save_pdf(doc, out_path(f, "rotated")))
            else:
                im = ImageOps.exif_transpose(Image.open(f))
                out = out_path(f, "rotated")
                im.rotate(-deg, expand=True).save(out)
                outs.append(out)
        return outs

    return run


action("organize.rotate_cw", "organize", "↻ 90°", "Xoay phải 90°", kinds=("pdf", "img"))(_rotate(90))
action("organize.rotate_ccw", "organize", "↺ 90°", "Xoay trái 90°", kinds=("pdf", "img"))(_rotate(-90))


# mức nén: (dpi ảnh PDF, chất lượng JPEG PDF, cạnh dài tối đa ảnh, chất lượng ảnh)
LEVELS = {"Nhẹ (giữ nét)": (150, 80, 3200, 85), "Vừa": (110, 65, 2560, 72), "Mạnh": (72, 45, 1600, 55), "Cực mạnh": (50, 35, 1200, 40)}
OOXML = {"docx", "xlsx", "pptx"}
_MEDIA = ("png", "jpg", "jpeg")


def _ask_level(files):
    from ..dialogs import ask_form

    return ask_form("Nén", [
        {"name": "level", "label": "Mức nén", "type": "choice", "choices": list(LEVELS)},
        {"name": "target_mb", "label": "Dung lượng tối đa (MB, 0 = chỉ theo mức nén; >0 = tự tăng mức nén cho tới khi đạt)",
         "type": "int", "min": 0, "max": 2000, "default": 0},
    ])


def _shrink_image(im: Image.Image, fmt: str, side: int, q: int, strong: bool) -> bytes:
    im = ImageOps.exif_transpose(im)
    im.thumbnail((side, side))
    buf = io.BytesIO()
    if fmt == "jpeg":
        im.convert("RGB").save(buf, "JPEG", quality=q, optimize=True)
    else:
        if strong and im.mode in ("RGB", "RGBA"):  # PNG ảnh chụp: giảm còn 256 màu (giữ alpha)
            im = im.quantize(256, method=Image.Quantize.FASTOCTREE if im.mode == "RGBA" else Image.Quantize.MEDIANCUT)
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _shrink_ooxml(src: Path, out: Path, level: tuple):
    """docx/xlsx/pptx là file zip: nén lại ảnh trong */media/*, giữ nguyên tên + định dạng nên không phải sửa quan hệ XML."""
    _, _, side, q = level
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for i in zin.infolist():
            data = zin.read(i)
            e = i.filename.rsplit(".", 1)[-1].lower()
            if "/media/" in i.filename and e in _MEDIA and len(data) > 20_000:
                try:
                    new = _shrink_image(Image.open(io.BytesIO(data)), "jpeg" if e != "png" else "png", side, q, q < 60)
                    if len(new) < len(data):
                        data = new
                except Exception:  # ảnh lạ/hỏng: giữ nguyên bản gốc
                    pass
            zout.writestr(i, data)


def _shrink(f: Path, out: Path, level: tuple):
    dpi, q_pdf, side, q_img = level
    k = kind_of(f)
    if k == "pdf":
        doc = open_pdf(f)
        doc.rewrite_images(dpi_threshold=dpi + 40, dpi_target=dpi, quality=q_pdf)
        save_pdf(doc, out, clean=True, use_objstms=True)
    elif k == "img":
        im = ImageOps.exif_transpose(Image.open(f))
        im.thumbnail((side, side))
        fmt = (f.suffix.lower().lstrip(".")).replace("jpg", "jpeg")
        if fmt in ("jpeg", "webp"):
            im.convert("RGB").save(out, fmt.upper(), quality=q_img, optimize=True)
        else:
            im.save(out, optimize=True)
    else:
        _shrink_ooxml(f, out, level)


@action("organize.compress", "organize", "Compress", "Nén PDF/ảnh/Word/Excel/PowerPoint (giảm ảnh bên trong); đặt dung lượng tối đa để tự nén tới khi đạt",
        kinds=("pdf", "img", "doc", "xls", "ppt"), ask=_ask_level,
        check=lambda files: all(kind_of(f) in ("pdf", "img") or f.suffix.lower().lstrip(".") in OOXML for f in files))
def compress(files, p):
    names = list(LEVELS)
    start = names.index(p.get("level", "Vừa"))
    limit = int(p.get("target_mb") or 0) * 1024 * 1024
    outs = []
    for f in steps(files):
        out = out_path(f, "small")
        for n, name in enumerate(names[start:]):
            _shrink(f, out, LEVELS[name])
            if not limit or out.stat().st_size <= limit:
                break
            if name != names[-1]:
                out.unlink()
        else:
            size = out.stat().st_size
            for o in (*outs, out):
                o.unlink(missing_ok=True)
            raise ValueError(f"{f.name}: nén mạnh nhất vẫn {size / 1048576:.1f} MB (> {limit // 1048576} MB). Thử tách file hoặc bỏ bớt ảnh")
        outs.append(out)
    return outs


def _ask_reorder(files):
    from ..viewer import ask_reorder

    return ask_reorder(files[0])


@action("organize.reorder", "organize", "Reorder", "Sắp xếp lại / xoá trang PDF bằng ảnh thu nhỏ (kéo thả)",
        kinds=PDF, ask=_ask_reorder, check=lambda files: len(files) == 1)
def reorder(files, p):
    """params.order: chỉ số trang (0-based) giữ lại theo thứ tự mới, trang vắng mặt bị xoá; params.rotate: {chỉ số gốc: độ xoay thêm}."""
    doc = open_pdf(files[0])
    order = [int(i) for i in p.get("order", [])]
    if not order or any(i < 0 or i >= len(doc) for i in order):
        raise ValueError("Thứ tự trang không hợp lệ")
    for i, deg in p.get("rotate", {}).items():  # {chỉ số trang gốc: độ xoay thêm}, làm trước select để chỉ số còn đúng
        doc[int(i)].set_rotation((doc[int(i)].rotation + int(deg)) % 360)
    doc.select(order)
    return [save_pdf(doc, out_path(files[0], "reordered"))]


@action("organize.pages", "organize", "Pages", "Trích các trang chọn ra PDF mới",
        kinds=PDF, ask=_ask_ranges("Trích trang", "Trang cần lấy (vd 1-3,5,7-)"))
def extract_pages(files, p):
    outs = []
    for f in steps(files):
        src = open_pdf(f)
        keep = [i for g in parse_ranges(p.get("ranges", "1"), len(src)) for i in g]
        doc = pymupdf.open()
        for i in keep:
            doc.insert_pdf(src, from_page=i, to_page=i)
        src.close()
        outs.append(save_pdf(doc, out_path(f, "pages")))
    return outs


@action("organize.images", "organize", "Images", "Trích toàn bộ ảnh nhúng trong PDF ra thư mục", kinds=PDF)
def extract_images(files, p):
    outs = []
    for f in steps(files):
        doc = open_pdf(f)
        d = unique(f.with_name(f"{f.stem}_images"))
        seen, n = set(), 0
        for page in steps(doc, lambda pg: f"{f.name}: trang {pg.number + 1}/{len(doc)}"):
            for img in page.get_images(full=True):
                if img[0] in seen:
                    continue
                seen.add(img[0])
                info = doc.extract_image(img[0])
                d.mkdir(exist_ok=True)
                n += 1
                (d / f"img_{n:03d}.{info['ext']}").write_bytes(info["image"])
        doc.close()
        if not n:
            raise ValueError(f"{f.name}: PDF không chứa ảnh nhúng")
        outs.append(d)
    return outs


@action("organize.zip", "organize", "Zip", "Nén các file đã chọn thành 1 file .zip")
def zip_files(files, p):
    out = unique(files[0].with_name((files[0].stem if len(files) == 1 else "archive") + ".zip"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in steps(files):
            z.write(f, f.name)
    return [out]
