"""
Simple test script to test the installation of the package
"""

from datetime import datetime
from balpy import balpy

key_file = "ethereum_private_key.txt"

with open(key_file, "r") as f:
    private_key = f.read().strip()


CHAIN_NAME = "mainnet"
bal = balpy.balpy(
    CHAIN_NAME,
    manualEnv={
        "privateKey": private_key,
        "customRPC": "https://rpc.ankr.com/eth",
        "etherscanApiKey": "YourKEY",
    },
)

is_buy = True

input_amount = 1
INPUT_TOKEN_ADDRESS = '0x0001a500a6b18995b03f44bb040a5ffc28e45cb0'
OUTPUT_TOKEN_ADDRESS = '0x6b175474e89094c44da98b954eedeac495271d0f'

from web3 import Account

account = Account.from_key(private_key)

params = {
            "network": CHAIN_NAME,
            "slippageTolerancePercent": "1.0",  # 1%
            "sor": {
                "sellToken": INPUT_TOKEN_ADDRESS,
                "buyToken": OUTPUT_TOKEN_ADDRESS,  # // token out
                "orderKind": "buy" if is_buy else "sell",
                "amount": input_amount,
                "gasPrice": 30000000000,
            },
            "batchSwap": {
                "funds": {
                    "sender": account.address,  #      // your address
                    "recipient": account.address,  #   // your address
                    "fromInternalBalance": False,  # // to/from internal balance
                    "toInternalBalance": False,  # // set to "false" unless you know what you're doing
                },
                # // unix timestamp after which the trade will revert if it hasn't executed yet
                "deadline": datetime.now().timestamp() + 60,
            },
        }

sor_result = bal.balSorQuery(params)

print(sor_result)