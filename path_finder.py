import asyncio
import json
from dataclasses import dataclass
from uniswap_smart_path import SmartPath
from web3 import Web3, Account
from web3.contract import Contract
from uniswap_universal_router_decoder import FunctionRecipient, RouterCodec

from rich import print


codec = RouterCodec()

rpc_endpoint = "https://nd-rwvsmdaoybb23lxrmty44k27ee.t.ethereum.managedblockchain.us-east-1.amazonaws.com/?billingtoken=Za0o-RFyZHzy8wOy3Wx-tJxAJ3HIdJW_jCnYN7N8VM"
rpc_endpoint = "http://localhost:8545"
rpc_endpoint = "https://nd-rwvsmdaoybb23lxrmty44k27ee.t.ethereum.managedblockchain.us-east-1.amazonaws.com/?billingtoken=Za0o-RFyZHzy8wOy3Wx-tJxAJ3HIdJW_jCnYN7N8VM"

OLAS = Web3.to_checksum_address("0x0001a500a6b18995b03f44bb040a5ffc28e45cb0")
SOL = Web3.to_checksum_address("0xD31a59c85aE9D8edEFeC411D448f90841571b89c")
WMATIC = Web3.to_checksum_address("0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0")
DAI = Web3.to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F")
WETH = Web3.to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")

AMOUNT = 1



w3 = Web3(Web3.HTTPProvider(rpc_endpoint))


with open("olas_arbitrage/abis/erc20.json") as f:
    erc20_abi = json.load(f)




@dataclass
class Erc20Token:
    """
    ERC20 Token
    """
    address: str
    symbol: str = None
    decimals: int = None
    contract: Contract = None


    @classmethod
    def from_address(cls, address, w3):
        """
        Create an ERC20 token from an address.
        """
        contract = w3.eth.contract(address=address, abi=erc20_abi)
        symbol = contract.functions.symbol().call()
        decimals = contract.functions.decimals().call()
        return cls(address, symbol, decimals, contract)





async def get_path(token_a, token_b, amount_a):


    amt_machine = int(amount_a * (10 ** token_a.decimals))



    smart_path = await SmartPath.create(rpc_endpoint=rpc_endpoint)
    path = await smart_path.get_swap_in_path(amt_machine, token_a.address, token_b.address,)
    print(path)

    rate = parse_path_to_rate(path, amt_machine, token_a, token_b)
    if not rate:
        raise Exception("No path found")
    return path


def parse_path_to_rate(path_obj, amount, token_a, token_b):
    """
    Parse the path object to rates.
    """
    total_out = 0
    for split in path_obj:
        estimated_amount = split['estimate']
        total_out += estimated_amount

    decimal_adjusted_amount = amount / (10 ** token_a.decimals)
    print(f"Amount in {decimal_adjusted_amount}")
    decimal_adjusted_out = total_out / (10 ** token_b.decimals)
    print(f"Amount out {decimal_adjusted_out}")
    rate = decimal_adjusted_out / decimal_adjusted_amount
    print(f"Rate {rate}")
    return rate


def get_permit2_info(token):
    """
    Get the permit2 info.
    """
    with open("olas_arbitrage/abis/uniswap/permit2.json") as f:
        permit2_abi = json.load(f)
    permit2_contract = w3.eth.contract(address=PERMIT2_ADDRESS, abi=permit2_abi)
    p2_amount, p2_expiration, p2_nonce = permit2_contract.functions.allowance(
            account.address,
            token.address,
            ROUTER_ADDRESS,
    ).call()
    print(f"Permit2 amount {p2_amount}")
    print(f"Permit2 expiration {p2_expiration}")
    print(f"Permit2 nonce {p2_nonce}")
    return p2_amount, p2_expiration, p2_nonce


