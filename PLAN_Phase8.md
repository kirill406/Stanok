# PLAN — Phase 8 (B6 «Счётчик при создании из генерации»)

Branch: `fix/002-generation-counter` (от `spec-002`). Spec: `specs/002-stabilization/spec.md`, блок B6 + Non-overlap contract.
Зона: только engine counter path (`src/docxforge/engine/schema.py` — хелпер, `src/docxforge/generate.py` — минимальные вызовы хелпера в путях создания, `tests/test_b6_generation_counter.py` — регрессионный тест). Чужие зоны (GUI, логи, renderer merge, B5-переименование) не трогать.

## Подпункты
- [ ] P1. Разведка: найти путь «создание из генерации», зафиксировать незачёт счётчика (этот файл).
- [x] P2. Repro: скрипт воспроизведения, зафиксировать было/стало значением счётчика.
- [ ] P3. Engine-хелпер счётчика в `engine/schema.py` (математика как обычная генерация).
- [ ] P4. Вызовы хелпера в трёх путях создания (`schema.create_projects`, `generate.create_projects_from_template`, `generate.create_nested_employee_projects`) + persist источника.
- [ ] P5. Регрессионный тест `tests/test_b6_generation_counter.py` (было/стало), прогон затронутых тестов.
- [ ] P6. Финал: полный `pytest`, checkout spec-002, pull --ff-only, merge --no-ff, push.

## P1. Разведка (факты)
- Обычная генерация: `generate.generate_project()` → `renderer.render()` → `execute_render()` → `update_resume_state()` (`engine/render_loop.py:389`) → `resume.last_counter_value = offset + doc_index`; `generate_project()` делает `renderer.save_project()` — счётчик персистится в `проект.docxforge`.
- Создание из генерации (fill-form `_create_projects_mode` → `generate.create_projects_from_template()`, композит → `create_nested_employee_projects()`, engine-уровень `schema.create_projects()`): ни один путь НЕ трогает `template_config.resume.last_counter_value` источника и НЕ сохраняет источник. Незачёт = созданные проекты не прибавляют счётчик.
- Фикс: после успешного создания — `last_counter_value = (last if continue_from_last else 0) + created_count` (та же математика, что `update_resume_state`), сохранить источник. Только счётчик; оффсеты строк (B1/B4) не трогать.

## P2. Repro (факты, до фикса)
- Скрипт: `C:/Users/kirill/AppData/Local/Temp/opencode/b6_repro.py` (источник: COUNTER start=1 + SEQUENTIAL `clients.xlsx` на 3 строки, `resume.last_counter_value=2` как след двух прошлых генераций).
- Было: `create_projects_from_template(..., max_projects=2)` → `before=2 created=2 after=2`, ожидалось `after=4`. Незачёт в `generate.create_projects_from_template` (плоский путь; композит и `schema.create_projects` кода счётчика не содержат вовсе — та же дыра).
- Контроль: `generate_project(..., num_docs=1)` → `before=2 docs=1 after=3`. Обычная генерация счётчик двигает (`render_execute` → `update_resume_state` → `save_project`).
