"""Tests for the scaffold entry point."""

import pytest

from app.main import main
from app.version import __version__


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_scaffold_exits_non_zero_until_implemented():
    assert main(["--config", "missing.yaml"]) == 1
