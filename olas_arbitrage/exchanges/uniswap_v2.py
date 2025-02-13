"""
Uniswap v2 exchange.
"""
import datetime
import time
from decimal import Decimal

from eth_defi.token import fetch_erc20_details
from web3.exceptions import ContractLogicError

from olas_arbitrage.exceptions import Reversion, SwapConfigurationError, SwapException
from olas_arbitrage.exchanges.base import DefiExchange
from olas_arbitrage.utils import to_human_readable

UNISWAP_SWAP_FEE = Decimal("0.00600")
ALLOWED_SLIPPAGE = Decimal("0.00500")


class UniswapV2Exchange(DefiExchange):
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
        input_token = self.tokens[input_token_address]
        output_token = self.tokens[output_token_address]
        if amount <= 0:
            raise SwapConfigurationError("Amount must be greater than 0")

        liqudity_pool = self.setup_pool()
        path = [input_token.address] + self.path + [output_token.address]

        raw_quote = liqudity_pool.functions.getAmountsOut(
            amountIn=int(input_token.convert_to_raw(amount)),
            path=[
                self.web3.to_checksum_address(address)
                for address in path
            ],
        ).call()
        raw_output = raw_quote[-1]
        decimal_output = output_token.convert_to_decimals(raw_output)
        rate = decimal_output / amount

        breakpoint()
        self.logger.info(
            f"""
                    UniswapV2 Exchange;
                        input:
                            Amount: {amount}
                            Address: {input_token}
                        output:
                            Amount: {output_token.convert_to_decimals(raw_output)}
                            Address: {output_token}
                        Rate: {rate:.6f}"""
        )
        return rate

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dex = self.setup_pool()
        self.tokens = {
            self.token_a.address: self.token_a,
            self.token_b.address: self.token_b,
        }

    def get_token(self, address):
        """
        Get the token.
        """
        token = fetch_erc20_details(self.web3, address)
        return token

    def setup_pool(self):
        """Setup the pool."""

        router = self.web3.eth.contract(
            address=self.router_address,
            abi=self.contracts["Router02"]["abi"],
        )

        return router

    def buy(
        self,
        token_a: str,
        token_b: str,
        amount: float,
    ):
        """
        Buy tokens on uniswap.
        use token_b as input token.
        use token_a as output token.

        basically we are swapping token_b for token_a.
        The amount is the amount of token_b we want to swap.
        """
        amount = self.swap(
            input_token_address=token_b,
            output_token_address=token_a,
            amount=amount,
        )
        if amount is not False:
            return amount
        raise SwapException("Swap failed")

    def sell(
        self,
        token_a: str,
        token_b: str,
        amount: float,
    ):
        """
        Sell tokens on uniswap.
        """
        amount = self.swap(
            input_token_address=token_a,
            output_token_address=token_b,
            amount=amount,
        )
        if amount is not False:
            return amount
        raise SwapException("Swap failed")

    def do_approval(self, input_token_address: str, amount: float):
        """Do the necessary approval for the swap."""
        self.log("Step 1: Approve tokens")
        token_0 = self.tokens[input_token_address]
        # Uniswap router must be allowed to spent our quote token
        # we check if we have enough balance and if we have enough approval
        current_allowance = token_0.contract.functions.allowance(
            self.account.address, self.router_address
        ).call()
        if current_allowance < amount:
            # we set the allowance
            self.log(
                f"Setting allowance for {to_human_readable(amount)} {input_token_address}"
            )
            approve = token_0.contract.functions.approve(
                self.router_address, int(amount)
            )
            # we build the transaction
            tx_1 = approve.build_transaction(
                {
                    # we use the gase price * 1.05
                    "from": self.account.address,
                    "gasPrice": int(self.web3.eth.gas_price * 1.025),
                    "nonce": self.web3.eth.get_transaction_count(self.account.address),
                }
            )
            # we first sign the transaction
            signed_tx_1 = self.account.sign_transaction(tx_1)
            # we send the transaction
            tx_hash_1 = self.web3.eth.send_raw_transaction(signed_tx_1.rawTransaction)
            # we wait for the transaction to be mined
            self.log(f"Transaction hash: {tx_hash_1.hex()}")
            self.log("Waiting for transaction to be mined")
            # we wait for the next block to be sure that the transaction nonce is correct
            self.log("Waiting for next block")
            current_block = self.web3.eth.block_number
            while current_block == self.web3.eth.block_number:
                time.sleep(0.1)
            if not self.wait_for_transaction(tx_hash_1):
                self.logger.error("Approval transaction failed to be mined.")
                # we dont need to hard exit here.
                return False
        else:
            self.log(
                f"Already approved {to_human_readable(current_allowance)} {input_token_address}"
            )
        return True

    def swap(  # pylint: disable=too-many-locals,W0221
        self,
        input_token_address: str,
        output_token_address: str,
        amount: float,
        retries: int = 3,
    ):
        """
        Perform the swap.
        """
        if retries < 0:
            return False
        input_token = self.tokens[input_token_address]
        _amount = input_token.convert_to_raw(amount)
        self.log(
            f"Swapping {amount} {input_token_address} "
            + f"for {output_token_address} on {self.chain_name}"
        )
        self.log("Step 2: Swap tokens")
        # we build the transaction
        try:
            minimum_input_quantity_wei = self._do_swap(
                self.dex, input_token_address, output_token_address, _amount
            )
        except Reversion as exc:
            # we retr
            if retries < 0:
                raise Reversion("Swap failed") from exc
            self.log(f"Swap failed. Retrying. {retries} retries left.")
            time.sleep(1)
            return self.swap(
                input_token_address=input_token_address,
                output_token_address=output_token_address,
                amount=amount,
                retries=retries,
            )
        return minimum_input_quantity_wei

    def _do_swap(
        self, dex, input_token_address, output_token_address, amount, gas_price=None
    ):
        """
        Perform the swap.
        """
        if gas_price is None:
            gas_price = int(self.web3.eth.gas_price * 1.10)

        try:
            minimum_input_quantity_wei = int(
                self.get_price(
                    input_token_address=input_token_address,
                    output_token_address=output_token_address,
                    amount=amount,
                )
            )
        except ContractLogicError as error:
            self.log(f"Transaction failed with error: {error}")
            time.sleep(1)
            if "execution reverted" in str(error):
                self.log("Failed to submit transaction. Execution reverted.")
                return self._do_swap(
                    dex,
                    input_token_address,
                    output_token_address,
                    amount,
                    gas_price=gas_price,
                )
        func = dex.functions.swapExactTokensForTokens(
            amountIn=int(amount),
            amountOutMin=int(minimum_input_quantity_wei),
            path=[
                self.web3.to_checksum_address(address)
                for address in [
                    input_token_address,
                    self.path,
                    output_token_address,
                ]
            ],
            to=self.account.address,
            deadline=int(datetime.datetime.now().timestamp()) + 60 * 10,
        )
        # we build the transaction
        try:
            tx_2 = func.build_transaction(
                {
                    # we use the gase price * 1.05
                    "from": self.account.address,
                    "gasPrice": gas_price,
                    "nonce": self.web3.eth.get_transaction_count(self.account.address),
                }
            )
            tx_2["gas"] = int(200_000)
        except ContractLogicError as error:
            self.log(f"Transaction failed with error: {error}")
            if "execution reverted" in str(error):
                self.log("Failed to submit transaction. Execution reverted.")
                return self._do_swap(
                    dex,
                    input_token_address,
                    output_token_address,
                    amount,
                    gas_price=gas_price,
                )
            raise Reversion("Swap failed") from error
        except ValueError as error:
            self.log(f"Transaction failed with error: {error}")
            if "fee cap less than block base" in str(error):
                self.log("Failed to submit transaction. Fee cap less than block base.")
                gas_price = int(1.05 * gas_price)
                return self._do_swap(
                    dex,
                    input_token_address,
                    output_token_address,
                    amount,
                    gas_price=gas_price,
                )
            raise Reversion("Swap failed") from error

        self.log(
            "Submitting transaction to swap "
            + f"{to_human_readable(amount)} {input_token_address} for {output_token_address} on {self.chain_name}"
        )

        tx_hash_2 = self.do_tx(tx_2)

        if not tx_hash_2:
            self.log(
                "Swap transaction failed to be mined. Hard exiting! "
                + f"{to_human_readable(amount)} {input_token_address} for {output_token_address} on {self.chain_name}\n"
            )
            raise Reversion("Swap transaction failed to be mined. Hard exiting!")
        self.log(
            f"Swap completed successfully! {to_human_readable(amount)} "
            + f"{input_token_address} for {output_token_address} on {self.chain_name}"
        )
        self.log(f"Transaction hash: {tx_hash_2.hex()}")
        return minimum_input_quantity_wei
