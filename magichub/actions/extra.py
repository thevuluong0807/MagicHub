"""v0.7: tác vụ ảnh (đổi cỡ, xoá metadata) và PDF (header/footer, flatten, unlock, so sánh)."""
from __future__ import annotations

import io

import pymupdf
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from .base import action, ext, find_font, kind_of, open_pdf, out_path, save_pdf, steps, tmpdir
from .convert import images_to_pdf
from .edit import PDF, PI, _form, save_img

IMG = ("img",)
ALIGN = ["Giữa", "Trái", "Phải"]


# ---------- Resize (ảnh) ----------
@action("edit.resize", "edit", "Resize", "Đổi kích thước ảnh theo % hoặc chiều rộng (giữ tỉ lệ)", kinds=IMG,
        ask=_form("Đổi kích thước", [
            {"name": "mode", "label": "Theo", "type": "choice", "choices": ["Phần trăm (%)", "Chiều rộng (px)"]},
            {"name": "value", "label": "Giá trị", "type": "int", "default": 50, "min": 1, "max": 20000}]))
def resize(files, p):
    outs = []
    for f in steps(files):
        im = ImageOps.exif_transpose(Image.open(f))
        w = round(im.width * p["value"] / 100) if p["mode"].startswith("Phần") else p["value"]
        size = (max(1, w), max(1, round(im.height * w / im.width)))
        outs.append(save_img(im.resize(size, Image.LANCZOS), out_path(f, "resized")))
    return outs


# ---------- Strip metadata (ảnh + PDF) ----------
@action("edit.strip", "edit", "Strip", "Xoá metadata riêng tư (ảnh: EXIF/GPS; PDF: tác giả, XML, JavaScript)", kinds=PI)
def strip(files, p):
    outs = []
    for f in steps(files):
        out = out_path(f, "clean")
        if kind_of(f) == "pdf":
            doc = open_pdf(f)
            doc.scrub(metadata=True, xml_metadata=True, javascript=True, thumbnails=True, attached_files=False,
                      clean_pages=False, embedded_files=False, hidden_text=False, redactions=False, remove_links=False,
                      reset_fields=False, reset_responses=False)
            outs.append(save_pdf(doc, out))
        else:
            im = ImageOps.exif_transpose(Image.open(f))  # giữ chiều đúng rồi mới bỏ EXIF
            if im.mode == "P":
                im = im.convert("RGBA")
            outs.append(save_img(Image.frombytes(im.mode, im.size, im.tobytes()), out))  # ảnh mới = không còn info/exif
    return outs


# ---------- Header / footer + số trang ----------
@action("edit.headfoot", "edit", "Số trang", "Thêm header/footer; dùng {n} = số trang, {N} = tổng số trang", kinds=PDF,
        ask=_form("Header / footer", [
            {"name": "header", "label": "Header", "type": "text", "default": ""},
            {"name": "footer", "label": "Footer", "type": "text", "default": "{n} / {N}"},
            {"name": "align", "label": "Căn", "type": "choice", "choices": ALIGN},
            {"name": "size", "label": "Cỡ chữ", "type": "int", "default": 10, "min": 6, "max": 48}]))
def headfoot(files, p):
    if not (p.get("header") or p.get("footer")):
        raise ValueError("Cần nhập header hoặc footer")
    font, size, margin = find_font(), p.get("size", 10), 28
    measure = pymupdf.Font(fontfile=font)
    outs = []
    for f in steps(files):
        doc = open_pdf(f)
        total = len(doc)
        for i, page in steps(enumerate(doc, 1), lambda t: f"{f.name}: trang {t[0]}/{total}"):
            r = page.rect  # hệ toạ độ đã xoay; đổi về gốc bằng derotation_matrix
            for text, y in ((p.get("header"), margin + size), (p.get("footer"), r.height - margin)):
                if not text:
                    continue
                text = text.replace("{n}", str(i)).replace("{N}", str(total))
                w = measure.text_length(text, fontsize=size)
                x = {"Trái": margin, "Phải": r.width - margin - w}.get(p.get("align"), (r.width - w) / 2)
                page.insert_text(pymupdf.Point(x, y) * page.derotation_matrix, text, fontsize=size,
                                 fontname="dj", fontfile=font, rotate=page.rotation)
        outs.append(save_pdf(doc, out_path(f, "numbered")))
    return outs


# ---------- Flatten ----------
@action("edit.flatten", "edit", "Flatten", "Ép ghi chú và ô form thành nội dung trang (không sửa lại được)", kinds=PDF)
def flatten(files, p):
    outs = []
    for f in steps(files):
        doc = open_pdf(f)
        doc.bake(annots=True, widgets=True)
        outs.append(save_pdf(doc, out_path(f, "flat")))
    return outs


# ---------- Unlock ----------
@action("edit.unlock", "edit", "Unlock", "Gỡ mật khẩu mở file PDF/Word/Excel/PowerPoint, hoặc khoá chỉ-đọc Word (cần biết mật khẩu hiện tại)", kinds=PDF + ("doc", "xls", "ppt"), check=lambda fs: all(ext(f) in ("pdf", "docx", "xlsx", "pptx") for f in fs),
        ask=_form("Gỡ mật khẩu", [{"name": "password", "label": "Mật khẩu hiện tại", "type": "text", "required": True}]))
def unlock(files, p):
    outs = []
    for f in files:
        if ext(f) != "pdf":
            from .. import wordlock

            o = out_path(f, "unlocked")
            if not wordlock.unlock(f, o, p["password"]):
                o.unlink()
                raise ValueError(f"{f.name}: file không đặt mật khẩu hoặc khoá chỉnh sửa")
            outs.append(o)
            continue
        doc = pymupdf.open(str(f))
        if doc.needs_pass and not doc.authenticate(p["password"]):
            doc.close()
            raise ValueError(f"{f.name}: sai mật khẩu")
        outs.append(save_pdf(doc, out_path(f, "unlocked"), encryption=pymupdf.PDF_ENCRYPT_NONE))
    return outs


# ---------- So sánh 2 PDF ----------
@action("organize.compare", "organize", "Compare", "So sánh 2 PDF theo từng trang, tô đỏ chỗ khác nhau", kinds=PDF,
        min_files=2, check=lambda files: len(files) == 2)
def compare(files, p):
    a, b = (open_pdf(f) for f in files)
    with tmpdir() as td:
        pages = []
        n = max(len(a), len(b))
        for i in steps(range(n), lambda i: f"Trang {i + 1}/{n}"):
            ims = [Image.open(io.BytesIO(d[i].get_pixmap(dpi=100, alpha=False).tobytes("png"))).convert("RGB")
                   if i < len(d) else None for d in (a, b)]
            base = ims[0] or ims[1]
            out = Image.blend(base, Image.new("RGB", base.size, "white"), 0.6)  # nền nhạt để nét đỏ nổi
            if ims[0] and ims[1]:
                other = ims[1].resize(base.size)
                diff = ImageChops.difference(ims[0].convert("L"), other.convert("L")).point(lambda v: 255 if v > 40 else 0)
                out.paste(Image.new("RGB", base.size, (220, 30, 30)), mask=diff.filter(ImageFilter.MaxFilter(5)))
            else:  # trang chỉ có ở một bên: khung đỏ dày
                ImageDraw.Draw(out).rectangle((0, 0, base.width - 1, base.height - 1), outline=(220, 30, 30), width=8)
            png = td / f"{i:04d}.png"
            out.save(png)
            pages.append(png)
        res = images_to_pdf(pages, out_path(files[0], "diff"))
    a.close()
    b.close()
    return [res]
