# Copyright (C) 2026 Kirill Borovoy
# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the Windows version resource for PyInstaller from pyproject.toml.

Usage: .venv/Scripts/python scripts/make-version-info.py [dest_file]
Default dest is build/version_info.txt (build/ is gitignored).
Pass the file to PyInstaller as --version-file before building the exe.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT / "build" / "version_info.txt"
NUMERIC = re.compile(r"(\d+)\.(\d+)\.(\d+)")

TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={nums},
    prodvers={nums},
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041904B0',
        [
          StringStruct('CompanyName', 'Kirill Borovoy'),
          StringStruct('FileDescription', 'Станок'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'Станок'),
          StringStruct('LegalCopyright', 'Copyright (C) 2026 Kirill Borovoy'),
          StringStruct('OriginalFilename', 'Станок.exe'),
          StringStruct('ProductName', 'Станок'),
          StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1049, 1200])])
  ]
)
"""


def numeric(version: str) -> tuple[int, int, int, int]:
    """Return the four-part version the Windows resource needs (pre-release tag dropped)."""
    match = NUMERIC.match(version)
    if match is None:
        raise ValueError(f"version is not MAJOR.MINOR.PATCH: {version}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch, 0


def main(dest: Path) -> Path:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        TEMPLATE.format(nums=numeric(version), version=version), encoding="utf-8"
    )
    return dest


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEST)
