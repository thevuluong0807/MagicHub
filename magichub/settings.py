"""Hộp thoại cài đặt: danh sách phím tắt (mỗi phím mở cả vòng hoặc một nhóm) + tuỳ biến menu (ẩn/hiện/sắp xếp tác vụ).
Chỉ GUI thread dùng."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QTabWidget, QVBoxLayout)

from .actions import ordered
from .actions.base import GROUPS, REGISTRY
from .dialogs import _front, ask_hotkey

GROUP_NAME = {"": "Tất cả nhóm", **{gid: label for gid, label in GROUPS}}


def hotkey_text(hk: dict) -> str:
    return "+".join(hk["modifiers"] + ([hk["key"]] if hk["key"] else [])) + "  →  " + GROUP_NAME[hk.get("group") or ""]


def ask_hotkeys(hotkeys: list[dict]) -> list[dict] | None:
    """Danh sách phím tắt: Thêm (bấm tổ hợp + chọn nhóm) / Xoá. Trả danh sách mới hoặc None nếu huỷ."""
    items = [dict(h) for h in hotkeys]
    dlg = QDialog()
    dlg.setWindowTitle("Phím tắt")
    dlg.setMinimumWidth(420)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Mỗi phím tắt mở cả vòng, hoặc vào thẳng một nhóm (Convert / Edit / Organize)."))
    lst = QListWidget()
    lay.addWidget(lst)
    err = QLabel()
    err.setStyleSheet("color:#c33")
    lay.addWidget(err)

    def refresh():
        lst.clear()
        lst.addItems([hotkey_text(h) for h in items])

    def add():
        new = ask_hotkey([], "")
        if not new:
            return
        mods, key = new
        pick = QComboBox()
        pick.addItems(list(GROUP_NAME.values()))
        d2 = QDialog()
        d2.setWindowTitle("Phím tắt mở nhóm nào?")
        v = QVBoxLayout(d2)
        v.addWidget(pick)
        bb2 = QDialogButtonBox(QDialogButtonBox.Ok)
        bb2.accepted.connect(d2.accept)
        v.addWidget(bb2)
        _front(d2)  # dlg cha luôn-trên-cùng: popup con phải cùng cờ, nếu không bị che
        d2.exec()
        gid = list(GROUP_NAME)[pick.currentIndex()] or None
        if any(h["modifiers"] == mods and h["key"] == key for h in items):
            err.setText("Tổ hợp này đã có")
            return
        err.setText("")
        items.append({"modifiers": mods, "key": key, "group": gid})
        refresh()

    def remove():
        r = lst.currentRow()
        if r < 0:
            return
        if len(items) == 1:
            err.setText("Phải còn ít nhất một phím tắt")
            return
        err.setText("")
        del items[r]
        refresh()

    row = QHBoxLayout()
    for text, fn in (("Thêm…", add), ("Xoá", remove)):
        b = QPushButton(text)
        b.clicked.connect(fn)
        row.addWidget(b)
    row.addStretch()
    lay.addLayout(row)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    refresh()
    _front(dlg)
    return items if dlg.exec() == QDialog.Accepted else None


def ask_menu(menu: dict) -> dict | None:
    """Mỗi nhóm một tab: bỏ tích = ẩn, kéo thả = đổi thứ tự. Trả {"hidden": [...], "order": [...]} hoặc None."""
    hidden, order = set(menu.get("hidden", [])), menu.get("order", [])
    dlg = QDialog()
    dlg.setWindowTitle("Tuỳ chỉnh menu")
    dlg.resize(460, 480)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Bỏ tích để ẩn tác vụ khỏi vòng tròn. Kéo thả để đổi thứ tự (thứ tự trên vòng: từ 12h theo chiều kim đồng hồ)."))
    tabs, lists = QTabWidget(), {}
    for gid, label in GROUPS:
        lst = QListWidget()
        lst.setDragDropMode(QAbstractItemView.InternalMove)
        for a in ordered([a for a in REGISTRY if a.group == gid], order):
            it = QListWidgetItem(f"{a.label}  —  {a.tip}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if a.id in hidden else Qt.Checked)
            it.setData(Qt.UserRole, a.id)
            lst.addItem(it)
        lists[gid] = lst
        tabs.addTab(lst, label)
    lay.addWidget(tabs, 1)
    reset = QPushButton("Mặc định")

    def do_reset():
        for gid, lst in lists.items():
            lst.clear()
            for a in [a for a in REGISTRY if a.group == gid]:
                it = QListWidgetItem(f"{a.label}  —  {a.tip}")
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
                it.setData(Qt.UserRole, a.id)
                lst.addItem(it)

    reset.clicked.connect(do_reset)
    lay.addWidget(reset)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    _front(dlg)
    if dlg.exec() != QDialog.Accepted:
        return None
    new_hidden, new_order = [], []
    for lst in lists.values():
        for k in range(lst.count()):
            it = lst.item(k)
            new_order.append(it.data(Qt.UserRole))
            if it.checkState() != Qt.Checked:
                new_hidden.append(it.data(Qt.UserRole))
    return {"hidden": new_hidden, "order": new_order}
