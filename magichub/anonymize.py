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

from .techterms import TECH_TERMS

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
META_PARTS = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")  # tiêu đề/chủ đề/từ khoá… cũng chứa tên; trường TITLE/SUBJECT ở bìa đọc lại từ đây khi cập nhật
PROPS = {"docProps/core.xml": ("creator", "lastModifiedBy"), "docProps/app.xml": ("Company", "Manager")}

PREFIX = {"PERSON": "PERSON", "ORG": "ORG", "PLACE": "PLACE", "TECH": "TECH", "IDENT": "IDENT", "SAFE": "SAFE", "PROJECT": "PROJECT", "EMAIL": "EMAIL", "PHONE": "PHONE", "URL": "URL", "ID": "ID",
          "IP": "IP", "TERM": "TERM", "CUSTOM": "TERM"}
KIND_LABEL = {"PERSON": "Người", "ORG": "Tổ chức", "PLACE": "Địa danh", "PROJECT": "Mã", "TECH": "Thuật ngữ", "IDENT": "Biến/định danh", "SAFE": "Bỏ qua", "EMAIL": "Email", "PHONE": "SĐT", "URL": "URL", "ID": "Số định danh",
              "IP": "IP", "TERM": "Cụm lặp", "CUSTOM": "Tự thêm"}

UP = "A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
SURNAMES = set("""Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý Đào Đinh Lương Trịnh Đoàn Mai Tô Hà Lâm Châu Phùng Tạ Cao Quách
Thái Triệu Tăng Lại Kiều Chu Từ Văn Diệp Giang La Mạc Ông Kim""".split()) - {"Văn", "Ông", "Kim"}
TITLES = r"(?:Ông|Bà|Anh|Chị|Cô|Chú|Bác|Thầy|Đ/c|Đồng chí|TS\.?|PGS\.?|GS\.?|ThS\.?|KS\.?|CN\.?|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)"
ORG_WORDS = ("công nghiệp|công nghệ|cao|viễn thông|quân đội|thương mại|dịch vụ|sản xuất|xây dựng|đầu tư|phát triển|kỹ thuật|trách nhiệm hữu hạn|một thành viên|"
             "tác chiến|điện tử|tham mưu|hậu cần|chính trị|quân sự|tình báo|trinh sát|phòng không|không quân|hải quân|pháo binh|công binh|tên lửa|cơ yếu|"
             "tài chính|kế hoạch|nghiên cứu|hành chính|nhân sự|đối ngoại|khoa học công nghệ|"
             "nông nghiệp|nông thôn|giáo dục|đào tạo|y tế|vận tải|thông tin|truyền thông|điện lực|năng lượng|khoa học|quốc gia|quốc tế|việt nam")
ORG_KW = ("Tổng công ty|Công ty|Tập đoàn|Ngân hàng|Học viện|Trường|Viện|Trung tâm|Ủy ban|Uỷ ban|Hiệp hội|Bộ|Sở|Cục|Vụ|Ban|Phòng|Hội|Đoàn|Quân đoàn|Sư đoàn|Trung đoàn|"
          "Bệnh viện|Đài|Báo|Nhà máy|Xí nghiệp|Chi nhánh|Văn phòng")
