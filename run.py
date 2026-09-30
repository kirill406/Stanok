# -*- coding: utf-8 -*-
"""Станок entry point."""

import sys
import os
import logging

# Ensure project root and src layout are on path (needed for the import below)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Shared log file location: single constant APP_LOG_FILE (Home), no hardcode here.
from docxforge.app_logging import APP_LOG_FILE, setup_app_logging

setup_app_logging()
logging.getLogger(__name__).info('Application log: %s', APP_LOG_FILE)

from docxforge.gui.main_window import run

if __name__ == '__main__':
    try:
        run()
    except Exception as e:
        logging.exception(f"Fatal error in Станок: {e}")
        sys.exit(1)
