# -*- coding: utf-8 -*-
"""Engine error codes with a single code -> message mapping.

Central place for engine failure reasons so GUI/CLI can reuse the same
texts instead of scattering literals across the engine. Message templates
use ``str.format`` placeholders documented per code.
"""

import logging

logger = logging.getLogger(__name__)

# Sequential source has no data rows for the first document.
EMPTY_SEQUENTIAL = 'EMPTY_SEQUENTIAL'
# Sequential source exhausted at a resume offset (rows/start known).
TABLE_EXHAUSTED = 'TABLE_EXHAUSTED'
# Render loop produced zero documents (generic, kept in English for
# backward compatibility with existing callers/tests).
NO_DOCUMENTS_GENERATED = 'NO_DOCUMENTS_GENERATED'

ERROR_MESSAGES = {
    EMPTY_SEQUENTIAL: 'Таблица «{source}» не имеет данных для генерации.',
    TABLE_EXHAUSTED: 'Таблица «{source}» исчерпана (строк: {rows}, начало: {start}).',
    NO_DOCUMENTS_GENERATED: 'No documents generated (check data sources and batch config)',
}


class EngineError(Exception):
    """Base engine exception carrying a machine-readable ``code``."""

    def __init__(self, message: str = '', code=None):
        super().__init__(message)
        self.code = code


class RenderError(EngineError):
    """Render-path failures (empty/exhausted sequential sources, ...)."""


def message_for_code(code: str, **kwargs) -> str:
    """Return the formatted message template for ``code``.

    Unknown codes fall back to the code itself so callers never crash
    on message lookup.
    """
    template = ERROR_MESSAGES.get(code)
    if template is None:
        logger.warning('Unknown engine error code: %r', code)
        return str(code)
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.warning('Missing placeholder %s for error code %s', e, code)
        return template
