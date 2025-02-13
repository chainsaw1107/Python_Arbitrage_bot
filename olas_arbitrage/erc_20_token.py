"""
Represents an ERC-20 token.
"""
import json
from dataclasses import dataclass

from web3.contract import Contract

from olas_arbitrage.constants import DEFAULT_ENCODING

with open("olas_arbitrage/abis/erc20.json", encoding=DEFAULT_ENCODING) as f:
    erc20_abi = json.load(f)


@dataclass
class Erc20Token:
    """
    ERC20 Token
    """

    address: str
    symbol: str = None
    decimals: int = None
    contract: Contract = None

    @classmethod
    def from_address(cls, address, w3):
        """
        Create an ERC20 token from an address.
        """
        contract = w3.eth.contract(address=address, abi=erc20_abi)
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        return cls(address, symbol, decimals, contract)
