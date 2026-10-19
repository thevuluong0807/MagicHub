from . import convert, edit, extra, organize  # noqa: F401  (import để đăng ký action)
from .base import GROUPS, REGISTRY


# thứ tự hiển thị mặc định (id không liệt kê giữ thứ tự đăng ký, xếp sau)
DEFAULT_ORDER = ["edit.markup", "edit.highlight", "edit.redact", "edit.crop", "edit.resize", "edit.headfoot", "edit.protect", "edit.unlock", "edit.flatten", "edit.strip",
                 "organize.merge", "organize.split", "organize.compress", "organize.reorder", "organize.pages",
                 "organize.rotate_cw", "organize.rotate_ccw", "organize.images", "organize.compare", "organize.zip"]


def ordered(acts, order):
    """Sắp theo `order` (danh sách id); id không có trong order giữ thứ tự đăng ký, xếp sau."""
    pos = {a: i for i, a in enumerate(list(order) + [d for d in DEFAULT_ORDER if d not in order])}
    return sorted(acts, key=lambda a: pos.get(a.id, len(pos)))  # sorted ổn định


def available(files):
    """[(group_id, label, [Action])] áp dụng được cho các file đã chọn, sau khi ẩn/sắp xếp theo config.menu."""
    from ..config import load

    menu = load().get("menu", {})
    hidden = set(menu.get("hidden", []))
    out = []
    for gid, label in GROUPS:
        acts = ordered([a for a in REGISTRY if a.group == gid and a.accepts(files) and a.id not in hidden],
                       menu.get("order", []))
        if acts:
            out.append((gid, label, acts))
    return out


def by_id(action_id):
    return next(a for a in REGISTRY if a.id == action_id)