# Từ nhãn/biểu mẫu/giao diện: cụm chỉ gồm các từ này là tiêu đề, không phải tên riêng ("Ngày soạn", "Người duyệt", "Hệ thống")
FORM_WORDS = set("""ngày tháng năm soạn duyệt kiểm tra người họ tên chức vụ đơn vị ghi chú mục đích kết quả mô tả yêu cầu chức năng hệ thống giao diện màn hình
hình bảng trang phần chương điều khoản số tờ stt nội dung thông tin dữ liệu danh sách quản lý dùng tài khoản mật khẩu đăng nhập xuất thời gian địa chỉ điện thoại phiên
bản tài liệu hướng dẫn sử dụng cài đặt cấu hình báo cáo thống kê tìm kiếm thêm sửa xóa xoá lưu hủy huỷ đồng ý xác nhận từ chối bước tiếp theo trước sau tổng cộng loại
trạng thái mã giá trị lỗi cảnh báo thông báo kết thúc bắt đầu hiện tại mới cũ chung riêng chính phụ vai trò quyền hạn lịch sử nhật ký tình huống mục tiêu phạm vi áp dụng
thuật ngữ viết tắt định nghĩa tham chiếu phụ lục tóm tắt giới thiệu tổng quan kiến trúc thiết kế kỹ thuật vận hành bảo trì khắc phục sự cố quy trình thao tác
chỉnh duyệt phê trình ký nhận gửi nơi người lập chủ biên đầu cuối trái phải trên dưới""".split())
PLACES = {s.lower() for s in """Hà Nội|Hải Phòng|Đà Nẵng|Cần Thơ|Huế|Hà Giang|Cao Bằng|Bắc Kạn|Tuyên Quang|Lào Cai|Điện Biên|Lai Châu|Sơn La|Yên Bái|Hoà Bình|Hòa Bình|Thái Nguyên|Lạng Sơn|Quảng Ninh|Bắc Giang|Phú Thọ|Vĩnh Phúc|Bắc Ninh|Hải Dương|Hưng Yên|Thái Bình|Hà Nam|Nam Định|Ninh Bình|Thanh Hoá|Thanh Hóa|Nghệ An|Hà Tĩnh|Quảng Bình|Quảng Trị|Thừa Thiên Huế|Quảng Nam|Quảng Ngãi|Bình Định|Phú Yên|Khánh Hoà|Khánh Hòa|Ninh Thuận|Bình Thuận|Kon Tum|Gia Lai|Đắk Lắk|Đắk Nông|Lâm Đồng|Bình Phước|Tây Ninh|Bình Dương|Đồng Nai|Bà Rịa Vũng Tàu|Long An|Tiền Giang|Bến Tre|Trà Vinh|Vĩnh Long|Đồng Tháp|An Giang|Kiên Giang|Hậu Giang|Sóc Trăng|Bạc Liêu|Cà Mau|Việt Nam|Nha Trang|Vũng Tàu|Biên Hoà|Biên Hòa|Phú Quốc""".split("|")}
ACRONYM_SKIP = set("""API PDF SQL HTML CSS URL ID IP UI UX GPS USB HTTP HTTPS JSON XML CPU GPU RAM OK TCP UDP DNS VPN LAN WAN PC OS PNG JPG JPEG GIF TXT DOC DOCX XLS XLSX
PPT PPTX CSV AI ML SMS PIN QR ATM AES RSA SSL TLS SSH FTP MAC LED LCD HD FHD UHD AM PM TV VN USD VND EUR NA N/A""".split())

RX_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RX_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')\]]+", re.I)
RX_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RX_PHONE = re.compile(r"(?<![\w.])(?:\+84|0084|0)[ .-]?\d(?:[ .-]?\d){8,9}(?!\w)(?!\.\d)")
RX_ID = re.compile(r"(?<![\w.])\d{9}(?:\d{3})?(?!\w)(?!\.\d)")  # CCCD 12 số / CMND 9 số
RX_CODE = re.compile(rf"(?<![\w-])(?:\d+\.)?[{UP}][{UP}\d]+(?:[-/.][{UP}\d]+)+(?![\w-])")  # BVL-2026-01, BV3C-01, 11.BVL-HS, VT/2026/05 (gạch dưới = định danh/biến)
SP = r"[ \t\u00a0]+"  # cùng một dòng: tên không vắt qua đoạn/ô bảng khác
RX_ORG = re.compile(rf"(?<!\w)(?=[{UP}])(?i:{ORG_KW})(?:{SP}(?:(?i:cổ{SP}phần)|(?i:{ORG_WORDS})(?![\w-])|(?i:và|của)(?={SP}(?:(?i:{ORG_WORDS})|[{UP}]\w*{SP}(?i:{ORG_WORDS}))(?![\w-]))|[{UP}][\w&'’-]*|&|[-–]|TNHH|CP|MTV))+(?:{SP}\d+)?")
RX_INITIALS = re.compile(rf"(?<![\w.])(?:[{UP}]\.[ \t]?){{2,3}}[{UP}][^\W\d_]+")  # D.M.Tùng, N.V. Trường (khung tên ở footer): ≥ 2 chữ cái đầu, tránh "P. Tổng"
RX_TITLED = re.compile(rf"\b{TITLES}{SP}((?:[{UP}][^\W\d_]*)(?:{SP}[{UP}][^\W\d_]*){{0,3}})")
RX_IDENT = re.compile(r"(?<![\w.])(?:[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+|(?:[A-Z][a-z0-9]+){2,})(?![\w])")  # FFT_WINDOW_FLAT, getUserName, UserName
RX_DEFINED = re.compile(rf"(?<![\w-])([{UP}]{{2,8}})[ \t]*\(([A-Za-z][A-Za-z \-/]{{4,80}})\)")  # TDOA (Time Difference of Arrival)
RX_WORD = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*")
RX_ACRONYM = re.compile(rf"(?<![\w-])[{UP}][{UP}\d]{{2,9}}(?![\w-])")  # BVL, MHTH, BV3C, B2B (có thể kèm số)


