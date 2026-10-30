# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Template layout (027): docx -> plain page model for window 3.

No Qt here. The model keeps what the window needs to look like the document:
paragraph alignment, indents and spacing, run styles, forced line and page
breaks, tables and header/footer blocks. Placeholders come out as `Field`
pieces, so the window can draw each one as a button.

Known limits (v1): no automatic page splitting, no drawings, tabs are text,
justify is kept as a flag only.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_UNDERLINE
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.text.run import Run

from ..engine.xmlops import PLACEHOLDER_RE

logger = logging.getLogger(__name__)

DEFAULT_SIZE_PT = 11.0
DEFAULT_FONT = "Calibri"
DEFAULT_PAGE_PT = (595.3, 841.9)  # A4
_BREAK_CHARS = "\n\f"
_WRAPPERS = (qn("w:hyperlink"), qn("w:ins"), qn("w:smartTag"), qn("w:fldSimple"))


class TemplateLayoutError(Exception):
    """The template cannot be read or laid out; the message is user-facing."""


@dataclass(frozen=True)
class Style:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    size_pt: float = DEFAULT_SIZE_PT
    font: str = DEFAULT_FONT


@dataclass(frozen=True)
class Text:
    text: str
    style: Style


@dataclass(frozen=True)
class Field:
    name: str
    style: Style


@dataclass(frozen=True)
class LineBreak:
    pass


@dataclass(frozen=True)
class PageBreak:
    pass


Piece = Union[Text, Field, LineBreak, PageBreak]


@dataclass
class Paragraph:
    align: str = "left"  # left | center | right | justify
    left_pt: float = 0.0
    right_pt: float = 0.0
    first_pt: float = 0.0
    before_pt: float = 0.0
    after_pt: float = 0.0
    page_break_before: bool = False
    base: Style = field(default_factory=Style)  # paragraph style: height of an empty line
    pieces: list[Piece] = field(default_factory=list)
    # The w:p element in the document: the window edits the text through it (027).
    element: object = field(default=None, repr=False, compare=False)


@dataclass
class Cell:
    span: int = 1
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Table:
    col_widths_pt: list[float]
    rows: list[list[Cell]]
    borders: bool = False


Block = Union[Paragraph, Table]


@dataclass
class Layout:
    width_pt: float
    height_pt: float
    margins_pt: tuple[float, float, float, float]  # left, right, top, bottom
    header: list[Block]
    body: list[Block]
    footer: list[Block]

    def placeholders(self) -> list[str]:
        """Field names in document order, each once (header, body, footer)."""
        names: list[str] = []
        for block in (*self.header, *self.body, *self.footer):
            for piece in iter_pieces(block):
                if isinstance(piece, Field) and piece.name not in names:
                    names.append(piece.name)
        return names


def iter_pieces(block: Block) -> Iterator[Piece]:
    """All pieces of a block, descending into table cells."""
    if isinstance(block, Paragraph):
        yield from block.pieces
        return
    for row in block.rows:
        for cell in row:
            for inner in cell.blocks:
                yield from iter_pieces(inner)


@dataclass
class _Context:
    doc: object
    styles_el: object
    default_size: float
    default_font: str
    default_after_pt: float


def open_document(path: Path):
    """Open a .docx template as a python-docx Document; TemplateLayoutError on failure."""
    try:
        return Document(str(path))
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"layout open {path}: {e}", exc_info=True)
        raise TemplateLayoutError(f"cannot open template {path.name}: {e}") from e
    except Exception as e:
        logger.critical(f"unexpected layout open {path}: {e}", exc_info=True)
        raise TemplateLayoutError(f"cannot open template {path.name}: {e}") from e


def load_template_layout(path: Path) -> Layout:
    """Read a .docx template and lay it out; raise TemplateLayoutError on failure."""
    return layout_of(open_document(path), path)


def layout_of(doc, path: Path) -> Layout:
    """Layout of an open document; `path` names the file in error messages."""
    try:
        return build_layout(doc)
    except Exception as e:
        logger.critical(f"unexpected layout {path}: {e}", exc_info=True)
        raise TemplateLayoutError(f"cannot lay out template {path.name}: {e}") from e


