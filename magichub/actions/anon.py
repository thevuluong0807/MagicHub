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
    return ask_anonymize(an.detect(paras))


def parse_term(line: str) -> tuple[str, str]:
    """'ORG: Viettel' -> ('Viettel', 'ORG'); dòng không có tiền tố loại hợp lệ -> (dòng, 'CUSTOM')."""
    kind, sep, rest = line.partition(":")
    if sep and kind.strip().upper() in an.PREFIX and rest.strip():
        return rest.strip(), kind.strip().upper()
    return line.strip(), "CUSTOM"


def dictionary_terms(name: str) -> list[tuple[str, str]]:
    from .. import config

    return [parse_term(t) for t in config.load().get("anonymize_dicts", {}).get(name, []) if t.strip()]


@action("edit.anonymize", "edit", "Mã hoá", "Thay tên người, đơn vị, mã dự án, email… bằng mã [PERSON_1], [ORG_2]…; tạo bảng mapping để Restore (docx, xlsx, pptx, txt, md)",
        kinds=KINDS, ask=_ask_anon, check=supported)
def anonymize(files, p):
    """params.entries: [{value, kind}] (bỏ trống = tự chọn theo gợi ý mặc định); params.custom: [dòng tự thêm, tuỳ chọn tiền tố 'ORG: '];
    params.dictionary: tên từ điển luôn áp dụng; params.scrub: xoá metadata tác giả/công ty. Khớp không phân biệt hoa thường/dấu/khoảng trắng."""
    entries = [(e["value"], e["kind"]) for e in p["entries"]] if "entries" in p else None
    if entries is None:
        entries = [(c.value, c.kind) for c in an.detect([t for f in files for t in an.read_text(f)]) if c.checked]
    entries += [parse_term(v) for v in p.get("custom", []) if v.strip()]
    if p.get("dictionary"):
        entries += dictionary_terms(p["dictionary"])
    if not entries:
        raise ValueError("Không có gì để mã hoá (chưa chọn mục nào)")
    mapper = an.Mapper(entries)
    outs = []
    for f in steps(files):
        out = out_path(f, "anon")
        mapper.hits.clear()
        an.transform(f, out, mapper.find, scrub=p.get("scrub", True))
        an.write_mapping(_mapping_path(out), mapper.rows(), an.leak_report(out, mapper), f.name)
        outs += [out, _mapping_path(out)]
    return outs


def _ask_restore(files):
    from ..dialogs import ask_mapping

    for f in files:  # tự tìm bảng mapping cạnh file (x_anon.docx -> x_anon_mapping.xlsx)
        m = _mapping_path(f)
        if not m.exists():
            break
    else:
        return {"mapping": str(_mapping_path(files[0])), "auto": True}
    return ask_mapping()


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
        mapping = an.read_mapping(m)
        out = out_path(f, "restored")
        if an.transform(f, out, an.restore_finder(mapping), restore=True) == 0:
            out.unlink(missing_ok=True)
            raise ValueError(f"{f.name}: không có mã nào khớp bảng {m.name} (nhầm file mapping?)")
        outs.append(out)
    return outs
