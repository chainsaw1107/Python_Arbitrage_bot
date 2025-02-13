"""
Test the cli functionality.
"""

import pytest
from click.testing import CliRunner

from olas_arbitrage.cli import cli
from tests.constants import CONFIG_FILES


def test_check_command():
    """Test if the cli tool executes."""
    runner = CliRunner()
    result = runner.invoke(cli, ["check"])
    assert result.exit_code == 0
    assert "Initializing Balancer Python API" in result.output


@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_check_command_configs(config_file):
    """Test if the cli tool executes."""
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--config-file", config_file])
    assert result.exit_code == 0
