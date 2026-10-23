import os
import sys


def _smoke(out: str) -> int:
    """CI: chạy thử bản đóng gói (app windowed không có console nên ghi kết quả ra file). Import mọi module + chạy vài tác vụ thật trên PDF mẫu,
    để lỗi thiếu file/thư viện khi đóng gói lộ ra lúc build chứ không phải lúc người dùng mở app."""
    import tempfile
    import traceback
    from pathlib import Path

    try:
        import magichub.app  # noqa: F401  (Qt, hotkey, wheel…)
        import magichub.dialogs  # noqa: F401
        import msoffcrypto  # noqa: F401  (Unlock Word)
        import pymupdf
        from magichub.actions import REGISTRY, by_id

        td = Path(tempfile.mkdtemp())
        pdf = td / "t.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "MagicHub smoke test")
        doc.save(str(pdf))
        for aid in ("organize.compress", "convert.pdf.docx"):
            (o,) = by_id(aid).run([pdf], {})
            assert Path(o).exists() and Path(o).stat().st_size > 0, aid
        Path(out).write_text(f"ok {len(REGISTRY)} actions, pymupdf {pymupdf.__version__}\n", "utf-8")
        return 0
    except BaseException:
        Path(out).write_text("FAIL\n" + traceback.format_exc(), "utf-8")
        return 1


if os.environ.get("MAGICHUB_SMOKE"):
    sys.exit(_smoke(os.environ["MAGICHUB_SMOKE"]))

from magichub.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
