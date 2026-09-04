# -*- coding: utf-8 -*-
"""Generate .docx test templates with {{ }} placeholders in various formatting scenarios
to test XML-run merging."""

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

def add_paragraph(doc, text, bold=False, italic=False, font_size=None, color=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    if font_size:
        run.font.size = Pt(font_size)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return p

def add_mixed_paragraph(doc, parts):
    """Add paragraph where each part has its own formatting.
    parts is a list of (text, bold, italic) tuples."""
    p = doc.add_paragraph()
    for text, bold, italic in parts:
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
    return p


# ===== TEMPLATE 1: Simple placeholders (no formatting inside) =====
doc = Document()
doc.styles['Normal'].font.name = 'Times New Roman'
doc.styles['Normal'].font.size = Pt(12)

add_paragraph(doc, 'TEMPLATE 1: ПРОСТЫЕ ПЛЕЙСХОЛДЕРЫ', bold=True, font_size=14)
add_paragraph(doc, '')
add_paragraph(doc, 'ДОГОВОР ПОСТАВКИ № {{ doc_number }}')
add_paragraph(doc, '')
add_paragraph(doc, 'г. Москва, {{ today:dd }} {{ today:MM:название_месяца }} {{ today:yyyy }} г.')
add_paragraph(doc, '')
add_paragraph(doc, '{{ организация }}, именуемое в дальнейшем «Поставщик», в лице {{ должность_поставщика }} {{ фио_поставщика }}, с одной стороны, и {{ название_клиента }}, с другой стороны.')
add_paragraph(doc, '')
add_paragraph(doc, 'ИНН Покупателя: {{ ИНН_клиента }}')
add_paragraph(doc, 'Адрес Покупателя: {{ адрес_клиента }}')
add_paragraph(doc, '')
add_paragraph(doc, 'Итого: {{ итого }} руб.')
add_paragraph(doc, 'С НДС (20%): {{ с_ндс }} руб.')
add_paragraph(doc, '')
add_paragraph(doc, '{{ image:подпись_поставщика }}')
add_paragraph(doc, '{{ image:подпись_покупателя }}')

doc.save('prototype/templates/test_01_simple.docx')


# ===== TEMPLATE 2: Bold/italic/underline inside placeholders =====
doc = Document()
doc.styles['Normal'].font.name = 'Times New Roman'
doc.styles['Normal'].font.size = Pt(12)

add_paragraph(doc, 'TEMPLATE 2: ФОРМАТИРОВАНИЕ ВНУТРИ ПЛЕЙСХОЛДЕРОВ', bold=True, font_size=14)
add_paragraph(doc, '')

# Placeholder split across bold and normal runs
p = doc.add_paragraph()
r1 = p.add_run('{{ ')
r1.bold = True
r2 = p.add_run('название_клиента')
r2.bold = False
r3 = p.add_run(' }}')
r3.bold = True
# This creates 3 runs: bold "{{ ", normal "название_клиента", bold " }}"
# Word does this when user makes part of placeholder bold.

add_paragraph(doc, '')

# Placeholder with italic part
p = doc.add_paragraph()
r1 = p.add_run('{{ ')
r1.italic = False
r2 = p.add_run('важное_поле')
r2.italic = True
r3 = p.add_run(' }}')
r3.italic = False

add_paragraph(doc, '')

# Multiple placeholders with mixed formatting in one line
p = doc.add_paragraph()
p.add_run('Клиент: ').bold = True
r = p.add_run('{{ ')
r.bold = True
r = p.add_run('название_клиента')
r.bold = False
r = p.add_run(' }}')
r.bold = True
p.add_run(', ИНН: ').bold = True
r = p.add_run('{{ ')
r.bold = True
r = p.add_run('ИНН_клиента')
r.bold = False
r = p.add_run(' }}')
r.bold = True

add_paragraph(doc, '')

# Russian characters with formatting split
p = doc.add_paragraph()
p.add_run('Сторона 1: «')
r = p.add_run('{{ ')
r.italic = True
r = p.add_run('сторона')
r.italic = False
r = p.add_run(' }}')
r.italic = True
p.add_run('»')

doc.save('prototype/templates/test_02_formatting.docx')


# ===== TEMPLATE 3: Table with placeholders (cycle simulation) =====
doc = Document()
doc.styles['Normal'].font.name = 'Times New Roman'
doc.styles['Normal'].font.size = Pt(12)

add_paragraph(doc, 'TEMPLATE 3: ТАБЛИЦА С ПЛЕЙСХОЛДЕРАМИ', bold=True, font_size=14)
add_paragraph(doc, '')

table = doc.add_table(rows=3, cols=3)
table.style = 'Table Grid'

# Header row
for i, text in enumerate(['Наименование', 'Количество', 'Цена']):
    cell = table.rows[0].cells[i]
    cell.text = ''
    run = cell.paragraphs[0].add_run(text)
    run.bold = True

# Data row 1 with placeholders
for i, text in enumerate(['{{ наименование }}', '{{ количество }}', '{{ цена }}']):
    cell = table.rows[1].cells[i]
    cell.text = ''
    cell.paragraphs[0].add_run(text)

# Data row 2 - placeholder split by formatting (bold number in the middle)
cell = table.rows[2].cells[0]
cell.text = ''
cell.paragraphs[0].add_run('{{ наименование }}')

cell = table.rows[2].cells[1]
cell.text = ''
r = cell.paragraphs[0].add_run('{{ ')
r = cell.paragraphs[0].add_run('количество')
r.bold = True  # Word might break the run here
r = cell.paragraphs[0].add_run(' }}')

cell = table.rows[2].cells[2]
cell.text = ''
r = cell.paragraphs[0].add_run('{{ цена }}')
r.italic = True  # Italic placeholder

doc.save('prototype/templates/test_03_table.docx')


# ===== TEMPLATE 4: Real document layout with headers, lists, formatting =====
doc = Document()
doc.styles['Normal'].font.name = 'Times New Roman'
doc.styles['Normal'].font.size = Pt(12)

# Header
h = doc.add_heading('ДОГОВОР ПОСТАВКИ № {{ doc_number }}', level=1)
for run in h.runs:
    run.font.name = 'Times New Roman'

add_paragraph(doc, '')

# Date line with mixed format
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
p.add_run('г. Москва, «')
r = p.add_run('{{ today:dd }}')
r.italic = True
p.add_run('» ')
r = p.add_run('{{ today:MM:название_месяца }}')
r.italic = True
p.add_run(' ')
r = p.add_run('{{ today:yyyy }}')
r.italic = True
p.add_run(' г.')

add_paragraph(doc, '')

# Company block
p = doc.add_paragraph()
p.add_run('{{ организация }}').bold = True
p.add_run(', именуемое в дальнейшем ')
p.add_run('«Поставщик»').bold = True
p.add_run(', в лице ')
p.add_run('{{ должность_поставщика }}').italic = True
p.add_run(' ')
p.add_run('{{ фио_поставщика }}').italic = True
p.add_run(', с одной стороны, и ')
p.add_run('{{ название_клиента }}').bold = True
p.add_run(', именуемое в дальнейшем ')
p.add_run('«Покупатель»').bold = True
p.add_run(', с другой стороны.')

add_paragraph(doc, '')

# Numbered list
add_paragraph(doc, '1. ПРЕДМЕТ ДОГОВОРА', bold=True)
add_paragraph(doc, '')
add_paragraph(doc, 'Поставщик обязуется поставить следующие товары:')
add_paragraph(doc, '')

# Table
table = doc.add_table(rows=2, cols=3)
table.style = 'Table Grid'
for i, text in enumerate(['Наименование', 'Кол-во', 'Цена (руб.)']):
    run = table.rows[0].cells[i].paragraphs[0].add_run(text)
    run.bold = True
for i, text in enumerate(['{{ наименование }}', '{{ количество }}', '{{ цена }}']):
    table.rows[1].cells[i].paragraphs[0].add_run(text)

add_paragraph(doc, '')
add_paragraph(doc, 'Итого: {{ итого }} руб.')
add_paragraph(doc, 'С НДС (20%): {{ с_ндс }} руб.')
add_paragraph(doc, '')

# Signatures in a table
add_paragraph(doc, 'ПОДПИСИ СТОРОН:', bold=True)
sig_table = doc.add_table(rows=1, cols=2)
sig_table.style = 'Table Grid'
cell_l = sig_table.rows[0].cells[0]
cell_l.paragraphs[0].add_run('Поставщик:').bold = True
cell_l.add_paragraph('{{ фио_поставщика }}')
cell_l.add_paragraph('')
cell_l.add_paragraph('{{ image:подпись_поставщика }}')

cell_r = sig_table.rows[0].cells[1]
cell_r.paragraphs[0].add_run('Покупатель:').bold = True
cell_r.add_paragraph('{{ фио_клиента }}')
cell_r.add_paragraph('')
cell_r.add_paragraph('{{ image:подпись_покупателя }}')

doc.save('prototype/templates/test_04_real_layout.docx')


# ===== TEMPLATE 5: Edge cases — partial overlaps, adjacent placeholders =====
doc = Document()

add_paragraph(doc, 'TEMPLATE 5: ГРАНИЧНЫЕ СЛУЧАИ', bold=True, font_size=14)
add_paragraph(doc, '')

# Adjacent placeholders (no space between }} and {{ )
p = doc.add_paragraph()
p.add_run('{{ поле1 }}')
p.add_run('{{ поле2 }}')
p.add_run('{{ поле3 }}')

add_paragraph(doc, '')

# Text touching placeholder
p = doc.add_paragraph()
p.add_run('текст')
p.add_run('{{ поле }}')
p.add_run('текст')

add_paragraph(doc, '')

# Line breaks inside and around placeholders
p = doc.add_paragraph()
p.add_run('{{ поле1 }}')
r = p.add_run('\n')
r = p.add_run('на новой строке {{ поле2 }}')

add_paragraph(doc, '')

# Very long placeholder name
p = doc.add_paragraph()
p.add_run('{{ очень_длинное_имя_поля_с_подчёркиваниями_и_цифрами_12345 }}')

add_paragraph(doc, '')

# Placeholder with digits and Russian
p = doc.add_paragraph()
p.add_run('Сумма: {{ сумма }} руб., в т.ч. НДС {{ nds_20_procentov }}')

add_paragraph(doc, '')

# Placeholder inside a list bullet
doc.add_paragraph('• Контрагент: {{ название_клиента }}', style='List Bullet')
doc.add_paragraph('• ИНН: {{ ИНН_клиента }}', style='List Bullet')

doc.save('prototype/templates/test_05_edge_cases.docx')


print("[OK] Generated 5 test templates in prototype/templates/")
print("     1: test_01_simple.docx      - simple placeholders")
print("     2: test_02_formatting.docx   - bold/italic inside placeholders")
print("     3: test_03_table.docx        - table with placeholders")
print("     4: test_04_real_layout.docx  - realistic document layout")
print("     5: test_05_edge_cases.docx   - adjacent, line breaks, long names")
