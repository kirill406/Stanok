# -*- coding: utf-8 -*-
"""DocxForge entry point."""

import sys
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('docxforge.log', encoding='utf-8')
    ]
)

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docxforge.gui.main_window import run

if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        logging.exception("Fatal error in DocxForge")
        sys.exit(1)
