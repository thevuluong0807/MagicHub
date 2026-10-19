from . import convert, edit, organize  # noqa: F401  (import để đăng ký action)
from .base import GROUPS, REGISTRY


def available(files):
    """[(group_id, label, [Action])] chỉ gồm nhóm/tác vụ áp dụng được cho các file đã chọn."""
    out = []
    for gid, label in GROUPS:
        acts = [a for a in REGISTRY if a.group == gid and a.accepts(files)]
        if acts:
            out.append((gid, label, acts))
    return out


def by_id(action_id):
    return next(a for a in REGISTRY if a.id == action_id)
