"""
Module for the conftest
"""

import pytest

from tests.constants import DEFAULT_FORK_BLOCK_NUMBER, TESTNET_RPC_URL
from tests.local_fork import LocalFork, get_unused_port


@pytest.fixture
def local_fork():
    """Use a local fork to test contract calls."""
    fork = LocalFork(TESTNET_RPC_URL, DEFAULT_FORK_BLOCK_NUMBER, port=get_unused_port())
    fork.run()
    yield fork
    fork.stop()


@pytest.fixture
def local_fork_2():
    """Use a local fork to test contract calls."""
    fork = LocalFork(TESTNET_RPC_URL, DEFAULT_FORK_BLOCK_NUMBER, port=get_unused_port())
    fork.run()
    yield fork
    fork.stop()