# độ dài tối thiểu (ký tự) để một giá trị đủ ngữ nghĩa theo loại: mã/viết tắt ngắn như "BVL" vẫn hợp lệ, cụm chữ thường phải dài hơn
MIN_LEN = {"TECH": 3, "IDENT": 5, "EMAIL": 6, "URL": 8, "IP": 7, "PHONE": 9, "ID": 9, "PROJECT": 3, "ORG": 3, "PERSON": 5, "PLACE": 4, "TERM": 6}


def _is_ip(v: str) -> bool:
    o = [int(x) for x in v.split(".")]
    return all(x <= 255 for x in o) and (o[0] in (10, 127, 172, 192) or o[0] >= 100) and not any(len(x) > 1 and x[0] == "0" for x in v.split("."))


_VOW = "aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ"
RX_SYLLABLE = re.compile(rf"(?:ngh|ng|nh|ph|th|tr|ch|gh|gi|kh|qu|[bcdđghklmnpqrstvx])?[{_VOW}]+(?:ch|ng|nh|[cmnpt])?")


def is_vn_syllable(word: str) -> bool:
    """Một âm tiết tiếng Việt hợp lệ (CAO, BAY, CHÍ, DIỄN…): không phải viết tắt. BVL, MHTH, UAV, GNSS không khớp (không nguyên âm / vần cuối lạ)."""
    return RX_SYLLABLE.fullmatch(word.lower()) is not None


ORG_ENDERS = {"cao", "quân đội", "viễn thông", "việt nam", "quốc gia", "quốc tế", "y tế", "giáo dục", "thông tin", "truyền thông", "điện lực", "năng lượng",
              "nông nghiệp", "nông thôn", "công nghệ cao", "tác chiến", "điện tử", "tham mưu", "hậu cần", "chính trị", "quân sự", "tình báo", "trinh sát",
              "phòng không", "không quân", "hải quân", "pháo binh", "công binh", "tên lửa", "cơ yếu", "tài chính", "kế hoạch", "nghiên cứu", "hành chính",
              "nhân sự", "đối ngoại", "công nghệ"}
_KW_FIRST = {k.split()[0].lower() for k in ORG_KW.split("|")}
_RX_KW = re.compile(rf"(?<!\w)(?i:{ORG_KW})(?!\w)")


def clean_org(text: str) -> str:
    """Cắt tên tổ chức dò được: dừng trước từ khoá tổ chức thứ hai ("… Viettel – Chi nhánh"), bỏ nối dở, từ nhãn và đuôi chữ thường thông dụng ở cuối."""
    first = _RX_KW.match(text)
    if first:
        nxt = _RX_KW.search(text, first.end())
        if nxt:
            text = text[:nxt.start()]
    toks = re.split(SP, text.strip())
    while len(toks) > 1:
        last = toks[-1].lower()
        two = " ".join(toks[-2:]).lower()
        if last in ("-", "–", "&", "và", "của") or last in FORM_WORDS or last in _KW_FIRST:
            toks.pop()
        elif toks[-1][0].islower() and last not in ORG_ENDERS and two not in ORG_ENDERS:
            toks.pop()  # "… Quân đội sản xuất": đuôi thường không phải tên
        else:
            break
    return " ".join(toks)


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


