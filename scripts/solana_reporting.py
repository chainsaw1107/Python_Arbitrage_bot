# const axios = require("axios");
# const fs = require("fs");
# const path = require("path");

# const API_KEY = "YOUR_API_KEY";
# const USER_ACCOUNT = "YOUR_USER_ACCOUNT";

# const newDirectory = path.join(__dirname, "build");

# function newDir() {
#   if (fs.existsSync(newDirectory)) {
#     fs.rmSync(newDirectory, { recursive: true, force: true });
#     fs.mkdir(newDirectory, (err) => console.log(err));
#   } else {
#     fs.mkdir(newDirectory, (err) => console.log(err));
#   }
# }

# const options = (params) => {
#   return {
#     method: "POST",
#     url: "https://rest-api.hellomoon.io/v0/solana/all-time/txns-by-user",
#     headers: {
#       accept: "application/json",
#       "content-type": "application/json",
#       authorization: `Bearer ${API_KEY}`,
#     },
#     data: params,
#   };
# };

# async function loopUntilNoPagination(paginationToken, params, responseArr) {
#   const paramsWithPagination = {
#     ...params,
#     paginationToken,
#   };
#   const response = await axios.request(options(paramsWithPagination));
#   const { data, paginationToken: newPaginationToken } = response.data;
#   responseArr.push(data);

#   if (paginationToken) {
#     await loopUntilNoPagination(newPaginationToken, params, responseArr);
#   }
# }

# async function printTransactions(params) {
#   const responseArr = [];
#   const response = await axios.request(options(params));
#   const { data, paginationToken } = response.data;
#   responseArr.push(data);
#   if (paginationToken) {
#     await loopUntilNoPagination(paginationToken, params, responseArr);
#   }
#   return responseArr;
# }

# const ONE_MONTH_EPOCH = 86400 * 30;

# async function main() {
#   const startBlockTime = 1677794553 - 86400 * 93; // add you own start and end blocktime here
#   const endBlockTime = 1677794553;

#   newDir();

#   const intervalParams = [];
#   let incrementBlockTime = endBlockTime;
#   while (startBlockTime < incrementBlockTime) {
#     let lessThan = incrementBlockTime;
#     if (startBlockTime > incrementBlockTime - ONE_MONTH_EPOCH) {
#       incrementBlockTime = startBlockTime;
#     } else {
#       incrementBlockTime = incrementBlockTime - ONE_MONTH_EPOCH;
#     }

#     let greaterThan = incrementBlockTime;

#     const params = {
#       blocktime: {
#         operator: "between",
#         greaterThan: greaterThan,
#         lessThan: lessThan,
#       },
#       userAccount: USER_ACCOUNT,
#     };

#     intervalParams.push(params);
#   }

#   console.log(intervalParams); // a list of start and end blocktime parameters by month

#   const allTxns = [];
#   await Promise.all(
#     intervalParams.map(async (params) => {
#       const txn = await printTransactions(params);
#       const flattenedTxn = txn.flat();
#       console.log(flattenedTxn.length);
#       allTxns.push(...flattenedTxn);
#     })
#   );

#   allTxns.sort((a, b) => b.blocktime - a.blocktime);

#   let transactionByString = "";
#   allTxns.forEach((transaction) => {
#     transactionByString += JSON.stringify(transaction) + "\n";
#   });

#   // Do something with "allTxns" here, like write it to a file
#   fs.writeFileSync(path.join(newDirectory, "text.json"), transactionByString);
# }

# main().then(() => console.log("done"));

## We convert this to python

import asyncio
import requests
import json
import os
from datetime import datetime

API_KEY = os.getenv("HELLOMOON_API_KEY")
USER_ACCOUNT = os.getenv("HELLOMOON_USER_ACCOUNT")

newDirectory = os.path.join(os.path.dirname(__file__), "build")


def new_dir():
    if os.path.exists(newDirectory):
        os.rmdir(newDirectory)
        os.mkdir(newDirectory)
    else:
        os.mkdir(newDirectory)


def options(params):
    return {
        "method": "POST",
        "url": "https://rest-api.hellomoon.io/v0/solana/all-time/txns-by-user",
        "headers": {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {API_KEY}",
        },
        "data": params,
    }


async def loop_until_no_pagination(pagination_token, params, response_arr):
    params_with_pagination = {**params, "paginationToken": pagination_token}
    response = requests.request(**options(params_with_pagination))
    data = response.json()
    response_arr.append(data["data"])

    if pagination_token:
        await loop_until_no_pagination(data["paginationToken"], params, response_arr)


async def print_transactions(params):
    response_arr = []
    response = requests.request(**options(params))
    data = response.json()
    print(data)
    response_arr.append(data["data"])
    if data["paginationToken"]:
        await loop_until_no_pagination(data["paginationToken"], params, response_arr)
    return response_arr


ONE_MONTH_EPOCH = 86400 * 30


async def main():
    start_block_time = 1677794553 - 86400 * 93
    end_block_time = 1677794553

    new_dir()

    interval_params = []
    increment_block_time = end_block_time
    while start_block_time < increment_block_time:
        less_than = increment_block_time
        if start_block_time > increment_block_time - ONE_MONTH_EPOCH:
            increment_block_time = start_block_time
        else:
            increment_block_time = increment_block_time - ONE_MONTH_EPOCH

        greater_than = increment_block_time

        params = {
            "blocktime": {
                "operator": "between",
                "greaterThan": greater_than,
                "lessThan": less_than,
            },
            "greaterThan": greater_than,
            "userAccount": USER_ACCOUNT,
        }

        interval_params.append(params)

    print(interval_params)

    all_txns = []
    await asyncio.gather(*[print_transactions(params) for params in interval_params])

    all_txns.sort(key=lambda x: x["blocktime"], reverse=True)

    transaction_by_string = ""
    for transaction in all_txns:
        transaction_by_string += json.dumps(transaction) + "\n"

    with open(os.path.join(newDirectory, "text.json"), "w") as f:
        f.write(transaction_by_string)


if __name__ == "__main__":
    asyncio.run(main())
