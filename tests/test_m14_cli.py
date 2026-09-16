# -*- coding: utf-8 -*-
"""Regression tests for 001-review M14 (CLI validation, exit codes, stderr).

M14: --field without --field-type, bad int(start)/multiplier,
unknown field type -> Russian error + non-zero exit, errors on stderr.
"""
import argparse
import os

import pytest

from docxforge.cli.commands import cmd_configure, cmd_scan
from docxforge.cli.helpers import _load_project
from docxforge.engine.schema import Project, create_project


def _ns(project_dir, **kw):
    base = dict(project_dir=project_dir, template='t.docx', field=None,
                field_type=None, value=None, column=None, linked_to=None,
                start=None, format=None, cycle=None, aggregation=None,
                multiplier=None)
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture()
def project_dir(tmp_path):
    d = str(tmp_path / 'proj')
    create_project(d)
    return d


class TestM14ConfigureValidation:
    def test_m14_field_without_type_exits_2_on_stderr(
            self, project_dir, capsys):
        with pytest.raises(SystemExit) as ei:
            cmd_configure(_ns(project_dir, field='name'))
        assert ei.value.code == 2
        out, err = capsys.readouterr()
        assert out == ''
        assert 'field-type' in err

    def test_m14_type_without_field_warns_but_succeeds(
            self, project_dir, capsys):
        cmd_configure(_ns(project_dir, field_type='constant',
                           value='x'))
        out, err = capsys.readouterr()
        assert 'без --field' in err
        prj = Project.from_file(
            os.path.join(project_dir, 'проект.docxforge'))
        assert prj.templates['t.docx'].fields == {}

    def test_m14_bad_start_exits_2(self, project_dir, capsys):
        with pytest.raises(SystemExit) as ei:
            cmd_configure(_ns(project_dir, field='num',
                               field_type='counter', start='abc'))
        assert ei.value.code == 2
        out, err = capsys.readouterr()
        assert out == ''
        assert 'start' in err

    def test_m14_good_counter_configured(self, project_dir, capsys):
        cmd_configure(_ns(project_dir, field='num', field_type='counter',
                           start='5', format='0001'))
        capsys.readouterr()
        prj = Project.from_file(
            os.path.join(project_dir, 'проект.docxforge'))
        fm = prj.templates['t.docx'].fields['num']
        assert fm.start == 5

    def test_m14_unknown_type_exits_1_on_stderr(
            self, project_dir, capsys):
        with pytest.raises(SystemExit) as ei:
            cmd_configure(_ns(project_dir, field='x',
                               field_type='bogus'))
        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ''
        assert 'bogus' in err

    def test_m14_bad_multiplier_exits_2(self, project_dir, capsys):
        with pytest.raises(SystemExit) as ei:
            cmd_configure(_ns(
                project_dir, aggregation=['total', 'sum_multiply',
                                          's.xlsx', 'price'],
                multiplier='xyz'))
        assert ei.value.code == 2
        out, err = capsys.readouterr()
        assert out == ''
        assert 'multiplier' in err


class TestM14LoadAndScanErrors:
    def test_m14_missing_project_exits_1_on_stderr(
            self, tmp_path, capsys):
        with pytest.raises(SystemExit) as ei:
            _load_project(str(tmp_path / 'nope'))
        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ''
        assert err != ''

    def test_m14_scan_missing_template_exits_1(
            self, project_dir, capsys):
        args = argparse.Namespace(project_dir=project_dir,
                                  template='missing.docx')
        with pytest.raises(SystemExit) as ei:
            cmd_scan(args)
        assert ei.value.code == 1
        out, err = capsys.readouterr()
        assert out == ''
        assert 'missing.docx' in err
