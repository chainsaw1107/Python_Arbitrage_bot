"""
Test that the strategy can be initialized.
"""

import pytest

from olas_arbitrage.strategy import Strategy
from olas_arbitrage.utils import get_config, get_logger
from tests.constants import CONFIG_FILES, EXCHANGES, FORK_PARAMS


@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_strategy_initalises(config_file):
    """
    Test that the strategy can be initialized.
    """
    logger = get_logger()
    chain_config = get_config(config_file)
    strategy = Strategy(
        chain_config=chain_config,
        logger=logger,
    )
    assert strategy


@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_strategy_get_rates(config_file):
    """
    Test that the strategy can be initialized.
    """
    logger = get_logger()
    chain_config = get_config(config_file)
    strategy = Strategy(
        chain_config=chain_config,
        logger=logger,
    )
    (best_bid, sell_exchange), (best_ask, buy_exchange) = strategy.get_rates()
    assert best_bid > 0
    assert best_ask > 0
    assert sell_exchange
    assert buy_exchange


@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_strategy_get_native_balances(config_file):
    """
    Test that the strategy can be initialized.
    """
    logger = get_logger()
    chain_config = get_config(config_file)
    strategy = Strategy(
        chain_config=chain_config,
        logger=logger,
    )
    assert strategy.has_sufficient_balance(native_only=True)


@pytest.mark.parametrize("config_file", CONFIG_FILES)
def test_strategy_get_all_balances(
    config_file,
):
    """
    Test that the strategy can be initialized.
    """

    logger = get_logger()
    strategy = Strategy(
        chain_config=get_config(config_file),
        logger=logger,
        execution_amount_token_a=1,
    )
    strategy.get_rates()
    assert strategy.has_sufficient_balance()


def test_does_strategy_close_arb(
    local_fork, local_fork_2
):  # pylint: disable=too-many-locals
    """
    Test that the strategy actually closes the arb.
    """
    _, exchange_1_kwargs = EXCHANGES["balancer"]
    block_no, rpc_url = FORK_PARAMS["balancer"]
    local_fork.fork_url = rpc_url
    local_fork.fork_block_number = block_no
    local_fork.stop()
    local_fork.run()
    exchange_1_kwargs["rpc_url"] = f"{local_fork.host}:{local_fork.port}"

    # we setup the second exchange
    _, exchange_2_kwargs = EXCHANGES["uniswap_v2"]
    block_no, rpc_url = FORK_PARAMS["uniswap_v2"]

    local_fork_2.fork_url = rpc_url
    local_fork_2.fork_block_number = block_no
    local_fork_2.stop()
    local_fork_2.run()
    exchange_2_kwargs["rpc_url"] = f"{local_fork_2.host}:{local_fork_2.port}"

    strategy = Strategy(
        chain_config={
            "exchange_1": exchange_1_kwargs,
            "exchange_2": exchange_2_kwargs,
        },
        logger=get_logger(),
        min_profit=0,
        execution_amount_token_a=100,
    )

    (rate_2, sell_exchange), (rate_1, _) = strategy.get_rates()
    delta = (rate_2 - rate_1) / rate_1
    assert delta > 0.0
    token_a_bal, token_b_bal, _ = sell_exchange.get_balances()

    strategy.run(
        sell_enabled=True,
        buy_enabled=True,
        async_execution=False,
    )

    (rate_2, sell_exchange), (rate_1, _) = strategy.get_rates()
    new_delta = (rate_2 - rate_1) / rate_1

    new_token_a_bal, new_token_b_bal, _ = sell_exchange.get_balances()

    assert new_delta < delta
    assert new_token_a_bal > token_a_bal
    assert new_token_b_bal < token_b_bal
