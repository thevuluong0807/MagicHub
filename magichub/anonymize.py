"""Ẩn danh hoá văn bản (docx/xlsx/pptx/txt/md) có đảo ngược: thay tên người, đơn vị, mã dự án, email... bằng mã [PERSON_1], [ORG_2]…
Bảng mapping (xlsx) giữ giá trị gốc để Restore. Không import Qt. Chỉ dò + thay trên chữ; ảnh/biểu đồ không được xử lý (xem `leak_report`)."""
from __future__ import annotations

import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
# (regex tên part, thẻ đoạn, thẻ chữ)
PARTS = [
    (re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"), f"{{{W}}}p", f"{{{W}}}t"),
    (re.compile(r"^ppt/(slides|notesSlides)/[^/]+\.xml$"), f"{{{A}}}p", f"{{{A}}}t"),
    (re.compile(r"^xl/sharedStrings\.xml$"), f"{{{S}}}si", f"{{{S}}}t"),
    (re.compile(r"^xl/worksheets/[^/]+\.xml$"), f"{{{S}}}is", f"{{{S}}}t"),  # chuỗi inline
]
OOXML = {"docx", "xlsx", "pptx"}
TEXT = {"txt", "md"}
SUPPORTED = OOXML | TEXT
PROPS = {"docProps/core.xml": ("creator", "lastModifiedBy"), "docProps/app.xml": ("Company", "Manager")}

PREFIX = {"PERSON": "PERSON", "ORG": "ORG", "PROJECT": "PROJECT", "EMAIL": "EMAIL", "PHONE": "PHONE", "URL": "URL", "ID": "ID",
          "IP": "IP", "TERM": "TERM", "CUSTOM": "TERM"}
KIND_LABEL = {"PERSON": "Người", "ORG": "Đơn vị", "PROJECT": "Mã dự án", "EMAIL": "Email", "PHONE": "SĐT", "URL": "URL", "ID": "Số định danh",
              "IP": "IP", "TERM": "Cụm lặp", "CUSTOM": "Tự thêm"}

UP = "A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
SURNAMES = set("""Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý Đào Đinh Lương Trịnh Đoàn Mai Tô Hà Lâm Châu Phùng Tạ Cao Quách
Thái Triệu Tăng Lại Kiều Chu Từ Văn Diệp Giang La Mạc Ông Kim""".split()) - {"Văn", "Ông", "Kim"}
TITLES = r"(?:Ông|Bà|Anh|Chị|Cô|Chú|Bác|Thầy|Đ/c|Đồng chí|TS\.?|PGS\.?|GS\.?|ThS\.?|KS\.?|CN\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)"
ORG_KW = ("Tổng công ty|Công ty|Tập đoàn|Ngân hàng|Học viện|Trường|Viện|Trung tâm|Ủy ban|Uỷ ban|Hiệp hội|Bộ|Sở|Cục|Vụ|Ban|Phòng|Hội|Đoàn|Quân đoàn|Sư đoàn|Trung đoàn|"
          "Bệnh viện|Đài|Báo|Nhà máy|Xí nghiệp|Chi nhánh|Văn phòng")
ACRONYM_SKIP = set("""API PDF SQL HTML CSS URL ID IP UI UX GPS USB HTTP HTTPS JSON XML CPU GPU RAM OK TCP UDP DNS VPN LAN WAN PC OS PNG JPG JPEG GIF TXT DOC DOCX XLS XLSX
PPT PPTX CSV AI ML SMS PIN QR ATM AES RSA SSL TLS SSH FTP MAC LED LCD HD FHD UHD AM PM TV VN USD VND EUR NA N/A""".split())

RX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RX_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')\]]+", re.I)
RX_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RX_PHONE = re.compile(r"(?<![\w.])(?:\+84|0084|0)[\s.-]?\d(?:[\s.-]?\d){8,9}(?!\w)(?!\.\d)")
RX_ID = re.compile(r"(?<![\w.])\d{9}(?:\d{3})?(?!\w)(?!\.\d)")  # CCCD 12 số / CMND 9 số
RX_CODE = re.compile(rf"(?<![\w-])(?:\d+\.)?[{UP}]{{2,}}\d*(?:[-_/.][{UP}0-9]+)+(?![\w-])")  # BVL-2026-01, 11.BVL-HS, VT/2026/05
RX_ORG = re.compile(rf"\b(?:{ORG_KW})(?:\s+(?:[{UP}][\w&'’-]*|của|và|&|TNHH|CP|MTV))+(?:\s+\d+)?")
RX_TITLED = re.compile(rf"\b{TITLES}\s+((?:[{UP}][^\W\d_]*)(?:\s+[{UP}][^\W\d_]*){{0,3}})")
RX_WORD = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*")
RX_ACRONYM = re.compile(rf"(?<![\w-])[{UP}]{{3,8}}(?![\w-])")


@dataclass
class Candidate:
    value: str
    kind: str
    count: int
    checked: bool
    alias_of: str | None = None  # dạng gọi tắt của một mục khác: dùng cùng họ mã ([ORG_1s] cho [ORG_1])


# ---------- Trích chữ ----------
def _own(t, p_tag):
    """Thẻ chữ t thuộc đoạn p gần nhất của nó (đoạn lồng trong text box được xử lý riêng)."""
    a = t.getparent()
    while a is not None and a.tag != p_tag:
        a = a.getparent()
    return a


def _paragraphs(root, p_tag, t_tag):
    """[(đoạn, [thẻ chữ của đúng đoạn đó])]."""
    out = []
    for p in root.iter(p_tag):
        ts = [t for t in p.iter(t_tag) if _own(t, p_tag) is p]
        if ts:
            out.append((p, ts))
    return out


def _parts_of(zf: zipfile.ZipFile):
    for name in zf.namelist():
        for rx, p_tag, t_tag in PARTS:
            if rx.match(name):
                yield name, p_tag, t_tag


def read_text(path: Path) -> list[str]:
    """Các đoạn chữ của file (mỗi đoạn một chuỗi)."""
    path = Path(path)
    if path.suffix.lower().lstrip(".") in TEXT:
        return path.read_text("utf-8", errors="replace").splitlines()
    out = []
    with zipfile.ZipFile(path) as zf:
        for name, p_tag, t_tag in _parts_of(zf):
            root = etree.fromstring(zf.read(name))
            out += ["".join(t.text or "" for t in ts) for _, ts in _paragraphs(root, p_tag, t_tag)]
    return out


# ---------- Dò ----------
def detect(paragraphs: list[str]) -> list[Candidate]:
    """Gợi ý các giá trị nên mã hoá; `checked` = mặc định chọn. Người dùng xem lại trước khi áp dụng."""
    text = "\n".join(paragraphs)
    found: dict[str, tuple[str, bool]] = {}
    alias: dict[str, str] = {}

    def add(value, kind, checked):
        value = value.strip(" \t.,;:")
        if len(value) < 2 or value in found:
            return
        found[value] = (kind, checked)

    for rx, kind in ((RX_EMAIL, "EMAIL"), (RX_URL, "URL"), (RX_IP, "IP"), (RX_PHONE, "PHONE"), (RX_ID, "ID"), (RX_CODE, "PROJECT")):
        for m in rx.finditer(text):
            add(m.group(0), kind, True)
    for m in RX_ORG.finditer(text):
        add(m.group(0), "ORG", True)
        core = re.sub(rf"^(?:{ORG_KW})\s+(?:(?:TNHH|CP|MTV)\s+)*|\s+(?:TNHH|CP|MTV)\b|\s+\d+$", "", m.group(0)).strip()  # dạng gọi tắt: "Tập đoàn Viettel" -> "Viettel"
        if core != m.group(0) and len(core) >= 3 and core[0].isupper():
            add(core, "ORG", True)
            alias.setdefault(core, m.group(0).strip(" \t.,;:"))
    for m in RX_TITLED.finditer(text):
        add(m.group(1), "PERSON", True)

    # cụm từ viết hoa liên tiếp (2-5 từ); họ phổ biến đứng đầu => người
    for line in paragraphs:
        words = list(RX_WORD.finditer(line))
        i = 0
        while i < len(words):
            if not (words[i].group(0)[0].isupper() and not words[i].group(0).isupper()):
                i += 1
                continue
            j = i
            while (j + 1 < len(words) and words[j + 1].group(0)[0].isupper() and not words[j + 1].group(0).isupper()
                   and line[words[j].end():words[j + 1].start()] == " "):
                j += 1
            n = j - i + 1
            if 2 <= n <= 5:
                phrase = line[words[i].start():words[j].end()]
                first = words[i].group(0)
                if first in SURNAMES and 2 <= n <= 4:
                    add(phrase, "PERSON", True)
                else:
                    add(phrase, "TERM", False)  # chốt `checked` theo số lần ở dưới
            i = j + 1

    ftext = fold_map(text)[0]  # đếm không phân biệt hoa thường/dấu để gộp "Viettel", "VIETTEL", "viettel"

    def n_of(v):
        rx = _fold_rx([fold_key(v)]) if fold_key(v) else None
        return len(rx.findall(ftext)) if rx else 0

    # viết tắt in hoa lặp lại (tên đơn vị/dự án viết tắt): chỉ lấy khi ≥ 3 lần
    keys = {fold_key(v) for v in found}
    for m in RX_ACRONYM.finditer(text):
        a = m.group(0)
        if a not in ACRONYM_SKIP and fold_key(a) not in keys and n_of(a) >= 3:
            found[a] = ("TERM", False)
            keys.add(fold_key(a))
    groups: dict[str, list] = {}
    for v, (kind, checked) in found.items():
        groups.setdefault(fold_key(v), []).append((v, kind, checked))
    order = {k: i for i, k in enumerate(["PROJECT", "ORG", "PERSON", "EMAIL", "PHONE", "ID", "URL", "IP", "TERM"])}
    out = []
    for key, items in groups.items():
        rep = max(items, key=lambda it: text.count(it[0]))[0]  # dạng hay gặp nhất làm giá trị chuẩn
        kind = min((it[1] for it in items), key=lambda k: order.get(k, 99))
        checked = any(it[2] for it in items)
        n = n_of(rep)
        if n == 0:
            continue
        if kind == "TERM":
            if n < 2:
                continue
            checked = checked or (n >= 3 and " " in rep)
        parent = next((alias[it[0]] for it in items if it[0] in alias), None)
        out.append(Candidate(rep, kind, n, checked, parent))
    # bỏ cụm con của một cụm đã dò cùng số lần (vd "Chí Minh" trong "Hồ Chí Minh")
    out = [c for c in out if not any(fold_key(c.value) != fold_key(o.value) and fold_key(c.value) in fold_key(o.value) and o.count >= c.count
                                     for o in out if c.kind == "TERM")]
    return sorted(out, key=lambda c: (order.get(c.kind, 99), -c.count, c.value))


# ---------- Mã ----------
def assign_tokens(entries: list[tuple]) -> dict[str, str]:
    """[(giá trị, loại[, mục gốc])] -> {giá trị: '[ORG_1]'}; đánh số theo thứ tự trong danh sách, mỗi loại một bộ đếm.
    Mục có "mục gốc" (dạng gọi tắt) dùng cùng họ mã: [ORG_1s], [ORG_1s2]… nên người đọc/AI thấy cùng một thực thể; Restore vẫn đúng từng dạng."""
    n: Counter = Counter()
    out: dict[str, str] = {}
    later = []
    for e in entries:
        value, kind, parent = (tuple(e) + (None,))[:3]
        if value in out or not value.strip():
            continue
        if parent:
            later.append((value, parent))
            continue
        pre = PREFIX.get(kind, "TERM")
        n[pre] += 1
        out[value] = f"[{pre}_{n[pre]}]"
    k: Counter = Counter()
    for value, parent in later:
        if value in out:
            continue
        if parent in out:
            k[parent] += 1
            out[value] = f"{out[parent][:-1]}s{'' if k[parent] == 1 else k[parent]}]"
        else:  # mục gốc không được chọn: coi như mục độc lập
            kind = next((e[1] for e in entries if e[0] == value), "TERM")
            pre = PREFIX.get(kind, "TERM")
            n[pre] += 1
            out[value] = f"[{pre}_{n[pre]}]"
    return out


_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2212"
_SPACES = "\u00a0\u2007\u202f\t"


def _fold_char(c: str) -> str:
    if c in _SPACES:
        return " "
    if c in _DASHES:
        return "-"
    d = "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))
    return d.replace("đ", "d").replace("Đ", "d").lower()


def fold_map(s: str) -> tuple[str, list[int]]:
    """Chuỗi đã gấp (không dấu, không phân biệt hoa thường, nbsp/gạch nối lạ -> thường) + chỉ số gốc của từng ký tự gấp."""
    out, origin = [], []
    for i, c in enumerate(s):
        for ch in _fold_char(c):
            out.append(ch)
            origin.append(i)
    return "".join(out), origin


def fold_key(v: str) -> str:
    return " ".join(fold_map(v)[0].split())


def _fold_rx(keys):
    parts = []
    for k in sorted(keys, key=len, reverse=True):  # dài trước để "Tập đoàn Viettel" thắng "Viettel"
        a = r"(?<!\w)" if re.match(r"\w", k[0]) else ""
        b = r"(?!\w)" if re.match(r"\w", k[-1]) else ""
        parts.append(a + r"\s+".join(re.escape(w) for w in k.split(" ")) + b)
    return re.compile("|".join(parts)) if parts else None


class Mapper:
    """Mã hoá: khớp KHÔNG phân biệt hoa thường/dấu/khoảng trắng/gạch nối. Mỗi dạng chữ khác dạng chuẩn (VIETTEL, viettel, "Viet tel"…)
    nhận mã biến thể [ORG_1v1] để Restore trả đúng nguyên văn từng chỗ."""

    def __init__(self, entries: list[tuple]):
        self.base = assign_tokens(entries)  # giá trị chuẩn -> mã
        self.kinds = {e[0]: e[1] for e in entries if e[0] in self.base}
        self.by_key = {fold_key(v): v for v in self.base}
        self.rx = _fold_rx(list(self.by_key))
        self.table = dict(self.base)  # dạng chữ thực tế -> mã (gồm biến thể)
        self.variant_of: dict[str, str] = {}  # biến thể -> giá trị chuẩn
        self.n: Counter = Counter()
        self.hits: Counter = Counter()

    def find(self, text: str, create: bool = True, count: bool = True):
        if not self.rx:
            return []
        folded, origin = fold_map(text)
        out = []
        for m in self.rx.finditer(folded):
            if m.end() <= m.start():
                continue
            s, e = origin[m.start()], origin[m.end() - 1] + 1
            surface = text[s:e]
            canon = self.by_key[" ".join(m.group(0).split())]
            tok = self.table.get(surface)
            if tok is None:
                if not create:
                    tok = self.base[canon]
                else:
                    base = self.base[canon]
                    self.n[base] += 1
                    tok = f"{base[:-1]}v{self.n[base]}]"
                    self.table[surface], self.variant_of[surface] = tok, canon
            if count:
                self.hits[surface] += 1
            out.append((s, e, tok))
        return out

    def rows(self):
        """[(mã, giá trị gốc, loại, số lần)] gồm cả biến thể."""
        return [(tok, v, self.kinds.get(self.variant_of.get(v, v), "TERM"), self.hits.get(v, 0)) for v, tok in self.table.items()]


def restore_finder(mapping: dict[str, str]):
    rev = {t.strip("[]").upper(): v for v, t in mapping.items()}
    rx = _token_rx(list(mapping.values()))
    return lambda s: [(m.start(), m.end(), rev[m.group(1).upper()]) for m in rx.finditer(s)] if rx else []


def _token_rx(tokens):
    """Khớp token có hoặc không có ngoặc vuông (AI hay bỏ ngoặc), không phân biệt hoa thường."""
    parts = sorted((re.escape(t.strip("[]")) for t in tokens), key=len, reverse=True)
    return re.compile(r"\[?(?<![\w])(" + "|".join(parts) + r")(?!\w)\]?", re.I) if parts else None


def _rewrite(ts, find) -> int:
    """Thay trong chuỗi ghép từ các run `ts` (thẻ chữ), giữ định dạng: chữ thay nằm ở run chứa ký tự đầu của vùng khớp."""
    texts = [t.text or "" for t in ts]
    full = "".join(texts)
    hits = find(full)
    if not hits:
        return 0
    cells, owner = [], []
    for i, s in enumerate(texts):
        cells += list(s)
        owner += [i] * len(s)
    for s, e, rep in hits:
        cells[s] = rep
        for k in range(s + 1, e):
            cells[k] = ""
    new = ["" for _ in texts]
    for ch, i in zip(cells, owner):
        new[i] += ch
    for t, s in zip(ts, new):
        if s != (t.text or ""):
            t.text = s
            if s != s.strip():
                t.set(XML_SPACE, "preserve")
    return len(hits)


def _scrub_props(name: str, data: bytes) -> bytes:
    root = etree.fromstring(data)
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname in PROPS[name]:
            el.text = ""
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def transform(src: Path, out: Path, find, scrub: bool = False, restore: bool = False) -> int:
    """Áp `find(text) -> [(start, end, thay)]` (Mapper.find hoặc restore_finder) lên src -> out; trả số lần thay."""
    src, out = Path(src), Path(out)
    n = 0
    if src.suffix.lower().lstrip(".") in TEXT:
        lines = src.read_text("utf-8", errors="replace").split("\n")
        res = []
        for line in lines:
            hits = find(line)
            n += len(hits)
            for s, e, rep in reversed(hits):
                line = line[:s] + rep + line[e:]
            res.append(line)
        out.write_text("\n".join(res), "utf-8")
        return n
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        tags = {name: (p, t) for name, p, t in _parts_of(zin)}
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename in tags:
                root = etree.fromstring(data)
                for _, ts in _paragraphs(root, *tags[info.filename]):
                    n += _rewrite(ts, find)
                if info.filename == "word/comments.xml" and not restore:
                    for el in root.iter(f"{{{W}}}comment"):
                        el.set(f"{{{W}}}author", "Author")
                        el.set(f"{{{W}}}initials", "")
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif scrub and info.filename in PROPS:
                data = _scrub_props(info.filename, data)
            zout.writestr(info, data)
    return n


def apply_spans(text: str, hits) -> str:
    for s, e, rep in sorted(hits, reverse=True):
        text = text[:s] + rep + text[e:]
    return text


def anonymize_text(text: str, mapper: Mapper) -> tuple[str, int]:
    hits = mapper.find(text)
    return apply_spans(text, hits), len(hits)


def restore_text(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    hits = restore_finder(mapping)(text)
    return apply_spans(text, hits), len(hits)


# ---------- Bảng mapping (xlsx) ----------
def write_mapping(path: Path, rows: list[tuple], leaks: list[str], source: str):
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mapping"
    ws.append(["Mã", "Giá trị gốc", "Loại", "Số lần thay"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for tok, value, kind, n in rows:
        ws.append([tok, value, KIND_LABEL.get(kind, ""), n])
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 18, 48
    info = wb.create_sheet("Lưu ý")
    for line in (f"Nguồn: {source}", "File này chứa DỮ LIỆU GỐC. Giữ riêng, KHÔNG gửi kèm văn bản đã mã hoá.",
                 "Restore: chọn file đã mã hoá (hoặc bản AI trả về), MagicHub đọc sheet Mapping để trả lại giá trị gốc.",
                 "Mã có hậu tố v1, v2… là cùng một thực thể nhưng viết khác (hoa/thường, dấu, khoảng trắng); Restore trả đúng nguyên văn từng chỗ.", "",
                 "Kiểm tra sau khi mã hoá (mục có thể còn lộ thông tin, cần xem tay):", *(leaks or ["Không phát hiện giá trị gốc còn sót trong chữ của file."])):
        info.append([line])
    info.column_dimensions["A"].width = 110
    wb.save(path)


def read_mapping(path: Path) -> dict[str, str]:
    """-> {giá trị gốc: mã}"""
    import openpyxl

    ws = openpyxl.load_workbook(path, read_only=True)["Mapping"]
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] and row[1] is not None:
            out[str(row[1])] = str(row[0])
    if not out:
        raise ValueError(f"{Path(path).name}: bảng mapping trống")
    return out


def leak_report(out: Path, mapper: Mapper) -> list[str]:
    """Giá trị gốc còn xuất hiện ở đâu trong file kết quả (kể cả phần không xử lý như tên sheet, biểu đồ) + số ảnh chưa kiểm."""
    out = Path(out)
    res = []
    if out.suffix.lower().lstrip(".") in TEXT:
        return res
    with zipfile.ZipFile(out) as zf:
        media = 0
        for name in zf.namelist():
            if "/media/" in name:
                media += 1
            if name.endswith((".xml", ".rels")):
                text = re.sub(r"<[^>]+>", "", zf.read(name).decode("utf-8", "replace"))
                hits = sorted({text[a:b] for a, b, _ in mapper.find(text, create=False, count=False)})
                if hits:
                    res.append(f"{name}: còn {', '.join(hits[:5])}" + (" …" if len(hits) > 5 else ""))
        if media:
            res.append(f"{media} ảnh/đối tượng nhúng chưa được kiểm tra: xem tay xem có chứa tên/đơn vị không")
    return res
