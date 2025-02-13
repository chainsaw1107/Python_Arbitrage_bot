"""
Constants for the olas_arbitrage package.
"""
import os
from pathlib import Path

from olas_arbitrage.exchanges.balancer import BalancerExchange
from olas_arbitrage.exchanges.balancer_optimised import BalancerExchangeOptimised
from olas_arbitrage.exchanges.jupitar_exchange import JupitarExchange
from olas_arbitrage.exchanges.uniswap_router import UniswapRouterExchange
from olas_arbitrage.exchanges.uniswap_v2 import UniswapV2Exchange
from tests.local_fork import LocalFork, get_unused_port

CONFIG_DIR = "configs/generated"
CONFIG_FILES = [
    str(Path(CONFIG_DIR) / Path(config_file)) for config_file in os.listdir(CONFIG_DIR)
]


DEFAULT_FORK_BLOCK_NUMBER = 18970222
TESTNET_RPC_URL = "https://rpc.ankr.com/eth"

# we make a local fork of mainnet for tests
local_fork = LocalFork(
    fork_url=TESTNET_RPC_URL,
    fork_block_number=DEFAULT_FORK_BLOCK_NUMBER,
    port=get_unused_port(),
)
local_fork.run()


UNISWAP_V2_KWARGS = {
    "chain_name": "ethereum",
    "chain_id": 1,
    "rpc_url": local_fork.host + ":" + str(local_fork.port),
    "block_explorer_url": "https://etherscan.io",
    "native_token_symbol": "ETH",
    "token_a": "0x0001A500A6B18995B03f44bb040A5fFc28E45CB0",
    "token_b": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "uniswap_pool_address": "0x09d1d767edf8fa23a64c51fa559e0688e526812f",
    "init_code_hash": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
    "router_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "path": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "exchange_type": "uniswap_v2",
}
BALANCER_EXCHANGE_KWARGS = {
    "chain_name": "gnosis",
    "chain_id": 100,
    "rpc_url": "https://rpc.gnosischain.com/",
    "block_explorer_url": "https://gnosisscan.io",
    "native_token_symbol": "XDAI",
    "vault_address": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    "token_a": "0xcE11e14225575945b8E6Dc0D4F2dD4C570f79d9f",
    "token_b": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
    "pool_id": "0x79c872ed3acb3fc5770dd8a0cd9cd5db3b3ac985000200000000000000000067",
    "exchange_type": "balancer",
}

UNISWAP_ROUTER_KWARGS = {
    "chain_name": "ethereum",
    "chain_id": 1,
    "rpc_url": local_fork.host + ":" + str(local_fork.port),
    "block_explorer_url": "https://etherscan.io",
    "native_token_symbol": "ETH",
    "token_a": "0x0001A500A6B18995B03f44bb040A5fFc28E45CB0",
    "token_b": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "router_address": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
    "permit2_address": "0x000000000022D473030F116dDEE9F6B43aC78BA3",
    "exchange_type": "uniswap_router",
}
SOL_ADDDRESS = "So11111111111111111111111111111111111111112"
OLAS_ADDRESS = "Ez3nzG9ofodYCvEmw73XhQ87LWNYVRM2s7diB5tBZPyM"

JUPITAR_EXCHANGE_PARAMS = {
    "chain_name": "solana",
    "rpc_url": "https://api.mainnet-beta.solana.com",
    "token_b": {
        "address": SOL_ADDDRESS,
        "symbol": "SOL",
    },
    "token_a": {
        "address": OLAS_ADDRESS,
        "symbol": "OLAS",
    },
    "exchange_type": "jupitar",
    "block_explorer_url": "https://solscan.io",
}


EXCHANGES = {
    "uniswap_v2": (UniswapV2Exchange, UNISWAP_V2_KWARGS),
    "uniswap_router": (UniswapRouterExchange, UNISWAP_ROUTER_KWARGS),
    "balancer": (BalancerExchange, BALANCER_EXCHANGE_KWARGS),
    "balancer_optimized": (BalancerExchangeOptimised, BALANCER_EXCHANGE_KWARGS),
    "jupitar": (JupitarExchange, JUPITAR_EXCHANGE_PARAMS),
}

FORK_PARAMS = {
    "uniswap_v2": (
        DEFAULT_FORK_BLOCK_NUMBER,
        TESTNET_RPC_URL,
    ),
    "uniswap_router": (
        19076358,
        TESTNET_RPC_URL,
    ),
    "balancer": (
        31863342,
        "https://rpc.ankr.com/gnosis",
    ),
    "balancer_optimized": (
        31863342,
        "https://rpc.ankr.com/gnosis",
    ),
}
