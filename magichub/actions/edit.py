"""Nhóm Edit cho PDF và ảnh. Word/Excel/PowerPoint không chỉnh tại chỗ (xem docs/CONSTRAINTS.md)."""
from __future__ import annotations

import re

import pymupdf
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .base import action, find_font, kind_of, open_pdf, out_path, save_pdf

PDF, PI = ("pdf",), ("pdf", "img")
COLORS = {"Đen": (0, 0, 0), "Đỏ": (0.85, 0.1, 0.1), "Xanh": (0.1, 0.3, 0.85), "Xám": (0.45, 0.45, 0.45)}
HL = {"Vàng": (1, 1, 0), "Xanh lá": (0.55, 1, 0.55), "Hồng": (1, 0.65, 0.85)}
TEXT_POS = ["Watermark chéo", "Trên", "Giữa", "Dưới"]
IMG_POS = ["Giữa", "Trên trái", "Trên phải", "Dưới trái", "Dưới phải"]


def _form(title, fields):
    def ask(files):
        from ..dialogs import ask_form

        return ask_form(title, fields)

    return ask


def _words(s: str) -> list[str]:
    return [w.strip() for w in re.split(r"[\n,;]+", s) if w.strip()]


# ---------- Protect ----------
@action("edit.protect", "edit", "Protect", "Đặt mật khẩu mở PDF (AES-256)", kinds=PDF,
        ask=_form("Đặt mật khẩu", [{"name": "password", "label": "Mật khẩu", "type": "password", "required": True}]))
def protect(files, p):
    outs = []
    for f in files:
        doc = open_pdf(f)
        outs.append(save_pdf(doc, out_path(f, "protected"), encryption=pymupdf.PDF_ENCRYPT_AES_256,
                             user_pw=p["password"], owner_pw=p["password"]))
    return outs


# ---------- Redact ----------
@action("edit.redact", "edit", "Redact", "Xoá vĩnh viễn từ khoá khỏi PDF (che đen + gỡ text bên dưới)", kinds=PDF,
        ask=_form("Redact", [{"name": "keywords", "label": "Từ khoá (mỗi dòng/dấu phẩy 1 mục)",
                              "type": "multiline", "required": True}]))
def redact(files, p):
    kws, outs = _words(p["keywords"]), []
    for f in files:
        doc, total = open_pdf(f), 0
        for page in doc:
            hits = [r for k in kws for r in page.search_for(k)]
            for r in hits:
                page.add_redact_annot(r, fill=(0, 0, 0))
            if hits:
                page.apply_redactions()
                total += len(hits)
        if total:
            outs.append(save_pdf(doc, out_path(f, "redacted")))
    if not outs:
        raise ValueError("Không tìm thấy từ khoá nào trong PDF (PDF scan cần OCR trước)")
    return outs


# ---------- Highlight ----------
@action("edit.highlight", "edit", "Highlight", "Tô sáng từ khoá trong PDF", kinds=PDF,
        ask=_form("Highlight", [
            {"name": "keywords", "label": "Từ khoá", "type": "multiline", "required": True},
            {"name": "color", "label": "Màu", "type": "choice", "choices": list(HL)}]))
def highlight(files, p):
    kws, outs = _words(p["keywords"]), []
    for f in files:
        doc, total = open_pdf(f), 0
        for page in doc:
            for k in kws:
                quads = page.search_for(k, quads=True)
                if quads:
                    a = page.add_highlight_annot(quads=quads)
                    a.set_colors(stroke=HL[p.get("color", "Vàng")])
                    a.update()
                    total += len(quads)
        if total:
            outs.append(save_pdf(doc, out_path(f, "highlighted")))
    if not outs:
        raise ValueError("Không tìm thấy từ khoá nào trong PDF")
    return outs


# ---------- Add text ----------
def _text_xy(W, H, w, size, pos):
    return {"Trên": (W / 2 - w / 2, size * 1.5), "Dưới": (W / 2 - w / 2, H - size),
            "Giữa": (W / 2 - w / 2, H / 2 + size / 3)}.get(pos, (W / 2 - w / 2, H / 2 + size / 3))


@action("edit.text", "edit", "Text", "Thêm chữ / watermark vào PDF hoặc ảnh", kinds=PI,
        ask=_form("Thêm chữ", [
            {"name": "text", "label": "Nội dung", "type": "text", "required": True},
            {"name": "pos", "label": "Vị trí", "type": "choice", "choices": TEXT_POS},
            {"name": "size", "label": "Cỡ chữ", "type": "int", "default": 48, "min": 6, "max": 400},
            {"name": "color", "label": "Màu", "type": "choice", "choices": list(COLORS)}]))
