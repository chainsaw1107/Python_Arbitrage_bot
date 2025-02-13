"""
Constants for the olas_arbitrage package.
"""
from decimal import Decimal
from glob import glob
from pathlib import Path

DEFAULT_ENCODING = "utf-8"
MIN_NATIVE_BALANCE = 0.01
BALANCER_SWAP_FEE = Decimal(0.003)
GNOSIS_RPC_URL = "https://rpc.gnosischain.com/"
MAINNET_RPC_URL = "https://rpc.mevblocker.io"


CHAIN_CONFIGS = {
    "exchange_1": {
        "chain_id": 100,
        "exchange_type": "balancer",
        "chain_name": "gnosis",
        "rpc_url": "https://lb.nodies.app/v1/91c9d7176d2543fc8037620721f9de2b",
        "block_explorer_url": "https://gnosisscan.io",
        "native_token_symbol": "XDAI",
        "vault_address": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        "token_a": "0xcE11e14225575945b8E6Dc0D4F2dD4C570f79d9f",
        "token_b": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
        "pool_id": "0x79c872ed3acb3fc5770dd8a0cd9cd5db3b3ac985000200000000000000000067",
    },
    "exchange_2": {
        "chain_id": 1,
        "chain_name": "ethereum",
        "exchange_type": "uniswap_v2",
        "rpc_url": "https://lb.nodies.app/v1/7606abc07b684b5a8a99e4ee99b24520",  # pylint: disable=line-too-long
        "block_explorer_url": "https://etherscan.io",
        "native_token_symbol": "ETH",
        "token_a": "0x0001a500a6b18995b03f44bb040a5ffc28e45cb0",
        "token_b": "0x6b175474e89094c44da98b954eedeac495271d0f",
        "uniswap_pool_address": "0x09d1d767edf8fa23a64c51fa559e0688e526812f",
        "init_code_hash": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
        "router_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "path": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    },
}


ETH_KEYPATH = Path("ethereum_private_key.txt")


PACKAGE_DIR = Path(__file__).parent
ABI_DIR = PACKAGE_DIR / "abis"


ABI_MAPPING = {
    Path(path)
    .stem.upper(): open(path, encoding=DEFAULT_ENCODING)  # pylint: disable=R1732
    .read()  # pylint: disable=R1732
    for path in glob(str(ABI_DIR / "*.json"))
}
