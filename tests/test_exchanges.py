"""
Test the functionality of the exchanges module.
"""


from olas_arbitrage.exchanges.balancer import BalancerExchange
from olas_arbitrage.exchanges.base import DefiExchange
from olas_arbitrage.exchanges.jupitar_exchange import JupitarExchange
from olas_arbitrage.exchanges.uniswap_router import UniswapRouterExchange
from olas_arbitrage.exchanges.uniswap_v2 import UniswapV2Exchange
from olas_arbitrage.utils import get_logger
from tests.constants import (
    BALANCER_EXCHANGE_KWARGS,
    JUPITAR_EXCHANGE_PARAMS,
    UNISWAP_ROUTER_KWARGS,
    UNISWAP_V2_KWARGS,
)

DEFAULT_AMOUNT = 10


class BaseTestExchanges:
    """
    Implements base test class for exchanges.
    """

    exchange = DefiExchange(logger=get_logger(), **UNISWAP_V2_KWARGS)
    token_a_address = UNISWAP_V2_KWARGS["token_a"]
    token_b_address = UNISWAP_V2_KWARGS["token_b"]

    def test_get_bid_price(self):
        """
        Test get_bid_price method.
        """
        self.exchange.get_price(
            input_token_address=self.token_a_address,
            output_token_address=self.token_b_address,
            amount=DEFAULT_AMOUNT,
        )

    def test_get_ask_price(self):
        """
        Test get_ask_price method.
        """
        self.exchange.get_price(
            input_token_address=self.token_b_address,
            output_token_address=self.token_a_address,
            amount=DEFAULT_AMOUNT,
        )


class TestUniswapExchange(BaseTestExchanges):
    """
    Test the UniswapExchange class.
    """

    exchange = UniswapV2Exchange(logger=get_logger(), **UNISWAP_V2_KWARGS)


class TestBalancerExchange(BaseTestExchanges):
    """
    Test the BalancerExchange class.
    """

    exchange = BalancerExchange(logger=get_logger(), **BALANCER_EXCHANGE_KWARGS)
    token_a_address = BALANCER_EXCHANGE_KWARGS["token_a"]
    token_b_address = BALANCER_EXCHANGE_KWARGS["token_b"]


class TestSolanaExchange(BaseTestExchanges):
    """Test the solana."""

    exchange = JupitarExchange(logger=get_logger(), **JUPITAR_EXCHANGE_PARAMS)
    token_a_address = JUPITAR_EXCHANGE_PARAMS["token_a"]["address"]
    token_b_address = JUPITAR_EXCHANGE_PARAMS["token_b"]["address"]


class TestUniswapRouterExchange(BaseTestExchanges):
    """
    Test the UniswapExchange class.
    """

    exchange = UniswapRouterExchange(logger=get_logger(), **UNISWAP_ROUTER_KWARGS)

    def teardown_class(self):
        """Tear down the class."""
        self.exchange.teardown()