def _open_zip(path, *args) -> zipfile.ZipFile:
    """ZipFile, nhưng báo lỗi dễ hiểu khi đuôi .docx/.xlsx/.pptx mà ruột không phải file Office mới (hay gặp: .doc đổi đuôi, file khoá ~$, file rỗng)."""
    try:
        return zipfile.ZipFile(path, *args)
    except zipfile.BadZipFile:
        head = Path(path).read_bytes()[:8] if args == () else b""
        why = (
            "là file Office cũ (.doc/.xls/.ppt) đổi đuôi, hoặc file đặt mật khẩu mở - dùng Unlock (nhập mật khẩu) để gỡ trước, hoặc mở bằng Word/Excel rồi 'Lưu thành' .docx/.xlsx/.pptx"
            if head.startswith(b"\xd0\xcf\x11\xe0")
            else "rỗng hoặc là file khoá tạm (~$...) - Word đang mở file?" if len(head) < 4 or Path(path).name.startswith("~$")
            else "không phải file Office hợp lệ (có thể bị hỏng hoặc đổi đuôi)"
        )
        raise ValueError(f"'{Path(path).name}' {why}") from None


def read_text(path: Path, progress=None) -> list[str]:
    """Các đoạn chữ của file (mỗi đoạn một chuỗi). `progress(frac)`: tiến độ đọc các phần của file."""
    path = Path(path)
    if path.suffix.lower().lstrip(".") in TEXT:
        return path.read_text("utf-8", errors="replace").splitlines()
    out = []
    with _open_zip(path) as zf:
        parts = list(_parts_of(zf))
        for i, (name, p_tag, t_tag) in enumerate(parts):
            if progress:
                progress(i / len(parts))
            root = etree.fromstring(zf.read(name))
            out += ["".join(t.text or "" for t in ts) for _, ts in _paragraphs(root, p_tag, t_tag)]
    return out


# ---------- Dò ----------
_SMALL = {"of", "and", "the", "for", "to", "in", "on", "a", "an", "with", "by"}


def _initials_match(acro: str, expansion: str) -> bool:
    words = re.findall(r"[A-Za-z]+", expansion)
    a = acro.upper()
    return a == "".join(w[0].upper() for w in words) or a == "".join(w[0].upper() for w in words if w.lower() not in _SMALL)


def load_safe() -> set[str]:
    """Khoá (đã gấp) của mọi cụm 'SAFE: …' trong các từ điển mã hoá: không bao giờ dò hay mã hoá."""
    from . import config

    out = set()
    for lines in config.load().get("anonymize_dicts", {}).values():
        for line in lines:
            kind, value = parse_dict_line(line)
            if kind == "SAFE":
                out.add(fold_key(value))
    return out


