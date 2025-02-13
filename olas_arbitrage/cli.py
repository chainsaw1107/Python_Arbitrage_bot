"""
Cli entry point for olas_arbitrage
"""
import logging
import os
import time
from datetime import datetime, timedelta

import click
import schedule
from dotenv import load_dotenv

from olas_arbitrage.constants import CHAIN_CONFIGS, DEFAULT_ENCODING
from olas_arbitrage.reporting import run_reporter
from olas_arbitrage.strategy import Strategy
from olas_arbitrage.utils import get_config, get_logger

load_dotenv()


@click.group()
@click.option("--log-file", default="log.txt")
@click.option(
    "--log-level",
    default="INFO",
)
@click.pass_context
def cli(ctx, log_level, log_file):
    """
    Entry point for olas_arbitrage
    """
    logger = get_logger(log_level=log_level, log_file=log_file)
    ctx.obj = logger
    logger.debug("Initialized logger")
    logger.critical("STARTING ARBITRAGE BOT")
    logger.critical("*" * 25)


# group to start watching for arbitrage opportunities


@cli.command()
@click.pass_context
@click.option("--watch/--no-watch", default=False)
@click.option("--execute-sell/--no-execute-sell", default=True)
@click.option("--execute-buy/--no-execute-buy", default=True)
@click.option("--async-execution/--no-async-execution", default=False)
@click.option("--min-profit", default=0.01)
@click.option("--trade-size", default=1.0)
@click.option("--config-file", default=None)
@click.option("--cool-down", default=0)
@click.option("--sell-bias", default=0.0, help="Bias for selling in a decimal i.e. 0.1 = 10%")
@click.option("--buy-bias", default=0.0, help="Bias for buying in a decimal i.e. 0.1 = 10%")
def check(
    ctx,
    watch,
    execute_sell,
    execute_buy,
    async_execution,
    min_profit,
    trade_size,
    config_file,
    cool_down,
    sell_bias,
    buy_bias,
):
    """
    Start watching for arbitrage opportunities
    """

    config = CHAIN_CONFIGS
    if config_file:
        ctx.obj.info(f"Loading config from {config_file}")
        config = get_config(config_file)

    ctx.obj.info("Checking for arbitrage opportunities")
    ctx.obj.info(f"Executing buys: {execute_buy}")
    ctx.obj.info(f"Executing sells: {execute_sell}") 

    strategy = Strategy(
        logger=ctx.obj,
        min_profit=min_profit,
        execution_amount_token_a=trade_size,
        chain_config=config,
        sell_bias=sell_bias,
        buy_bias=buy_bias,
    )

    while True:
        try:
            strategy.run(
                sell_enabled=execute_sell,
                buy_enabled=execute_buy,
                async_execution=async_execution,
            )
            ctx.obj.debug(f"Sleeping for {strategy.execution_interval} seconds")
            if not watch:
                break
            if cool_down:
                time.sleep(cool_down)
        except KeyboardInterrupt:
            ctx.obj.info("Keyboard interrupt detected. Stopping bot")
            break


@cli.command()
@click.pass_context
def run_from_env(ctx):
    """
    Run the bot using the environment variables
    """

    ctx.obj.setLevel(logging.DEBUG)
    ctx.obj.info("Running bot from environment variables")

    config_file = os.getenv("CONFIG_FILE")
    if not config_file:
        ctx.obj.info("No config file specified, Please set CONFIG_FILE")
        return

    config = get_config(config_file)
    if config_file:
        ctx.obj.info(f"Loading config from {config_file}")

    eth_key = os.getenv("ETH_KEY")
    if not eth_key:
        ctx.obj.info("No eth key specified, Please set ETH_KEY")
        return

    # we check if a file called etehreum_private_key exists, if it does we use that as the key

    if os.path.exists("ethereum_private_key.txt"):
        ctx.obj.error("ethereum_private_key.txt exists, please remove it")
        return

    with open("ethereum_private_key.txt", "w", encoding=DEFAULT_ENCODING) as f:
        f.write(eth_key)
        ctx.obj.info("Wrote ethereum private key to file")

    ctx.obj.setLevel(logging.CRITICAL)

    strategy_config = {}
    for k, v in {
        "min_profit": 0.10,
        "execution_interval": 1,
        "execution_amount_token_a": 20,
        "min_native_balance": 0.1,
        "buy_bias": 0,
        "sell_bias": 0.1,
    }.items():
        env_name = k.upper()
        if os.getenv(env_name):
            strategy_config[k] = os.getenv(env_name)
        else:
            strategy_config[k] = v

    strategy = Strategy(logger=ctx.obj, chain_config=config, **strategy_config)
    # we make sure we loop forever
    while True:
        strategy.run()
        time.sleep(int(strategy.execution_interval))


