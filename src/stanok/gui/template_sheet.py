# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Template page for window 3 (027): draws a TemplateLayout, fields as buttons.

Each paragraph line is a FlowWidget of word labels, spacers and field
buttons, so a field sits in the text where it is in the document. Lines
wrap at word boundaries; alignment and the first-line indent are applied
per line.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetricsF, QTextCursor
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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


class _Spacer(QWidget):
    """A horizontal gap of fixed width between two words (a space or a tab)."""

    def __init__(self, width: int, parent: QWidget) -> None:
        super().__init__(parent)
        self._gap = max(1, width)

    def sizeHint(self) -> QSize:
        return QSize(self._gap, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(self._gap, 0)


class FlowWidget(QWidget):
    """Children flow left to right and wrap; alignment and first indent apply per line.

    A plain widget, not a QLayout: the children are the widgets created with this
    widget as parent, in creation order. A deleted child leaves the list by itself,
    so there is no item bookkeeping that Qt could touch after a page is removed.
    """

    def __init__(self, parent: QWidget | None = None, align: str = "left", first_indent: int = 0) -> None:
        super().__init__(parent)
        self._align = align
        self._first_indent = first_indent

    def _items(self) -> list[QWidget]:
        return [w for w in self.children() if isinstance(w, QWidget) and not w.isWindow()]

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(width, apply=False)

    def sizeHint(self) -> QSize:
        items = self._items()
        width = sum(w.sizeHint().width() for w in items) + self._first_indent
        height = max((w.sizeHint().height() for w in items), default=0)
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        items = self._items()
        width = max((w.minimumSizeHint().width() for w in items), default=0)
        height = max((w.minimumSizeHint().height() for w in items), default=0)
        return QSize(width, height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place(self.width(), apply=True)

    def relayout(self) -> None:
        """Place the children again, after children were added or removed."""
        self._place(self.width(), apply=True)

    def _rows(self, width: int) -> list[list[tuple[QWidget, QSize]]]:
        """Split children into lines; a line never starts with a spacer after a wrap."""
        rows: list[list[tuple[QWidget, QSize]]] = [[]]
        used = 0
        limit = max(0, width - self._first_indent)
        for item in self._items():
            size = item.sizeHint()
            spacer = isinstance(item, _Spacer)
            row = rows[-1]
            if not spacer and row and used + size.width() > limit:
                while row and isinstance(row[-1][0], _Spacer):
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

    def _place(self, width: int, apply: bool) -> int:
        """Lay out the lines for `width`; returns the height, moves children if `apply`."""
        y = 0
        for index, row in enumerate(self._rows(width)):
            indent = self._first_indent if index == 0 else 0
            row_width = sum(size.width() for _, size in row)
            row_height = max((size.height() for _, size in row), default=0)
            free = max(0, width - indent - row_width)
            shift = {"center": free // 2, "right": free}.get(self._align, 0)
            x = indent + shift
            for item, size in row:
                if apply:
                    item.setGeometry(QRect(x, y + (row_height - size.height()) // 2, size.width(), size.height()))
                x += size.width()
            y += row_height
        return y


PAGE_BREAK = "\f"


def to_display(text: str) -> str:
    """Document text -> editor text: a page break is shown as a readable token."""
    return text.replace(PAGE_BREAK, STRINGS.TPL_PAGE_BREAK_TOKEN)


def from_display(text: str) -> str:
    """Editor text -> document text: the token becomes a page break again."""
    return text.replace(STRINGS.TPL_PAGE_BREAK_TOKEN, PAGE_BREAK)


class ParagraphEditor(QPlainTextEdit):
    """Plain editor for one paragraph's text. Esc cancels; the owner commits the rest."""

    ended = pyqtSignal(bool, str)  # committed, text

    def __init__(self, text: str, font: QFont, parent: QWidget) -> None:
        super().__init__(text, parent)
        self._done = False
        self.setObjectName("paragraphEditor")
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._fit()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

    def _fit(self) -> None:
        """Height of the whole text at the current width, at least three lines."""
        width = max(1, self.viewport().width() - 8)
        text_rect = self.fontMetrics().boundingRect(
            QRect(0, 0, width, 100000), Qt.TextWordWrap, self.toPlainText()
        )
        lines = self.fontMetrics().lineSpacing()
        height = text_rect.height() + 2 * self.frameWidth() + 12
        self.setFixedHeight(max(height, 3 * lines + 8))

    def resizeEvent(self, event) -> None:
        # The width is known only after layout: the height follows it here.
        super().resizeEvent(event)
        self._fit()

    def finish(self, commit: bool) -> None:
        if self._done:
            return
        self._done = True
        self.ended.emit(commit, self.toPlainText())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.finish(False)
            return
        super().keyPressEvent(event)


class _ParagraphBox(QWidget):
    """Paragraph block; a double click asks the sheet to edit it."""

    def __init__(self, para: Paragraph, parent: QWidget, on_activate) -> None:
        super().__init__(parent)
        self._para = para
        self._on_activate = on_activate

    def mouseDoubleClickEvent(self, event) -> None:
        self._on_activate(self._para)
        event.accept()


class TemplateSheet(QScrollArea):
    """Scrollable white page with the template text; field buttons emit fieldClicked.

    A double click on a paragraph emits paragraphActivated. The owner answers with
    begin_edit (shows the editor), then with set_layout (text changed) or end_edit.
    Esc in the editor restores the page by itself.
    """

    fieldClicked = pyqtSignal(str)
    paragraphActivated = pyqtSignal(object)  # Paragraph
    paragraphEdited = pyqtSignal(object, str)  # Paragraph, editor text

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
        self._editing_para: Paragraph | None = None
        self._editing_text = ""
        self._editor: ParagraphEditor | None = None
        self.setObjectName("sheetScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area = QWidget(self)
        area.setObjectName("sheetArea")
        self._row = QHBoxLayout(area)
        self._row.setContentsMargins(16, 16, 16, 16)
        self._row.addStretch(1)
        self._page: QWidget | None = None
        self._row.addStretch(1)
        self.setWidget(area)
        self._show_page()
        logger.debug(f"template sheet built: {len(self._buttons)} fields")

    @property
    def field_names(self) -> list[str]:
        """Names of the fields drawn on the page, in document order."""
        return list(self._buttons)

    def set_layout(self, layout: Layout) -> None:
        """Replace the page with a new layout (after a text change); ends any edit."""
        self._layout_model = layout
        self._editing_para = None
        self._editor = None
        self._show_page()

    def begin_edit(self, para: Paragraph, text: str) -> None:
        """Show the paragraph as an editor holding `text` (editor form)."""
        self._editing_para = para
        self._editing_text = text
        self._show_page()

    def end_edit(self) -> None:
        self._editing_para = None
        self._editor = None
        self._show_page()

    def commit_edit(self) -> None:
        """Apply the open paragraph editor, if any (used when the window closes)."""
        if self._editor is not None:
            self._editor.finish(True)

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

    def _show_page(self) -> None:
        """Build the page for the current layout and keep the scroll position."""
        scroll = self.verticalScrollBar().value()
        old = self._page
        self._buttons = {}
        self._page = self._build_page()
        self._row.insertWidget(1, self._page)
        # A page built under the scroll area is not shown by the layout; show it explicitly,
        # otherwise a new paragraph editor stays hidden and loses focus at once.
        self._page.show()
        if self._editor is not None:
            self._editor.setFocus()
        if old is not None:
            self._row.removeWidget(old)
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self.refresh()
        self.verticalScrollBar().setValue(scroll)

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
        box = _ParagraphBox(para, parent, self._activate)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        column = QVBoxLayout(box)
        column.setContentsMargins(
            px(para.left_pt), px(para.before_pt), px(para.right_pt), px(para.after_pt)
        )
        column.setSpacing(0)
        if para.page_break_before:
            column.addWidget(self._page_break(box))
        if self._editing_para is not None and para.element is self._editing_para.element:
            self._editor = ParagraphEditor(self._editing_text, _font(para.base), box)
            self._editor.ended.connect(
                lambda commit, text, p=para: self._on_ended(p, commit, text)
            )
            column.addWidget(self._editor)
            return box
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

    def _activate(self, para: Paragraph) -> None:
        # While a paragraph is open, the page stays as it is: Save or Close applies the edit.
        if self._editing_para is None:
            self.paragraphActivated.emit(para)

    def _on_ended(self, para: Paragraph, commit: bool, text: str) -> None:
        """Esc restores the page here; a commit waits for the owner to rebuild it."""
        if commit:
            self.paragraphEdited.emit(para, text)
        else:
            self.end_edit()

    def _line(
        self, pieces: list[Piece], para: Paragraph, indent: int, parent: QWidget
    ) -> QWidget:
        line = FlowWidget(parent, align=para.align, first_indent=indent)
        added = False
        for piece in pieces:
            if isinstance(piece, Field):
                self._field_button(piece, line)
                added = True
            elif isinstance(piece, Text):
                added = bool(self._words(piece, line)) or added
        if not added:
            # An empty line keeps the height of the paragraph font.
            empty = QLabel(" ", line)
            empty.setFont(_font(para.base))
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
        return _Spacer(round(width), parent)

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
