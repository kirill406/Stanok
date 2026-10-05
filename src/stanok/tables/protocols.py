from typing import Protocol, Any
from pathlib import Path


class TableReader(Protocol):
    def read(self, path: Path) -> list[dict[str, Any]]:
        """Читает таблицу, возвращает список строк (dict: колонка -> значение).

        Все строки возвращаются (включая пустые — с None значениями).
        Первая строка файла — заголовки.
        """