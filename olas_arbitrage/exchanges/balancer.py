"""
Balancer exchange.
"""
import datetime
import json
import os
import time

from balancerv2cad.WeightedPool import WeightedPool
from balpy import balpy
from eth_defi.token import fetch_erc20_details
from web3 import Web3
from web3.exceptions import BlockNotFound, ContractLogicError

from olas_arbitrage.constants import BALANCER_SWAP_FEE
from olas_arbitrage.exceptions import SorRetrievalException, SwapConfigurationError
from olas_arbitrage.exchanges.base import DefiExchange

GAS_PRICE_PREMIUM = 20
GAS_SPEED = "fast"
GAS_PRICE = 888


class BalancerExchange(DefiExchange):
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
        pool = self.setup_pool()
        input_token = self.tokens[input_token_address]
        output_token = self.tokens[output_token_address]

        recieved_amount = pool.swap(
            token_in=self.web3.to_checksum_address(input_token_address),
            token_out=self.web3.to_checksum_address(output_token_address),
            amount=input_token.convert_to_raw(amount),
            given_in=True,
        )

        self.logger.info(
            f"""
                    Balancer Exchange;
                        input:
                            Amount: {amount}
                            Address: {input_token}
                        output:
                            Amount: {output_token.convert_to_raw(recieved_amount)}
                            Address: {output_token}
                        Rate: {(recieved_amount / input_token.convert_to_raw(amount)):.6f}"""
        )
        self.pool = pool
        return recieved_amount / output_token.convert_to_raw(amount)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pool_id = kwargs.get("pool_id")
        self.vault_address = kwargs.get("vault_address")
        self.pool = self.setup_pool()
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
        self.gas_price = kwargs.get("gas_price", GAS_PRICE)
        self.gas_price_premium = kwargs.get("gas_price_premium", GAS_PRICE_PREMIUM)

    def setup_pool(self):  # pylint: disable=too-many-locals
        """
        We need to parse the Pool. so that we collect the contract addresses,
        along with the current balances.
        We need to call the vault in order to get the current balances.
        """
        # an ethere address is 42 characters long
        try:
            pool_id = self.pool_id
            pool_address = self.web3.to_checksum_address(pool_id[:42])
            vault_contract = self.web3.eth.contract(
                address=self.vault_address,
                abi=self.contracts["Vault"]["abi"],
            )
            tokens = vault_contract.functions.getPoolTokens(pool_id).call()
            pool = self.web3.eth.contract(
                address=pool_address, abi=self.contracts["WeightedPool"]["abi"]
            )
            weights = pool.functions.getNormalizedWeights().call()
            scaling_factors = pool.functions.getScalingFactors().call()
            token_addresses, balances, _ = tokens
            balances = {
                self.web3.to_checksum_address(token): balance
                for token, balance in zip(token_addresses, balances)
            }
            for balance, factor in zip(balances, scaling_factors):
                balances[balance] = balances[balance] * factor
            for token in balances:
                self.logger.debug(f"Balance for {token} is {balances[token]}")
            total_weight = sum(weights)
            weights = [weight / total_weight for weight in weights]
            ratios = {
                self.web3.to_checksum_address(token): weight
                for token, weight in zip(token_addresses, weights)
            }
            liquidity_pool = WeightedPool()
            liquidity_pool.join_pool(balances=balances, weights=ratios)
            liquidity_pool._swap_fee = (  # pylint: disable=protected-access
                BALANCER_SWAP_FEE
            )
            return liquidity_pool
        except Exception as error:  # pylint: disable=broad-except
            self.log(f"Failed to setup pool: {error}")
            time.sleep(1)
            return self.setup_pool()

    def validate_trade(self, token_a, token_b, amount):
        """
        Validate the trade.
        """
        if token_a == token_b:
            raise SwapConfigurationError(
                "Input and output token addresses are the same"
            )
        if amount <= 0:
            raise SwapConfigurationError("Amount must be greater than 0")
        input_token = self.tokens[token_a]
        output_token = self.tokens[token_b]
        _amount = input_token.convert_to_raw(amount)
        return input_token, output_token, _amount

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
        input_token, output_token, trade_amount = self.validate_trade(
            token_a, token_b, amount
        )

        self.log(
            f"{self.chain_name} Selling {amount} {output_token.symbol} for {input_token.symbol}"
        )
        return self._execute_swap(
            input_token=input_token,
            output_token=output_token,
            trade_amount=trade_amount,
            caller_func=self.sell,
            retries=retries,
        )

    def _execute_swap(
        self,
        input_token,
        output_token,
        trade_amount,
        caller_func,
        retries=30,
    ):
        """Perform the swap."""
        try:
            successful = self._swap(
                input_token_address=output_token.address,
                output_token_address=input_token.address,
                amount_in=trade_amount,
            )
        except SorRetrievalException:
            self.setup_pool()
            self.log("Transaction failed with SorRetrievalException")
            if retries > 0:
                self.log(f"Retrying transaction. {retries} retries left")
                return caller_func(
                    token_a=input_token.address,
                    token_b=output_token.address,
                    amount=int(input_token.convert_to_decimals(trade_amount)),
                    retries=retries - 1,
                )
            return False
        if not successful and retries > 0:
            self.log(f"Retrying transaction. {retries} retries left")
            return caller_func(
                token_a=input_token.address,
                token_b=output_token.address,
                amount=int(input_token.convert_to_decimals(trade_amount)),
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
        input_token, output_token, trade_amount = self.validate_trade(
            token_a, token_b, amount
        )

        return self._execute_swap(
            input_token=input_token,
            output_token=output_token,
            trade_amount=trade_amount,
            caller_func=self.sell,
            retries=retries,
        )

    def approve(self, token_address: str, spender: str, amount: float):
        """
        We need to approve the token for the vault.
        """
        gas_price = self.web3.eth.gas_price * self.gas_price_premium

        erc20_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(token_address),
            abi=self.contracts["erc20"],
        )
        current_allowance = erc20_contract.functions.allowance(
            self.web3.to_checksum_address(spender),
            self.web3.to_checksum_address(self.account.address),
        ).call()

        self.log(f"Current allowance: {current_allowance}")

        if current_allowance >= amount:
            return True

        tx = erc20_contract.functions.approve(spender, int(amount)).build_transaction(
            {
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "gasPrice": gas_price,
                "chainId": self.chain_id,
            }
        )
        signed_tx = self.account.sign_transaction(tx)

        # we submit the transaction
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        self.log("Approving token {token_address} for {spender} with amount {amount}")
        self.log("Transaction hash: {tx_hash.hex()}")
        self.log("Waiting for transaction to be mined")
        self.web3.eth.wait_for_transaction_receipt(tx_hash)
        # we get the transaction receipt to get the transaction hash
        self.log(f"Transaction mined @ {self.block_explorer_url}/tx/{tx_hash.hex()}")
        status = self.web3.eth.get_transaction_receipt(tx_hash).status
        if status == 0:
            return False
        return True

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
        except (ContractLogicError, BlockNotFound):
            self.log("Transaction failed with ContractLogicError")
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
        swap = sor_result["batchSwap"]
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
        return self.check_tx(tx_hash)

    def check_tx(self, tx_hash, retries=10):
        """
        Check the transaction status.
        """
        try:
            tx_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            self.log("Got TX receipt!")
        except Exception as error:  # pylint: disable=broad-except
            self.log(f"Failed to get transaction receipt: {error}")
            if retries > 0:
                self.log(f"Retrying transaction collection. {retries} retries left")
                time.sleep(1)
                return self.check_tx(tx_hash, retries - 1)
            return False
        status = tx_receipt.status
        self.log(f"Transaction status: {status}")
        if status == 0:
            return False
        return True

    def do_tx(
        self, swap, gas_factor=GAS_PRICE_PREMIUM, gas_speed=GAS_SPEED, retries=3
    ):  # pylint: disable=W0237
        """Do the actual transaction."""

        try:
            tx_hash = self.bal.balDoBatchSwap(
                swap,
                gasFactor=gas_factor,
                gasPriceSpeed=gas_speed,
                gasPriceGweiOverride=self.gas_price
                if self.gas_price
                else float(Web3.from_wei(self.web3.eth.gas_price, "gwei")) * 1.1,
            )
            self.gas_price = None
        except (TypeError, ValueError) as error:
            self.log(f"Transaction failed with error: {error}")
            if "nonce too high" in str(error):
                self.log("Nonce too high. Retrying as chain may be out of sync.")
                return self.do_tx(swap)
            retry_on_issue = False

            if "nonce too low" in str(error).lower():
                self.log(f"Failed to submit transaction. Nonce too low. {error}")
                retry_on_issue = True
            if "fee cap less than block base" in str(error):
                self.log(
                    "Failed to submit transaction. Fee cap less than block base. {error}"
                )
                retry_on_issue = True
            if "EffectivePriorityFeePerGas too low" in str(error):
                self.log(
                    "Failed to submit transaction. EffectivePriorityFeePerGas too low. {error}"
                )
                retry_on_issue = True
            if "INTERNAL_ERROR: could not replace existing tx" in str(error):
                self.log(
                    "Failed to submit transaction. INTERNAL_ERROR: could not replace existing tx. {error}"
                )
                retry_on_issue = True
            if "nonce too low" in str(error).lower():
                self.log(f"Failed to submit transaction. Nonce too low. {error}")
                retry_on_issue = True
            if "+= self.calldataFlag" in str(error):
                retry_on_issue = True
            if "exceeds the configured cap" in str(error):
                retry_on_issue = True
            if "replacement transaction underpriced" in str(error):
                retry_on_issue = True
                self.logger.error(f"Halting due to error: {error}")
                self.gas_price = int(self.web3.eth.gas_price * 1.1)
                time.sleep(5)
            if retry_on_issue and retries > 0:
                return self.do_tx(
                    gas_factor=int(gas_factor * 1.2),
                    gas_speed=gas_speed,
                    swap=swap,
                    retries=retries - 1,
                )
            return False
        return tx_hash

    def get_params_for_swap(
        self, input_token_address, output_token_address, amount_in: float, is_buy=False
    ):
        """
        Return sor parameters so we can do smart routing...
        """
        gas_price = self.web3.eth.gas_price * GAS_PRICE_PREMIUM
        params = {
            "network": self.chain_name,
            "slippageTolerancePercent": "0.1",  # 1%
            "sor": {
                "sellToken": input_token_address,
                "buyToken": output_token_address,  # // token out
                "orderKind": "buy" if is_buy else "sell",
                "amount": amount_in,
                "gasPrice": gas_price,
            },
            "batchSwap": {
                "funds": {
                    "sender": self.account.address,  #      // your address
                    "recipient": self.account.address,  #   // your address
                    "fromInternalBalance": False,  # // to/from internal balance
                    "toInternalBalance": False,  # // set to "false" unless you know what you're doing
                },
                # // unix timestamp after which the trade will revert if it hasn't executed yet
                "deadline": datetime.datetime.now().timestamp() + 60,
            },
        }

        return params

    def do_approval(self, input_token_address: str, amount: float):
        """Do the necessary approval for the swap."""
        self.log("Step 1: Approve tokens")
        token_0 = fetch_erc20_details(self.web3, input_token_address)
        # Uniswap router must be allowed to spent our quote token
        # we check if we have enough balance and if we have enough approval
        current_allowance = token_0.contract.functions.allowance(
            self.account.address, self.vault_address
        ).call()
        if current_allowance < amount:
            # we set the allowance
            self.log(
                f"Setting allowance for {token_0.convert_to_decimals(amount)} {input_token_address}"
            )
            approve = token_0.contract.functions.approve(
                self.vault_address, int(amount)
            )
            # we build the transaction
            tx_1 = approve.build_transaction(
                {
                    # we use the gase price * 1.05
                    "from": self.account.address,
                    "gasPrice": int(self.web3.eth.gas_price * 2.025),
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
            if not self.check_tx(tx_hash_1):
                self.logger.error("Approval transaction failed to be mined.")
                # we dont need to hard exit here.
                return False
        else:
            self.log(
                f"Already approved {token_0.convert_to_decimals(current_allowance)} {input_token_address}"
            )
        return True