def build_layout(doc) -> Layout:
    """Layout of an open python-docx Document (first section sets the page)."""
    styles_el = doc.styles.element
    ctx = _Context(
        doc=doc,
        styles_el=styles_el,
        default_size=_doc_default_size(styles_el),
        default_font=_doc_default_font(styles_el),
        default_after_pt=_doc_default_after(styles_el),
    )
    section = doc.sections[0]
    width = section.page_width.pt if section.page_width else DEFAULT_PAGE_PT[0]
    height = section.page_height.pt if section.page_height else DEFAULT_PAGE_PT[1]
    margins = (
        _pt(section.left_margin),
        _pt(section.right_margin),
        _pt(section.top_margin),
        _pt(section.bottom_margin),
    )
    return Layout(
        width_pt=width,
        height_pt=height,
        margins_pt=margins,
        header=_part_blocks(section.header, ctx),
        body=_blocks(doc.element.body, doc, ctx),
        footer=_part_blocks(section.footer, ctx),
    )


# -- containers ---------------------------------------------------------------
def _part_blocks(part, ctx: _Context) -> list[Block]:
    """Header or footer blocks; a part linked to the previous section is empty."""
    if part.is_linked_to_previous:
        return []
    return _blocks(part._element, part, ctx)


def _blocks(container, parent, ctx: _Context) -> list[Block]:
    """Paragraphs and tables of a container in document order."""
    out: list[Block] = []
    for child in container:
        if child.tag == qn("w:p"):
            out.append(_paragraph(child, parent, ctx))
        elif child.tag == qn("w:tbl"):
            out.append(_table(child, parent, ctx))
        elif child.tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                out.extend(_blocks(content, parent, ctx))
    return out


# -- paragraphs ---------------------------------------------------------------
def _paragraph(p_el, parent, ctx: _Context) -> Paragraph:
    p = DocxParagraph(p_el, parent)
    chain = list(_style_chain(p.style))
    formats = [p.paragraph_format] + [s.paragraph_format for s in chain]
    base = _style(None, chain, ctx)
    atoms = _atoms(p_el, p, chain, ctx)
    return Paragraph(
        element=p_el,
        align=_align(_first(formats, "alignment")),
        left_pt=_pt(_first(formats, "left_indent")),
        right_pt=_pt(_first(formats, "right_indent")),
        first_pt=_pt(_first(formats, "first_line_indent")),
        before_pt=_pt(_first(formats, "space_before")),
        after_pt=_pt(_first(formats, "space_after"), ctx.default_after_pt),
        page_break_before=bool(_first(formats, "page_break_before")),
        base=base,
        pieces=_pieces(atoms),
    )


def _atoms(p_el, p: DocxParagraph, chain, ctx: _Context) -> list[tuple[str, Style]]:
    """One (char, style) pair per character; breaks and tabs are control chars."""
    atoms: list[tuple[str, Style]] = []
    for r_el in iter_run_elements(p_el):
        style = _style(Run(r_el, p), chain, ctx)
        for char in run_chars(r_el):
            atoms.append((char, style))
    return atoms


def iter_run_elements(parent_el) -> Iterator:
    for child in parent_el:
        if child.tag == qn("w:r"):
            yield child
        elif child.tag in _WRAPPERS:
            yield from iter_run_elements(child)


def run_chars(r_el) -> Iterator[str]:
    for child in r_el:
        tag = child.tag
        if tag == qn("w:t"):
            yield from child.text or ""
        elif tag == qn("w:tab"):
            yield "\t"
        elif tag in (qn("w:cr"), qn("w:br")):
            is_page = child.get(qn("w:type")) == "page"
            yield "\f" if is_page else "\n"
        elif tag == qn("w:noBreakHyphen"):
            yield "-"


def _pieces(atoms: list[tuple[str, Style]]) -> list[Piece]:
    """Group characters into text, fields and breaks; fields may span runs."""
    joined = "".join(char for char, _ in atoms)
    fields: dict[int, tuple[int, str, Style]] = {}
    for m in PLACEHOLDER_RE.finditer(joined):
        if any(c in m.group(0) for c in "\n\f\t"):
            continue  # a field name cannot hold a break: keep it as text
        fields[m.start()] = (m.end(), m.group(1).strip(), atoms[m.start()][1])

    pieces: list[Piece] = []
    text, style = "", None

    def flush() -> None:
        nonlocal text
        if text:
            pieces.append(Text(text, style))
        text = ""

    index = 0
    while index < len(atoms):
        if index in fields:
            end, name, field_style = fields[index]
            flush()
            pieces.append(Field(name, field_style))
            index = end
            continue
        char, char_style = atoms[index]
        index += 1
        if char == "\n":
            flush()
            pieces.append(LineBreak())
        elif char == "\f":
            flush()
            pieces.append(PageBreak())
        else:
            if char_style != style:
                flush()
                style = char_style
            text += char
    flush()
    return pieces


