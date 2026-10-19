"""python -m magichub [run | menu FILE... | do ACTION_ID FILE... [-p k=v] | actions [FILE...]]"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(prog="magichub")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("run", help="chạy daemon hotkey (mặc định)")
    m = sub.add_parser("menu", help="mở vòng tròn tại con trỏ cho các file, bấm chuột để chọn")
    m.add_argument("files", nargs="+")
    d = sub.add_parser("do", help="chạy thẳng 1 tác vụ, không GUI")
    d.add_argument("action")
    d.add_argument("files", nargs="+")
    d.add_argument("-p", "--param", action="append", default=[], help="key=value")
    i = sub.add_parser("install-integration", help="tự chạy khi đăng nhập + mục menu trong file manager (Nautilus/Nemo/Dolphin, Windows Send to)")
    i.add_argument("--remove", action="store_true", help="gỡ các file đã tạo")
    a = sub.add_parser("actions", help="liệt kê tác vụ (áp dụng cho FILE nếu có)")
    a.add_argument("files", nargs="*")
    args = ap.parse_args()

    if args.cmd in (None, "run"):
        from .app import main as run

        return run()
    if args.cmd == "menu":
        from .app import main as run

        return run([Path(f).resolve() for f in args.files])
    if args.cmd == "install-integration":
        from . import integrate

        for f in (integrate.remove() if args.remove else integrate.install()):
            print(("đã xoá " if args.remove else "đã tạo ") + str(f))
        return 0
    from .actions import REGISTRY, available, by_id

    if args.cmd == "actions":
        files = [Path(f) for f in args.files]
        for a_ in (REGISTRY if not files else [x for _, _, acts in available(files) for x in acts]):
            print(f"{a_.id:24} {a_.group:9} {a_.tip}")
        return 0
    act = by_id(args.action)
    params = dict(kv.split("=", 1) for kv in args.param)
    if "size" in params or "pct" in params:
        params = {k: int(v) if v.isdigit() else v for k, v in params.items()}
    if "box" in params:
        params["box"] = tuple(float(x) for x in params["box"].split(","))
    for o in act.run([Path(f).resolve() for f in args.files], params):
        print(o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
