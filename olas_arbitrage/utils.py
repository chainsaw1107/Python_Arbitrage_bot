"""
Utilities for auto_dev.
"""
import json
import logging

from rich.console import Console
from rich.logging import RichHandler
from web3 import Web3

from olas_arbitrage.constants import DEFAULT_ENCODING


def get_logger(name=__name__, log_level="INFO", log_file=None):
    """Get the logger."""
    # we add in an extra var to show the client so that we can see the logs
    # we need to see the exact module that is causing the error
    msg_format = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        console=Console(width=256),
    )
    logging.basicConfig(
        level="NOTSET", format=msg_format, datefmt="[%X]", handlers=[handler]
    )

    # Disable logging of JSON-RPC requests and replies
    logging.getLogger("web3.RequestManager").setLevel(logging.WARNING)
    logging.getLogger("web3.providers.HTTPProvider").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uniswap_smart_path").setLevel(logging.WARNING)
    logging.getLogger("_client.py").setLevel(logging.WARNING)
    logging.getLogger("packages").setLevel(logging.WARNING)
    logging.getLogger("certifi").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)

    log = logging.getLogger(name)
    log.setLevel(log_level)
    if log_file:
        handler = logging.FileHandler(log_file)
        handler.setLevel(log_level)
        log.addHandler(handler)
    return log


def to_human_readable(num):
    """
    Convert number to human readable format
    """
    return Web3.from_wei(num, "ether")


def get_config(config_file):
    """Loads the config from the config file"""
    with open(config_file, "r", encoding=DEFAULT_ENCODING) as f:
        config = json.loads(f.read())
    return config
