"""
Script to read the token list from the token_list.json file and generate the config file for the bot.
"""
from dataclasses import asdict, dataclass
import json
from rich import print_json

import requests

import yaml
import pandas as pd

SOURCE = "https://raw.githubusercontent.com/balancer/tokenlists/main/generated/balancer.tokenlist.json"


exchanges = ["uniswap_router", "balancer_optimised"]

# arbitrum, optimism, xdai, polygon, ethereum


@dataclass
class ChainConfig:
    chain_name: str
    exchange_type: str
    rpc_url: str
    block_explorer_url: str
    chain_id: int
    native_token_symbol: str
    token_a: str = None
    token_b: str = None
    router_address: str = None
    permit2_address: str = None
    vault_address: str = None


@dataclass
class Config:
    exchange_1: ChainConfig
    exchange_2: ChainConfig


chain_id_to_base = {
    1: ChainConfig(
        chain_name="ethereum",
        exchange_type="uniswap_router",
        chain_id=1,
        rpc_url="http://eth.chains.wtf:8545",
        block_explorer_url="https://etherscan.io/",
        native_token_symbol="ETH",
        router_address="0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
        permit2_address="0x000000000022D473030F116dDEE9F6B43aC78BA3",
    ),
    100: ChainConfig(
        chain_name="gnosis",
        exchange_type="balancer_optimised",
        chain_id=100,
        rpc_url="http://gnosis.chains.wtf:8545",
        vault_address="0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        block_explorer_url="https://blockscout.com/xdai/mainnet/",
        native_token_symbol="XDAI",
    ),
    137: ChainConfig(
        chain_name="polygon",
        exchange_type="balancer_optimised",
        chain_id=137,
        rpc_url="https://lb.nodies.app/v1/ed47ccb3c5c4464d8eb445e6c7cd82d7",
        vault_address="0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        block_explorer_url="https://polygonscan.com/",
        native_token_symbol="MATIC",
    ),
    42161: ChainConfig(
        chain_name="arbitrum",
        exchange_type="balancer_optimised",
        chain_id=42161,
        rpc_url="https://sly-special-tent.arbitrum-mainnet.quiknode.pro/aa465b0cd78549ec017e0368656a4b1a0087cc7a",
        vault_address="0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        block_explorer_url="https://arbiscan.io/",
        native_token_symbol="ETH",
    ),
    10: ChainConfig(
        chain_name="optimism",
        exchange_type="balancer_optimised",
        chain_id=10,
        rpc_url="https://lb.nodies.app/v1/8240365311df4c6d988304692f63b2dd",
        vault_address="0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        block_explorer_url="https://optimistic.etherscan.io/",
        native_token_symbol="ETH",
    ),
    # base
    8453: ChainConfig(
        chain_name="base",
        exchange_type="balancer_optimised",
        chain_id=8453,
        rpc_url="https://rpc.ankr.com/base",
        vault_address="0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        block_explorer_url="https://basescan.org/",
        native_token_symbol="ETH",
    ),
}

from functools import lru_cache

def get_address_from_symbol(symbol: str, token_list_df: pd.DataFrame, chain_id: int):
    token_list_df = pd.DataFrame(token_list_df)
    try:
        res = token_list_df[token_list_df["symbol"] == symbol]
        return res[res["chainId"] == chain_id]["address"].values[0]
    except IndexError:
        raise ValueError(
            f"Token with symbol {symbol} not found in token list for chain {chain_id}"
        )


@lru_cache
def generate_config_for_chain(chain_id: int, token_a: str, token_b: str):
    config = chain_id_to_base[chain_id]
    config.token_a = get_address_from_symbol(token_a, token_list_df, chain_id)
    config.token_b = get_address_from_symbol(token_b, token_list_df, chain_id)
    return config


def generate_config(
    exchange_1_chain_id: int = 1,
    exchange_2_chain_id: int = 100,
    exchange_1_token_a: str = "WETH",
    exchange_1_token_b: str = "wstETH",
    exchange_2_token_a: str = "WETH",
    exchange_2_token_b: str = "wstETH",
):
    exchange_1 = generate_config_for_chain(
        exchange_1_chain_id, exchange_1_token_a, exchange_1_token_b
    )
    exchange_2 = generate_config_for_chain(
        exchange_2_chain_id, exchange_2_token_a, exchange_2_token_b
    )
    config = Config(exchange_1=asdict(exchange_1), exchange_2=asdict(exchange_2))
    return config


