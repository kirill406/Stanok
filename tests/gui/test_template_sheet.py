# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen tests for the template page (027): field buttons, lines, layout."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from docx import Document
from docx.enum.text import WD_BREAK
from PyQt5.QtCore import QRect
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QWidget

import pytest

from stanok.gui.strings import STRINGS
from stanok.gui.template_sheet import FlowWidget, TemplateSheet
from stanok.services.template_layout import load_template_layout


def _double_click(widget):
    """Deliver a double click as a plain event: QTest's mouse state leaks between tests."""
    from PyQt5.QtCore import QEvent, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtWidgets import QApplication

    pos = QPointF(widget.rect().center())
    event = QMouseEvent(QEvent.MouseButtonDblClick, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, event)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _layout(tmp_path, build):
    doc = Document()
    build(doc)
    path = tmp_path / "tpl.docx"
    doc.save(path)
    return load_template_layout(path)


def _sheet(qapp, layout, configured=lambda name: True):
    sheet = TemplateSheet(
        layout,
        describe=lambda name: f"описание {name}",
        is_configured=configured,
    )
    sheet.resize(900, 700)
    sheet.show()  # geometry is computed on show
    qapp.processEvents()
    return sheet


def test_template_sheet_field_becomes_button_with_field_name(qapp, tmp_path):
    layout = _layout(tmp_path, lambda d: d.add_paragraph("Договор {{ФИО}} на {{Сумма}}"))
    sheet = _sheet(qapp, layout)

    assert sheet.field_names == ["ФИО", "Сумма"]
    assert [b.text() for b in sheet._buttons["ФИО"]] == ["ФИО"]


def test_template_sheet_repeated_field_has_button_per_place(qapp, tmp_path):
    def build(doc):
        doc.add_paragraph("{{Имя}}")
        doc.add_paragraph("снова {{Имя}}")

    sheet = _sheet(qapp, _layout(tmp_path, build))

    assert sheet.field_names == ["Имя"]
    assert len(sheet._buttons["Имя"]) == 2


def test_template_sheet_click_on_field_emits_its_name(qapp, tmp_path):
    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("{{Город}}")))
    clicked: list[str] = []
    sheet.fieldClicked.connect(clicked.append)

    sheet._buttons["Город"][0].click()

    assert clicked == ["Город"]


def test_template_sheet_unconfigured_field_has_unset_state(qapp, tmp_path):
    def build(doc):
        doc.add_paragraph("{{Готово}} {{Нет}}")

    sheet = _sheet(qapp, _layout(tmp_path, build), configured=lambda n: n == "Готово")

    assert sheet._buttons["Готово"][0].property("state") == "set"
    assert sheet._buttons["Нет"][0].property("state") == "unset"


def test_template_sheet_refresh_follows_configuration(qapp, tmp_path):
    state = {"ready": False}
    sheet = _sheet(
        qapp,
        _layout(tmp_path, lambda d: d.add_paragraph("{{Поле}}")),
        configured=lambda n: state["ready"],
    )
    button = sheet._buttons["Поле"][0]
    assert button.property("state") == "unset"

    state["ready"] = True
    sheet.refresh()

    assert button.property("state") == "set"
    assert button.toolTip() == "описание Поле"


def test_template_sheet_line_break_starts_new_line(qapp, tmp_path):
    def build(doc):
        para = doc.add_paragraph("первая")
        para.runs[0].add_break()
        para.add_run("вторая")

    sheet = _sheet(qapp, _layout(tmp_path, build))

    labels = [w.text() for w in sheet.findChildren(QLabel) if w.text() in ("первая", "вторая")]
    assert labels == ["первая", "вторая"]
    first = next(w for w in sheet.findChildren(QLabel) if w.text() == "первая")
    second = next(w for w in sheet.findChildren(QLabel) if w.text() == "вторая")
    assert second.mapTo(sheet, second.rect().topLeft()).y() > first.mapTo(sheet, first.rect().topLeft()).y()


def test_template_sheet_page_break_draws_separator(qapp, tmp_path):
    def build(doc):
        para = doc.add_paragraph("до")
        para.runs[0].add_break(WD_BREAK.PAGE)
        para.add_run("после")

    sheet = _sheet(qapp, _layout(tmp_path, build))

    separators = sheet.findChildren(QLabel, "pageBreak")
    assert [s.text() for s in separators] == [STRINGS.TPL_PAGE_BREAK]


def test_template_sheet_header_and_footer_are_captioned(qapp, tmp_path):
    def build(doc):
        section = doc.sections[0]
        section.header.paragraphs[0].text = "шапка {{Орг}}"
        section.footer.paragraphs[0].text = "подвал"
        doc.add_paragraph("тело")

    sheet = _sheet(qapp, _layout(tmp_path, build))

    captions = [c.text() for c in sheet.findChildren(QLabel, "partCaption")]
    assert captions == [STRINGS.TPL_PART_HEADER, STRINGS.TPL_PART_FOOTER]
    assert sheet.field_names == ["Орг"]


def test_template_sheet_table_cells_hold_their_fields(qapp, tmp_path):
    def build(doc):
        table = doc.add_table(rows=1, cols=2)
        table.style = doc.styles["Table Grid"]
        table.cell(0, 0).text = "Товар"
        table.cell(0, 1).text = "{{Цена}}"

    sheet = _sheet(qapp, _layout(tmp_path, build))

    assert sheet.field_names == ["Цена"]
    assert sheet.findChildren(QWidget, "tableBlock")


def test_template_sheet_empty_paragraph_keeps_a_line(qapp, tmp_path):
    def build(doc):
        doc.add_paragraph("до")
        doc.add_paragraph()
        doc.add_paragraph("после")

    sheet = _sheet(qapp, _layout(tmp_path, build))

    texts = [w.text() for w in sheet.findChildren(QLabel)]
    assert "до" in texts and "после" in texts
    assert " " in texts  # the empty paragraph's placeholder label