@cli.command()
@click.pass_context
@click.option("--config-file", default=None)
def balance(ctx, config_file):
    """
    Check the balance of the bot
    """
    config = None
    if config_file:
        ctx.obj.info(f"Loading config from {config_file}")
        config = get_config(config_file)

    ctx.obj.setLevel(logging.DEBUG)
    ctx.obj.info("Checking balance")
    strategy = Strategy(logger=ctx.obj, chain_config=config)
    strategy.has_sufficient_balance()


# group to check the balances of the bot
@cli.command()
@click.pass_context
@click.option("--config-file", default=None)
@click.option("--amount", default=10000000000008)
@click.option("--exchange", default=None)
def approvals(ctx, config_file, amount, exchange):
    """
    Check the approvals of the bot account
    """
    config = None
    if config_file:
        ctx.obj.info(f"Loading config from {config_file}")
        config = get_config(config_file)

    ctx.obj.setLevel(logging.DEBUG)
    ctx.obj.info("Checking balance")
    strategy = Strategy(logger=ctx.obj, chain_config=config)
    strategy.do_approvals(amount=amount, exchange=exchange)


@cli.command()
@click.pass_context
@click.option("--time-of-report", default=None, help="Time of report in HH:MM format")
@click.option("--repeat/--no-repeat", default=False)
@click.option("--output", default="gsheets")
@click.option("--timeperiod", default=1)
@click.option("--chains", default="ethereum,xdai")
@click.option("--currencies", default="DAI,OLAS")
def report(ctx, time_of_report, repeat, output, timeperiod, chains, currencies):
    """
    Run the reporter
    if the time is given wait until the right time, otherwise run the reporter once.
    if period is given schedule collect the data for the given period.
    if repeat is given schedule the reporter to run at the given time every day.
    """

    eth_key = os.getenv("ETH_KEY")
    if not eth_key and not os.path.exists("ethereum_private_key.txt"):
        ctx.obj.info("No eth key specified, Please set ETH_KEY")
        return

    # we check if a file called etehreum_private_key exists, if it does we use that as the key
    if os.path.exists("ethereum_private_key.txt") and eth_key:
        ctx.obj.error("ethereum_private_key.txt exists, please remove it")
        return

    if eth_key:
        with open("ethereum_private_key.txt", "w", encoding=DEFAULT_ENCODING) as f:
            f.write(eth_key)
            ctx.obj.info("Wrote ethereum private key to file")

    # we also check for the gsheets credentials

    ctx.obj.setLevel(logging.DEBUG)
    ctx.obj.info("Running reporter for arbitrage bot")
    ctx.obj.info(f"Time of report: {time_of_report}")
    ctx.obj.info(f"Watch: {repeat}")

    report_time = time_of_report
    if not time_of_report:
        report_time = datetime.now().strftime("%H:%M")
    ctx.obj.info(f"Running reporter once at {report_time}")

    # we set the start date to yesterday and the end date to today, using the time of report as the end time
    # this way we can collect data for the previous day
    report_end_time = datetime.now().replace(
        hour=int(report_time.split(":")[0]), minute=int(report_time.split(":")[1])
    )
    report_start_time = report_end_time - timedelta(days=timeperiod)
    ctx.obj.info(f"Report start time: {report_start_time}")
    ctx.obj.info(f"Report end time: {report_end_time}")

    # we now check if the report should be run now, by checking if the current time is > the report end time

    strategy = Strategy(logger=ctx.obj)
    wallet_address = strategy.exchange_1.account.address
    if (
        datetime.now() > report_end_time
        and timedelta(minutes=5) > datetime.now() - report_end_time
    ):
        ctx.obj.info("Running report now")
        run_reporter(
            report_start_time,
            report_end_time,
            wallet_address,
            output=output,
            chains=chains.split(","),
            currencies=currencies.split(","),
        )
    else:
        ctx.obj.info(f"Scheduling report for {report_end_time}")
        schedule.every().day.at(time_of_report).do(
            run_reporter,
            report_start_time,
            report_end_time,
            wallet_address,
            output,
            chains.split(","),
            currencies.split(","),
        )

    while repeat:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
