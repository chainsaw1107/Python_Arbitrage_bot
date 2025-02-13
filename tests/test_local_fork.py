"""
Test that the local fork works.
"""
import requests

from tests.constants import DEFAULT_FORK_BLOCK_NUMBER


def test_local_fork(local_fork):
    """Test that the local fork is running."""
    assert local_fork.is_ready()


def test_get_block_number(local_fork):
    """Test that the local fork is running."""
    res = requests.post(
        f"{local_fork.host}:{local_fork.port}",
        json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
        timeout=1,
    )
    assert res.status_code == 200
    assert int(res.json()["result"], 16) == DEFAULT_FORK_BLOCK_NUMBER
