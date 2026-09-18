# -*- coding: utf-8 -*-
"""Root conftest: put src/ layout on sys.path so `import docxforge` works."""
import os
import sys

# Headless-first: Qt renders offscreen so the suite runs without a display.
# An explicitly exported QT_QPA_PLATFORM is respected (setdefault).
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