def test_flow_widget_wraps_words_when_narrow(qapp):
    host = FlowWidget()
    for i in range(6):
        QLabel(f"слово{i}", host)

    wide = host.heightForWidth(2000)
    narrow = host.heightForWidth(60)

    assert narrow > wide


def test_flow_widget_right_alignment_puts_last_item_at_edge(qapp):
    host = FlowWidget(align="right")
    label = QLabel("конец", host)

    host.resize(400, 40)
    host.relayout()

    assert label.geometry().right() == 399


def test_flow_widget_center_alignment_centers_the_line(qapp):
    host = FlowWidget(align="center")
    label = QLabel("х", host)

    host.resize(400, 40)
    host.relayout()

    assert abs(label.geometry().center().x() - 200) <= 2


def test_flow_widget_first_indent_applies_to_first_line_only(qapp):
    host = FlowWidget(first_indent=50)
    first = QLabel("а", host)

    host.resize(400, 40)
    host.relayout()

    assert first.geometry().x() == 50


def test_flow_widget_removed_child_is_not_placed(qapp):
    host = FlowWidget()
    kept = QLabel("оставить", host)
    gone = QLabel("убрать", host)
    gone.setParent(None)
    gone.deleteLater()

    host.resize(400, 40)
    host.relayout()

    assert kept.geometry().x() == 0
    assert host._items() == [kept]


def test_template_sheet_double_click_during_edit_is_ignored(qapp, tmp_path):
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("один")))
    edited, asked = [], []
    sheet.paragraphEdited.connect(lambda p, t: edited.append(t))
    sheet.paragraphActivated.connect(asked.append)
    sheet.begin_edit(sheet._layout_model.body[0], "один, правка")

    sheet._activate(sheet._layout_model.body[0])

    assert edited == [] and asked == []
    assert sheet.findChild(QPlainTextEdit, "paragraphEditor") is not None



def test_template_sheet_words_keep_space_between_them(qapp, tmp_path):
    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("раз два")))
    first = next(w for w in sheet.findChildren(QLabel) if w.text() == "раз")
    second = next(w for w in sheet.findChildren(QLabel) if w.text() == "два")

    gap = second.mapTo(sheet, second.rect().topLeft()).x() - first.mapTo(sheet, first.rect().topLeft()).x() - first.width()

    assert gap > 0


def test_template_sheet_editor_stays_visible_and_focused_after_events(qapp, tmp_path):
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("текст")))
    sheet.begin_edit(sheet._layout_model.body[0], "текст")
    qapp.processEvents()

    editor = sheet.findChild(QPlainTextEdit, "paragraphEditor")
    assert editor is not None and editor.isVisible()
    assert sheet._editing_para is not None  # not ended by a focus change


def test_template_sheet_editor_cursor_starts_at_end(qapp, tmp_path):
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("старый")))
    sheet.begin_edit(sheet._layout_model.body[0], "старый")

    editor = sheet.findChild(QPlainTextEdit, "paragraphEditor")
    assert editor.textCursor().position() == len("старый")


def test_template_sheet_double_click_on_paragraph_requests_edit(qapp, tmp_path):
    from stanok.gui.template_sheet import _ParagraphBox

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("правка меня")))
    asked = []
    sheet.paragraphActivated.connect(asked.append)
    box = sheet.findChildren(_ParagraphBox)[0]

    _double_click(box)
    qapp.processEvents()  # the request is handed over on the next event-loop turn

    assert len(asked) == 1
    assert asked[0].element is not None


def test_template_sheet_begin_edit_shows_editor_with_text(qapp, tmp_path):
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("старый")))
    para = sheet._layout_model.body[0]

    sheet.begin_edit(para, "новый текст")

    editor = sheet.findChild(QPlainTextEdit, "paragraphEditor")
    assert editor is not None
    assert editor.toPlainText() == "новый текст"


def test_template_sheet_escape_cancels_edit_without_change(qapp, tmp_path):
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("старый")))
    edited = []
    sheet.paragraphEdited.connect(lambda p, t: edited.append(t))
    sheet.begin_edit(sheet._layout_model.body[0], "старый")
    editor = sheet.findChild(QPlainTextEdit, "paragraphEditor")
    editor.setPlainText("черновик")

    QTest.keyClick(editor, Qt.Key_Escape)
    qapp.processEvents()

    assert edited == []
    assert sheet._editing_para is None


def test_template_sheet_commit_emits_editor_text(qapp, tmp_path):
    from PyQt5.QtWidgets import QPlainTextEdit

    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("старый")))
    edited = []
    sheet.paragraphEdited.connect(lambda p, t: edited.append(t))
    sheet.begin_edit(sheet._layout_model.body[0], "старый")
    editor = sheet.findChild(QPlainTextEdit, "paragraphEditor")
    editor.setPlainText("новый\nабзац")

    editor.finish(True)

    assert edited == ["новый\nабзац"]


def test_template_sheet_display_token_round_trips_page_break():
    from stanok.gui.template_sheet import from_display, to_display

    text = "до\fпосле"

    assert "\f" not in to_display(text)
    assert from_display(to_display(text)) == text


def test_template_sheet_set_layout_rebuilds_buttons(qapp, tmp_path):
    sheet = _sheet(qapp, _layout(tmp_path, lambda d: d.add_paragraph("{{А}}")))
    second = tmp_path / "second"
    second.mkdir()
    new = _layout(second, lambda d: d.add_paragraph("{{Б}} {{В}}"))

    sheet.set_layout(new)

    assert sheet.field_names == ["Б", "В"]
