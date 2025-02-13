"""
Arbitrage Strategy Class.
"""

import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from multiprocessing.pool import ThreadPool

import requests
from web3.exceptions import BadFunctionCallOutput

from olas_arbitrage.constants import CHAIN_CONFIGS, DEFAULT_ENCODING
from olas_arbitrage.exchanges.balancer import BalancerExchange
from olas_arbitrage.exchanges.balancer_optimised import BalancerExchangeOptimised
from olas_arbitrage.exchanges.jupitar_exchange import JupitarExchange
from olas_arbitrage.exchanges.uniswap_router import UniswapRouterExchange
from olas_arbitrage.exchanges.uniswap_v2 import UniswapV2Exchange
from olas_arbitrage.utils import to_human_readable

MAX_GAS_PRICE = 70


EXCHANGES = {
    "balancer": BalancerExchange,
    "balancer_optimised": BalancerExchangeOptimised,
    "uniswap_v2": UniswapV2Exchange,
    "uniswap_router": UniswapRouterExchange,
    "jupitar": JupitarExchange,
}

NTFYY_URL = "https://ntfy.sh"
NTFY_CHANNEL = "crazy-french-igloo"


class Strategy:  # pylint: disable=too-many-instance-attributes
    """
    Strategy class to watch for arbitrage opportunities
    """

    rate_1 = None
    rate_2 = None

    delta = None
    is_gas_price_high = False
    best_rate = None

    def __init__(
        self,
        logger=None,
        min_profit=0.05,
        execution_interval=1,
        execution_amount_token_a=0.0001,
        min_native_balance=0.1,
        chain_config=None,
        exit_on_low_balance=False,
        buy_bias=0.0,
        sell_bias=0.0,
    ):
        if chain_config is None:
            chain_config = CHAIN_CONFIGS
        exchange_1_config = chain_config["exchange_1"]
        exchange_2_config = chain_config["exchange_2"]
        self.logger = logger
        self.exchange_1 = EXCHANGES[exchange_1_config["exchange_type"]](
            logger=self.logger,
            **exchange_1_config,
        )
        self.exchange_2 = EXCHANGES[exchange_2_config["exchange_type"]](
            logger=self.logger,
            **exchange_2_config,
        )
        self.min_profit = float(min_profit)
        self.execution_interval = int(execution_interval)
        self.execution_amount_token_a = float(execution_amount_token_a)
        self.min_native_balance = float(min_native_balance)
        self.logger.critical(
            f"""Initialized strategy.
        Self Address: {self.exchange_1.account.address}
        Exchange 1: {self.exchange_1}
        Exchange 2: {self.exchange_2}
        Min Profit: {self.min_profit}
        Execution Interval: {self.execution_interval}
        Execution Amount Token A: {self.execution_amount_token_a}
        Trading Address 1: {self.exchange_1.account.address}
        Trading Address 2: {self.exchange_2.account.address}
        Buy Bias: {buy_bias}
        Sell Bias: {sell_bias}"""
        )
        self.buy_bias = buy_bias
        self.sell_bias = sell_bias

        self.exchanges = {
            self.exchange_1.chain_name: self.exchange_1,
            self.exchange_2.chain_name: self.exchange_2,
        }
        try:
            self.run(
                sell_enabled=False,
                buy_enabled=False,
                async_execution=False
            )
            self.has_sufficient_balance()

        except Exception as e:  # pylint: disable=broad-except
            from traceback import print_exc

            print(print_exc())
            print("please fix this error in the code")
            sys.exit(1)

    def do_approvals(self, amount, exchange=None):
        """
        Do approvals for both exchanges
        """
        params = []
        if exchange == "exchange_1":
            params.append(self.exchange_1)
        elif exchange == "exchange_2":
            params.append(self.exchange_2)
        elif exchange is None:
            params = [self.exchange_1, self.exchange_2]

        for _exchange in params:
            self.logger.critical(f"Doing approvals for {_exchange}")
            self.do_approvals_for_exchange(_exchange, amount)

    def do_approvals_for_exchange(self, exchange, amount):
        """
        Do approvals for exchange 2
        """
        self.logger.critical(f"Doing approvals for {exchange} weth")
        exchange.do_approval(
            input_token_address=exchange.token_a.address,
            amount=amount * 10**18,
        )
        self.logger.critical(f"Doing approvals for {exchange} olas")
        exchange.do_approval(
            input_token_address=exchange.token_b.address,
            amount=amount * 10**18,
        )

    def is_gas_price_too_high(self) -> bool:
        """Check the gas price of the chain."""
        for exchange in [self.exchange_1, self.exchange_2]:
            if exchange.chain_name == "ethereum":
                wei = self.exchange_2.web3.eth.gas_price
                gwei = self.exchange_2.web3.from_wei(wei, "gwei")

                if self.is_gas_price_high and gwei < MAX_GAS_PRICE:
                    self.logger.critical(
                        f"Gas price has dropped from {gwei} to {gwei} executing trade"
                    )
                    self.is_gas_price_high = False

                if gwei > MAX_GAS_PRICE and not self.is_gas_price_high:
                    self.logger.critical(f"Extremely high gas price, not txing {gwei}")
                    self.is_gas_price_high = True

        return self.is_gas_price_high

    def run(  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        self,
        sell_enabled=True,
        buy_enabled=True,
        async_execution=True,
    ):
        """
        Run the strategy
        """
        self.logger.debug("Running strategy")


        # check if we can buy on exchange 1 and sell on exchange 2

        try:
            (best_bid, sell_exchange), (best_ask, buy_exchange) = self.get_rates()
            if sell_exchange == buy_exchange:
                self.logger.debug("Cannot trade on the same exchange")
                time.sleep(self.execution_interval)
                return

            profit = (best_bid - best_ask) / best_ask
            self.logger.info(f"Best Bid: {best_bid} on {sell_exchange}")
            self.logger.info(f"Best Ask: {best_ask} on {buy_exchange}")
            # we check whether the best bid is greater than the best ask
            self.logger.info(f"Profit: {profit * 100:.5f}%")

            if self.is_gas_price_too_high():
                time.sleep(self.execution_interval)
                return

            if self.delta is None:
                self.delta = profit
                self.logger.critical(f"Delta is {profit * 100:.5f}%")
            else:
                if round(self.delta, 3) != round(profit, 3):
                    print(
                        f"Delta changed from {self.delta * 100:.4f}% to {profit * 100:.4f}%",
                        end="\r",
                    )
                    self.delta = profit

            if profit < self.min_profit:
                time.sleep(self.execution_interval)
                return

            mid_rate = (best_bid + best_ask) / 2

            required_token_b = self.execution_amount_token_a * float(mid_rate) * 1.1
            self.has_sufficient_balance()
            self.logger.critical(
                f"Profit {profit} is greater than min profit! "
                + f"Executing trade sell {self.execution_amount_token_a} @ {best_bid} on {sell_exchange} and "
                + f"buy on {buy_exchange} @ {best_ask} with {required_token_b} {buy_exchange.token_b.symbol}"
            )
            has_buy = self.verify_available_tokens(buy_exchange, required_token_b, is_buy=True)
            has_sell = self.verify_available_tokens(
                sell_exchange, self.execution_amount_token_a, is_buy=False
            )


            if buy_enabled and not has_buy:
                self.logger.critical(
                    f"Insufficient balance on {buy_exchange.chain_name} to execute trade"
                )
                return
            if sell_enabled and not has_sell:
                self.logger.critical(
                    f"Insufficient balance on {sell_exchange.chain_name} to execute trade"
                )
                return

        except KeyboardInterrupt:
            self.logger.critical("Keyboard interrupt detected. Stopping bot")
            sys.exit(1)
        except IndexError as e:
            self.logger.critical("Index Error detected. Stopping bot")
            self.logger.critical(e)
            sys.exit(1)
        except:  # pylint: disable=bare-except
            self.logger.critical(traceback.format_exc())

            return

        if async_execution:
            order_threads = []

        sell_amount = self.execution_amount_token_a

        if sell_enabled:
            self.logger.critical(f"Selling on {sell_exchange.chain_name}")
            sell_params = {
                "token_a": sell_exchange.token_a.address,
                "token_b": sell_exchange.token_b.address,
                "amount": sell_amount * (1 + self.sell_bias ),
            }
            if async_execution:
                order_threads.append(
                    {"target": sell_exchange.sell, "kwargs": sell_params}
                )
            else:
                sell_exchange.sell(**sell_params)

        buy_amount = self.execution_amount_token_a * float(mid_rate)

        if buy_enabled:
            self.logger.critical(
                f"Buying on {buy_amount:.2f} {buy_exchange.chain_name}"
            )
            buy_params = {
                "token_a": buy_exchange.token_a.address,
                "token_b": buy_exchange.token_b.address,
                "amount": buy_amount * (1 + self.buy_bias),
            }
            if async_execution:
                order_threads.append({"target": buy_exchange.buy, "kwargs": buy_params})
            else:
                buy_exchange.buy(**buy_params)

        if async_execution:
            pool = ThreadPool(processes=2)
            results = pool.map(lambda x: x["target"](**x["kwargs"]), order_threads)
            pool.close()
            pool.join()
            # we check the results of the trade
            failed = False
            for result in results:
                if result is None or not result:
                    self.logger.critical("Leg of trade failed!")
                    failed = True
                else:
                    self.logger.critical("Leg of Trade executed successfully!")
                # we check the results of the trade
            if failed:
                self.logger.critical("At least 1 Trade failed!")
                self.send_msg_to_ntfy(
                    f"Arb failed for {sell_exchange.chain_name} and {buy_exchange.chain_name} "
                    + f"{sell_exchange.token_a.symbol}/{buy_exchange.token_b.symbol}",
                    channel=NTFY_CHANNEL,
                )
                sys.exit(1)
            else:
                self.logger.critical("Complete Arbitrage Trade executed successfully!")
                sell_amt = sell_amount * (1 + self.sell_bias)
                buy_amt = buy_amount * (1 + self.buy_bias)
                sell_recieved = sell_amt * float(best_bid)
                buy_recieved = buy_amt / float(best_ask)

                self.send_msg_to_ntfy(
                    f"{sell_exchange.token_a.symbol}/{buy_exchange.token_b.symbol} Arb executed successfully!\n"
                    + f"Chains {sell_exchange.chain_name} and {buy_exchange.chain_name} \n"
                    + f"Sell {sell_amt:.5f} {sell_exchange.token_a.symbol} for {sell_recieved:.5f} {sell_exchange.token_b.symbol} on {sell_exchange.chain_name} @ {best_bid:.3f} \n"
                    + f"Buy {buy_recieved:.5f} {buy_exchange.token_a.symbol} for {buy_amt:.5f} {buy_exchange.token_b.symbol} on {buy_exchange.chain_name} @ {best_ask:.3f} \n"
                    + f"Profit: {profit * 100:.5f}%\n"
                    + f"Buy tx: {buy_exchange.block_explorer_url}/tx/{results[1]} \n"
                    + f"Sell tx: {sell_exchange.block_explorer_url}/tx/{results[0]}",
                    channel=NTFY_CHANNEL,
                )

                if not self.has_sufficient_balance(native_only=True):
                    self.logger.critical(
                        "Insufficient GAS balance to execute strategy quitting to avoid errors."
                    )
                    sys.exit(1)

        self.has_sufficient_balance()

    def send_msg_to_ntfy(self, msg, channel=NTFY_CHANNEL):
        """
        Send a simple request to the ntfy server.
        curl -d "Hi" ntfy.rae.cloud/alerts
        """
        try:
            requests.post(f"{NTFYY_URL}/{channel}", data=msg, timeout=10)
        except requests.exceptions.RequestException as e:
            self.logger.critical(f"Failed to send message to ntfy: {e}")

    def record_data(self, rate_1, rate_2, profit):
        """Write to a file such that we can record the data"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("data.csv", "a", encoding=DEFAULT_ENCODING) as f:
            f.write(f"{timestamp},{rate_1},{rate_2},{profit}\n")

    def get_rates(self):
        """
        buy on exchange 1 and sell on exchange 2
        """
        bid_1 = self.exchange_1.get_price(
            input_token_address=self.exchange_1.token_a.address,
            output_token_address=self.exchange_1.token_b.address,
            amount=Decimal(self.execution_amount_token_a),
        )
        bid_2 = self.exchange_2.get_price(
            input_token_address=self.exchange_2.token_a.address,
            output_token_address=self.exchange_2.token_b.address,
            amount=Decimal(self.execution_amount_token_a),
        )

        exchange_to_bids = {
            self.exchange_1.chain_name: bid_1,
            self.exchange_2.chain_name: bid_2,
        }

        best_bid_exchange, best_bid_price = sorted(
            exchange_to_bids.items(), key=lambda x: x[1]
        )[-1]
        # the best bid is the one with the highest rate
        amount_to_trade = Decimal(self.execution_amount_token_a) * best_bid_price

        ask_1 = 1 / self.exchange_1.get_price(
            input_token_address=self.exchange_1.token_b.address,
            output_token_address=self.exchange_1.token_a.address,
            amount=amount_to_trade,
        )
        ask_2 = 1 / self.exchange_2.get_price(
            input_token_address=self.exchange_2.token_b.address,
            output_token_address=self.exchange_2.token_a.address,
            amount=amount_to_trade,
        )

        exchange_to_asks = {
            self.exchange_1.chain_name: ask_1,
            self.exchange_2.chain_name: ask_2,
        }
        # the best ask is the one with the lowest rate
        best_ask_exchange, best_ask_price = sorted(
            exchange_to_asks.items(), key=lambda x: x[1]
        )[0]

        self.best_rate = best_ask_price

        self.logger.info(f"Bid Rates: {exchange_to_bids}")
        self.logger.info(f"Ask Rates: {exchange_to_asks}")

        return (
            (best_bid_price, self.exchanges[best_bid_exchange]),
            (best_ask_price, self.exchanges[best_ask_exchange]),
        )

    def has_sufficient_balance(self, native_only=False, log=None):
        """
        Check if we have sufficient balance to execute the strategy
        """
        if log is None:
            log = self.logger.debug
        try:
            insufficient_balance = False
            for exchange in [self.exchange_1, self.exchange_2]:
                balance_a, balance_b, native_bal = exchange.get_balances()
                log(
                    f"""Exchange: {exchange.chain_name}
                {exchange.token_a.symbol} Balance: {balance_a}
                {exchange.token_b.symbol} Balance: {balance_b}
                Native Balance: {native_bal}"""
                )
                exchange.balance_a = balance_a
                exchange.balance_b = balance_b
                if native_bal < to_human_readable(self.min_native_balance):
                    log(
                        f"Insufficient Native Balance on {exchange.chain_name} : {native_bal}"
                    )
                    insufficient_balance = True
                if native_only:
                    continue
                if balance_a < self.execution_amount_token_a:
                    log(
                        f"Insufficient {exchange.token_a} Balance on {exchange.chain_name} : {balance_a}"
                    )
                    insufficient_balance = True

                required_b = (
                    float(self.best_rate) * float(self.execution_amount_token_a) * 1.1
                )
                if float(balance_b) < required_b:
                    log(
                        f"Insufficient {exchange.token_b} Balance on {exchange.chain_name} : {balance_b}"
                    )
                    insufficient_balance = True

            return not insufficient_balance
        except BadFunctionCallOutput:
            self.logger.critical(traceback.format_exc())
            time.sleep(2)
            return self.has_sufficient_balance(native_only=native_only, log=log)

    def verify_available_tokens(self, exhange, amount, is_buy=True, wait=False):
        """
        Verify that the tokens are available, wait until they are available send
        notifation on not available and when it then becomes available.
        if is_buy is True, we are buying, else we are selling
        We make sure that we send 2 noticiaions only.
        The first notification is to notify that the tokens are not available.
        If the tokens are not available, we wait until they are available.
        When they are available, we send a notification that the tokens are available.
        """

        if is_buy:
            token = exhange.token_b
            balance = exhange.balance_b
        else:
            token = exhange.token_a
            balance = exhange.balance_a

        if balance < amount:
            self.logger.critical(
                f"Insufficient {token.symbol} balance {balance} on {exhange.chain_name} "
            )
            self.send_msg_to_ntfy(
                f"Insufficient {token.symbol} balance {balance:.5f} on {exhange.chain_name} "
                + f"required {amount} waiting for balance to be available.",
                channel=NTFY_CHANNEL,
            )
            while (balance < amount) and wait:
                self.has_sufficient_balance()
                time.sleep(30)
                token_a, token_b, _ = exhange.get_balances()
                if is_buy:
                    balance = token_b
                else:
                    balance = token_a

                self.logger.critical(
                    f"{token.symbol} balance {balance} on {exhange.chain_name} is now available."
                )
                self.send_msg_to_ntfy(
                    f"{token.symbol} balance {balance} on {exhange.chain_name} is now available.",
                    channel=NTFY_CHANNEL,
                )
            return False
            

        else:
            self.logger.critical(
                f"{token.symbol} balance {balance} on {exhange.chain_name} is available."
            )
            return True
