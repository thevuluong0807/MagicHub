"""Ẩn danh hoá / khôi phục văn bản trước khi gửi cho AI hoặc đơn vị ngoài. Logic ở magichub/anonymize.py."""
from __future__ import annotations

from pathlib import Path

from .. import anonymize as an
from .base import action, ext, kind_of, out_path, steps

KINDS = ("txt", "doc", "xls", "ppt")
supported = lambda files: all(ext(f) in an.SUPPORTED for f in files)


def _mapping_path(out: Path) -> Path:
    return out.with_name(f"{out.stem}_mapping.xlsx")


def _ask_anon(files):
    from ..dialogs import ask_anonymize

    paras = [t for f in files for t in an.read_text(f)]
    return ask_anonymize(an.detect(paras, an.load_safe()))


def parse_term(line: str) -> tuple[str, str]:
    """'ORG: Viettel' -> ('Viettel', 'ORG'); dòng không có tiền tố loại hợp lệ -> (dòng, 'CUSTOM')."""
    kind, sep, rest = line.partition(":")
    if sep and kind.strip().upper() in an.PREFIX and rest.strip():
        return rest.strip(), kind.strip().upper()
    return line.strip(), "CUSTOM"


def dictionary_terms(name: str) -> list[tuple[str, str]]:
    from .. import config

    return [parse_term(t) for t in config.load().get("anonymize_dicts", {}).get(name, []) if t.strip()]


def entries_from(p: dict, paragraphs: list[str]) -> list[tuple]:
    """Danh sách (giá trị, loại, mục gốc) từ tham số hộp thoại: mục đã tick (hoặc mặc định theo gợi ý nếu không có), dòng tự thêm, từ điển."""
    if "entries" in p:
        entries = [(e["value"], e["kind"], e.get("alias_of")) for e in p["entries"]]
    else:
        entries = [(c.value, c.kind, c.alias_of) for c in an.detect(paragraphs, an.load_safe()) if c.checked]
    entries += [parse_term(v) for v in p.get("custom", []) if v.strip()]
    if p.get("dictionary"):
        entries += dictionary_terms(p["dictionary"])
    safe = an.load_safe()  # 'SAFE: …' trong mọi từ điển: không bao giờ mã hoá, kể cả khi người dùng tick hoặc nằm trong từ điển khác
    entries = [e for e in entries if e[1] != "SAFE" and an.fold_key(e[0]) not in safe]
    if not entries:
        raise ValueError("Không có gì để mã hoá (chưa chọn mục nào)")
    return entries


@action("edit.anonymize", "edit", "Mã hoá", "Thay tên người, đơn vị, mã dự án, email… bằng mã [PERSON_1], [ORG_2]…; tạo bảng mapping để Restore (docx, xlsx, pptx, txt, md)",
        kinds=KINDS, ask=_ask_anon, check=supported)
def anonymize(files, p):
    """params.entries: [{value, kind}] (bỏ trống = tự chọn theo gợi ý mặc định); params.custom: [dòng tự thêm, tuỳ chọn tiền tố 'ORG: '];
    params.dictionary: tên từ điển luôn áp dụng; params.scrub: xoá metadata tác giả/công ty. Khớp không phân biệt hoa thường/dấu/khoảng trắng."""
    entries = entries_from(p, [t for f in files for t in an.read_text(f)])
    mapper = an.Mapper(entries)
    outs = []
    for f in steps(files):
        out = out_path(f, "anon")
        mapper.hits.clear()
        an.transform(f, out, mapper.find, scrub=p.get("scrub", True))
        an.write_mapping(_mapping_path(out), mapper.rows(), an.leak_report(out, mapper), f.name)
        if p.get("password"):  # không có mật khẩu thì không mở được bảng, nên không giải mã được
            from .. import wordlock

            plain = _mapping_path(out)
            enc = plain.with_name(plain.stem + ".enc")
            wordlock.encrypt(plain, enc, p["password"])
            enc.replace(plain)
        outs += [out, _mapping_path(out)]
    return outs


def _ask_restore(files):
    from ..dialogs import ask_mapping

    for f in files:  # tự tìm bảng mapping cạnh file (x_anon.docx -> x_anon_mapping.xlsx)
        m = _mapping_path(f)
        if not m.exists():
            break
    else:
        res = {"mapping": str(_mapping_path(files[0])), "auto": True}
        if any(an.is_encrypted(_mapping_path(f)) for f in files):
            return _with_password(res)
        return res
    res = ask_mapping()
    return _with_password(res) if res and an.is_encrypted(Path(res["mapping"])) else res


def _with_password(res):
    from ..dialogs import ask_password

    pw = ask_password("Bảng mapping có mật khẩu")
    return {**res, "password": pw} if pw else None


@action("edit.restore", "edit", "Giải mã", "Trả lại tên/đơn vị gốc từ các mã [PERSON_1]… bằng bảng mapping (tự tìm cạnh file, hoặc chọn file mapping)",
        kinds=KINDS, ask=_ask_restore, check=supported)
def restore(files, p):
    outs = []
    for f in steps(files):
        m = Path(p["mapping"])
        if p.get("auto"):
            m = _mapping_path(f)
        if not m.exists():
            raise ValueError(f"{f.name}: không thấy bảng mapping ({m.name})")
        mapping = an.read_mapping(m, p.get("password"))
        out = out_path(f, "restored")
        if an.transform(f, out, an.restore_finder(mapping), restore=True) == 0:
            out.unlink(missing_ok=True)
            raise ValueError(f"{f.name}: không có mã nào khớp bảng {m.name} (nhầm file mapping?)")
        outs.append(out)
    return outs
