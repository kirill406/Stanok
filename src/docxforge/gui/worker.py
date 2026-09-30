# -*- coding: utf-8 -*-
"""Background workers for long GUI operations (M10).

Engine calls run in a QThread so the main (GUI) thread keeps pumping
events; cancellation is cooperative and therefore HONEST: it takes
effect between jobs, never in the middle of an engine call (the engine
has no interruption checkpoints — a mid-call "cancel" would be fake).
Single-document paths stay synchronous on purpose for the same reason.
"""

import logging
from functools import partial
from typing import Callable, List, Tuple

from PyQt5.QtCore import QThread, pyqtSignal


logger = logging.getLogger(__name__)


class GenerateWorker(QThread):
    """Run a list of zero-arg job thunks off the GUI thread.

    Signals:
        progressed(int, str): job index and label when a job starts.
        done(list): ``[(label, result, error)]`` when all jobs finish
            or cancellation was requested between jobs.
    """

    progressed = pyqtSignal(int, str)
    done = pyqtSignal(list)

    def __init__(self, jobs: List[Tuple[str, Callable[[], object]]],
                 parent=None):
        super().__init__(parent)
        self._jobs = list(jobs)
        self._cancel_requested = False

    def request_cancel(self):
        """Ask the worker to stop after the current job (thread-safe)."""
        self._cancel_requested = True

    def run(self):  # noqa: D102 (Qt override)
        results = []
        for index, (label, job) in enumerate(self._jobs):
            if self._cancel_requested:
                logger.info('GenerateWorker cancelled after %d job(s)',
                            len(results))
                break
            self.progressed.emit(index, label)
            try:
                results.append((label, job(), None))
            except Exception as e:  # noqa: BLE001 (report, don't crash)
                logger.exception(f'Background job {label!r} failed: {e}')
                results.append((label, None, str(e)))
        self.done.emit(results)


def project_job(project_path: str, num_docs: int):
    """Zero-arg thunk factory: generate documents for one project."""
    from docxforge.generate import generate_project
    return partial(generate_project, project_path, num_docs=num_docs)
