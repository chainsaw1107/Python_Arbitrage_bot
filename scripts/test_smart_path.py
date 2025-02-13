import datetime
import decimal
import os
import sys
from decimal import Decimal

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3.middleware import construct_sign_and_send_raw_middleware

from eth_defi.provider.multi_provider import create_multi_provider_web3
from eth_defi.revert_reason import fetch_transaction_revert_reason
from eth_defi.token import fetch_erc20_details
from eth_defi.confirmation import wait_transactions_to_complete
from eth_defi.uniswap_v3.constants import UNISWAP_V3_DEPLOYMENTS
from eth_defi.uniswap_v3.deployment import fetch_deployment
from eth_defi.uniswap_v3.swap import swap_with_slippage_protection

# The address of a token we are going to swap out
#
# Use https://tradingstrategy.ai/search to find your token
#
# For quote terminology see https://tradingstrategy.ai/glossary/quote-token
#
QUOTE_TOKEN_ADDRESS = "0x471EcE3750Da237f93B8E339c536989b8978a438"  # USDC (native)

# The address of a token we are going to receive
#
# Use https://tradingstrategy.ai/search to find your token
#
# For base terminology see https://tradingstrategy.ai/glossary/base-token
BASE_TOKEN_ADDRESS = "0x122013fd7df1c6f636a5bb8f03108e876548b455"  # WETH


# Connect to JSON-RPC node
rpc_env_var_name = "JSON_RPC_POLYGON"
json_rpc_url = 'http://eth.chains.wtf:8545'
json_rpc_url = "https://forno.celo.org"
assert json_rpc_url, f"You need to give {rpc_env_var_name} node URL. Check ethereumnodes.com for options"

w3 = create_multi_provider_web3(json_rpc_url)

from web3 import Web3
from uniswap_universal_router_decoder import RouterCodec
codec = RouterCodec(w3=w3)


trx_hash = '0xeab1ceaa6e162d59db111f3ab68ae5530415255951970eb0071303a8a6bd3e14'
decoded_transaction = codec.decode.transaction(trx_hash)

from rich import print
print(decoded_transaction)
