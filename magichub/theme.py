"""Giao diện chung (Fluent-like, như Outlook/Snipping Tool): font hệ thống, góc bo, nút chính màu nhấn, sáng/tối theo hệ điều hành.
Chỉ GUI thread dùng."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

LIGHT = dict(bg="#f3f3f3", card="#ffffff", text="#1b1b1b", muted="#616161", border="#d1d1d1", hover="#ebebeb",
             accent="#0f6cbd", accent_hover="#115ea3", accent_soft="#dbeafe", on_accent="#ffffff", field="#ffffff",
             danger="#c42b1c", ok="#107c10")
DARK = dict(bg="#202020", card="#2b2b2b", text="#f3f3f3", muted="#a8a8a8", border="#4a4a4a", hover="#383838",
            accent="#479ef5", accent_hover="#62abf5", accent_soft="#0f3a63", on_accent="#0b0b0b", field="#333333",
            danger="#f1707b", ok="#6ccb5f")


def is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hasattr(hints, "colorScheme") and hints.colorScheme() == Qt.ColorScheme.Dark


def tokens() -> dict:
    return DARK if is_dark() else LIGHT


def font() -> QFont:
    fams = {"win32": ["Segoe UI Variable Text", "Segoe UI"], "darwin": [".AppleSystemUIFont", "Helvetica Neue"]}.get(
        sys.platform, ["Inter", "Noto Sans", "Ubuntu", "DejaVu Sans"])
    f = QFont()
    f.setFamilies(fams)
    f.setPointSize(10)
    return f


def qss(t: dict) -> str:
    return f"""
QDialog, QMessageBox {{ background: {t['bg']}; color: {t['text']}; }}
QLabel {{ color: {t['text']}; background: transparent; }}
QLabel#h1 {{ font-size: 17px; font-weight: 600; }}
QLabel#muted {{ color: {t['muted']}; }}
QLabel#err {{ color: {t['danger']}; }}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {{
  background: {t['field']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px;
  padding: 6px 10px; selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']};
  selection-background-color: {t['accent_soft']}; selection-color: {t['text']}; outline: 0; }}
QPushButton {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px;
  padding: 6px 16px; min-width: 64px; }}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton:pressed {{ background: {t['border']}; }}
QPushButton:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['muted']}; background: {t['bg']}; }}
QPushButton:default {{ background: {t['accent']}; color: {t['on_accent']}; border: 1px solid {t['accent']}; font-weight: 600; }}
QPushButton:default:hover {{ background: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
QPushButton:default:disabled {{ background: {t['border']}; color: {t['muted']}; border-color: {t['border']}; }}
QToolButton {{ background: transparent; color: {t['text']}; border: 1px solid transparent; border-radius: 6px; padding: 5px 8px; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QListWidget {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 4px; outline: 0; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 5px; }}
QListWidget::item:hover {{ background: {t['hover']}; }}
QListWidget::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
QTabWidget::pane {{ border: 1px solid {t['border']}; border-radius: 8px; background: {t['card']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 8px 18px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {t['text']}; border-bottom: 2px solid {t['accent']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QCheckBox {{ color: {t['text']}; spacing: 8px; }}
QProgressBar {{ background: {t['border']}; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 3px; min-height: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 3px; min-width: 28px; }}
QMenu {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 7px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
QMenu::item:disabled {{ color: {t['muted']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}
QToolTip {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px 8px; }}
"""


def apply(app: QApplication) -> None:
    t = tokens()
    app.setStyle("Fusion")
    app.setFont(font())
    pal = QPalette()
    for role, key in ((QPalette.Window, "bg"), (QPalette.Base, "field"), (QPalette.AlternateBase, "card"),
                      (QPalette.Button, "card"), (QPalette.WindowText, "text"), (QPalette.Text, "text"),
                      (QPalette.ButtonText, "text"), (QPalette.Highlight, "accent"),
                      (QPalette.HighlightedText, "on_accent"), (QPalette.ToolTipBase, "card"), (QPalette.ToolTipText, "text")):
        pal.setColor(role, QColor(t[key]))
    app.setPalette(pal)
    app.setStyleSheet(qss(t))
