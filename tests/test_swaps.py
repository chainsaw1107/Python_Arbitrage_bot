"""
Test that the exchange swap functionality works againsta  local fork.
"""

import pytest

from olas_arbitrage.utils import get_logger
from tests.constants import EXCHANGES, FORK_PARAMS


@pytest.mark.parametrize("name", EXCHANGES)
def test_exchange_can_buy(name, local_fork):
    """
    Test that the exchange can buy.
    """
    exchange, kwargs = EXCHANGES[name]
    amount, decimals = 0.001, 3
    if exchange.can_fork:
        block_no, rpc_url = FORK_PARAMS[name]
        local_fork.fork_url = rpc_url
        local_fork.fork_block_number = block_no
        local_fork.stop()
        local_fork.run()
        kwargs["rpc_url"] = f"{local_fork.host}:{local_fork.port}"
        amount, decimals = 10, 0

    exchange = exchange(logger=get_logger(), **kwargs)
    token_a_bal, token_b_bal, _ = exchange.get_balances()

    # we now check that we can swap from token a to token b

    rate = exchange.get_price(
        input_token_address=exchange.token_a.address,
        output_token_address=exchange.token_b.address,
        amount=amount,
    )
    exchange.buy(
        token_a=exchange.token_a.address,
        token_b=exchange.token_b.address,
        amount=amount * rate,  # the amount to pay in token b
    )

    new_token_a_bal, new_token_b_bal, _ = exchange.get_balances()
    assert new_token_a_bal > token_a_bal
    assert new_token_b_bal < token_b_bal
    diff_token_a = new_token_a_bal - token_a_bal
    assert round(diff_token_a, decimals) == round(amount * 0.99, decimals)


@pytest.mark.parametrize("name", EXCHANGES)
def test_exchange_can_sell(name, local_fork):
    """
    Tets that the exchange can sell.
    """
    exchange, kwargs = EXCHANGES[name]
    amount, decimals = 0.005, 3
    if exchange.can_fork:
        block_no, rpc_url = FORK_PARAMS[name]
        local_fork.fork_url = rpc_url
        local_fork.fork_block_number = block_no
        local_fork.stop()
        local_fork.run()
        kwargs["rpc_url"] = f"{local_fork.host}:{local_fork.port}"
        amount, decimals = 10, 0
    exchange = exchange(logger=get_logger(), **kwargs)
    token_a_bal, token_b_bal, _ = exchange.get_balances()

    # we now check that we can swap from token a to token b
    exchange.sell(
        token_a=exchange.token_a.address,
        token_b=exchange.token_b.address,
        amount=amount,  # the amount to pay in token a
    )

    new_token_a_bal, new_token_b_bal, _ = exchange.get_balances()
    assert new_token_a_bal < token_a_bal
    assert new_token_b_bal > token_b_bal
    diff_token_a = new_token_a_bal - token_a_bal
    assert round(diff_token_a, decimals) == -amount
