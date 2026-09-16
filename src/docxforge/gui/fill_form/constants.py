# -*- coding: utf-8 -*-
"""Shared constants and type mappings for the fill form."""

from docxforge.engine.schema import FieldType
from ..strings import STRINGS

FIELD_TYPES = [
    STRINGS['field_type_constant'],
    STRINGS['field_type_table'],
    STRINGS['field_type_counter'],
    STRINGS['field_type_today'],
    STRINGS['field_type_image'],
]

FIELD_TYPES_ENUM = {
    STRINGS['field_type_constant']: FieldType.CONSTANT,
    STRINGS['field_type_table']: FieldType.TABLE,
    STRINGS['field_type_counter']: FieldType.COUNTER,
    STRINGS['field_type_today']: FieldType.TODAY,
    STRINGS['field_type_image']: FieldType.IMAGE,
}
