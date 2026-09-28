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

Сравнение — текстовое: тексты параграфов и ячеек таблиц по порядку
(`assert_docx_text_equal`). Форматирование, картинки и метаданные docx
НЕ сравниваются (ограничение осознанное; форматирование покрыто
`test_formatting_unit.py`). Байтовое сравнение невозможно (zip-метаданные).
