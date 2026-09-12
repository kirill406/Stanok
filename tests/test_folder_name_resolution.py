# -*- coding: utf-8 -*-
"""Unit tests for resolve_folder_name_template function."""

import pytest
from datetime import datetime
from docxforge.engine.render_loop import resolve_folder_name_template


class TestResolveFolderNameTemplate:
    """Tests for resolve_folder_name_template function."""

    def test_empty_template(self):
        """Empty template returns empty string."""
        assert resolve_folder_name_template('') == ''
        assert resolve_folder_name_template(None) == ''

    def test_no_placeholders(self):
        """Template without placeholders returns as-is."""
        result = resolve_folder_name_template('simple_folder')
        assert result == 'simple_folder'

    def test_constant_field_resolution(self):
        """Constants are resolved from constants dict."""
        template = 'Клиенты/{{client_name}}/{{year}}'
        constants = {'client_name': 'ООО Альфа', 'year': '2024'}
        result = resolve_folder_name_template(template, constants=constants)
        assert result == 'Клиенты/ООО Альфа/2024'

    def test_row_data_field_resolution(self):
        """Row data fields are resolved from row_data dict."""
        template = 'Договоры/{{client_name}}/{{contract_num}}'
        row_data = {'client_name': 'ООО Бета', 'contract_num': '123'}
        result = resolve_folder_name_template(template, row_data=row_data)
        assert result == 'Договоры/ООО Бета/123'

    def test_user_values_field_resolution(self):
        """User values are resolved from user_values dict."""
        template = 'Проекты/{{project_name}}/{{manager}}'
        user_values = {'project_name': 'Сайт', 'manager': 'Иванов'}
        result = resolve_folder_name_template(template, user_values=user_values)
        assert result == 'Проекты/Сайт/Иванов'

    def test_priority_constants_row_user(self):
        """Priority: constants < row_data < user_values."""
        template = '{{field}}'
        constants = {'field': 'constant_value'}
        row_data = {'field': 'row_value'}
        user_values = {'field': 'user_value'}
        result = resolve_folder_name_template(template, constants=constants, row_data=row_data, user_values=user_values)
        # user_values should win
        assert result == 'user_value'

    def test_today_field_resolution(self):
        """Today fields with format are resolved."""
        template = 'Отчеты/{{today:yyyy}}/{{today:MM}}'
        now = datetime(2024, 9, 15)
        result = resolve_folder_name_template(template, now=now)
        assert result == 'Отчеты/2024/09'

    def test_today_field_default_format(self):
        """Today field without format uses default dd.MM.yyyy."""
        template = 'Дни/{{today}}'
        now = datetime(2024, 9, 15)
        result = resolve_folder_name_template(template, now=now)
        assert result == 'Дни/15.09.2024'

    def test_today_field_month_format(self):
        """Today field with month format (Russian month name)."""
        template = 'Месяцы/{{today:MM:название_месяца}}'
        now = datetime(2024, 9, 15)
        result = resolve_folder_name_template(template, now=now)
        assert result == 'Месяцы/сентября'

    def test_counter_field_resolution(self):
        """Counter field is resolved when counter_value provided."""
        template = 'Номера/{{counter}}'
        result = resolve_folder_name_template(template, counter_value=5, counter_format='0000')
        assert result == 'Номера/0005'

    def test_counter_field_not_provided(self):
        """Counter field not resolved when counter_value is None."""
        template = 'Номера/{{counter}}'
        result = resolve_folder_name_template(template, counter_value=None)
        assert result == 'Номера/'

    def test_mixed_fields(self):
        """Multiple field types in one template."""
        template = '{{year}}/{{client_name}}/Договор_{{counter}}'
        constants = {'year': '2024'}
        row_data = {'client_name': 'ООО Гамма'}
        now = datetime(2024, 9, 15)
        result = resolve_folder_name_template(
            template,
            constants=constants,
            row_data=row_data,
            counter_value=1,
            counter_format='0001',
            now=now)
        assert result == '2024/ООО Гамма/Договор_0001'

    def test_missing_field_replaced_with_empty(self):
        """Missing fields are replaced with empty string."""
        template = 'Папка/{{missing_field}}/конец'
        result = resolve_folder_name_template(template)
        assert result == 'Папка//конец'

    def test_placeholder_with_spaces(self):
        """Placeholders with spaces {{ field }} are handled."""
        template = 'Тест/{{ field }}/конец'
        constants = {'field': 'значение'}
        result = resolve_folder_name_template(template, constants=constants)
        assert result == 'Тест/значение/конец'

    def test_nested_path_creation(self):
        """Resolved template can create nested paths."""
        template = 'Год_{{today:yyyy}}/Месяц_{{today:MM}}/День_{{today:dd}}/{{client}}'
        constants = {'client': 'Клиент_1'}
        now = datetime(2024, 9, 15)
        result = resolve_folder_name_template(template, constants=constants, now=now)
        assert result == 'Год_2024/Месяц_09/День_15/Клиент_1'

    def test_special_characters_in_values(self):
        """Special characters in field values are preserved."""
        template = '{{name}}'
        constants = {'name': 'ООО "Ромашка" (ИП Петров)'}
        result = resolve_folder_name_template(template, constants=constants)
        assert result == 'ООО "Ромашка" (ИП Петров)'

    def test_unicode_paths(self):
        """Unicode folder names work correctly."""
        template = 'Клиенты/{{name}}/Документы'
        row_data = {'name': 'Иванов Иван Иванович'}
        result = resolve_folder_name_template(template, row_data=row_data)
        assert result == 'Клиенты/Иванов Иван Иванович/Документы'

    def test_multiple_same_field(self):
        """Multiple occurrences of same field are all replaced."""
        template = '{{id}}/{{id}}/{{id}}'
        constants = {'id': 'ABC123'}
        result = resolve_folder_name_template(template, constants=constants)
        assert result == 'ABC123/ABC123/ABC123'

    def test_whitespace_in_template(self):
        """Whitespace in template is preserved."""
        template = '  Папка / {{name}}  '
        constants = {'name': 'Тест'}
        result = resolve_folder_name_template(template, constants=constants)
        assert result == '  Папка / Тест  '


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