def get_token_list():
    response = requests.get(SOURCE)
    return response.json()


def get_token_list_df():
    token_list = get_token_list()
    token_list_df = pd.DataFrame(token_list["tokens"])
    return token_list_df


def make_config():
    config = generate_config()
    print_json(data=asdict(config))

    with open("config.json", "w") as f:
        json.dump(asdict(config), f, indent=4)
    pass


def find_overlap(exchange_1: ChainConfig, exchange_2: ChainConfig):
    """GIve 2 exchange, find tokens that are in both and return them"""
    token_list_df = get_token_list_df()
    exchange_1_tokens = token_list_df[token_list_df["chainId"] == exchange_1.chain_id][
        "symbol"
    ].values
    exchange_2_tokens = token_list_df[token_list_df["chainId"] == exchange_2.chain_id][
        "symbol"
    ].values
    overlapping_tokens = [f for f in exchange_1_tokens if f in exchange_2_tokens]
    return overlapping_tokens


if __name__ == "__main__":
    # we do some quick groupby to see how many tokens are on each chain
    token_list_df = get_token_list_df()
    print(token_list_df.groupby("chainId").count())
    # we also want to figure out what we should be trading, so we can do some quick analysis
    print(
        token_list_df.groupby("symbol")["chainId"]
        .count()
        .sort_values(ascending=False)
        .head(20)
    )

    chains_ids = [
        100, 
        8453,
        ]
    for chain_id in chains_ids:
        print(f"Tokens for chain {chain_id}")
        print(token_list_df[token_list_df["chainId"] == chain_id]["symbol"].values)

    # we can also find the overlap between the 2 chains
    exchange_1 = chain_id_to_base[100]
    exchange_2 = chain_id_to_base[10]
    overlap = find_overlap(exchange_1, exchange_2)
    print(f"Overlap between {exchange_1.chain_name} and {exchange_2.chain_name}")
    print(overlap)

    make_config()

    print("Generating configs")
    # calculate how many possible configs we could have.

    BASES = [
        "OLAS",
    ]
    QUOTE = [
        "USDC",
        "USDT",
        "DAI",
        "WBTC",
        "ETH",
        "WETH",
        "wxDAI",
    ]
    CHAINS = [
        100, # xdai
        10, # optimism
        42161, # arbitrum
        8453,  # base
        137,  # polygon
        1 # ethereum
        ]
    configs = []
    for base in BASES:
        for quote in QUOTE:
            for chain in CHAINS:
                if base == quote:
                    continue
                # we skip stablecoin pairs
                if quote in ["USDC", "USDT", "DAI", "WXDAI", "wxDAI"]:
                    quotable = ["USDC", "USDT", "DAI", "WXDAI", "wxDAI"]
                else:
                    quotable = [quote]

                for chain_2 in CHAINS:
                    if chain == chain_2:
                        continue
                    if base == quote:
                        continue
                    # we check if the base is on the chain
                    if (
                        base
                        not in token_list_df[token_list_df["chainId"] == chain][
                            "symbol"
                        ].values
                    ):
                        continue
                    if (
                        base
                        not in token_list_df[token_list_df["chainId"] == chain_2][
                            "symbol"
                        ].values
                    ):
                        continue
                    # we check if the quote is on the chain
                    if (
                        quote
                        not in token_list_df[token_list_df["chainId"] == chain][
                            "symbol"
                        ].values
                    ):
                        continue

                    counter_found = False
                    for chain_2_quote in quotable:
                        if (
                            chain_2_quote
                            not in token_list_df[token_list_df["chainId"] == chain_2][
                                "symbol"
                            ].values
                        ):
                            continue

                        config = generate_config(
                            exchange_1_chain_id=chain,
                            exchange_2_chain_id=chain_2,
                            exchange_1_token_a=base,
                            exchange_1_token_b=quote,
                            exchange_2_token_a=base,
                            exchange_2_token_b=chain_2_quote,
                        )

                        if config not in configs:
                            configs.append(config)

    filtered_configs = {}
    for config in configs:
        # we here, effectively create a unique key for the config, based off the sorted tokens and chains
        chains = sorted([config.exchange_1["chain_id"], config.exchange_2["chain_id"]])
        # we then get the token names
        chain_1_tokens = token_list_df[
            token_list_df["chainId"] == config.exchange_1["chain_id"]
        ]
        chain_2_tokens = token_list_df[
            token_list_df["chainId"] == config.exchange_2["chain_id"]
        ]
        exa_token_a, exa_token_b = (
            config.exchange_1["token_a"],
            config.exchange_1["token_b"],
        )
        exb_token_a, exb_token_b = (
            config.exchange_2["token_a"],
            config.exchange_2["token_b"],
        )
        exa_token_a_name = chain_1_tokens[chain_1_tokens["address"] == exa_token_a][
            "symbol"
        ].values[0]
        exa_token_b_name = chain_1_tokens[chain_1_tokens["address"] == exa_token_b][
            "symbol"
        ].values[0]
        exb_token_a_name = chain_2_tokens[chain_2_tokens["address"] == exb_token_a][
            "symbol"
        ].values[0]
        exb_token_b_name = chain_2_tokens[chain_2_tokens["address"] == exb_token_b][
            "symbol"
        ].values[0]

        tokens = sorted(
            [exa_token_a_name, exa_token_b_name, exb_token_a_name, exb_token_b_name]
        )

        key = f"{chains[0]}-{chains[1]}-{tokens[0]}-{tokens[1]}-{tokens[2]}-{tokens[3]}"
        print(key)
        if key not in filtered_configs:
            filtered_configs[key] = config

    ## we write each of the configs to a file

    output_dir = "configs/generated"

    print(f"Writing {len(filtered_configs)} configs to {output_dir}")

    blacklist = []

    config_name_list = []
    for config in filtered_configs.values():
        exa_token_a, exa_token_b = (
            config.exchange_1["token_a"],
            config.exchange_1["token_b"],
        )
        exb_token_a, exb_token_b = (
            config.exchange_2["token_a"],
            config.exchange_2["token_b"],
        )
        # we now get the names of the tokens

        token_list_df = get_token_list_df()

        # we then select the chain names;
        chain_1, chain_2 = (
            config.exchange_1["chain_name"],
            config.exchange_2["chain_name"],
        )

        chain_1_tokens = token_list_df[
            token_list_df["chainId"] == config.exchange_1["chain_id"]
        ]
        chain_2_tokens = token_list_df[
            token_list_df["chainId"] == config.exchange_2["chain_id"]
        ]

        # we then get the token names
        exa_token_a_name = chain_1_tokens[chain_1_tokens["address"] == exa_token_a][
            "symbol"
        ].values[0]
        exa_token_b_name = chain_1_tokens[chain_1_tokens["address"] == exa_token_b][
            "symbol"
        ].values[0]
        exb_token_a_name = chain_2_tokens[chain_2_tokens["address"] == exb_token_a][
            "symbol"
        ].values[0]
        exb_token_b_name = chain_2_tokens[chain_2_tokens["address"] == exb_token_b][
            "symbol"
        ].values[0]

        chain_1, chain_2 = (
            config.exchange_1["chain_name"],
            config.exchange_2["chain_name"],
        )

        config_name = f"{chain_1}-{exa_token_a_name}-{exa_token_b_name}-{chain_2}-{exb_token_a_name}-{exb_token_b_name}".lower()

        path = f"{output_dir}/{config_name}"

        found = False
        for black in blacklist:
            if config_name.find(black) != -1:
                print(f"Skipping {config_name} as {black} is in blacklist")
                found = True

        if found:
            continue
        with open(path, "w") as f:
            json.dump(asdict(config), f, indent=4)

        config_name_list.append(config_name)


    with open("charts/arbitrage/config_list.yaml", "r") as f:
        old = yaml.safe_load(f)

    old['config']['config_paths'] = config_name_list
    with open("charts/arbitrage/config_list.yaml", "w") as f:
        yaml.safe_dump(old, f, indent=2)

    print("Done")
