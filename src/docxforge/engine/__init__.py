# -*- coding: utf-8 -*-
"""docxforge engine — template rendering, XML utilities, and formatting."""

from .renderer import Renderer
from .xml_utils import run_text, set_run_text, clone_run_with_text, clone_element, row_contains_placeholder, row_has_placeholders
from .merge import merge_and_replace_paragraph, expand_table_cycle
from .formatting import compute_aggregation, format_counter, format_today
