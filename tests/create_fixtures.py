# -*- coding: utf-8 -*-
"""Create test fixtures for functional tests."""

import os
import shutil
from docx import Document
from openpyxl import Workbook

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'documents')


def create_simple_template():
    """Simple template with just text placeholders."""
    project_dir = os.path.join(FIXTURES_DIR, 'simple')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    # Template
    doc = Document()
    doc.add_paragraph('Договор № {{ number }}')
    doc.add_paragraph('Дата: {{ date }}')
    doc.add_paragraph('Клиент: {{ client_name }}')
    doc.add_paragraph('Сумма: {{ amount }} руб.')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'simple.docx'))

    # Data
    wb = Workbook()
    ws = wb.active
    ws.append(['number', 'date', 'client_name', 'amount'])
    ws.append(['001', '01.01.2024', 'ООО Ромашка', '10000'])
    ws.append(['002', '02.01.2024', 'ИП Иванов', '20000'])
    ws.append(['003', '03.01.2024', 'АО Спектр', '30000'])
    wb.save(os.path.join(project_dir, 'Данные', 'data.xlsx'))

    # Project config
    import json
    config = {
        "version": 2,
        "templates": {
            "simple.docx": {
                "fields": {
                    "number": {"type": "table", "file": "data.xlsx", "column": "number"},
                    "date": {"type": "table", "file": "data.xlsx", "column": "date"},
                    "client_name": {"type": "table", "file": "data.xlsx", "column": "client_name"},
                    "amount": {"type": "table", "file": "data.xlsx", "column": "amount"},
                },
                "batch": {
                    "sources": {
                        "data.xlsx": {"file": "data.xlsx", "mode": "sequential"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_cycle_template():
    """Template with table cycle (repeating rows)."""
    project_dir = os.path.join(FIXTURES_DIR, 'with_cycle')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    # Template with table
    doc = Document()
    doc.add_paragraph('Счёт № {{ invoice_no }}')
    doc.add_paragraph('Клиент: {{ client }}')
    doc.add_paragraph('')

    table = doc.add_table(rows=2, cols=3)
    table.style = 'Table Grid'
    # Header row
    table.rows[0].cells[0].text = 'Товар'
    table.rows[0].cells[1].text = 'Кол-во'
    table.rows[0].cells[2].text = 'Цена'
    # Template row with placeholders
    table.rows[1].cells[0].text = '{{ item_name }}'
    table.rows[1].cells[1].text = '{{ qty }}'
    table.rows[1].cells[2].text = '{{ price }}'

    doc.add_paragraph('')
    doc.add_paragraph('Итого: {{ total }} руб.')

    doc.save(os.path.join(project_dir, 'Шаблоны', 'invoice.docx'))

    # Data - invoice header
    wb = Workbook()
    ws = wb.active
    ws.title = 'invoices'
    ws.append(['invoice_no', 'client'])
    ws.append(['INV-001', 'ООО Ромашка'])
    ws.append(['INV-002', 'ИП Иванов'])
    wb.save(os.path.join(project_dir, 'Данные', 'invoices.xlsx'))

    # Data - items
    wb = Workbook()
    ws = wb.active
    ws.title = 'items'
    ws.append(['invoice_no', 'item_name', 'qty', 'price'])
    ws.append(['INV-001', 'Товар А', '2', '1000'])
    ws.append(['INV-001', 'Товар Б', '1', '2000'])
    ws.append(['INV-002', 'Товар В', '5', '500'])
    wb.save(os.path.join(project_dir, 'Данные', 'items.xlsx'))

    # Project config
    import json
    config = {
        "version": 2,
        "templates": {
            "invoice.docx": {
                "fields": {
                    "invoice_no": {"type": "table", "file": "invoices.xlsx", "column": "invoice_no"},
                    "client": {"type": "table", "file": "invoices.xlsx", "column": "client"},
                },
                "advanced": {
                    "cycles": [
                        {
                            "table": "items.xlsx",
                            "columns": {
                                "item_name": "item_name",
                                "qty": "qty",
                                "price": "price"
                            }
                        }
                    ]
                },
                "batch": {
                    "sources": {
                        "invoices.xlsx": {"file": "invoices.xlsx", "mode": "sequential"},
                        "items.xlsx": {"file": "items.xlsx", "mode": "constant", "lookup_column": "invoice_no", "lookup_value": "{{ invoice_no }}"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_aggregation_template():
    """Template with aggregation (sum)."""
    project_dir = os.path.join(FIXTURES_DIR, 'with_aggregation')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    doc = Document()
    doc.add_paragraph('Отчёт по продажам')
    doc.add_paragraph('Менеджер: {{ manager }}')
    doc.add_paragraph('Всего сделок: {{ deal_count }}')
    doc.add_paragraph('Сумма: {{ total_sum }} руб.')
    doc.add_paragraph('Средний чек: {{ avg_deal }} руб.')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'report.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['manager', 'deal_amount'])
    ws.append(['Иванов', '10000'])
    ws.append(['Иванов', '20000'])
    ws.append(['Иванов', '30000'])
    ws.append(['Петров', '5000'])
    ws.append(['Петров', '15000'])
    wb.save(os.path.join(project_dir, 'Данные', 'deals.xlsx'))

    import json
    config = {
        "version": 2,
        "templates": {
            "report.docx": {
                "fields": {
                    "manager": {"type": "constant", "value": "Иванов"},
                },
                "advanced": {
                    "aggregations": {
                        "deal_count": {"function": "count", "table": "deals.xlsx", "column": "deal_amount"},
                        "total_sum": {"function": "sum", "table": "deals.xlsx", "column": "deal_amount"},
                        "avg_deal": {"function": "sum", "table": "deals.xlsx", "column": "deal_amount", "multiplier": 0.3333}
                    }
                },
                "batch": {
                    "sources": {
                        "deals.xlsx": {"file": "deals.xlsx", "mode": "constant"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_batch_modes_template():
    """Template to test different batch modes."""
    project_dir = os.path.join(FIXTURES_DIR, 'batch_modes')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    doc = Document()
    doc.add_paragraph('Письмо № {{ num }}')
    doc.add_paragraph('Кому: {{ name }}')
    doc.add_paragraph('Тема: {{ subject }}')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'letter.docx'))

    # Data with 5 rows
    wb = Workbook()
    ws = wb.active
    ws.append(['num', 'name', 'subject'])
    for i in range(1, 6):
        ws.append([f'L{i:03d}', f'Клиент {i}', f'Тема {i}'])
    wb.save(os.path.join(project_dir, 'Данные', 'letters.xlsx'))

    import json
    config = {
        "version": 2,
        "templates": {
            "letter.docx": {
                "fields": {
                    "num": {"type": "table", "file": "letters.xlsx", "column": "num"},
                    "name": {"type": "table", "file": "letters.xlsx", "column": "name"},
                    "subject": {"type": "table", "file": "letters.xlsx", "column": "subject"},
                },
                "batch": {
                    "sources": {
                        "letters.xlsx": {"file": "letters.xlsx", "mode": "sequential"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_counter_template():
    """Template with counter field."""
    project_dir = os.path.join(FIXTURES_DIR, 'with_counter')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    doc = Document()
    doc.add_paragraph('Заявка № {{ req_num }}')
    doc.add_paragraph('Тип: {{ req_type }}')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'request.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['req_type'])
    for i in range(1, 11):
        ws.append([f'Тип {i}'])
    wb.save(os.path.join(project_dir, 'Данные', 'types.xlsx'))

    import json
    config = {
        "version": 2,
        "templates": {
            "request.docx": {
                "fields": {
                    "req_num": {"type": "counter", "start": 100, "step": 1, "format": "0000"},
                    "req_type": {"type": "table", "file": "types.xlsx", "column": "req_type"},
                },
                "batch": {
                    "sources": {
                        "types.xlsx": {"file": "types.xlsx", "mode": "sequential"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_today_template():
    """Template with today field."""
    project_dir = os.path.join(FIXTURES_DIR, 'with_today')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    doc = Document()
    doc.add_paragraph('Акт приёмки от {{ today:dd.MM.yyyy }}')
    doc.add_paragraph('Номер: {{ doc_num }}')
    doc.add_paragraph('Поставщик: {{ supplier }}')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'act.docx'))

    wb = Workbook()
    ws = wb.active
    ws.append(['supplier'])
    ws.append(['ООО Поставщик'])
    wb.save(os.path.join(project_dir, 'Данные', 'suppliers.xlsx'))

    import json
    config = {
        "version": 2,
        "templates": {
            "act.docx": {
                "fields": {
                    "doc_num": {"type": "counter", "start": 1, "format": "000"},
                    "supplier": {"type": "table", "file": "suppliers.xlsx", "column": "supplier"},
                },
                "batch": {
                    "sources": {
                        "suppliers.xlsx": {"file": "suppliers.xlsx", "mode": "constant"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_all_basic_fields_template():
    """Template with all basic field types: constant, table, counter, today."""
    project_dir = os.path.join(FIXTURES_DIR, 'all_basic_fields')
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)

    doc = Document()
    doc.add_paragraph('Документ: {{ doc_title }}')
    doc.add_paragraph('Номер: {{ doc_number }}')
    doc.add_paragraph('Дата: {{ today:dd.MM.yyyy }}')
    doc.add_paragraph('Клиент: {{ client_name }}')
    doc.add_paragraph('Менеджер: {{ manager_name }}')
    doc.add_paragraph('Сумма: {{ amount }} руб.')
    doc.add_paragraph('Статус: {{ status }}')
    doc.save(os.path.join(project_dir, 'Шаблоны', 'all_fields.docx'))

    # Data - clients (10 rows for resume testing)
    wb = Workbook()
    ws = wb.active
    ws.append(['client_name', 'amount'])
    for i in range(1, 11):
        ws.append([f'Клиент {i}', f'{i * 10000}'])
    wb.save(os.path.join(project_dir, 'Данные', 'clients.xlsx'))

    # Data - managers (10 rows for resume testing)
    wb = Workbook()
    ws = wb.active
    ws.append(['manager_name'])
    for i in range(1, 11):
        ws.append([f'Менеджер {i}'])
    wb.save(os.path.join(project_dir, 'Данные', 'managers.xlsx'))

    import json
    config = {
        "version": 2,
        "templates": {
            "all_fields.docx": {
                "fields": {
                    "doc_title": {"type": "constant", "value": "Договор поставки"},
                    "doc_number": {"type": "counter", "start": 1, "step": 1, "format": "0000"},
                    "client_name": {"type": "table", "file": "clients.xlsx", "column": "client_name"},
                    "amount": {"type": "table", "file": "clients.xlsx", "column": "amount"},
                    "manager_name": {"type": "table", "file": "managers.xlsx", "column": "manager_name"},
                    "status": {"type": "constant", "value": "Новый"},
                },
                "batch": {
                    "sources": {
                        "clients.xlsx": {"file": "clients.xlsx", "mode": "sequential"},
                        "managers.xlsx": {"file": "managers.xlsx", "mode": "sequential"}
                    }
                }
            }
        }
    }
    with open(os.path.join(project_dir, 'проект.docxforge'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_all_fixtures(base_dir):
    """Create all test fixtures in the given directory."""
    global FIXTURES_DIR
    FIXTURES_DIR = base_dir
    
    create_simple_template()
    create_cycle_template()
    create_aggregation_template()
    create_batch_modes_template()
    create_counter_template()
    create_today_template()
    create_all_basic_fields_template()


if __name__ == '__main__':
    create_all_fixtures(FIXTURES_DIR)
    print('Created: all_basic_fields')
    print('All fixtures created!')