def detect(paragraphs: list[str], safe: set[str] | None = None, progress=None) -> list[Candidate]:
    """Gợi ý các giá trị nên mã hoá; `checked` = mặc định chọn. Người dùng xem lại trước khi áp dụng.
    `progress(frac)`: báo tiến độ 0..1 (có thể ném ngoại lệ để huỷ). `safe`: khoá gấp của các cụm luôn bỏ qua (xem load_safe). Loại: Mã (chọn sẵn, gồm viết tắt chưa rõ), Thuật ngữ và Biến/định danh (không chọn sẵn)."""
    safe = safe or set()
    paragraphs = [unicodedata.normalize("NFC", p) for p in paragraphs]  # file Word/PDF hay lẫn dạng tổ hợp: so khớp chữ thường cần cùng dạng
    text = "\n".join(paragraphs)
    found: dict[str, tuple[str, bool]] = {}
    alias: dict[str, str] = {}
    stage = [0]

    def tick():
        stage[0] += 1
        if progress:
            progress(min(1.0, stage[0] / 9))

    def lower_seen(word):
        """Từ in hoa mà dạng thường cũng xuất hiện ("HÌNH" ~ "hình") là chữ tiêu đề, không phải viết tắt.
        Từ có chữ số (BV3C) không phải chữ thường: dạng thường "bv3c.system" là tên bảng/đường dẫn của chính mã đó."""
        if any(ch.isdigit() for ch in word):
            return False
        return re.search(rf"(?<!\w){re.escape(word.lower())}(?!\w)", text) is not None

    def add(value, kind, checked):
        value = value.strip(" \t.,;:")
        if len(value) < MIN_LEN.get(kind, 2) or value in found:
            return
        found[value] = (kind, checked)

    def common(phrase):
        """Cụm thông dụng (không phải tên riêng): từng xuất hiện viết thường trong văn bản ("phạm vi"), hoặc toàn từ nhãn/biểu mẫu ("Ngày soạn")."""
        low = phrase.lower()
        if low != phrase and re.search(rf"(?<!\w){re.escape(low)}(?!\w)", text):
            return True
        words = [w.lower() for w in RX_WORD.findall(phrase)]
        return bool(words) and all(w in FORM_WORDS for w in words)

    for rx, kind in ((RX_EMAIL, "EMAIL"), (RX_URL, "URL"), (RX_IP, "IP"), (RX_PHONE, "PHONE"), (RX_ID, "ID"), (RX_CODE, "PROJECT")):
        for m in rx.finditer(text):
            if kind == "IP" and not _is_ip(m.group(0)):  # số mục "5.8.9.3", phiên bản "1.1.1.4" không phải IP
                continue
            if kind == "PROJECT" and all(lower_seen(w) or is_vn_syllable(w) for w in re.findall(r"[^\W\d_]+", m.group(0))):  # "NGHIỆP-VIỄN": tiêu đề in hoa, không phải mã
                continue
            add(m.group(0), kind, True)
    tick()
    for m in RX_ORG.finditer(text):
        full = clean_org(m.group(0))
        if " " not in full.strip():
            continue
        core = re.sub(rf"^(?i:{ORG_KW}){SP}(?:(?:TNHH|CP|MTV){SP})*|{SP}(?:TNHH|CP|MTV)\b|{SP}\d+$", "", full).strip()  # dạng gọi tắt: "Tập đoàn Viettel" -> "Viettel"
        one_word_common = " " not in core and lower_seen(core)  # "Công ty Công", "Bộ Quốc": tên bị cụt ở một từ thông dụng
        if common(full) or common(core) or one_word_common or all(is_vn_syllable(w) and w.lower() in FORM_WORDS for w in core.split()):
            continue  # "Ban hành", "Phòng ngừa"… viết hoa đầu câu/tiêu đề
        add(full, "ORG", True)
        if core != full and len(core) >= 3 and core[0].isupper() and len(core.split()) <= 3 and not re.fullmatch(rf"(?i:{ORG_WORDS}|\s)+", core):
            add(core, "ORG", True)
            alias.setdefault(core, full.strip(" \t.,;:"))
        tail = core.split()[-1] if core else ""  # "…Công nghệ cao Viettel": tên riêng cuối cụm cũng hay đứng một mình
        if " " in core and len(tail) >= 4 and tail[0].isupper() and tail.isalpha() and not is_vn_syllable(tail) and tail.lower() not in FORM_WORDS and tail not in found:
            add(tail, "ORG", True)
            alias.setdefault(tail, full.strip(" \t.,;:"))
    tick()
    for m in RX_TITLED.finditer(text):
        add(m.group(1), "PERSON", True)
    for m in RX_INITIALS.finditer(text):
        add(m.group(0), "PERSON", True)

    tick()
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
                if phrase.lower() in PLACES:
                    add(phrase, "PLACE", False)  # địa danh: không phải người/tổ chức, mặc định không mã hoá
                elif common(phrase):
                    pass  # nhãn, tiêu đề, cụm thông dụng
                elif first in SURNAMES and 2 <= n <= 4:
                    add(phrase, "PERSON", True)
                else:
                    add(phrase, "TERM", False)  # chốt `checked` theo số lần ở dưới
            i = j + 1

    fm_text = fold_map(text)
    ftext = fm_text[0]  # đếm không phân biệt hoa thường/dấu để gộp "Viettel", "VIETTEL", "viettel"

    def n_of(v):
        rx = _fold_rx([fold_key(v)]) if fold_key(v) else None
        return len(rx.findall(ftext)) if rx else 0

    def n_glued(v):
        """Số lần v xuất hiện dính liền chữ khác ("BVLclient"): cũng là bằng chứng v là một mã."""
        k = fold_key(v)
        if not re.fullmatch(r"[a-z\d]{3,10}", k):
            return 0
        glued = lambda a, b: (a > 0 and (text[a - 1].isalnum() or text[a - 1] == "_")) or (b < len(text) and (text[b].isalnum() or text[b] == "_"))
        return sum(glued(a, b) for a, b, _ in glue_hits(text, re.compile(re.escape(k)), fm=fm_text))

    tick()
    # Tiền tố của mã có gạch nối (BVL trong BVL-GN-CNP) luôn là Mã dù có trong bảng thuật ngữ
    prefixes = set()
    for v, (kind, _) in found.items():
        if kind == "PROJECT":
            m0 = re.match(rf"(?:\d+\.)?([{UP}][{UP}\d]+)", v)
            if m0:
                prefixes.add(fold_key(m0.group(1)))
    # thuật ngữ được định nghĩa bằng tiếng Anh ngay trong văn bản: "TDOA (Time Difference of Arrival)" / "Time Difference of Arrival (TDOA)"
    defined = set()
    for m in RX_DEFINED.finditer(text):
        if _initials_match(m.group(1), m.group(2)):
            defined.add(fold_key(m.group(1)))
    for m in re.finditer(rf"((?:[A-Za-z]+[ \-]){{1,8}}[A-Za-z]+)[ \t]*\(([{UP}]{{2,8}})\)", text):
        if _initials_match(m.group(2), m.group(1)):
            defined.add(fold_key(m.group(2)))
    tick()
    # định danh/biến: FFT_WINDOW_FLAT, getUserName (văn bản thường không viết thế)
    for m in RX_IDENT.finditer(text):
        add(m.group(0), "IDENT", False)
    tick()
    # viết tắt in hoa lặp lại (có thể kèm số như BV3C): chỉ lấy khi ≥ 2 lần. Thuật ngữ công khai -> TECH; còn lại là mã (an toàn hơn: sót mới lộ)
    keys = {fold_key(v) for v in found}
    for m in RX_ACRONYM.finditer(text):
        a = m.group(0)
        if a not in ACRONYM_SKIP and a.lower() not in FORM_WORDS and fold_key(a) not in keys and sum(ch.isalpha() for ch in a) >= 2 and n_of(a) + n_glued(a) >= 2 and not lower_seen(a) and not is_vn_syllable(a):
            tech = fold_key(a) not in prefixes and (a in TECH_TERMS or fold_key(a) in defined)
            found[a] = ("TECH", False) if tech else ("PROJECT", True)
            keys.add(fold_key(a))
    tick()
    groups: dict[str, list] = {}
    for v, (kind, checked) in found.items():
        groups.setdefault(fold_key(v), []).append((v, kind, checked))
    order = {k: i for i, k in enumerate(["PROJECT", "ORG", "PERSON", "EMAIL", "PHONE", "ID", "URL", "IP", "TECH", "IDENT", "PLACE", "TERM"])}
    out = []
    for key, items in groups.items():
        rep = max(items, key=lambda it: text.count(it[0]))[0]  # dạng hay gặp nhất làm giá trị chuẩn
        kind = min((it[1] for it in items), key=lambda k: order.get(k, 99))
        checked = any(it[2] for it in items)
        if key in safe:
            continue
        n = n_of(rep)
        if n == 0:
            continue
        if kind in ("TERM", "PLACE", "IDENT", "TECH") and n < 2:
            continue
        if kind == "TERM":
            checked = False  # cụm viết hoa lặp (nhãn giao diện, tiêu đề…) nhiều khả năng không phải tên: để người dùng tự tick
        parent = next((alias[it[0]] for it in items if it[0] in alias), None)
        out.append(Candidate(rep, kind, n, checked, parent))
    # bỏ cụm con của một cụm đã dò cùng số lần (vd "Chí Minh" trong "Hồ Chí Minh")
    out = [c for c in out if not any(fold_key(c.value) != fold_key(o.value) and fold_key(c.value) in fold_key(o.value) and o.count >= c.count
                                     for o in out if c.kind == "TERM")]
    return sorted(out, key=lambda c: (order.get(c.kind, 99), -c.count, c.value))


