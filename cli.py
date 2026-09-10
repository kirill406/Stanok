# -*- coding: utf-8 -*-
"""Станок CLI entry point."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docxforge.cli import main
if __name__ == '__main__':
    main()
