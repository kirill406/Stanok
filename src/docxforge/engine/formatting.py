# -*- coding: utf-8 -*-
"""Formatting utilities: aggregations, counters, and date formatting."""

from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

from .schema import AggregationMapping, AggregationFunction


def compute_aggregation(agg: AggregationMapping,
                        table_data: List[Dict[str, str]]) -> str:
    try:
        values = []
        for row in table_data:
            val = row.get(agg.column, '0').replace(',', '.').replace(' ', '')
            try:
                values.append(float(val))
            except ValueError:
                continue
        if not values:
            return '0'
        if agg.function == AggregationFunction.SUM:
            result = sum(values)
        elif agg.function == AggregationFunction.COUNT:
            result = len(values)
        elif agg.function == AggregationFunction.MAX:
            result = max(values)
        elif agg.function == AggregationFunction.MIN:
            result = min(values)
        else:
            result = sum(values)
        if agg.function == AggregationFunction.SUM_MULTIPLY and agg.multiplier:
            result *= agg.multiplier
        if result == int(result):
            return str(int(result))
        return '{:.2f}'.format(result).replace('.', ',')
    except Exception as e:
        logger.exception(f'Aggregation {agg.function} failed: {e}')
        return '0'


def format_counter(value: int, fmt: str) -> str:
    if fmt and fmt.startswith('0'):
        return str(value).zfill(len(fmt))
    return str(value)


def format_today(fmt: str, dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    months_ru = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    result = fmt
    result = result.replace('month', months_ru[dt.month - 1])
    result = result.replace('MM:название_месяца', months_ru[dt.month - 1])
    result = result.replace('dd', dt.strftime('%d'))
    result = result.replace('MM', dt.strftime('%m'))
    result = result.replace('yyyy', dt.strftime('%Y'))
    result = result.replace('HH', dt.strftime('%H'))
    result = result.replace('mm', dt.strftime('%M'))
    result = result.replace('ss', dt.strftime('%S'))
    return result