# ---------- Từ điển ----------
def parse_dict_line(line: str) -> tuple[str, str]:
    """'ORG: Viettel' -> ('ORG', 'Viettel'); dòng không có tiền tố loại hợp lệ -> ('TERM', dòng)."""
    kind, sep, rest = line.partition(":")
    if sep and kind.strip().upper() in PREFIX and rest.strip():
        return ("TERM" if kind.strip().upper() == "CUSTOM" else kind.strip().upper()), rest.strip()
    return "TERM", line.strip()


def format_dict_line(kind: str, value: str) -> str:
    return f"{kind}: {value.strip()}"


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


def glue_hits(text: str, rx, taken: list[tuple[int, int]] = (), fm=None) -> list[tuple[int, int, str]]:
    """Mã viết hoa dính liền chữ khác: "BVLclient", "BVLClient", "myBVL", "BVL_server" -> (đầu, cuối, khoá gấp). Chỉ nhận khi mã đứng nguyên dạng IN HOA
    và không kéo dài một cụm in hoa/số khác (không khớp "BVLC", "BVL2", "XBVL")."""
    folded, origin = fm or fold_map(text)  # fm: kết quả fold_map(text) tính sẵn (văn bản lớn: gấp lại mỗi lần rất chậm)
    out = []
    for m in rx.finditer(folded):
        a, b = origin[m.start()], origin[m.end() - 1] + 1
        if not text[a:b].isupper() or any(a < te and ts < b for ts, te in taken):
            continue
        left_ok = a == 0 or not (text[a - 1].isupper() or text[a - 1].isdigit())
        nxt = text[b] if b < len(text) else ""
        right_ok = not nxt or nxt == "_" or not nxt.isalnum() or nxt.islower() or (nxt.isupper() and b + 1 < len(text) and text[b + 1].islower())
        if left_ok and right_ok:
            out.append((a, b, m.group(0)))
    return out


