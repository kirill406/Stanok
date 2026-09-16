# -*- coding: utf-8 -*-
"""Shared GUI dialogs: multi-directory selection (Qt has no
``QFileDialog.getExistingDirectoryList`` static)."""

import logging
from typing import List, Optional

from PyQt5.QtWidgets import QFileDialog, QListView, QTreeView, QWidget

from docxforge.gui.strings import STRINGS


logger = logging.getLogger(__name__)


def configure_multiselect(dialog: QFileDialog) -> QFileDialog:
    """Turn a QFileDialog into a multi-directory picker (in place)."""
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    # Native Windows dialog cannot multi-select directories.
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    list_view = dialog.findChild(QListView, 'listView')
    if list_view is not None:
        list_view.setSelectionMode(list_view.MultiSelection)
    tree_view = dialog.findChild(QTreeView, 'treeView')
    if tree_view is not None:
        tree_view.setSelectionMode(tree_view.MultiSelection)
    return dialog


def get_existing_directory_list(
    parent: Optional[QWidget] = None,
    caption: Optional[str] = None,
    start_dir: str = '',
) -> List[str]:
    """Select multiple directories; returns the chosen paths (may be empty)."""
    dialog = QFileDialog(parent, caption or STRINGS['dlg_select_dirs'],
                         start_dir)
    configure_multiselect(dialog)
    if dialog.exec():
        selected = [str(p) for p in dialog.selectedFiles()]
        logger.info('Selected %d directorie(s)', len(selected))
        return selected
    return []
