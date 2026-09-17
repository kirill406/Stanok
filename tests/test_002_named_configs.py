# -*- coding: utf-8 -*-
"""002 named configs: per-project `<name>.docxforge`, migration, resolver.

- Generated projects carry `<folder>.docxforge` next to Данные/Шаблоны.
- On open the config migrates to `~/.docxforge` and is deleted from folder.
- Opening resolves folder-first, Home-second; saves go back to Home copy.

Run with: python -m pytest tests/test_002_named_configs.py -q
"""

import os

from docxforge import generate as gen_module


def _make_folder(base, name, with_config=None):
    project_dir = os.path.join(base, name)
    os.makedirs(os.path.join(project_dir, 'Данные'), exist_ok=True)
    os.makedirs(os.path.join(project_dir, 'Шаблоны'), exist_ok=True)
    if with_config:
        with open(os.path.join(project_dir, with_config), 'w',
                  encoding='utf-8') as f:
            f.write('{"version": 2, "templates": {}}')
    return project_dir


def test_resolve_prefers_folder_legacy_file(tmp_path):
    """проект.docxforge in folder wins over everything."""
    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    folder = _make_folder(str(tmp_path), 'Proj1', 'проект.docxforge')
    with open(os.path.join(home, 'Proj1.docxforge'), 'w') as f:
        f.write('{}')
    assert gen_module.resolve_project_file(folder, home).endswith(
        'проект.docxforge')


def test_resolve_single_folder_config_without_legacy(tmp_path):
    """Unmigrated generated folder opens via its named config."""
    folder = _make_folder(str(tmp_path), 'Proj1', 'Proj1.docxforge')
    assert gen_module.resolve_project_file(folder).endswith('Proj1.docxforge')


def test_resolve_home_fallback_after_migration(tmp_path):
    """Migrated folder (no config left) resolves to the Home copy."""
    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    folder = _make_folder(str(tmp_path), 'Proj1', 'Proj1.docxforge')
    migrated = gen_module.migrate_project_configs_to_home(folder, home)
    assert migrated == [os.path.join(home, 'Proj1.docxforge')]
    assert sorted(os.listdir(folder)) == ['Данные', 'Шаблоны']
    assert gen_module.resolve_project_file(folder, home) == migrated[0]


def test_resolve_none_without_any_config(tmp_path):
    """Empty folder resolves to None."""
    folder = _make_folder(str(tmp_path), 'Empty')
    assert gen_module.resolve_project_file(folder, str(tmp_path)) is None


def test_migrate_moves_all_configs_to_folder_name_and_gates(tmp_path):
    """All configs migrate under the folder name; folders w/o data untouched."""
    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    folder = _make_folder(str(tmp_path), 'Proj1', 'проект.docxforge')
    with open(os.path.join(folder, 'Other.docxforge'), 'w') as f:
        f.write('{}')
    migrated = gen_module.migrate_project_configs_to_home(folder, home)
    assert migrated == [os.path.join(home, 'Proj1.docxforge'),
                        os.path.join(home, 'Proj1 (1).docxforge')]
    assert sorted(os.listdir(folder)) == ['Данные', 'Шаблоны']

    plain = os.path.join(str(tmp_path), 'plain')
    os.makedirs(plain, exist_ok=True)
    with open(os.path.join(plain, 'X.docxforge'), 'w') as f:
        f.write('{}')
    assert gen_module.migrate_project_configs_to_home(plain, home) == []
    assert os.path.isfile(os.path.join(plain, 'X.docxforge'))


def test_migrate_collision_renames_new_copy(tmp_path):
    """Occupied Home name → migrated copy gets (1), source deleted."""
    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    with open(os.path.join(home, 'Proj1.docxforge'), 'wb') as f:
        f.write(b'OLD')
    folder = _make_folder(str(tmp_path), 'Proj1', 'Proj1.docxforge')
    migrated = gen_module.migrate_project_configs_to_home(folder, home)
    assert migrated == [os.path.join(home, 'Proj1 (1).docxforge')]
    with open(os.path.join(home, 'Proj1.docxforge'), 'rb') as f:
        assert f.read() == b'OLD'
    assert sorted(os.listdir(folder)) == ['Данные', 'Шаблоны']


def test_renderer_round_trips_through_home_copy(tmp_path, monkeypatch):
    """Open migrated folder via Renderer; save persists to the Home copy."""
    import sys
    sys.path.insert(0, 'src')
    from docxforge.engine.renderer import Renderer

    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    import docxforge.engine.schema as schema_module
    monkeypatch.setattr(schema_module, 'get_docxforge_home', lambda: home)
    folder = _make_folder(str(tmp_path), 'Proj1', 'Proj1.docxforge')
    gen_module.migrate_project_configs_to_home(folder, home)
    renderer = Renderer(folder, None)
    renderer.load_project()
    assert renderer.project_file == os.path.join(home, 'Proj1.docxforge')
    renderer.save_project()
    assert sorted(os.listdir(folder)) == ['Данные', 'Шаблоны']
    assert os.path.isfile(os.path.join(home, 'Proj1.docxforge'))


def test_is_project_folder_matrix(tmp_path):
    """Validation accepts legacy, named, and migrated folders."""
    home = str(tmp_path / 'home')
    os.makedirs(home, exist_ok=True)
    legacy = _make_folder(str(tmp_path), 'A', 'проект.docxforge')
    named = _make_folder(str(tmp_path), 'B', 'B.docxforge')
    migrated = _make_folder(str(tmp_path), 'C', 'C.docxforge')
    gen_module.migrate_project_configs_to_home(migrated, home)
    empty = _make_folder(str(tmp_path), 'D')
    assert gen_module.is_project_folder(legacy)
    assert gen_module.is_project_folder(named)
    assert gen_module.is_project_folder(migrated, home)
    assert not gen_module.is_project_folder(empty, home)
    assert not gen_module.is_project_folder(
        os.path.join(str(tmp_path), 'missing'), home)
