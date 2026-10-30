# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Template page for window 3 (027): draws a TemplateLayout, fields as buttons.

Each paragraph line is a FlowLayout of word labels, spacers and field
buttons, so a field sits in the text where it is in the document. Lines
wrap at word boundaries; alignment and the first-line indent are applied
per line.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetricsF
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)

from ..services.template_layout import (
    Block,
    Cell,
    Field,
    Layout,
    LineBreak,
    PageBreak,
    Paragraph,
    Piece,
    Style,
    Table,
    Text,
)
from .strings import STRINGS

logger = logging.getLogger(__name__)

PX_PER_PT = 96 / 72
TAB_SPACES = 4
_TOKEN_RE = re.compile(r"[ \t]+|[^ \t]+")


def px(points: float) -> int:
    """Points of the document -> logical pixels of the window."""
    return round(points * PX_PER_PT)


def _font(style: Style) -> QFont:
    font = QFont(style.font)
    font.setPointSizeF(style.size_pt)
    font.setBold(style.bold)
    font.setItalic(style.italic)
    font.setUnderline(style.underline)
    return font


def _is_spacer(item: QLayoutItem) -> bool:
    widget = item.widget()
    return widget is not None and bool(widget.property("spacer"))


class FlowLayout(QLayout):
    """Left-to-right items with wrapping; alignment and first indent per line."""

    def __init__(
        self,
        parent: QWidget | None = None,
        align: str = "left",
        first_indent: int = 0,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._align = align
        self._first_indent = first_indent

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def addWidget(self, widget: QWidget) -> None:
        self.addChildWidget(widget)
        self._items.append(QWidgetItem(widget))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._place(rect, test_only=False)

    def sizeHint(self) -> QSize:
        width = sum(item.sizeHint().width() for item in self._items)
        height = max((item.sizeHint().height() for item in self._items), default=0)
        return QSize(width + self._first_indent, height)

    def minimumSize(self) -> QSize:
        width = max((item.minimumSize().width() for item in self._items), default=0)
        height = max((item.minimumSize().height() for item in self._items), default=0)
        return QSize(width, height)

    def _rows(self, width: int) -> list[list[tuple[QLayoutItem, QSize]]]:
        """Split items into lines; a line never starts with a spacer after a wrap."""
        rows: list[list[tuple[QLayoutItem, QSize]]] = [[]]
        used = 0
        limit = max(0, width - self._first_indent)
        for item in self._items:
            size = item.sizeHint()
            row = rows[-1]
            spacer = _is_spacer(item)
            if not spacer and row and used + size.width() > limit:
                while row and _is_spacer(row[-1][0]):
                    row.pop()
                rows.append([])
                used = 0
                limit = width
                row = rows[-1]
            elif spacer and not row and len(rows) > 1:
                continue  # leading spaces after a wrap are not shown
            row.append((item, size))
            used += size.width()
        return rows

    def _place(self, rect: QRect, test_only: bool) -> int:
        y = rect.y()
        for index, row in enumerate(self._rows(rect.width())):
            indent = self._first_indent if index == 0 else 0
            row_width = sum(size.width() for _, size in row)
            row_height = max((size.height() for _, size in row), default=0)
            free = max(0, rect.width() - indent - row_width)
            shift = {"center": free // 2, "right": free}.get(self._align, 0)
            x = rect.x() + indent + shift
            for item, size in row:
                if not test_only:
                    top = y + (row_height - size.height()) // 2
                    item.setGeometry(QRect(QPoint(x, top), size))
                x += size.width()
            y += row_height
        return y - rect.y()


class TemplateSheet(QScrollArea):
    """Scrollable white page with the template text; field buttons emit fieldClicked."""

    fieldClicked = pyqtSignal(str)

    def __init__(
        self,
        layout: Layout,
        describe: Callable[[str], str],
        is_configured: Callable[[str], bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layout_model = layout
        self._describe = describe
        self._is_configured = is_configured
        self._buttons: dict[str, list[QPushButton]] = {}
        self.setObjectName("sheetScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._page = self._build_page()
        area = QWidget(self)
        area.setObjectName("sheetArea")
        row = QHBoxLayout(area)
        row.setContentsMargins(16, 16, 16, 16)
        row.addStretch(1)
        row.addWidget(self._page)
        row.addStretch(1)
        self.setWidget(area)
        self.refresh()
        logger.debug(
            f"template sheet built: {len(self._buttons)} fields, "
            f"{len(layout.body)} body blocks"
        )

    @property
    def field_names(self) -> list[str]:
        """Names of the fields drawn on the page, in document order."""
        return list(self._buttons)

    def refresh(self) -> None:
        """Re-read state of every field button (after the user changed a field)."""
        for name, buttons in self._buttons.items():
            configured = self._is_configured(name)
            tip = self._describe(name)
            for button in buttons:
                button.setProperty("state", "set" if configured else "unset")
                button.setToolTip(tip)
                button.style().unpolish(button)
                button.style().polish(button)

    # -- page -------------------------------------------------------------------
    def _build_page(self) -> QWidget:
        model = self._layout_model
        left, right, top, bottom = model.margins_pt
        page = QFrame(self)
        page.setObjectName("page")
        page.setFixedWidth(px(model.width_pt))
        page.setMinimumHeight(px(model.height_pt))
        page.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        box = QVBoxLayout(page)
        box.setContentsMargins(px(left), px(top), px(right), px(bottom))
        box.setSpacing(0)
        if model.header:
            box.addWidget(self._part(model.header, STRINGS.TPL_PART_HEADER, page))
        for block in model.body:
            box.addWidget(self._block(block, page))
        box.addStretch(1)
        if model.footer:
            box.addWidget(self._part(model.footer, STRINGS.TPL_PART_FOOTER, page))
        return page

    def _part(self, blocks: list[Block], caption: str, parent: QWidget) -> QWidget:
        frame = QFrame(parent)
        frame.setObjectName("pagePart")
        box = QVBoxLayout(frame)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        label = QLabel(caption, frame)
        label.setObjectName("partCaption")
        box.addWidget(label)
        for block in blocks:
            box.addWidget(self._block(block, frame))
        return frame

    def _block(self, block: Block, parent: QWidget) -> QWidget:
        if isinstance(block, Paragraph):
            return self._paragraph(block, parent)
        return self._table(block, parent)

    # -- paragraphs -------------------------------------------------------------
    def _paragraph(self, para: Paragraph, parent: QWidget) -> QWidget:
        box = QWidget(parent)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        column = QVBoxLayout(box)
        column.setContentsMargins(
            px(para.left_pt), px(para.before_pt), px(para.right_pt), px(para.after_pt)
        )
        column.setSpacing(0)
        if para.page_break_before:
            column.addWidget(self._page_break(box))
        # A line is a list of pieces; None is a page separator between two lines.
        entries: list[list[Piece] | None] = [[]]
        for piece in para.pieces:
            if isinstance(piece, LineBreak):
                entries.append([])
            elif isinstance(piece, PageBreak):
                entries.append(None)
                entries.append([])
            else:
                entries[-1].append(piece)
        first = True
        for entry in entries:
            if entry is None:
                column.addWidget(self._page_break(box))
                continue
            indent = px(para.first_pt) if first and para.first_pt > 0 else 0
            column.addWidget(self._line(entry, para, indent, box))
            first = False
        return box

    def _line(
        self, pieces: list[Piece], para: Paragraph, indent: int, parent: QWidget
    ) -> QWidget:
        line = QWidget(parent)
        flow = FlowLayout(line, align=para.align, first_indent=indent)
        flow.setContentsMargins(0, 0, 0, 0)
        added = False
        for piece in pieces:
            if isinstance(piece, Field):
                flow.addWidget(self._field_button(piece, line))
                added = True
            elif isinstance(piece, Text):
                for word in self._words(piece, line):
                    flow.addWidget(word)
                    added = True
        if not added:
            # An empty line keeps the height of the paragraph font.
            empty = QLabel(" ", line)
            empty.setFont(_font(para.base))
            flow.addWidget(empty)
        return line

    def _words(self, piece: Text, parent: QWidget) -> list[QWidget]:
        font = _font(piece.style)
        space_px = QFontMetricsF(font).horizontalAdvance(" ")
        out: list[QWidget] = []
        for token in _TOKEN_RE.findall(piece.text):
            if token[0] in " \t":
                width = sum(
                    space_px * (TAB_SPACES if char == "\t" else 1) for char in token
                )
                out.append(self._spacer(width, parent))
            else:
                label = QLabel(token, parent)
                label.setFont(font)
                label.setTextFormat(Qt.PlainText)
                out.append(label)
        return out

    @staticmethod
    def _spacer(width: float, parent: QWidget) -> QWidget:
        spacer = QWidget(parent)
        spacer.setFixedWidth(max(1, round(width)))
        spacer.setProperty("spacer", True)
        return spacer

    def _field_button(self, piece: Field, parent: QWidget) -> QPushButton:
        button = QPushButton(piece.name, parent)
        button.setObjectName("fieldButton")
        button.setFont(_font(piece.style))
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(lambda _checked=False, name=piece.name: self.fieldClicked.emit(name))
        self._buttons.setdefault(piece.name, []).append(button)
        return button

    def _page_break(self, parent: QWidget) -> QWidget:
        label = QLabel(STRINGS.TPL_PAGE_BREAK, parent)
        label.setObjectName("pageBreak")
        label.setAlignment(Qt.AlignCenter)
        return label

    # -- tables -----------------------------------------------------------------
    def _table(self, table: Table, parent: QWidget) -> QWidget:
        frame = QFrame(parent)
        frame.setObjectName("tableBlock")
        grid = QGridLayout(frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        widths = table.col_widths_pt or [1.0]
        columns = max(
            [len(widths)] + [sum(cell.span for cell in row) for row in table.rows]
        )
        widths = (widths + [sum(widths) / len(widths)] * columns)[:columns]
        for col, width in enumerate(widths):
            grid.setColumnStretch(col, max(1, round(width * 100)))
        for row_index, row in enumerate(table.rows):
            col = 0
            for cell in row:
                cell_box = self._cell(cell, table.borders, frame)
                grid.addWidget(cell_box, row_index, col, 1, cell.span)
                col += cell.span
        return frame

    def _cell(self, cell: Cell, borders: bool, parent: QWidget) -> QWidget:
        box = QFrame(parent)
        box.setFrameShape(QFrame.Box if borders else QFrame.NoFrame)
        column = QVBoxLayout(box)
        column.setContentsMargins(4, 2, 4, 2)
        column.setSpacing(0)
        for block in cell.blocks:
            column.addWidget(self._block(block, box))
        return box
