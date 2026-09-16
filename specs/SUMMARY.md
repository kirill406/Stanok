# Specs

Исторические и активные спеки фич. Формат: `specs/NNN-slug/spec.md + plan.md + tasks.md`.

## Active

- `000-pre-alpha/` — Nested Employee/Project Generation: двухуровневая генерация Сотрудник → Проекты (7 фаз, все закрыты, тесты 261 passed). Содержит исторические файлы (`PLAN.md`, `PLAN_Phase1–7.md`, `SPEC.md`, `ORCHESTRATION_REPORT.md`), заморожены.
- `001-review/` — глубокое ревью кода после src/uv-миграции. Статус: done, смерджено в `main` — `REPORT.md` (10 blocker, majors, minors), все B1–B10 и M1–M17 закрыты с регрессионными тестами (384 passed), follow-up зафиксирован в `tasks.md`.

## Done

- `001-review` — см. выше (Active).

## Conventions

- `spec.md` — что и зачем (контракт, долгоживущий)
- `plan.md` — как (одноразовый, удаляется после мержа)
- `tasks.md` — шаги реализации
- После `done`: ценное graduate в `docs/` + `AGENTS.md`, в спеке поставить `Status: done`

