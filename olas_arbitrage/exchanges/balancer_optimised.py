"""
Balancer exchange.
"""
import json
import os
from decimal import Decimal

from balpy import balpy
from requests import JSONDecodeError
from web3.exceptions import BlockNotFound, ContractLogicError

from olas_arbitrage.exceptions import SorRetrievalException, SwapConfigurationError
from olas_arbitrage.exchanges.balancer import BalancerExchange
from olas_arbitrage.exchanges.base import DefiExchange
from requests.exceptions import ConnectionError

GAS_PRICE_PREMIUM = 20
GAS_SPEED = "fast"
GAS_PRICE = 888


class BalancerExchangeOptimised(BalancerExchange):
    """
    Balancer exchange.
    """

    def get_price(
        self, input_token_address: str, output_token_address: str, amount: float
    ) -> float:
        """
        Get the price of the token.
        """
        if input_token_address == output_token_address:
            raise SwapConfigurationError(
                "Input and output token addresses are the same"
            )
        if amount <= 0:
            raise SwapConfigurationError("Amount must be greater than 0")

        input_token = self.tokens[input_token_address]
        output_token = self.tokens[output_token_address]

        params = self.get_params_for_swap(
            input_token_address=input_token_address,
            output_token_address=output_token_address,
            amount_in=input_token.convert_to_decimals(
                input_token.convert_to_raw(amount)
            ),
        )
        # we query the smart router
        sor_result = self.bal.balSorQuery(params)
        amount_out = float(sor_result['returnAmount'])
        output_amount = amount_out

        rate = Decimal(output_amount) / Decimal(amount)
        self.logger.info(
            f"""
                    Balancer Exchange on {self.chain_name}:;
                        input:
                            Amount: {amount}
                            Address: {input_token}
                        output:
                            Amount: {output_amount}
                            Address: {output_token}
                        Rate: {rate:.4f}"""
        )
        return rate

    def __init__(self, **kwargs):  # pylint: disable=super-init-not-called
        DefiExchange.__init__(self, **kwargs)  # pylint: disable=W0233

        self.pool_id = kwargs.get("pool_id")
        self.vault_address = kwargs.get("vault_address")
        self.bal = balpy.balpy(
            self.chain_name,
            manualEnv={
                "privateKey": self.account._private_key,
                "customRPC": self.rpc_url,
                "etherscanApiKey": os.environ["ETHERSCAN_API_KEY"],
            },
        )
        self.tokens = {
            self.token_a.address: self.token_a,
            self.token_b.address: self.token_b,
        }
        self.gas_price = kwargs.get("gas_price", None)
        self.gas_price_premium = kwargs.get("gas_price_premium", GAS_PRICE_PREMIUM)

    def sell(
        self,
        token_a: str,
        token_b: str,
        amount: float,
        retries=30,
    ):
        """
        Sell the token.
        """
        if token_a == token_b:
            raise SwapConfigurationError(
                "Input and output token addresses are the same"
            )
        if amount <= 0:
            raise SwapConfigurationError("Amount must be greater than 0")

        input_token = self.tokens[token_b]
        output_token = self.tokens[token_a]
        self.log(f"{self.chain_name} Selling {amount} {output_token} for {input_token}")
        _amount = output_token.convert_to_raw(amount)

        try:
            successful = self._swap(
                input_token_address=output_token.address,
                output_token_address=input_token.address,
                amount_in=_amount,
                is_buy=False,
            )
        except SorRetrievalException:
            self.log("Transaction failed with SorRetrievalException")
            if retries > 0:
                self.log(f"Retrying transaction. {retries} retries left")
                return self.sell(
                    token_a=token_a,
                    token_b=token_b,
                    amount=amount,
                    retries=retries - 1,
                )
            return False
        if not successful and retries > 0:
            self.log(f"Retrying transaction. {retries} retries left")
            return self.sell(
                token_a=token_a,
                token_b=token_b,
                amount=amount,
                retries=retries - 1,
            )
        if not successful:
            return False

        return successful

    def buy(
        self,
        token_a: str,
        token_b: str,
        amount: float,
        retries=30,
    ):
        """
        Buy the token.
        """
        if token_a == token_b:
            raise SwapConfigurationError(
                "Input and output token addresses are the same"
            )
        if amount <= 0:
            raise SwapConfigurationError("Amount must be greater than 0")

        input_token = self.tokens[token_b]
        output_token = self.tokens[token_a]
        self.log(
            f"{self.chain_name} Swapping {amount} {input_token} for {output_token}"
        )
        _amount = input_token.convert_to_raw(amount)

        try:
            successful = self._swap(
                input_token_address=input_token.address,
                output_token_address=output_token.address,
                amount_in=_amount,
                is_buy=False,
            )
        except SorRetrievalException:
            self.log("Buy Transaction failed with SorRetrievalException")
            if retries > 0:
                self.log(f"Retrying transaction. {retries} retries left")
                return self.buy(
                    token_a=token_a,
                    token_b=token_b,
                    amount=amount,
                    retries=retries - 1,
                )
            return False
        if not successful and retries > 0:
            self.log(f"Unsuccessful Buy. Retrying transaction. {retries} retries left")
            return self.buy(
                token_a=token_a,
                token_b=token_b,
                amount=amount,
                retries=retries - 1,
            )
        if not successful:
            return False
        return successful

    def _swap(
        self,
        input_token_address: str,
        output_token_address: str,
        amount_in: float,
        is_buy=False,
        retries=10,
    ):
        # we build the transaction

        self.log(
            f"Step 1: Query SOR {amount_in} {input_token_address} for {output_token_address}"
        )
        input_token = self.tokens[input_token_address]
        params = self.get_params_for_swap(
            input_token_address=input_token_address,
            output_token_address=output_token_address,
            amount_in=input_token.convert_to_decimals(amount_in),
            is_buy=is_buy,
        )
        # we query the smart router
        try:
            sor_result = self.bal.balSorQuery(params)
        except (ContractLogicError, BlockNotFound, JSONDecodeError, ConnectionError) as error:
            self.log(f"Transaction failed with {error}")
            if retries > 0:
                self.log(f"Retrying transaction. {retries} retries left")
                return self._swap(
                    input_token_address=input_token_address,
                    output_token_address=output_token_address,
                    amount_in=amount_in,
                    is_buy=is_buy,
                    retries=retries - 1,
                )
            return False
        res = self.bal.balSorResponseToBatchSwapFormat(params, sor_result, )
        swap = res["batchSwap"]
        self.logger.info(f"Recommended swap: {json.dumps(swap, indent=4)}")
        tokens = swap["assets"]
        limits = swap["limits"]
        if not tokens or not limits:
            self.log("Problem with SOR retrieval!!")
            if retries > 0:
                self.log(f"Retrying transaction. {retries} retries left")
                return self._swap(
                    input_token_address=input_token_address,
                    output_token_address=output_token_address,
                    amount_in=amount_in,
                    is_buy=is_buy,
                    retries=retries - 1,
                )
            raise SorRetrievalException(
                f"No tokens {tokens} or limits: {limits} provided in swap"
            )

        self.log("Step 2: Execute Batch Swap Txn")
        tx_hash = self.do_tx(swap)
        if not tx_hash:
            self.log("Transaction Failed.")
            return False
        self.log(f"Transaction hash: {tx_hash}")
        # check it was successful

        self.log("Step 3: Check Transaction Status")
        if not self.check_tx(tx_hash):
            self.log("Transaction Failed.")
            return False
        return tx_hash
