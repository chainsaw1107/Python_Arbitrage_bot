"""
Use the zerion api in order to generate reports on transactions
"""
import csv
import json
import os

import pandas as pd
import pygsheets
import requests

from olas_arbitrage.constants import DEFAULT_ENCODING

DEFAULT_TIMEOUT = 30


class CryptoTransactionReporter:
    """
    Reports on crypto transactions for a given wallet address
    """

    def __init__(self, base_url, auth_header):
        """
        Initialize the reporter.
        """
        self.base_url = base_url
        self.auth_header = auth_header

    def fetch_transactions(
        self, wallet_address, currency, start_date, end_date, page_size=100
    ):
        """
        Fetch transactions for a given wallet address
        """
        endpoint = f"{self.base_url}/{wallet_address}/transactions/"
        params = {
            "currency": currency,
            "page[size]": page_size,
            "filter[min_mined_at]": int(start_date.timestamp() * 1000),
            "filter[max_mined_at]": int(end_date.timestamp() * 1000),
        }
        headers = {"accept": "application/json", "authorization": self.auth_header}

        transactions = []
        while True:
            response = requests.get(
                endpoint, headers=headers, params=params, timeout=DEFAULT_TIMEOUT
            )
            if response.status_code != 200:
                print(f"Error fetching transactions: {response.text}")
                break

            data = response.json()
            transactions.extend(data["data"])

            if "next" in data["links"] and data["links"]["next"]:
                endpoint = data["links"]["next"]
            else:
                break

        return transactions

    def parse_transactions(
        self, transactions, chains, currencies
    ):  # pylint: disable=R0914
        """
        Check if the transaction is a trade and parse it.
        """
        parsed_transactions = []
        for transaction in transactions:
            tx_data = transaction["attributes"]
            chain_data = transaction["relationships"]["chain"]["data"]

            transfers = tx_data["transfers"]

            if len(transfers) == 0:
                continue

            in_transfers = [t for t in transfers if t["direction"] == "in"]
            out_transfers = [t for t in transfers if t["direction"] == "out"]

            if len(in_transfers) == 0 or len(out_transfers) == 0:
                continue
            if tx_data["operation_type"] != "trade":
                continue

            input_amount = in_transfers[0]["quantity"]["numeric"]
            input_currency = in_transfers[0]["fungible_info"]["symbol"]

            output_amount = out_transfers[0]["quantity"]["numeric"]
            output_currency = out_transfers[0]["fungible_info"]["symbol"]

            bases = ["OLAS"]

            parsed_tx = {
                "hash": tx_data["hash"],
                "operation_type": tx_data["operation_type"],
                "mined_at": tx_data["mined_at"],
                "status": tx_data["status"],
                "nonce": tx_data["nonce"],
                "fee": tx_data["fee"]["value"],
                "chain": chain_data["id"],
                "input_amount": input_amount,
                "input_currency": input_currency,
                "output_amount": output_amount,
                "output_currency": output_currency,
                "side": "buy" if input_currency in bases else "sell",
            }

            rate = float(parsed_tx["input_amount"]) / float(parsed_tx["output_amount"])
            if parsed_tx["side"] == "sell":
                parsed_tx["rate"] = rate
            else:
                parsed_tx["rate"] = 1 / rate
            parsed_transactions.append(parsed_tx)
        # we apply the filters here
        if chains:
            parsed_transactions = [
                tx for tx in parsed_transactions if tx["chain"] in chains
            ]

        if currencies:
            parsed_transactions = [
                tx
                for tx in parsed_transactions
                if (
                    tx["input_currency"] in currencies
                    and tx["output_currency"] in currencies
                )
            ]
        return parsed_transactions

    def generate_csv_report(self, parsed_transactions, file_name):
        """
        Generate a csv report with the parsed transactions.
        """
        with open(file_name, mode="w", newline="", encoding=DEFAULT_ENCODING) as file:
            writer = csv.DictWriter(file, fieldnames=parsed_transactions[0].keys())
            writer.writeheader()
            for transaction in parsed_transactions:
                writer.writerow(transaction)

    def run_report(
        self,
        wallet_address,
        currency,
        file_name,
        start_date,
        end_date,
        output=None,
        chains=None,
        currencies=None,
        sheet_name="Arb tracking",
    ):
        """
        Run the report for the given wallet address.
        """
        transactions = self.fetch_transactions(
            wallet_address, currency, start_date, end_date
        )
        print(f"Found {len(transactions)} transactions")
        parsed_transactions = self.parse_transactions(
            transactions, chains=chains, currencies=currencies
        )
        self.generate_csv_report(parsed_transactions, file_name)

        if output == "gsheets":
            self.upload_to_gsheets(file_name, sheet_name)
        elif output == "slack":
            self.upload_to_slack(file_name)
        elif output == "database":
            self.upload_to_database(file_name)
        else:
            print("No output specified")

    def upload_to_gsheets(self, file_name, sheet_name="Arb tracking"):
        """upload csv to google sheets, appending to the existing sheet."""

        new_txs = pd.read_csv(file_name)
        default_service_file = "gsheets_private_key.json"
        service_file = os.environ.get("GSHEET_CREDS_PATH", default_service_file)
        gc = pygsheets.authorize(service_file=service_file)
        sheet_name = os.environ.get("SHEET_NAME", sheet_name)
        sh = gc.open(sheet_name)
        # the sheet is called 'raw_data'
        wks = sh[0]
        # we insert enough empty rows to make sure we don't overwrite any existing data
        # we read in the existing data and create a set sorted by mined_at
        # we then append the new data to the existing data
        # we then write the new data to the sheet
        existing_txs = wks.get_as_df()
        existing_txs = existing_txs.append(new_txs)
        existing_txs = existing_txs.sort_values(by="mined_at")
        wks.clear()
        wks.insert_rows(row=1, number=len(existing_txs))
        wks.set_dataframe(new_txs, "A1")

    def upload_to_slack(self, file_name):
        """upload csv to slack, appending to the existing sheet."""

        token = os.environ.get("SLACK_TOKEN")
        channel = os.environ.get("SLACK_CHANNEL")
        url = "https://slack.com/api/files.upload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        with open(file_name, "rb", encoding=DEFAULT_ENCODING) as f:
            csv_data = f.read()

        msg = "New for the day"
        data = {
            "channels": channel,
            "initial_comment": msg,
            "filetype": "csv",
            "filename": file_name,
            "content": csv_data,
        }

        response = requests.post(
            url, headers=headers, data=data, timeout=DEFAULT_TIMEOUT
        )
        print(f"Uploaded to slack: {json.loads(response.text)['ok']}")

    def upload_to_database(self, file_name):
        """upload csv to database, appending to the existing sheet."""
        # we create our conenction using the sqlalchemy engine
        # we then read in the csv file
        # we then write the data to the database
        # we then close the connection

        from sqlalchemy import create_engine, text

        database_url = os.environ.get("DATABASE_URL")
        engine = create_engine(database_url)
        connection = engine.connect()

        print(f"Collecting Hashes from database")
        existing_data = pd.read_sql(
            text("SELECT hash FROM transactions"), con=connection
        )
        new_data = pd.read_csv(file_name)
        # we check if we have any new data
        diffs = new_data[~new_data.hash.isin(existing_data.hash)].dropna()
        if diffs.empty:
            print("No new data to upload")
            return
        df = pd.concat([diffs], ignore_index=True)

        # we make sure we don't have any duplicates based on the hash
        df = df.drop_duplicates(subset=["hash"])
        df.to_sql("transactions", con=engine, if_exists="append", index=False)
        engine.dispose()


def run_reporter(
    start_date,
    end_date,
    wallet_address,
    currencies: list,
    chains: list,
    output: str = "gsheets",
):
    """
    Run the reporter.
    """

    zerion_api = os.environ.get("ZERION_API_KEY")
    reporter = CryptoTransactionReporter(
        "https://api.zerion.io/v1/wallets", "Basic " + zerion_api
    )
    sheet_name = os.environ.get("SHEET_NAME", "Arb tracking")
    reporter.run_report(
        wallet_address,
        "usd",
        "crypto_transactions.csv",
        start_date,
        end_date,
        currencies=currencies,
        chains=chains,
        output=output,
        sheet_name=sheet_name,
    )
    print(f"Done reporting for {wallet_address} from {start_date} to {end_date}")
