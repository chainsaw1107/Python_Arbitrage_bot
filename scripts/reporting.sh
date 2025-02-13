!# /bin/bash

GSHEET_CREDS_PATH=$(echo $(pwd)/gsheets_private_key.json.kep)
echo "Using auth $GSHEET_CREDS_PATH"

# we check if we have the env var `GSHEET_SHEET_CREDS_PATH`

if [ -z "$GSHEET_CREDS_PATH" ]; then
  echo "GSHEET_CREDS_PATH is not set"
  exit 1
fi

# we check if we have the env var `CURRENCIES`
if [ -z "$CURRENCIES" ]; then
  echo "CURRENCIES is not set"
  exit 1
fi

# we check if we have the env var `CHAINS`
if [ -z "$CHAINS" ]; then
  echo "CHAINS is not set"
  exit 1
fi

# we check if timeframe is set
if [ -z "$TIMEPERIOD" ]; then
  echo "TIMEPERIOD is not set"
  exit 1
fi

arb report --timeperiod $TIMEPERIOD --chains $CHAINS --currencies $CURRENCIES