async def build_transaction(path_obj, amount, token_a, account):
    """
    Build the transaction.
    """

    encoded_input = (
        codec
        .encode
        .chain()
    )

    for split in path_obj:
        function_name = split['function']
        path = split['path']
        estimated_amount = split['estimate']
        weight = split['weight'] / 100

        if function_name == "V2_SWAP_EXACT_IN":
            encoded_input = (
                encoded_input.v2_swap_exact_in(
                    FunctionRecipient.SENDER,
                    amount_in=int(amount * weight * (10 ** token_a.decimals)),
                    amount_out_min=int(estimated_amount),
                    path=path,
                    )
            )
        elif function_name == "V3_SWAP_EXACT_IN":

            # we need to add the permit

            p2_amount, p2_expiration, p2_nonce = get_permit2_info(token_a)


            allowance_amount = 2**159 - 1  # max/infinite
            permit_data, signable_message = codec.create_permit2_signable_message(
                    token_a.address,
                    allowance_amount,
                    codec.get_default_expiration(60 * 24 * 3600 * 10),  # 30 days
                    p2_nonce,
                    ROUTER_ADDRESS,
                    codec.get_default_deadline(18000),  # 180 seconds
                    chain_id=1,
                )

            signed_message = account.sign_message(signable_message)
            encoded_input = encoded_input.permit2_permit(permit_data, signed_message)
            encoded_input = (
                encoded_input.v3_swap_exact_in(
                    FunctionRecipient.SENDER,
                    amount_in=int(amount * weight * (10 ** token_a.decimals)),
                    amount_out_min=int(estimated_amount),
                    path=path,
                    )
            )


    txn_data = encoded_input.build(
        codec.get_default_deadline(valid_duration=180000000),
    )
    return txn_data


def approve_permit_2(token, ADDRESS):
    """
    Approve the token.
    """
    permit2_allowance = 2**200 - 1  # max

    contract_function = token.contract.functions.approve(
            ADDRESS,
            int(permit2_allowance)
    )
    trx_params = contract_function.build_transaction(
            {
                "from": account.address,
                "gas": 500_000,
                "gasPrice": int(w3.eth.gas_price * 1.1),
                "chainId": 1,
                "value": 0,
                "nonce": w3.eth.get_transaction_count(account.address),
            }
        )
    raw_transaction = w3.eth.account.sign_transaction(trx_params, account.key).rawTransaction
    trx_hash = w3.eth.send_raw_transaction(raw_transaction)
    print(f"Permit2 UNI approve trx hash: {trx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(trx_hash)
    receipt = w3.eth.get_transaction_receipt(trx_hash)
    print(f"Was the transaction successful? {receipt['status'] == 1}")
    if receipt['status'] != 1:
        raise Exception("Transaction failed")



ROUTER_ADDRESS = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
PERMIT2_ADDRESS = Web3.to_checksum_address("0x000000000022D473030F116dDEE9F6B43aC78BA3")


if __name__ == "__main__":
    token_b = Erc20Token.from_address(OLAS, w3)
    token_a = Erc20Token.from_address(WETH, w3)
    amt = 10
    print(token_b)
    print(token_a)

    with open("ethereum_private_key.txt") as f:
        private_key = f.read()
    account = Account.from_key(private_key)

    print(f"From: {account.address}")

    path = asyncio.run(get_path(token_a, token_b, amt))
    txn_data = asyncio.run(build_transaction(path, amt, token_a, account))

    if False:

        allowance = token_a.contract.functions.allowance(account.address, ROUTER_ADDRESS).call()

        print(f"Allowance {allowance}")
        if allowance < ((10 ** token_a.decimals) * amt):
            print("Approving")
            approve_permit_2(token_a, ROUTER_ADDRESS)

        allowance = token_a.contract.functions.allowance(account.address, PERMIT2_ADDRESS).call()

        print(f"Allowance {allowance}")
        if allowance < ((10 ** token_a.decimals) * amt):
            print("Approving")
            approve_permit_2(token_a, amt, PERMIT2_ADDRESS)


    if False:


        txn = {
            "from": account.address,
            "to": ROUTER_ADDRESS,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 1_000_000,
            "gasPrice": int(w3.eth.gas_price * 1.1),
            "chainId": 1,
            "data": txn_data,
        }

        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        print(signed_txn)
        trx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

        print(f"Transaction hash: {trx_hash.hex()}")
        print(f"Transaction link: https://etherscan.io/tx/{trx_hash.hex()}")
        # we wait for the transaction to be mined
        w3.eth.wait_for_transaction_receipt(trx_hash)
        print("Transaction mined!")
        receipt = w3.eth.get_transaction_receipt(trx_hash)
        print(f"Was the transaction successful? {receipt['status'] == 1}")


