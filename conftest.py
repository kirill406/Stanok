# -*- coding: utf-8 -*-
"""Root conftest: put src/ layout on sys.path so `import docxforge` works."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
