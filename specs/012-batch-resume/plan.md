# План: 012-batch-resume

> Детализация `spec.md` → шаги реализации.

---

## Шаг 1: Движок (`resolve_rows(limit)`)

- Параметр `limit` + выборка по §2.1 (sequential/circular/constant).
- Тесты 003: круг 2×5, constant×3, limit 0, круг без лимита.

## Шаг 2: Сервис

- Убрать mode-ветвление окна строк, передавать `limit=max_docs`.
- Курсор по режимам (§2.2), `resumed_from` в отчёт.
- Тесты 006: circular+max_docs, resumed_from None/2.

## Шаг 3: Имена файлов

- Тесты dist: счётчик/today/константа, кириллица, `{Нетакого}`, `..`.

## Definition of Done

- [ ] resolve/generate тесты зелёные, покрытие ≥ 90%
- [ ] `pytest tests/ -q` — все зелёные
- [ ] Pre-commit чистый, CHANGELOG — запись о 012
