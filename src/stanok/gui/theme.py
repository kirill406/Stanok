# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application-wide visual theme (QSS + font)."""

from __future__ import annotations

APP_QSS = """
QWidget {
    color: #1f2933;
    font-family: "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans";
    font-size: 10pt;
}
QMainWindow, QDialog {
    background-color: #f3f6f8;
}
QLabel {
    background: transparent;
}
QLabel#appTitle {
    color: #17324d;
    font-size: 22pt;
    font-weight: 700;
}
QLabel#appSubtitle {
    color: #667085;
    font-size: 10pt;
}
QLabel#pageTitle {
    color: #17324d;
    font-size: 16pt;
    font-weight: 700;
}
QLabel#pageSubtitle {
    color: #667085;
}
QLabel#sectionTitle {
    color: #17324d;
    font-size: 11pt;
    font-weight: 600;
    padding-top: 2px;
}
QLabel#rowTitle {
    color: #17324d;
    font-weight: 600;
}
QLabel#rowSubtitle, QLabel#muted {
    color: #667085;
    font-size: 9pt;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dfe6ec;
    border-radius: 10px;
    color: #17324d;
    font-weight: 600;
    margin-top: 14px;
    padding: 16px 16px 14px 16px;
}
QGroupBox::title {
    color: #52606d;
    left: 14px;
    padding: 0 6px;
    subcontrol-origin: margin;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 7px;
    color: #1f2933;
    font-weight: 500;
    min-height: 18px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #f5f8fa;
    border-color: #aebdca;
}
QPushButton:pressed {
    background-color: #eaf0f4;
    border-color: #9aacbc;
}
QPushButton:focus {
    border-color: #2e7d32;
}
QPushButton:disabled {
    background-color: #f1f4f6;
    border-color: #e1e7ec;
    color: #98a2b3;
}
QPushButton[role="primary"] {
    background-color: #2e7d32;
    border-color: #2e7d32;
    color: #ffffff;
    font-weight: 600;
}
QPushButton[role="primary"]:hover {
    background-color: #388e3c;
    border-color: #388e3c;
}
QPushButton[role="primary"]:pressed {
    background-color: #1b5e20;
    border-color: #1b5e20;
}
QPushButton[role="primary"]:disabled {
    background-color: #a5d6a7;
    border-color: #a5d6a7;
    color: #ffffff;
}
QPushButton[role="danger"] {
    color: #b42318;
}
QPushButton[role="danger"]:hover {
    background-color: #fef3f2;
    border-color: #fda29b;
    color: #912018;
}
QPushButton[role="danger"]:pressed {
    background-color: #fee4e2;
}
QTableWidget QPushButton {
    padding: 5px 8px;
}
QLineEdit, QComboBox, QSpinBox, QAbstractSpinBox {
    background-color: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 6px;
    min-height: 20px;
    padding: 6px 9px;
    selection-background-color: #c8e6c9;
    selection-color: #1f2933;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QAbstractSpinBox:focus {
    border-color: #2e7d32;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #f1f4f6;
    border-color: #e1e7ec;
    color: #98a2b3;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cfd8e3;
    color: #1f2933;
    outline: 0;
    selection-background-color: #e3f2e4;
    selection-color: #1f2933;
}
QTableWidget, QListWidget, QTreeWidget {
    alternate-background-color: #f8fafc;
    background-color: #ffffff;
    border: 1px solid #dfe6ec;
    border-radius: 8px;
    gridline-color: #edf1f5;
    outline: 0;
    selection-background-color: #e3f2e4;
    selection-color: #1f2933;
}
QTableWidget::item, QTreeWidget::item {
    border: none;
    padding: 5px 7px;
}
QTableWidget::item:selected, QTreeWidget::item:selected {
    background-color: #e3f2e4;
    color: #1f2933;
}
QListWidget::item {
    border: none;
    border-radius: 6px;
    padding: 3px 6px;
}
QListWidget::item:selected {
    background-color: #e3f2e4;
    color: #1f2933;
}
QHeaderView::section {
    background-color: #f1f5f9;
    border: none;
    border-bottom: 1px solid #dfe6ec;
    color: #52606d;
    font-weight: 600;
    padding: 7px 8px;
}
QTableCornerButton::section {
    background-color: #f1f5f9;
    border: none;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    margin: 2px;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #c7d2dd;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #a9b7c5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #c7d2dd;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: #a9b7c5;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QProgressBar {
    background-color: #e8edf2;
    border: none;
    border-radius: 7px;
    color: #52606d;
    font-size: 9pt;
    height: 14px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #2e7d32;
    border-radius: 7px;
}
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #dfe6ec;
    color: #667085;
}
QStatusBar::item {
    border: none;
}
QToolTip {
    background-color: #1f2933;
    border: none;
    color: #ffffff;
    padding: 5px 7px;
}
QPushButton#glyphButton {
    font-size: 14pt;
    font-weight: 700;
    padding: 0px;
}
/* Template page (027): the sheet keeps paper-white with a grey work area. */
QWidget#sheetArea { background-color: #d9dde3; }
QFrame#page {
    background-color: #ffffff;
    border: 1px solid #b8bec8;
}
QFrame#pagePart { background-color: #f3f4f6; }
QLabel#partCaption { color: #6b7280; font-size: 8pt; }
QLabel#pageBreak {
    color: #8a8f98;
    font-size: 8pt;
    border-top: 1px dashed #b0b4bb;
    padding: 6px 0px;
}
QPushButton#fieldButton {
    background-color: #e7f0fb;
    color: #1d4f91;
    border: 1px solid #7fa6d6;
    border-radius: 4px;
    padding: 1px 6px;
}
QPushButton#fieldButton:hover { background-color: #d4e4f8; }
QPushButton#fieldButton[state="unset"] {
    background-color: #fff3dc;
    color: #8a5a00;
    border: 1px dashed #d59b3d;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #dfe6ec;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    border-radius: 5px;
    color: #1f2933;
    padding: 6px 18px 6px 14px;
}
QMenu::item:selected {
    background-color: #e3f2e4;
    color: #17324d;
}
QMenu::separator {
    background-color: #edf1f5;
    height: 1px;
    margin: 4px 8px;
}
QCheckBox, QRadioButton {
    spacing: 7px;
}
QCheckBox::indicator, QRadioButton::indicator {
    height: 16px;
    width: 16px;
}
"""


def apply_theme(app) -> None:
    """Apply the application font and stylesheet."""
    from PyQt5.QtGui import QFont

    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(APP_QSS)


def set_button_role(widget, role: str) -> None:
    """Mark a button as primary/danger and repolish it after the dynamic property."""
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
