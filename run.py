# -*- coding: utf-8 -*-
"""Станок entry point."""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'docxforge.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
    ]
)

# Ensure project root and src layout are on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from docxforge.gui.main_window import run

if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        logging.exception("Fatal error in Станок")
        sys.exit(1)
