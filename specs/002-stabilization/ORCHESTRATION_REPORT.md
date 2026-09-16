# ORCHESTRATION_REPORT — 002-stabilization (Waves A+B, orchestrator: main session)

Date: 2026-09-16. Integration branch: `spec-002` (мерж в `main` — Phase 3, за оркестратором).
Workers: FirstAgentF2–F8 (F8 создана копированием FirstAgent: `cp -r` минус build/dist/__pycache__).
Full suite on assembled `spec-002`: **425 passed** (было 384 на старте).

## Wave A (разведка, параллельно)
- **#1 B0-verify (F2, `feat/002-b0-verify`, merge `43d05cf`)** — done. Мультивыбор подтверждён;
  GAP: `output/` захардкожен (`config_io.py:218` + legacy-fallbacks) — отдан в B1;
  баг разрыва строки подтверждён в `engine/merge.py` (не `renderer.py` — резерв
  переопределён для Phase 9). Доказательства: `PLAN_Phase1.md`, `specs/002-stabilization/B0-verify.md`.
- **#2 B3-recon (F3, `fix/002-b3-recon`, merge `b48700a`)** — done. 3 traceback
  (FileNotFoundError шаблона, битый проект → JSONDecodeError, битый шаблон →
  BadZipFile); заявлены `config_io.py`/`form_dialog.py`/`project_window.py`. Артефакт: `RECON_B3.md`.

## Wave B (реализация, параллельно, F2–F8)
- **#3 B1 (F2, `feat/002-projects`, merge `1470abb`)** — done: снапшоты в Home с `(1),(2)`,
  предзаполнение, секция полей (новое поле `TemplateConfig.generated_project_fields`),
  перевод `output/`→`Результат`. 12 тестов (`test_002_projects.py`).
- **#4 B2 (F3, `feat/002-user-logs`, merge `d4d3cde`)** — done: новый `app_logging.py`
  (`APP_LOG_FILE` = `~/.docxforge/docxforge.log`, RotatingFileHandler append), `run.py` переведён.
- **#5 B3-fix (F4, `fix/002-fill-menu-crash`, merge `119ab73` оркестратором)** — done:
  guards + `FillFormOpenError`, 6 регрессионных тестов. Ветка не вмержилась сама (гонка
  пушей) — влил оркестратор; конфликт `config_io.py` (строка B1 внутри ханка B3)
  сведён в try/except + `Результат`.
- **#6 B4 (F5, `feat/002-skip-copy`, merge `0a8c8d4`)** — частично: UI-чекбокс, `get_skip_copy_tables()`,
  `copy_data_tree()`, 4 теста. GAP: сквозной проводки не было (dead code) — дотянул
  оркестратор (`119ab73`): поле `skip_copy` в схеме + сериализация, сбор флага в
  `config_collector`, restore в `config_io`, exclude в flat+nested путях + 2 e2e-теста.
- **#7 B5 (F6, `feat/002-no-overwrite`, merge `58db161`)** — done: `resolve_unique_output_path()`
  (`файл (1)`, `(2)`…), формат недавних не тронут. 3 теста.
- **#8 B6 (F7, `fix/002-generation-counter`, merge `8b8889e`)** — done: `advance_counter_after_creation()`,
  фикс 3 путей + persist, счётчик не двигается при rollback. 6 тестов.
- **#9 linebreak (F8, `fix/002-linebreak-merge`, merge `3344bae`)** — done: `_split_mixed_runs` +
  order-preserving emission в `engine/merge.py` (+130/−50), 4 теста (до фикса 2 failed).

## Проблемы (все без потерь, рестарты не понадобились)
1. **Гонки пуша в `spec-002`** — B3-ветка не вмержилась (remote ушёл вперёд); агент корректно
   сделал reset и отчитался, мерж выполнил оркестратор. Остальные разрулили rebase сами.
2. **Предсуществующие GUI-флейки** (не связаны с диффом, в изоляции зелёные):
   `test_m12_engine_failure_restores_snapshot` (автосейв-таймер), `test_delete_recent_project`,
   один `F` в `test_gui_*`. Фиксировать отдельно.
3. **Stale fetch** у оркестратора скрыл ветки `002-*` — лечится `git fetch` перед проверкой.
4. **Мусор в папках** (`prototype/`, `test_project*/`, `.bash_tmp`) — untracked, агентам велено не трогать.
5. Отклонение от AGENT.md: интеграция в `spec-002`, а не в `main` (эпик-ветка; мерж в `main` — Phase 3).

## Follow-ups (не в 002)
- GUI-флейки (п.2) — отдельная задача.
- B4: видимость чекбокса только в режиме генерации (упёрлось бы в запрещённый `form_dialog.py`).
- B1: `print` в `generate_cli` оставлен осознанно (тест через capsys).
- Корневые `PLAN_Phase*.md`/`RECON_B3.md` — артефакты агентов, при закрытии спеки перенести/сжать.
