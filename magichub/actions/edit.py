"""Nhóm Edit cho PDF và ảnh. Word/Excel/PowerPoint không chỉnh tại chỗ (xem docs/CONSTRAINTS.md)."""
from __future__ import annotations

import math
import re
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from .base import action, find_font, kind_of, open_pdf, out_path, save_pdf, tmpdir
from .convert import images_to_pdf

PDF, PI = ("pdf",), ("pdf", "img")
HL = {"Vàng": (1, 1, 0), "Xanh lá": (0.55, 1, 0.55), "Hồng": (1, 0.65, 0.85)}


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
def _ask_redact(files):
    from ..viewer import ask_redact

    return ask_redact(files[0])


@action("edit.redact", "edit", "Redact", "Xoá vĩnh viễn từ khoá/vùng tự chọn khỏi PDF (xem trước, che đen + gỡ text bên dưới)",
        kinds=PDF, ask=_ask_redact)
def redact(files, p):
    """params: keywords (tuỳ chọn, mọi file) + rects (tuỳ chọn, chỉ file đầu): [{page,x0,y0,x1,y1}] toạ độ 0..1 theo trang."""
    kws, outs = _words(p.get("keywords", "")), []
    for n, f in enumerate(files):
        doc, total = open_pdf(f), 0
        rects = p.get("rects", []) if n == 0 else []
        for i, page in enumerate(doc):
            W, H = page.rect.width, page.rect.height
            hits = [r for k in kws for r in page.search_for(k)]
            hits += [pymupdf.Rect(m["x0"] * W, m["y0"] * H, m["x1"] * W, m["y1"] * H) for m in rects if m["page"] == i]
            for r in hits:
                page.add_redact_annot(r, fill=(0, 0, 0))
            if hits:
                page.apply_redactions()
                total += len(hits)
        if total:
            outs.append(save_pdf(doc, out_path(f, "redacted")))
    if not outs:
        raise ValueError("Không tìm thấy từ khoá/vùng nào để che (PDF scan cần OCR trước)")
    return outs


# ---------- Markup: vẽ, hình, khung, chữ/watermark, ảnh, ghi chú ----------
NOTE_FS, NOTE_W = 11, 0.35  # cỡ chữ ghi chú (pt), bề rộng hộp (tỉ lệ khổ trang)


