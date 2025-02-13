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


# Connect to JSON-RPC node
rpc_env_var_name = "JSON_RPC_POLYGON"
json_rpc_url = 'http://eth.chains.wtf:8545'
json_rpc_url = "https://forno.celo.org"
assert json_rpc_url, f"You need to give {rpc_env_var_name} node URL. Check ethereumnodes.com for options"

w3 = create_multi_provider_web3(json_rpc_url)

from web3 import Web3
from uniswap_universal_router_decoder import RouterCodec
codec = RouterCodec(w3=w3)


# trx_hash = '0xeab1ceaa6e162d59db111f3ab68ae5530415255951970eb0071303a8a6bd3e14'
# decoded_transaction = codec.decode.transaction(trx_hash)

from rich import print
# print(decoded_transaction)


from olas_arbitrage.exchanges.uniswap_router import UniswapRouterExchange

QUOTE_TOKEN_ADDRESS = w3.to_checksum_address("0x471EcE3750Da237f93B8E339c536989b8978a438") # USDC (native)

# The address of a token we are going to receive
#
# Use https://tradingstrategy.ai/search to find your token
#
# For base terminology see https://tradingstrategy.ai/glossary/base-token
BASE_TOKEN_ADDRESS = w3.to_checksum_address("0x122013fd7df1c6f636a5bb8f03108e876548b455")

import logging

logger = logging.getLogger(__name__)
kwargs = {
    "chain_name": "celo",
    "exchange_type": "uniswap_router",
    "chain_id": 42220,
    "rpc_url": "https://forno.celo.org",
    "block_explorer_url": "https://celoscan.io",
    "native_token_symbol": "CELO",
    "token_a": QUOTE_TOKEN_ADDRESS,
    "token_b": BASE_TOKEN_ADDRESS,
    "router_address": "0xE3D8bd6Aed4F159bc8000a9cD47CffDb95F96121",
    "permit2_address": "0x000000000022D473030F116dDEE9F6B43aC78BA3",
    "logger": logger,
}
exchange = UniswapRouterExchange(**kwargs)




from uniswap_smart_path import SmartPath



USDT_ADDRESS = w3.to_checksum_address('0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e')
CELO_ADDRESS = w3.to_checksum_address('0x471ece3750da237f93b8e339c536989b8978a438')
USDC_ADDRESS = w3.to_checksum_address('0xceba9300f2b948710d2653dd7b07f33a8b32118c')

pivot_tokens = (CELO_ADDRESS, USDT_ADDRESS, USDC_ADDRESS, )  # BSC addresses
v3_pool_fees = (100, 500, 3000, 10000)  # Pancakeswap v3 fees

V2_ROUTER =  w3.to_checksum_address('0xe3d8bd6aed4f159bc8000a9cd47cffdb95f96121')
v2_FACTORY = w3.to_checksum_address('0x62d5b84be28a183abb507e125b384122d2c25fae')
v3_QUOTER =  w3.to_checksum_address('0x1f34a843832044A085bB9cAe48cc7294D5478FAA')
v3_FACTORY = w3.to_checksum_address('0x67FEa58D5a5a4162cED847E13c2c81c73bf8aeC4')


kwargs = {
    'pivot_tokens': pivot_tokens,
    'v3_pool_fees': v3_pool_fees,
    'v2_router': V2_ROUTER,
    'v2_factory': v2_FACTORY,
    'v3_quoter': v3_QUOTER,
    'v3_factory': v3_FACTORY,
    'rpc_endpoint': 'https://rpc.ankr.com/celo',
    'chain_id': 42220,
}

async def get_custom_path(kwargs, w3) -> SmartPath:
    smart_path = await SmartPath.create_custom(
            **kwargs
        )
    
    return smart_path


async def main():
    from web3 import Web3
    # we make an async web3 instance
    smart_path = await get_custom_path(kwargs, w3)
    path = await (smart_path.get_swap_in_path(
        int(1e6),
        USDC_ADDRESS, 
        CELO_ADDRESS, 
        ))
    print(path)

import json
print(json.dumps(kwargs))

import asyncio

asyncio.run(main())




