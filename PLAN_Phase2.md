# PLAN Phase 2 — B3 «Падение из меню заполнения» (разведка, без кода)

Ветка разведки: `fix/002-b3-recon` от `spec-002`. Код не пишется (только чтение + фиксация).
Фикс и регрессионный тест — отдельная ветка `fix/002-fill-menu-crash` (Phase 1).

- [x] 1. Прочитать конвенции (`AGENT.md`, `FirstAgentF3/AGENTS.md`: logging вместо print, RU-строки через STRINGS, багфикс → регрессионный тест) и `specs/002-stabilization/spec.md` (B3 + Non-overlap contract)
- [x] 2. Найти entry points окна заполнения шаблона (окно, меню/создание, слот кнопки)
- [x] 3. Воспроизвести падение headless-способом (pytest-qt / offscreen `QApplication`), зафиксировать полный traceback
- [x] 4. Определить точные файлы/функции причины, заявить файлы за B3 (приоритет по Non-overlap contract)
- [x] 5. Записать `RECON_B3.md`, закоммитить оба файла (`PLAN_Phase2.md`, `RECON_B3.md`) с push, смержить в `spec-002`
