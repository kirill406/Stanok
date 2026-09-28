# tests/json — фикстуры JSON-слоя (003)

Каждый тест — подпапка `tests/json/<test_name>/`:

```
<test_name>/
  data.xlsx      # исходные таблицы (вход границы Excel → JSON)
  template.docx  # шаблон с {{ полями }} (вход render)
  filling.json   # Filling JSON: разрешённые данные документа
                 # {"template": "template.docx", "fields": {"имя": "значение", ...}}
  expected.docx  # эталон результата
```

Запуск: `tests/test_json_fixtures.py` параметризован по подпапкам —
рендерит `template.docx` данными из `filling.json` и сравнивает
с `expected.docx`.

Второй тип кейсов — `project.json` + `data.xlsx` + `expected_filling.json`
(поток PJ + Excel → FJ): маппинг полей резолвится строкой таблицы,
результат сравнивается с ожидаемым Filling JSON.

GUI-потоки (AJ, PJ) — в `tests/test_json_gui_flows.py`: AJ изолирован
фикстурой (настройки в tmp, реальный Home не трогаем).

Сравнение — текстовое: тексты параграфов и ячеек таблиц по порядку
(`assert_docx_text_equal`). Форматирование, картинки и метаданные docx
НЕ сравниваются (ограничение осознанное; форматирование покрыто
`test_formatting_unit.py`). Байтовое сравнение невозможно (zip-метаданные).
