# -*- coding: utf-8 -*-
"""pytest-qt configuration and shared fixtures for GUI tests."""

import os
import tempfile
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with fixture data copied."""
    from tests.create_fixtures import create_all_fixtures
    
    # Create fixtures in temp directory
    fixtures_dir = tmp_path / "fixtures"
    create_all_fixtures(fixtures_dir)
    
    # Copy the all_basic_fields fixture as a project
    project_dir = tmp_path / "test_project"
    shutil.copytree(fixtures_dir / "all_basic_fields", project_dir)
    
    return project_dir


@pytest.fixture
def sample_project(temp_project_dir):
    """Return path to a ready-to-use test project."""
    return str(temp_project_dir)


# Configure pytest-qt
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "gui: mark test as requiring GUI (Qt)"
    )