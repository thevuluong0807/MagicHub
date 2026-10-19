from . import convert, edit, organize  # noqa: F401  (import để đăng ký action)
from .base import GROUPS, REGISTRY


def ordered(acts, order):
    """Sắp theo `order` (danh sách id); id không có trong order giữ thứ tự đăng ký, xếp sau."""
    pos = {a: i for i, a in enumerate(order)}
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
