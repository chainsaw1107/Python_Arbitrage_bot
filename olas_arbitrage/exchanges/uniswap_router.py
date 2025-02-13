"""
Uniswap router exchange.
"""
import asyncio
import json
import time
from decimal import Decimal

from requests import ReadTimeout
from uniswap_smart_path.smart_path import V3PoolPath, SmartPath

from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec
from web3 import Web3
from web3.exceptions import ContractLogicError

from olas_arbitrage.constants import DEFAULT_ENCODING
from olas_arbitrage.exchanges.base import DefiExchange

UNISWAP_SWAP_FEE = Decimal("0.00600")
ALLOWED_SLIPPAGE = Decimal("0.0500")


def parse_path_to_rate(path_obj, amount, token_a, token_b):
    """
    Parse the path object to rates.
    """
    total_out = 0
    for split in path_obj:
        estimated_amount = split["estimate"]
        total_out += estimated_amount

    decimal_adjusted_amount = amount / (10**token_a.decimals)
    decimal_adjusted_out = total_out / (10**token_b.decimals)
    rate = decimal_adjusted_out / decimal_adjusted_amount
    return rate, total_out


# ROUTER_ADDRESS = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
# PERMIT2_ADDRESS = Web3.to_checksum_address("0x000000000022D473030F116dDEE9F6B43aC78BA3")


class PathFindingException(Exception):
    """
    Exception raised when we cannot find a path.
    """


