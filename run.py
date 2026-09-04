# -*- coding: utf-8 -*-
"""DocxForge entry point."""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docxforge.gui.main_window import run

if __name__ == '__main__':
    run()
