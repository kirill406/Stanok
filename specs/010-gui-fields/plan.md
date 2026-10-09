# План: 010-gui-fields

> Детализация `spec.md` → шаги реализации.

---

## Шаг 1: Диалог

- `src/stanok/gui/fields_dialog.py` — `FieldsDialog(project_ref, template_name,
  store, parent)`: таблица (имя, источник, значение), line edit только для
  `constant`, остальные readonly с превью.
- `STRINGS`: ключи `FLD_*` (заголовок, шапка, «Сохранить», «Сохранить?»).

## Шаг 2: Сохранение и dirty-чек

- «Сохранить»: константы → `pj.templates[name].fields[*].value` + `store.save`.
- `closeEvent`/`reject`: при dirty — `QMessageBox.question`
  (Save → сохранить+закрыть, Discard → закрыть, Cancel → остаться).

## Шаг 3: Стык с окном 2

- Удалить ветку `ImportError` и ключ `PROJ_FIELDS_TBD` из окна 2.
- Тест заглушки → мок `FieldsDialog.exec_`.

## Definition of Done

- [ ] `QT_QPA_PLATFORM=offscreen pytest tests/gui/test_fields_dialog.py -v` — зелёные
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый, CHANGELOG — запись о 010