class UniswapRouterExchange(DefiExchange):
    """
    Balancer exchange.
    """

    last_trade_path = None

    def __init__(self, **kwargs):
        """
        initialize the exchange
        """
        super().__init__(**kwargs)
        self.exchange_type = "uniswap_router"
        self.permit2_address = self.web3.to_checksum_address(kwargs.get("permit2_address"))

        self._custom_path_config = kwargs.get("custom_smart_path_kwargs")

        self.setup()

    async def get_path(self, token_a, token_b, amount_a):
        """
        Get the path for the tokens.
        """
        amt_machine = int(amount_a * (10**token_a.decimals))
        path = await self.smart_path.get_swap_in_path(
            amt_machine,
            token_a.address,
            token_b.address,
        )
        rate, total = parse_path_to_rate(path, amt_machine, token_a, token_b)
        if not rate:
            raise PathFindingException("No path found")
        return path, Decimal(rate), total

    def setup(self):
        """
        Setup the codec and the loop.
        """
        self.codec = RouterCodec()
        self.loop = asyncio.get_event_loop()
        if not self._custom_path_config:
            self.smart_path = self.loop.run_until_complete(
                SmartPath.create(rpc_endpoint=self.rpc_url)
            )
        else:
            self.smart_path = self.loop.run_until_complete(
                SmartPath.create_custom(**self._custom_path_config)
            )


    def teardown(self):
        """
        Teardown the codec and the loop.
        """
        self.loop.close()

    def get_price(self, input_token_address, output_token_address, amount):
        """
        get the price for a given input.
        """

        token_a = self.tokens.get(input_token_address)
        if not token_a:
            raise ValueError(f"Token {input_token_address} not found")
        token_b = self.tokens.get(output_token_address)
        if not token_b:
            raise ValueError(f"Token {output_token_address} not found")
        path, rate, total = self.loop.run_until_complete(
            self.get_path(token_a, token_b, amount)
        )
        self.last_trade_path = path
        self.logger.info(
            f"""
                    {self.exchange_type} Exchange;
                        input:
                            Amount: {amount}
                            Address: {token_a}
                        output:
                            Amount: {token_b.convert_to_decimals(total)}
                            Address: {token_b}
                        Rate: {rate:.6f}"""
        )
        return Decimal(rate)

    def buy(self, token_a, token_b, amount, retries=1):
        """
        Buy token b with token a.
        """
        token_b, token_a = self.tokens.get(token_a), self.tokens.get(token_b)
        path, _, _ = self.loop.run_until_complete(
            self.get_path(token_a, token_b, amount_a=amount)
        )
        # if we were to store the last price here we could reduce the calls for buys.
        try:
            result = self._swap(amount, token_a, path)
        except ContractLogicError as error:
            self.logger.error(f"Failed to swap {token_a} for {token_b}")
            if retries > 0:
                time.sleep(1)
                return self.buy(token_b.address, token_a.address, amount, retries - 1)
            return False
        return result

    def sell(self, token_a, token_b, amount, retries=1):
        """
        Buy token b with token a.
        """
        token_a, token_b = self.tokens.get(token_a), self.tokens.get(token_b)
        path, _, _ = self.loop.run_until_complete(
            self.get_path(token_a, token_b, amount)
        )
        try:
            res = self._swap(amount, token_a, path)
        except ContractLogicError as error:
            self.logger.error(f"Failed to swap {token_a} for {token_b} {error}")
            if retries > 0:
                time.sleep(1)
                return self.sell(token_a.address, token_b.address, amount, retries - 1)
            return False
        return res

    def _swap(self, amount, token_a, path, retries=2):
        """
        Swap the tokens.
        """
        try:
            allowance = token_a.contract.functions.allowance(
                self.account.address, self.router_address
            ).call()

            if allowance < ((10**token_a.decimals) * amount):
                self.approve_permit_2(token_a, self.router_address)

            allowance = token_a.contract.functions.allowance(
                self.account.address, self.permit2_address
            ).call()
        except ReadTimeout as error:
            self.logger.error("Failed to read allowance")
            if retries > 0:
                time.sleep(1)
                return self._swap(amount, token_a, path, retries - 1)
            raise ApprovalException("Failed to read allowance") from error

        if allowance < ((10**token_a.decimals) * amount):
            self.approve_permit_2(token_a, self.permit2_address)

        txn_data = self.loop.run_until_complete(
            self.build_transaction_data(path, amount, token_a)
        )
        txn = self.build_transaction(
            txn_data,
        )
        # we simulate the transaction
        try:
            self.web3.eth.call(txn)
        except Exception as error:
            self.logger.error("Failed to estimate gas! The transaction will revert!")
            from rich import print_json
            print_json(data=txn)
            if retries > 0:
                time.sleep(10)
                return self._swap(amount, token_a, path, retries - 1)
            raise error

        self.log(f"Sending transaction {txn}")
        result = self.do_tx(txn)
        if not result and retries > 0:
            self.logger.error(
                "Transaction failed to be successfully executed! Retrying"
            )
            time.sleep(5)
            return self._swap(amount, token_a, path, retries - 1)
        self.logger.info(f"Transaction hash: {result.hex()}")
        return result

    def build_transaction(self, txn_data):
        """
        Build the raw txn.
        """
        txn = {
            "from": self.account.address,
            "to": self.router_address,
            "nonce": self.web3.eth.get_transaction_count(self.account.address),
            "gas": 1_000_000,
            "gasPrice": int(self.web3.eth.gas_price * 1.1),
            "chainId": self.chain_id,
            "data": txn_data,
        }
        return txn

    async def build_transaction_data(
        self, path_obj, amount, token_a
    ):  # pylint: disable=too-many-locals
        """
        Build the transaction.
        """

        amount = float(amount)

        encoded_input = self.codec.encode.chain()

        for split in path_obj:
            function_name = split["function"]
            path = split["path"]
            estimated_amount = split["estimate"]
            weight = split["weight"] / 100

            _, _, p2_nonce = self.get_permit2_info(token_a)
            allowance_amount = 2**159 - 1  # max/infinite
            (
                permit_data,
                signable_message,
            ) = self.codec.create_permit2_signable_message(
                token_a.address,
                allowance_amount,
                self.codec.get_default_expiration(60 * 24 * 3600 * 10),  # 30 days
                p2_nonce,
                self.router_address,
                self.codec.get_default_deadline(18000),  # 180 seconds
                chain_id=self.chain_id,
            )

            signed_message = self.account.sign_message(signable_message)
            encoded_input = encoded_input.permit2_permit(permit_data, signed_message)

            if function_name == "V2_SWAP_EXACT_IN":
                encoded_input = encoded_input.v2_swap_exact_in(
                    FunctionRecipient.SENDER,
                    amount_in=int(amount * weight * (10**token_a.decimals)),
                    amount_out_min=int(estimated_amount * (1 - float(ALLOWED_SLIPPAGE))),
                    path=path,
                )
            elif function_name == "V3_SWAP_EXACT_IN":
                # we need to add the permit
                encoded_input = encoded_input.v3_swap_exact_in(
                    FunctionRecipient.SENDER,
                    amount_in=int(amount * weight * (10**token_a.decimals)),
                    amount_out_min=int(estimated_amount * (1 - float(ALLOWED_SLIPPAGE))),
                    path=path,
                )

        txn_data = encoded_input.build(
            self.codec.get_default_deadline(valid_duration=180000000),
        )
        return txn_data

    def get_permit2_info(self, token):
        """
        Get the permit2 info.
        """
        with open(
            "olas_arbitrage/abis/uniswap/permit2.json", encoding=DEFAULT_ENCODING
        ) as f:
            permit2_abi = json.load(f)
        permit2_contract = self.web3.eth.contract(
            address=self.permit2_address, abi=permit2_abi
        )
        p2_amount, p2_expiration, p2_nonce = permit2_contract.functions.allowance(
            self.account.address,
            token.address,
            self.router_address,
        ).call()
        return p2_amount, p2_expiration, p2_nonce

    def approve_permit_2(self, token, address):
        """
        Approve the token.
        """
        permit2_allowance = 2**200 - 1  # max
        contract_function = token.contract.functions.approve(
            address, int(permit2_allowance)
        )
        trx_params = contract_function.build_transaction(
            {
                "from": self.account.address,
                "gas": 500_000,
                "gasPrice": int(self.web3.eth.gas_price * 1.1),
                "chainId": self.chain_id,
                "value": 0,
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
            }
        )
        if not self.do_tx(trx_params):
            raise ApprovalException("Failed to approve token")
        return True

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
            self.log("Token already approved")
        return True


class ApprovalException(Exception):
    """
    Exception raised when we cannot approve a token.
    """
