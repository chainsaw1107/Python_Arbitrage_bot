# olas_arbitrage


requirements

- [poetry](https://python-poetry.org/docs/#installing-with-the-official-installer)

## Checking out and installing

```bash
git submodule update --init --recursive
poetry install
```

# setting up to run

```bash
export ETHERSCAN_API_KEY=xxx123
echo -n PRIVATE_KEY > ethereum_private_key.txt
```

# confirm sufficient balances of the trading assets
```bash
arb balance
```
# Running the strategy

The strategy can be run from the command line as so.
```bash
arb --log-level DEBUG check \ 
    --config-file gno_config.json \
    --trade-size 0.001 \ # this is of the OLAS token.
    --min-profit 0.025 # 2.5%
    # --execute  # uncomment the line to enable execution.
```

# Running in docker-compose

```bash
# Necessary env vars saved in a .env file.

ZERION_API_KEY=
SLACK_CHANNEL=
SLACK_TOKEN=
```

start the gno strategy
```bash
docker-compose  --profile gno up --build --force-recreate -d --remove-orphans
```

start the olas strategy

```bash
docker-compose  --profile olas up --build --force-recreate -d --remove-orphans
```