def note_box(text: str, W: float, H: float, x: float, y: float) -> pymupdf.Rect:
    """Hộp ghi chú tại (x, y) 0..1; cao ước lượng theo số dòng (cùng công thức cho xem trước và PDF)."""
    bw = min(NOTE_W * W, W - x * W - 4)
    lines = sum(max(1, -(-int(len(l) * NOTE_FS * 0.6) // max(int(bw - 8), 1))) for l in text.split("\n"))
    return pymupdf.Rect(x * W, y * H, x * W + bw, min(y * H + lines * NOTE_FS * 1.4 + 8, H - 2))


def arrow_head(a, b, w):
    """Hai điểm cánh mũi tên tại b cho đoạn a->b (a, b: (x, y)); dùng chung cho xem trước và PDF."""
    ang, L = math.atan2(b[1] - a[1], b[0] - a[0]), max(9, 4 * w)
    return [(b[0] - L * math.cos(ang - s * 0.45), b[1] - L * math.sin(ang - s * 0.45)) for s in (1, -1)]


def _draw_mark(page, m, font):
    W, H = page.rect.width, page.rect.height
    t, col, w = m["type"], tuple(m.get("color", (0.85, 0.1, 0.1))), m.get("w", 2)
    P = pymupdf.Point
    if t == "ink":
        a = page.add_ink_annot([[(x * W, y * H) for x, y in m["pts"]]])
        a.set_colors(stroke=col)
        a.set_border(width=w)
        a.update()
    elif t == "note":
        r = note_box(m["text"], W, H, m["x"], m["y"])
        page.draw_rect(r, color=(0.8, 0.6, 0), fill=(1, 0.95, 0.6), width=0.8)
        page.insert_textbox(r + (4, 3, -4, -2), m["text"], fontsize=NOTE_FS, fontname="dj", fontfile=font)
    elif t == "shape":
        a, b = (m["x0"] * W, m["y0"] * H), (m["x1"] * W, m["y1"] * H)
        r = pymupdf.Rect(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        fill = dict(fill=col, fill_opacity=0.25) if m.get("fill") else {}
        if m["kind"] == "rect":
            page.draw_rect(r, color=col, width=w, **fill)
        elif m["kind"] == "ellipse":
            page.draw_oval(r, color=col, width=w, **fill)
        else:
            page.draw_line(P(*a), P(*b), color=col, width=w)
            if m["kind"] == "arrow":
                for h in arrow_head(a, b, w):
                    page.draw_line(P(*b), P(*h), color=col, width=w)
    elif t == "border":
        inset = w / 2 + m.get("margin", 10)
        page.draw_rect(page.rect + (inset, inset, -inset, -inset), color=col, width=w)
    elif t == "text":
        f, size, rot = pymupdf.Font(fontfile=font), m.get("size", 24), m.get("rot", 0)
        lines = m["text"].split("\n")
        tw = pymupdf.TextWriter(page.rect)
        cx, cy = m["x"] * W, m["y"] * H  # rot=0: góc trên-trái; rot!=0: tâm (watermark)
        for i, line in enumerate(lines):
            if rot:
                tw.append((cx - f.text_length(line, size) / 2, cy + size / 3 + (i - (len(lines) - 1) / 2) * size * 1.25),
                          line, font=f, fontsize=size)
            else:
                tw.append((cx, cy + size * (1 + 1.25 * i)), line, font=f, fontsize=size)
        tw.write_text(page, color=col, opacity=m.get("opacity", 0.35 if rot else 1),
                      morph=(P(cx, cy), pymupdf.Matrix(rot)) if rot else None)
    elif t == "image":
        with Image.open(m["path"]) as im:
            iw, ih = im.size
        w_ = m["w"] * W
        page.insert_image(pymupdf.Rect(m["x"] * W, m["y"] * H, m["x"] * W + w_, m["y"] * H + w_ * ih / iw),
                          filename=m["path"], overlay=True)


def apply_marks(doc, marks) -> int:
    """Vẽ marks lên doc; mark có all=True áp mọi trang, ngược lại theo `page`. Trả số mark đã vẽ."""
    font, n = find_font(), 0
    for i, page in enumerate(doc):
        for m in marks:
            if m.get("all") or m.get("page") == i:
                _draw_mark(page, m, font)
                n += 1
    return n


def _ask_markup(files):
    from ..viewer import ask_markup

    return ask_markup(files[0])


@action("edit.markup", "edit", "Markup", "Vẽ tay, hình, khung, chữ/watermark, ảnh/chữ ký, ghi chú lên PDF hoặc ảnh",
        kinds=PI, ask=_ask_markup)
def markup(files, p):
    """params.marks (toạ độ 0..1 theo trang; all=True: mọi trang; nhiều file: áp dụng cho từng file):
    ink{pts,color,w} · note{x,y,text} · text{x,y,text,size,color,rot} · image{x,y,w,path} ·
    shape{kind:rect|ellipse|line|arrow,x0,y0,x1,y1,color,w,fill} · border{color,w,margin}."""
    marks = p.get("marks", [])
    if not marks:
        raise ValueError("Chưa thêm gì để vẽ")
    outs = []
    for f in files:
        if kind_of(f) == "pdf":
            doc = open_pdf(f)
            apply_marks(doc, marks)
            outs.append(save_pdf(doc, out_path(f, "marked")))
            continue
        out = out_path(f, "marked")  # ảnh: dựng tạm thành PDF 1 trang (1 px = 0,75 pt) rồi dựng lại ở 96 dpi = đúng kích thước gốc
        with tmpdir() as td:
            doc = pymupdf.open(str(images_to_pdf([f], td / "i.pdf")))
            apply_marks(doc, marks)
            pix = doc[0].get_pixmap(dpi=96, alpha=False)
            doc.close()
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        im.save(out, quality=92) if out.suffix.lower() in (".jpg", ".jpeg") else im.save(out)
        outs.append(out)
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


def save_img(im, out):
    """Lưu theo đuôi file; JPEG/BMP không có alpha nên đè lên nền trắng."""
    out = Path(out)
    jpg = out.suffix.lower() in (".jpg", ".jpeg")
    if (jpg or out.suffix.lower() == ".bmp") and im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    elif im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")
    im.save(out, **({"quality": 95} if jpg or out.suffix.lower() == ".webp" else {}))
    return out


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
            box = (round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height))
            outs.append(save_img(im.crop(box), out))
    return outs
