"""Nhóm Organize: merge, split, rotate, compress, extract, zip."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from .base import (action, kind_of, natural_key, open_pdf, out_path, parse_ranges, save_pdf,
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
        for f in files:
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
        for g in parse_ranges(p.get("ranges", ""), len(src)):
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
        for f in files:
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
LEVELS = {"Nhẹ (giữ nét)": (150, 80, 3200, 85), "Vừa": (110, 65, 2560, 72), "Mạnh": (72, 45, 1600, 55)}


def _ask_level(files):
    from ..dialogs import ask_form

    return ask_form("Nén", [{"name": "level", "label": "Mức nén", "type": "choice", "choices": list(LEVELS)}])


@action("organize.compress", "organize", "Compress", "Nén PDF/ảnh (giảm độ phân giải ảnh, tối ưu cấu trúc)",
        kinds=("pdf", "img"), ask=_ask_level)
def compress(files, p):
    dpi, q_pdf, side, q_img = LEVELS[p.get("level", "Vừa")]
    outs = []
    for f in files:
        out = out_path(f, "small")
        if kind_of(f) == "pdf":
            doc = open_pdf(f)
            doc.rewrite_images(dpi_threshold=dpi + 40, dpi_target=dpi, quality=q_pdf)
            outs.append(save_pdf(doc, out, clean=True, use_objstms=True))
        else:
            im = ImageOps.exif_transpose(Image.open(f))
            im.thumbnail((side, side))
            fmt = (f.suffix.lower().lstrip(".")).replace("jpg", "jpeg")
            if fmt in ("jpeg", "webp"):
                im.convert("RGB").save(out, fmt.upper(), quality=q_img, optimize=True)
            else:
                im.save(out, optimize=True)
            outs.append(out)
    return outs


@action("organize.pages", "organize", "Pages", "Trích các trang chọn ra PDF mới",
        kinds=PDF, ask=_ask_ranges("Trích trang", "Trang cần lấy (vd 1-3,5,7-)"))
def extract_pages(files, p):
    outs = []
    for f in files:
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
    for f in files:
        doc = open_pdf(f)
        d = unique(f.with_name(f"{f.stem}_images"))
        seen, n = set(), 0
        for page in doc:
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
        for f in files:
            z.write(f, f.name)
    return [out]
