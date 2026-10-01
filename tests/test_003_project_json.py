# -*- coding: utf-8 -*-
"""Phase 3 (003-json): Project JSON validation / normalization tests."""

import copy
import json
import os

from docxforge.engine.schema import (
    normalize_project_json,
    validate_project_json,
)

SPEC_EXAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'specs', '003-json', 'project_generation.json')


def _load_example():
    with open(SPEC_EXAMPLE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _minimal_template(**overrides):
    tpl = {
        'fields': {
            'name': {'type': 'constant', 'value': 'x'},
        },
        'batch': {'sources': {}},
        'resume': {'last_counter_value': 0, 'sources': {},
                   'continue_from_last': False},
    }
    tpl.update(overrides)
    return tpl


# --- normative example ----------------------------------------------------


def test_project_json_valid_example_no_errors():
    data = _load_example()
    assert validate_project_json(data) == []


def test_project_json_example_round_trip_clean():
    data = _load_example()
    assert validate_project_json(normalize_project_json(data)) == []


def test_project_json_example_legacy_input_normalized():
    """Array + absolute paths + number + project_name → canonical dict."""
    data = _load_example()
    assert validate_project_json(data) == []
    norm = normalize_project_json(data)
    assert validate_project_json(norm) == []
    assert norm.get('project_name') == 'имя_проекта'
    assert 'templates_new' not in norm
    tpl = norm['templates']['договор 1.docx']
    # Dict version keeps its fields as-is.
    assert tpl['fields']['doc_number']['type'] == 'constant'
    assert tpl['batch']['filename_template'] == \
        '{{ фио_клиента }}{{ фио_поставщика }}'
    # Array version normalizes alongside: number→counter, abs→basename.
    tpl2 = norm['templates']['договор 2.docx']
    assert tpl2['fields']['doc_number']['type'] == 'counter'
    assert tpl2['batch']['sources']['клиенты.xlsx']['file'] == 'клиенты.xlsx'


# --- error classes --------------------------------------------------------


def test_project_json_missing_templates_reports_error():
    assert validate_project_json({}) != []
    assert validate_project_json({'templates': {}}) != []
    assert validate_project_json({'templates': []}) != []


def test_project_json_missing_fields_reports_error():
    data = {'templates': {'a.docx': {'batch': {'sources': {}}}}}
    errors = validate_project_json(data)
    assert any('fields' in e for e in errors)
    data2 = {'templates': {'a.docx': {'fields': {}}}}
    assert validate_project_json(data2) != []


def test_project_json_unknown_field_type_reports_error():
    data = {'templates': {
        'a.docx': _minimal_template(
            fields={'n': {'type': 'number', 'value': '1'}})}}
    errors = validate_project_json(data)
    assert any('type' in e and 'number' in e for e in errors)


def test_project_json_unknown_batch_mode_reports_error():
    data = {'templates': {
        'a.docx': _minimal_template(
            batch={'sources': {'s.xlsx': {'file': 's.xlsx',
                                          'mode': 'all_rows'}}})}}
    errors = validate_project_json(data)
    assert any('mode' in e and 'all_rows' in e for e in errors)


def test_project_json_absolute_paths_reports_error():
    data = {'templates': {
        '/c/User/inf/a.docx': _minimal_template(
            fields={'f': {'type': 'table', 'file': '/c/User/inf/s.xlsx',
                          'column': 'c'}},
            batch={'sources': {'s': {'file': 'C:\\data\\s.xlsx',
                                     'mode': 'constant'}},
                   'filename_template': '/c/User/inf/out/{{ f }}.docx'})}}
    errors = validate_project_json(data)
    assert any('template name' in e for e in errors)
    assert any('fields' in e and 'relative' in e for e in errors)
    assert any('sources' in e and 'relative' in e for e in errors)
    assert any('filename_template' in e for e in errors)


def test_project_json_table_field_requires_file_and_column():
    data = {'templates': {
        'a.docx': _minimal_template(
            fields={'f': {'type': 'table'}})}}
    errors = validate_project_json(data)
    assert any('file' in e for e in errors)
    assert any('column' in e for e in errors)


# --- legacy migration -----------------------------------------------------


def test_project_json_number_migrates_to_counter():
    data = {'templates': {
        'a.docx': _minimal_template(
            fields={'n': {'type': 'number', 'value': '5'}})}}
    assert validate_project_json(data) != []  # legacy is invalid as-is
    norm = normalize_project_json(data)
    assert norm['templates']['a.docx']['fields']['n']['type'] == 'counter'
    assert validate_project_json(norm) == []


def test_project_json_templates_new_array_migrates_to_dict():
    data = {
        'version': 2,
        'templates_new': [
            {'name': 'договор 1.docx',
             'path': '/c/User/inf/договор 1.docx',
             'fields': [{'name': 'org', 'type': 'constant', 'value': ''},
                        {'name': 'n', 'type': 'number', 'value': '1'}],
             'batch': {'sources': [
                 {'name': 'инфа.xlsx', 'file': 'инфа.xlsx',
                  'mode': 'single', 'continue_from_last': False}],
                       'filename_template': '/c/User/inf/out.docx'},
             'resume': {'last_counter_value': 0, 'sources': {},
                        'continue_from_last': False}},
        ],
    }
    norm = normalize_project_json(data)
    assert 'templates_new' not in norm
    assert 'договор 1.docx' in norm['templates']
    tpl = norm['templates']['договор 1.docx']
    assert set(tpl['fields']) == {'org', 'n'}
    assert tpl['fields']['n']['type'] == 'counter'
    assert tpl['batch']['sources']['инфа.xlsx']['mode'] == 'constant'
    assert tpl['batch']['filename_template'] == 'out.docx'
    assert validate_project_json(norm) == []


def test_project_json_legacy_batch_modes_migrated():
    data = {'templates': {
        'a.docx': _minimal_template(
            batch={'sources': {
                's1': {'file': 's1.xlsx', 'mode': 'all_rows'},
                's2': {'file': 's2.xlsx', 'mode': 'n_rows'}}})}}
    norm = normalize_project_json(data)
    assert norm['templates']['a.docx']['batch']['sources']['s1']['mode'] \
        == 'sequential'
    assert norm['templates']['a.docx']['batch']['sources']['s2']['mode'] \
        == 'sequential'
    assert validate_project_json(norm) == []


def test_project_json_resume_and_source_defaults_filled():
    data = {'templates': {'a.docx': {'fields': {
        'name': {'type': 'constant', 'value': 'x'}}, 'batch': {'sources': {
            's.xlsx': {'file': 's.xlsx', 'mode': 'sequential'}}}}}}
    norm = normalize_project_json(data)
    resume = norm['templates']['a.docx']['resume']
    assert resume['last_counter_value'] == 0
    assert resume['sources'] == {}
    assert 'continue_from_last' in resume
    src = norm['templates']['a.docx']['batch']['sources']['s.xlsx']
    assert src['continue_from_last'] is True
    assert validate_project_json(norm) == []


def test_project_json_absolute_file_relativized_to_basename():
    data = {'templates': {
        'a.docx': _minimal_template(
            fields={'f': {'type': 'table',
                          'file': '/c/User/inf/клиенты.xlsx',
                          'column': 'адрес'}})}}
    norm = normalize_project_json(data)
    assert norm['templates']['a.docx']['fields']['f']['file'] \
        == 'клиенты.xlsx'
    assert validate_project_json(norm) == []


def test_project_json_normalize_does_not_mutate_input():
    data = _load_example()
    snapshot = copy.deepcopy(data)
    normalize_project_json(data)
    assert data == snapshot


def test_project_json_legacy_full_round_trip_clean():
    data = {
        'templates_new': [
            {'name': '/c/User/inf/a.docx',
             'fields': [{'name': 'n', 'type': 'number'}],
             'batch': {'sources': [
                 {'name': 's.xlsx', 'file': '/c/User/inf/s.xlsx',
                  'mode': 'single'}]},
             'resume': {}},
        ],
    }
    norm = normalize_project_json(data)
    assert validate_project_json(norm) == []
    assert 'a.docx' in norm['templates']
