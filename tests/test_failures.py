"""
Test that the exchange swap handles failures corretly.
"""

from unittest.mock import MagicMock

import pytest

from olas_arbitrage.utils import get_logger
from tests.constants import EXCHANGES, FORK_PARAMS


@pytest.mark.skip(reason="This test is not implemented yet.")
@pytest.mark.parametrize("name", EXCHANGES)
def test_exchange_can_handle_replacement_tx_underpriced(name, local_fork):
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
    else:
        return

    exchange = exchange(logger=get_logger(), **kwargs)
    token_a_bal, token_b_bal, _ = exchange.get_balances()

    # we now check that we can swap from token a to token b

    mocker = MagicMock()
    mocker.return_value = lambda: Exception(
        {"code": -32000, "message": "replacement transaction underpriced"}
    )

    rate = exchange.get_price(
        input_token_address=exchange.token_a.address,
        output_token_address=exchange.token_b.address,
        amount=amount,
    )
    # theoretically we should be able to mock the exchange as so exchange.web3.eth.get_transaction_receipt = mocker

    # # the following function call should fail with  Transaction failed with error:
    # # this is the error from the rpc; {'code': -32000, 'message': 'replacement transaction underpriced'}
    # # we should fail this status with a failure exchange.web3.eth.get_transaction_receipt(tx_hash).status
    exchange.buy(
        token_a=exchange.token_a.address,
        token_b=exchange.token_b.address,
        amount=amount * rate,  # the amount to pay in token b
    )

    # with pytest.raises

    new_token_a_bal, new_token_b_bal, _ = exchange.get_balances()
    assert new_token_a_bal > token_a_bal
    assert new_token_b_bal < token_b_bal
    diff_token_a = new_token_a_bal - token_a_bal
    assert round(diff_token_a, decimals) == amount