# -- tables -------------------------------------------------------------------
def _table(tbl_el, parent, ctx: _Context) -> Table:
    widths = [int(w) / 20 for w in tbl_el.xpath("./w:tblGrid/w:gridCol/@w:w")]
    rows: list[list[Cell]] = []
    for tr in tbl_el.xpath("./w:tr"):
        row: list[Cell] = []
        for tc in tr.xpath("./w:tc"):
            spans = tc.xpath("./w:tcPr/w:gridSpan/@w:val")
            row.append(
                Cell(
                    span=int(spans[0]) if spans else 1,
                    blocks=_blocks(tc, parent, ctx),
                )
            )
        rows.append(row)
    return Table(
        col_widths_pt=widths,
        rows=rows,
        borders=_has_borders(tbl_el, ctx),
    )


def _has_borders(tbl_el, ctx: _Context) -> bool:
    """Borders come from the table itself or from its table style."""
    if _real_borders(tbl_el.xpath("./w:tblPr/w:tblBorders")):
        return True
    style_ids = tbl_el.xpath("./w:tblPr/w:tblStyle/@w:val")
    if not style_ids:
        return False
    for style in ctx.styles_el.findall(qn("w:style")):
        if style.get(qn("w:styleId")) == style_ids[0]:
            return _real_borders(style.xpath("./w:tblPr/w:tblBorders"))
    return False


def _real_borders(nodes) -> bool:
    for node in nodes:
        for side in node:
            if side.get(qn("w:val")) not in (None, "nil", "none"):
                return True
    return False


# -- styles -------------------------------------------------------------------
def _style_chain(style) -> Iterator:
    while style is not None:
        yield style
        style = style.base_style


def _first(objs, attr: str):
    """First non-None attribute value along a chain of format objects."""
    for obj in objs:
        value = getattr(obj, attr)
        if value is not None:
            return value
    return None


def _style(run: Run | None, chain, ctx: _Context) -> Style:
    """Run format: run, its character style, then the paragraph style chain."""
    fonts = []
    if run is not None:
        fonts.append(run.font)
        fonts.extend(s.font for s in _style_chain(run.style))
    fonts.extend(s.font for s in chain)
    size = _first(fonts, "size")
    underline = _first(fonts, "underline")
    return Style(
        bold=bool(_first(fonts, "bold")),
        italic=bool(_first(fonts, "italic")),
        underline=bool(underline) and underline != WD_UNDERLINE.NONE,
        size_pt=_pt(size, ctx.default_size),
        font=_first(fonts, "name") or ctx.default_font,
    )


def _doc_default_size(styles_el) -> float:
    values = styles_el.xpath("./w:docDefaults/w:rPrDefault/w:rPr/w:sz/@w:val")
    return int(values[0]) / 2 if values else DEFAULT_SIZE_PT


def _doc_default_font(styles_el) -> str:
    values = styles_el.xpath(
        "./w:docDefaults/w:rPrDefault/w:rPr/w:rFonts/@w:ascii"
    )
    return values[0] if values else DEFAULT_FONT


def _doc_default_after(styles_el) -> float:
    values = styles_el.xpath(
        "./w:docDefaults/w:pPrDefault/w:pPr/w:spacing/@w:after"
    )
    return int(values[0]) / 20 if values else 0.0


# -- values -------------------------------------------------------------------
def _pt(value, default: float = 0.0) -> float:
    """python-docx Length (or None) -> points."""
    if value is None:
        return default
    return float(value.pt)


_ALIGN = {
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    WD_ALIGN_PARAGRAPH.DISTRIBUTE: "justify",
}


def _align(value) -> str:
    return _ALIGN.get(value, "left")
