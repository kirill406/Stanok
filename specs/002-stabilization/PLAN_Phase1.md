# PLAN Phase 1 — B0 «Сверка готового» (002-stabilization)

Branch: `feat/002-b0-verify` (от `spec-002`). Интеграция — только в `spec-002`, НЕ в main.
Отчёт-доказательство: `specs/002-stabilization/B0-verify.md` (дописывается по подпунктам).

Конвенции: `logging` вместо `print`, RU-строки через `STRINGS`, багфикс → регрессионный тест.
Non-overlap: код не трогаем (фикс разрыва строки — ветка `fix/002-linebreak-merge` другого агента;
`config_io.py`/`generate.py` — за B1). Найденные gaps — в отчёт как follow-up задачи.

## Подпункты

- [x] P1. План и ветка: `PLAN_Phase1.md`, ветка `feat/002-b0-verify`, push -u origin. (этот файл)
- [x] P2(a). Множественный выбор папок: прогнать `tests/test_dialogs.py`, проверить по коду
  (кнопка `STRINGS['main_add_many_btn']` → `_add_many_projects`: валидные в недавние,
  остальные в сводку). Результат — раздел A в `B0-verify.md`. Коммит + push.
- [x] P3(б). Папка вывода `Результат`: grep `output` по `src/`, свежие генерации/тесты
  (`test_functional_generate.py`), состояние на диске. Результат — раздел B в `B0-verify.md`
  (done либо gap с описанием). Коммит + push.
- [x] P4(в). Баг разрыва строки `текст-текст{{поле}}` → `тексттекст-{{поле}}`: воспроизвести
  на `merge_and_replace_paragraph`, указать место в коде. НЕ ЧИНИТЬ (фикс — другой агент).
  Результат — раздел C в `B0-verify.md`. Коммит + push.
- [x] P5. Финал: отметить чекбоксы здесь, merge `--no-ff` в `spec-002`, push `spec-002`,
  прогнать релевантные тесты. При конфликте/non-fast-forward — `merge --abort`, без форса.