def add_text(files, p):
    text, pos, size = p["text"], p.get("pos", TEXT_POS[0]), int(p.get("size", 48))
    rgb = COLORS[p.get("color", "Đỏ")]
    diag = pos == TEXT_POS[0]
    outs = []
    for f in files:
        out = out_path(f, "text")
        if kind_of(f) == "pdf":
            font, doc = pymupdf.Font(fontfile=find_font()), open_pdf(f)
            for page in doc:
                W, H = page.rect.width, page.rect.height
                x, y = _text_xy(W, H, font.text_length(text, size), size, pos)
                tw = pymupdf.TextWriter(page.rect)
                tw.append((x, y), text, font=font, fontsize=size)
                tw.write_text(page, color=rgb, opacity=0.35 if diag else 1,
                              morph=(pymupdf.Point(W / 2, H / 2), pymupdf.Matrix(45)) if diag else None)
            outs.append(save_pdf(doc, out))
        else:
            im = ImageOps.exif_transpose(Image.open(f)).convert("RGBA")
            px = max(10, int(size * im.width / 800))
            font = ImageFont.truetype(find_font(), px)
            w = int(font.getlength(text))
            layer = Image.new("RGBA", (w + 20, px * 2), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((10, px // 2), text, font=font,
                                       fill=tuple(int(c * 255) for c in rgb) + (90 if diag else 255,))
            if diag:
                layer = layer.rotate(45, expand=True)
            y = {"Trên": 10, "Dưới": im.height - layer.height - 10}.get(pos, (im.height - layer.height) / 2)
            im.alpha_composite(layer, (max(0, int((im.width - layer.width) / 2)), max(0, int(y))))
            im.convert("RGB").save(out) if out.suffix.lower() in (".jpg", ".jpeg") else im.save(out)
            outs.append(out)
    return outs


# ---------- Add image ----------
def _img_rect(W, H, w, h, pos, m=20):
    x = {"Trên trái": m, "Dưới trái": m, "Trên phải": W - w - m, "Dưới phải": W - w - m}.get(pos, (W - w) / 2)
    y = {"Trên trái": m, "Trên phải": m, "Dưới trái": H - h - m, "Dưới phải": H - h - m}.get(pos, (H - h) / 2)
    return x, y


@action("edit.image", "edit", "Image", "Chèn logo/ảnh (chữ ký, tem) vào PDF hoặc ảnh", kinds=PI,
        ask=_form("Chèn ảnh", [
            {"name": "image", "label": "File ảnh", "type": "file", "required": True},
            {"name": "pos", "label": "Vị trí", "type": "choice", "choices": IMG_POS},
            {"name": "pct", "label": "Rộng (% khổ trang)", "type": "int", "default": 25, "min": 3, "max": 100}]))
def add_image(files, p):
    stamp, pos, pct = Image.open(p["image"]).convert("RGBA"), p.get("pos", "Giữa"), int(p.get("pct", 25))
    outs = []
    for f in files:
        out = out_path(f, "stamped")
        if kind_of(f) == "pdf":
            doc = open_pdf(f)
            for page in doc:
                W, H = page.rect.width, page.rect.height
                w = W * pct / 100
                h = w * stamp.height / stamp.width
                x, y = _img_rect(W, H, w, h, pos)
                page.insert_image(pymupdf.Rect(x, y, x + w, y + h), filename=p["image"], overlay=True)
            outs.append(save_pdf(doc, out))
        else:
            im = ImageOps.exif_transpose(Image.open(f)).convert("RGBA")
            w = int(im.width * pct / 100)
            s = stamp.resize((w, int(w * stamp.height / stamp.width)))
            x, y = _img_rect(im.width, im.height, s.width, s.height, pos)
            im.alpha_composite(s, (max(0, int(x)), max(0, int(y))))
            im.convert("RGB").save(out) if out.suffix.lower() in (".jpg", ".jpeg") else im.save(out)
            outs.append(out)
    return outs


# ---------- Crop ----------
def _ask_crop(files):
    from ..dialogs import ask_crop

    return ask_crop(files)


@action("edit.crop", "edit", "Crop", "Cắt vùng chọn (PDF: ẩn phần ngoài vùng, mọi trang cùng tỉ lệ)", kinds=PI,
        ask=_ask_crop)
def crop(files, p):
    x0, y0, x1, y1 = p["box"]  # tỉ lệ 0..1
    outs = []
    for f in files:
        out = out_path(f, "cropped")
        if kind_of(f) == "pdf":
            doc = open_pdf(f)
            for page in doc:
                r = page.rect
                box = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                                   r.x0 + x1 * r.width, r.y0 + y1 * r.height)
                page.set_cropbox(box * page.derotation_matrix)
            outs.append(save_pdf(doc, out))
        else:
            im = ImageOps.exif_transpose(Image.open(f))
            im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height))).save(out)
            outs.append(out)
    return outs
