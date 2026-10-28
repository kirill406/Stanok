# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Background generation worker (GUI never blocks on generate_documents)."""

from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from ..engine.render import RenderError
from ..engine.resolve import ResolveError
from ..engine.schema import SchemaError
from ..services.generate import (
    GenerateCommand,
    GenerateReport,
    TemplateError,
    generate_documents,
)
from ..services.storage import ProjectStore, StorageError

logger = logging.getLogger(__name__)


class GenerateWorker(QThread):
    """Run generate_documents off the GUI thread; talk via signals only."""

    progressed = pyqtSignal(int, int)  # (created, total)
    finished = pyqtSignal(object)  # GenerateReport
    failed = pyqtSignal(str)  # error text

    def __init__(
        self,
        cmd: GenerateCommand,
        store: ProjectStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._cmd = cmd
        self._store = store
        self._cancel = False

    def request_cancel(self) -> None:
        """Ask the worker to stop after the current document."""
        self._cancel = True

    def _on_progress(self, created: int, total: int) -> bool:
        self.progressed.emit(created, total)
        return self._cancel

    def run(self) -> None:
        self._execute()  # pragma: no cover - QThread body untraceable, see _execute test

    def _execute(self) -> None:
        """Generate body (also callable directly in tests, same-thread)."""
        logger.debug(
            f"worker starting: ref={self._cmd.project_ref} "
            f"template={self._cmd.template or 'default'}"
        )
        try:
            report: GenerateReport = generate_documents(
                self._cmd, store=self._store, progress=self._on_progress
            )
        except (
            TemplateError,
            StorageError,
            ResolveError,
            RenderError,
            SchemaError,
        ) as e:
            logger.error(f"worker failed: {e}", exc_info=True)
            self.failed.emit(str(e))
            return
        except Exception as e:
            logger.critical(
                f"worker unexpected failure: {e}", exc_info=True
            )
            self.failed.emit(str(e))
            return
        logger.debug(
            f"worker finished: created={report.created} "
            f"errors={len(report.errors)}"
        )
        self.finished.emit(report)