class Mapper:
    """Mã hoá: khớp KHÔNG phân biệt hoa thường/dấu/khoảng trắng/gạch nối. Mỗi dạng chữ khác dạng chuẩn (VIETTEL, viettel, "Viet tel"…)
    nhận mã biến thể [ORG_1v1] để Restore trả đúng nguyên văn từng chỗ."""

    def __init__(self, entries: list[tuple]):
        self.base = assign_tokens(entries)  # giá trị chuẩn -> mã
        self.kinds = {e[0]: e[1] for e in entries if e[0] in self.base}
        self.by_key = {fold_key(v): v for v in self.base}
        self.rx = _fold_rx(list(self.by_key))
        glue = [k for k in self.by_key if re.fullmatch(r"[a-z\d]{3,10}", k) and self.kinds.get(self.by_key[k]) == "PROJECT"]  # mã dính liền chữ khác
        self.glue_rx = re.compile("|".join(sorted(map(re.escape, glue), key=len, reverse=True))) if glue else None
        self.table = dict(self.base)  # dạng chữ thực tế -> mã (gồm biến thể)
        self.variant_of: dict[str, str] = {}  # biến thể -> giá trị chuẩn
        self.n: Counter = Counter()
        self.hits: Counter = Counter()

    def find(self, text: str, create: bool = True, count: bool = True):
        if not self.rx:
            return []
        folded, origin = fold_map(text)
        spans = []
        for m in self.rx.finditer(folded):
            if m.end() > m.start():
                spans.append((origin[m.start()], origin[m.end() - 1] + 1, " ".join(m.group(0).split())))
        if self.glue_rx:
            spans += glue_hits(text, self.glue_rx, [(a, b) for a, b, _ in spans])
        out = []
        for s, e, key in sorted(spans):
            surface = text[s:e]
            canon = self.by_key[key]
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
    with _open_zip(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
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
            elif info.filename in META_PARTS:
                root = etree.fromstring(data)
                for el in root.iter():
                    if isinstance(el.tag, str) and el.text and el.text.strip():
                        hits = find(el.text)
                        n += len(hits)
                        el.text = apply_spans(el.text, hits)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                if scrub and info.filename in PROPS:
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


def is_encrypted(path: Path) -> bool:
    """Bảng mapping có mật khẩu mở file (container OLE thay vì zip)."""
    with open(path, "rb") as f:
        return f.read(4) == b"\xd0\xcf\x11\xe0"


def read_mapping(path: Path, password: str | None = None) -> dict[str, str]:
    """-> {giá trị gốc: mã}. Bảng có mật khẩu: cần `password` (sai -> ValueError)."""
    import io

    import openpyxl

    src = path
    if is_encrypted(path):
        if not password:
            raise ValueError(f"{Path(path).name}: bảng mapping có mật khẩu - cần nhập mật khẩu để giải mã")
        import tempfile

        from . import wordlock

        tmp = Path(tempfile.mkdtemp()) / "m.xlsx"
        try:
            wordlock.unlock(Path(path), tmp, password)
            src = io.BytesIO(tmp.read_bytes())
        finally:
            tmp.unlink(missing_ok=True)
            tmp.parent.rmdir()
    ws = openpyxl.load_workbook(src, read_only=True)["Mapping"]
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
